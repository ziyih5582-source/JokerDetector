"""Explicitly labelled offline replay of fictional live-model recordings."""
import copy
import json
from pathlib import Path

from app.services import communication as cm, dossier
from app.services.profiles import public_profile

DIRECTORY = Path(__file__).resolve().parents[2] / "tests/fixtures"


def cases():
    legacy=json.loads((DIRECTORY / "campus_cases.json").read_text(encoding="utf-8"))
    new=DIRECTORY / "archive_preview_recordings.json"
    return legacy + (json.loads(new.read_text(encoding="utf-8"))["cases"] if new.exists() else [])


def recordings():
    legacy=json.loads((DIRECTORY / "campus_model_recordings.json").read_text(encoding="utf-8"))["calls"]
    new=DIRECTORY / "archive_preview_recordings.json"
    return legacy + (json.loads(new.read_text(encoding="utf-8"))["calls"] if new.exists() else [])


def catalog():
    labels = {r["label"] for r in recordings()}
    return [{"id": c["id"], "name": c["name"], "count": len(c["steps"])} for c in cases()
            if all(c["id"] + ":" + str(i + 1) in labels for i in range(len(c["steps"])))]


def start(store, case_id):
    if case_id not in {c["id"] for c in catalog()}:
        raise ValueError("这个虚构案例还没有完整的模型录制结果")
    c = next(c for c in cases() if c["id"] == case_id)
    p = store.create(c["name"] + "（虚构）")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        p = store._read(db, p["id"])
        p.update(relationship_tags=c["tags"], preview_case=case_id, preview_next=0)
        p = dossier.save(store, db, p)
    return state(p)


def state(p):
    c = next(c for c in cases() if c["id"] == p["preview_case"])
    index = p["preview_next"]
    return {"profile": public_profile(p), "step": index, "count": len(c["steps"]),
            "next_text": c["steps"][index]["text"] if index < len(c["steps"]) else "案例已全部回放，可以查看每条认识的来源与变化。",
            "next_date": c["steps"][index]["day"] if index < len(c["steps"]) else None}


def replay(store, p, record):
    payload = record["fictional_payload"]
    raw = json.loads(record["fictional_response"])["items"]
    raw = copy.deepcopy(raw)
    # Recorded IDs belong to a separate disposable database. Match their stored
    # identity to this replay's IDs; no answer/gold data enters recognition.
    prior = {f["id"]: f for f in payload.get("existing", [])}
    for item in raw:
        old = prior.get(item.get("target_id"))
        if old:
            matches = [f for f in p["facts"] if all(f.get(k) == old.get(k) for k in ("memory_type", "subject", "topic"))]
            item["target_id"] = matches[0]["id"] if len(matches) == 1 else None
    if record.get("verified"):
        for item in raw:
            if item.get("retention") == "pending":
                item["retention"] = "episode"  # Same current policy as a supported verifier result.
    items, rejected = cm.validate_items(raw, payload["messages"], semantic_checked=bool(record.get("verified")))
    preview = cm.preview(store, p, payload["messages"], items, payload.get("chat_date"), payload.get("scene_hint", ""), "ai")
    if preview["token"]:
        p = cm.commit(store, p["id"], preview["token"])
    return p, {"items": items, "rejected": rejected, "changes": preview["changes"], "duplicate": preview["duplicate"]}


def advance(store, contact_id, revision):
    p = store.get(contact_id)
    dossier.check_revision(p, revision)
    if "preview_case" not in p:
        raise ValueError("只能回放专门创建的虚构档案")
    case_id, index = p["preview_case"], p["preview_next"]
    record = next((r for r in recordings() if r["label"] == case_id + ":" + str(index + 1)), None)
    if record is None:
        return state(p)
    p, report = replay(store, p, record)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        current = store._read(db, p["id"])
        dossier.check_revision(current, p["revision"])
        current["preview_next"] = index + 1
        p = dossier.save(store, db, current)
    return {**state(p), **report, "notice": "已保存模型结果的离线回放；虚构聊天，不调用API。"}
