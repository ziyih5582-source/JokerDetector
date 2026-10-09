# ruff: noqa: E402
# Standalone script resolves the backend import path before importing app modules.
"""Bounded fictional archive checks. Same ledger across runs; no automatic retries."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

import httpx
from app.core import config
from app.services import communication as cm
from app.services.profiles import (
    ProfileStore,
    ai_error_detail,
    prepare_messages,
    public_profile,
)
from openai import OpenAI

FIXTURES = Path(__file__).resolve().parents[1] / "backend/tests/fixtures/campus_cases.json"


def prepared(step):
    rows = []
    for line in step["text"].splitlines():
        name, text = line.split("：", 1)
        rows.append({"speaker": "我" if name == "我" else "对方", "content": text})
    return prepare_messages(rows, "我", "对方")


def checks(step, items, profile):
    kinds = {i["memory_type"] for i in items}
    text = json.dumps(items, ensure_ascii=False)
    failures = ["缺少类别:" + k for k in step.get("required", []) if k not in kinds]
    # Need/support and a concrete communication request overlap semantically. A
    # category-only mismatch is not a wrong memory; still require the actual need.
    if "support_need" in step.get("required", []) and kinds & {"communication_request", "boundary"}:
        failures = [f for f in failures if f != "缺少类别:support_need"]
    failures += ["不应出现类别:" + k for k in step.get("forbidden_types", []) if k in kinds]
    failures += ["不应出现表述:" + w for w in step.get("forbidden", []) if w in text]
    if step.get("empty") and items:
        failures.append("寒暄/指令反例应留空")
    events = [f for f in profile["facts"] if f.get("memory_type") == "event"]
    if step.get("event_date") and not any(f.get("event_date") == step["event_date"] and not f.get("conflict") for f in events):
        failures.append("当前事件日期没有按明确变化更新")
    if len(events) < step.get("minimum_events", 0):
        failures.append("不同事件被合并或遗漏")
    return failures


class BudgetStop(RuntimeError):
    pass


class Ledger:
    def __init__(self, path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"calls": [], "results": [], "contacts": {}, "max_calls": 100, "max_tokens": 30000}
        self.label = ""

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def charged(self):
        return sum(c.get("usage", {}).get("total_tokens", c["reserved_tokens"]) for c in self.data["calls"])

    def request(self, create, kwargs):
        # UTF-8 bytes is a conservative upper bound for this provider's byte-based
        # tokenizer. Reserve completion limit and message framing as well. Missing
        # usage (including failures) keeps the full reservation charged.
        digest = hashlib.sha256(kwargs["messages"][0]["content"].encode()).hexdigest()
        known = [c["usage"]["prompt_tokens"] for c in self.data["calls"] if c.get("prompt_sha256") == digest and c.get("usage")]
        system_bound = min(known) if known else len(kwargs["messages"][0]["content"].encode("utf-8"))
        reservation = system_bound + sum(len(m["content"].encode("utf-8")) for m in kwargs["messages"][1:]) + 256 + kwargs.get("max_tokens", 2200)
        if len(self.data["calls"]) >= 100 or self.charged() + reservation > 30000:
            raise BudgetStop("预算保护停止；不会为凑满请求次数超过3万token")
        row = {"label": self.label, "status": "started", "reserved_tokens": reservation,
               "prompt_sha256": digest,
               "prompt_version": cm.PROMPT_VERSION, "fictional_payload": json.loads(kwargs["messages"][1]["content"])}
        self.data["calls"].append(row)
        self.save()
        started = time.monotonic()
        try:
            result = create(**kwargs)
            row["status"] = "completed"
            if result.usage and result.usage.total_tokens is not None:
                row["usage"] = {k: getattr(result.usage, k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
            row["fictional_response"] = result.choices[0].message.content if result.choices else ""
            return result
        except Exception as exc:
            row.update(status="failed", error=ai_error_detail(exc)["message"])
            raise
        finally:
            row["seconds"] = round(time.monotonic() - started, 2)
            self.save()


class Client:
    def __init__(self, real, ledger):
        self.real, self.ledger, self.base_url = real, ledger, real.base_url
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: ledger.request(real.chat.completions.create, kw)))

    def with_options(self, **kw):
        return Client(self.real.with_options(**kw), self.ledger)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-new", type=int, default=1)
    parser.add_argument("--cases", default="")
    args = parser.parse_args()
    if not args.live:
        print("仅准备虚构资料；未调用API。")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = args.output.with_suffix(".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        config.load_env_file(args.config)
        if config.is_placeholder_key(config.api_key()):
            raise ValueError("API尚未配置")
        ledger = Ledger(args.output)
        ledger.data["model"] = config.model_name()
        ledger.save()
        fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
        selected = set(args.cases.split(",")) if args.cases else set()
        done = {r["label"] for r in ledger.data["results"]}
        store = ProfileStore(args.output.parent / "campus-fictional-live-data")
        with OpenAI(api_key=config.api_key(), base_url=config.base_url(), max_retries=0,
                    http_client=httpx.Client(trust_env=False)) as real:
            client = Client(real, ledger)
            new = 0
            for case in fixtures:
                if selected and case["id"] not in selected:
                    continue
                if case["id"] not in ledger.data["contacts"]:
                    ledger.data["contacts"][case["id"]] = store.create(case["name"])["id"]
                    ledger.save()
                cid = ledger.data["contacts"][case["id"]]
                for index, step in enumerate(case["steps"]):
                    label = case["id"] + ":" + str(index + 1)
                    if label in done:
                        continue
                    if new >= args.max_new:
                        return
                    p, msgs = store.get(cid), prepared(step)
                    ledger.label = label
                    try:
                        items, rejected = cm.extract_ai(msgs, p, client, config.model_name(), step["day"], case["scene"])
                    except BudgetStop as exc:
                        print(str(exc), "已计费/保守预留token", ledger.charged(), flush=True)
                        return
                    except Exception as exc:  # noqa: BLE001 - stop safely, don't retry a billed request
                        ledger.data["results"].append({"label": label, "error": ai_error_detail(exc)["message"]})
                        ledger.save()
                        print(label, "识别失败，停止并保留预算记录", flush=True)
                        return
                    preview = cm.preview(store, p, msgs, items, step["day"], case["scene"], "ai")
                    if preview["token"]:
                        p = cm.commit(store, cid, preview["token"])
                    failures = checks(step, items, p)
                    ledger.data["results"].append({"label": label, "items": items, "rejected": rejected,
                        "checks_failed": failures, "changes": preview["changes"], "profile": public_profile(p)})
                    ledger.save()
                    new += 1
                    print(label, "items", len(items), "failed checks", failures, "calls", len(ledger.data["calls"]), "tokens", ledger.charged(), flush=True)
                    if failures:
                        print("语义核对未通过，停止继续请求，先复查。", flush=True)
                        return
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
