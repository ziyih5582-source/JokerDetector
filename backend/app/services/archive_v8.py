"""Conversation-grounded portraits and a small, useful continuity view.

This module consumes the shared importer's messages. It never runs OCR, changes
single-chat scores, calls a model on GET, or treats its own summaries as evidence.
Only selected, redacted interaction segments are retained in the encrypted store.
"""
import copy
import hashlib
import json
import re
from datetime import date, timedelta

from app.services import archive_v7, communication
from app.services.archive_personality import DESCRIPTION_LIMIT, STYLE, SYNTHESIZE, VERIFY
from app.services.profiles import AIResultError, SENSITIVE, normalize, now, redact
from app.services import archive_continuity
from app.services.archive_quality import copy_issue, distinct_traits

VERSION = "archive-v8.1"
MAX_BANK = 48
CONTEXT_CHARS = 58000
BAD_CLAIM = re.compile(r"MBTI|[IE][NS][FT][JP]|依恋型|型依恋|人格障碍|讨好型|渣男|渣女|一定喜欢|肯定喜欢|欲擒故纵|让[他她]吃醋|服从性|\d+\s*[%％]", re.I)
VISUAL = re.compile(r"^\s*(?:【图片|【表情|\[图片|\[表情|\[贴图|\[sticker|\[image)", re.I)
SYSTEM = re.compile(r"^\s*(?:I\s*tickled|You\s*tickled|You recalled|Call duration|通话时长|对方撤回了一条消息)", re.I)
EVENT_TITLE = re.compile(r"这段|本次|这次|初步理解|初步观察|机票|酒店|装备|奶茶|追星|线下|点赞|准备物料|提供帮助|(?:交流|聊天|社群|兴趣|活动|讨论)中|^在|^当|^面对")
REFUSAL = re.compile(r"不要|不用|不想|不愿|不方便|不接受|不去|不来|不约|拒绝|算了|取消|有压力|不打算")
UNASKED_ARRANGEMENT = re.compile(r"(?:^|[，,。；;])\s*(?:可以|不妨|建议|尝试|主动)?\s*(?:一起)?(?:参加|邀请|约见|约出来|见面|接机|接送|买礼物|送礼|去(?:现场|线下|同好会))")
EVENT_PROGRESS = re.compile(r"(?:本次|这次|下一场|下次).{0,16}(?:计划|准备|进展)|(?:制作|应援物|物料).{0,8}进展")
MONEY_DETAIL = re.compile(r"转账|红包|收款|代付|费用|\d+\s*元")
CLOSED = {"completed", "cancelled"}
TIMED = {"event", "open_loop", "commitment", "stage_context", "emotional_state", "interaction_signal"}


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def eligible_facts(profile):
    return [f for f in profile.get("facts", []) if f.get("validity", "current") in {"current", "ended"}
            and not f.get("conflict") and f.get("retention") != "pending"]


def signature(profile):
    # The signature also invalidates generated views when a user changes consent,
    # corrects a record, resolves a conflict, or deletes a supporting source.
    return _hash({"version": VERSION, "facts": profile.get("facts", []),
                  "sources": profile.get("archive_v8", {}).get("sources", []),
                  "suppressed": profile.get("memory_tombstones", []),
                  "deleted": profile.get("deleted_quotes", []),
                  "dismissed": profile.get("archive_v8", {}).get("dismissed", [])})


def prune(profile):
    """Run on every encrypted write; corrections/deletions remove derived text too."""
    archive_continuity.prune(profile)
    state = profile.get("archive_v8")
    if not state:
        return
    by_id = {f["id"]: f for f in profile.get("facts", [])}
    state["sources"] = [s for s in state.get("sources", [])
                        if all(i in by_id and by_id[i].get("use_in_ai", True)
                               and not by_id[i].get("manual_locked") for i in s.get("fact_ids", []))]
    if state.get("analysis") and state.get("signature") != signature(profile):
        state.pop("analysis", None)
        state.pop("signature", None)
        state["status"] = "needs_refresh"


def _usable_turn(m):
    return m.get("role") in {"self", "other"} and bool(str(m.get("content", "")).strip())


def _turn(m, chat_date, number=None):
    content = redact(str(m["content"]))
    kind = m.get("kind", "text")
    if SYSTEM.search(content) or kind == "system":
        content, kind = "[系统提示；不作为性格证据]", "system"
    if VISUAL.search(content) or kind in {"image", "sticker"}:
        # Preserve that an image was sent, never promote its generated emotional
        # description into the speaker's words. Named activities remain in facts.
        content, kind = "[发送了表情或图片；识别描述不作为性格证据]", "visual"
    turn = {"role": m["role"], "content": content, "number": number or m.get("id", 0) + 1,
            "chat_date": chat_date, "kind": kind}
    if m.get("time"):
        turn.update(time_label=str(m["time"])[:100], time_guessed=bool(m.get("time_guessed")))
    return turn


def _linked_facts(turns, facts):
    return [f["id"] for f in facts if any(e.get("role") == t["role"] and e.get("quote")
            and normalize(e["quote"]) in normalize(t["content"])
            for t in turns for e in f.get("evidence", []))]


def interaction_sources(messages, chat_date, facts):
    """Adjacent overlaps keep proposals, refusals and repairs readable together.

    The full new exchange is read during synthesis; only cited blocks survive.
    These are transport segments, not a count of independent psychological events.
    """
    turns = [_turn(m, chat_date) for m in messages if _usable_turn(m)]
    result, block, size = [], [], 0
    for t in turns:
        if block and size + len(t["content"]) > 2200 and len(block) > 4:
            result.append(block)
            # Four long paragraphs can nearly repeat the entire preceding
            # block. Bound overlap by characters as well as turn count. Every
            # original turn remains available in the preceding source.
            overlap, overlap_size = [], 0
            for previous in reversed(block[-4:]):
                length = len(previous["content"])
                if overlap_size + length > 600:
                    break
                overlap.insert(0, previous)
                overlap_size += length
            block = overlap
            size = sum(len(x["content"]) for x in block)
        block.append(t)
        size += len(t["content"])
    if block:
        result.append(block)
    sources = []
    for block in result:
        key = _hash([(t["role"], normalize(t["content"])) for t in block])
        sources.append({"id": "s_" + key[:18], "kind": "exchange", "chat_date": chat_date,
                        "turns": block, "fact_ids": _linked_facts(block, facts)})
    return sources


def excerpt_sources(profile):
    """Legacy migration: exact retained excerpts, explicitly NOT complete chats."""
    groups = {}
    for f in eligible_facts(profile):
        if not f.get("use_in_ai", True) or f.get("manual_locked"):
            continue
        for e in f.get("evidence", []):
            if e.get("historical") or e.get("context_only") or e.get("role") not in {"self", "other"}:
                continue
            quote = e.get("quote", "")
            if not quote or VISUAL.search(quote):
                continue
            batch = e.get("batch_id") or e.get("source_session") or "legacy"
            group = groups.setdefault(batch, {})
            number = e.get("message_number", 0)
            key = (number, e["role"], quote)
            entry = group.setdefault(key, {"role": e["role"], "content": redact(quote),
                                          "number": number, "chat_date": e.get("chat_date"), "kind": "text", "fact_ids": []})
            if f["id"] not in entry["fact_ids"]:
                entry["fact_ids"].append(f["id"])
    result = []
    for group in groups.values():
        ordered = sorted(group.values(), key=lambda t: t["number"])
        for start in range(0, len(ordered), 16):
            rows = ordered[start:start + 16]
            ids = list(dict.fromkeys(i for r in rows for i in r["fact_ids"]))
            turns = [{k: v for k, v in r.items() if k != "fact_ids"} for r in rows]
            result.append({"id": "x_" + _hash(turns)[:18], "kind": "excerpt", "chat_date": None,
                           "turns": turns, "fact_ids": ids})
    return result


def _facts_payload(profile):
    selected = [f for f in eligible_facts(profile) if f.get("use_in_ai", True)]
    selected.sort(key=lambda f: (f.get("observed_on") or "", f.get("last_seen") or ""), reverse=True)
    selected.sort(key=lambda f: (f.get("validity") == "ended", f.get("memory_type") not in {"relationship_position", "special_date", "boundary", "commitment"}))
    return [{"id": f["id"], "subject": f.get("subject", "other"), "type": f.get("memory_type", f.get("category")),
             "topic": f.get("topic", ""), "text": f["text"], "scope": f.get("context", ""),
             "chat_date": f.get("observed_on"), "event_date": f.get("event_date"),
             "state": f.get("item_state", "unknown"), "event_status": f.get("event_status", "unknown"),
             "retention": f.get("retention"), "validity": f.get("validity", "current"),
             "manual": bool(f.get("manual_locked")),
             "evidence": [{"role":e["role"], "quote":e["quote"], "chat_date":e.get("chat_date")}
                          for e in f.get("evidence", []) if not e.get("historical")][-3:] if not f.get("manual_locked") else []}
            for f in selected[:160]]


def _safe_text(value, limit, required=True):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise AIResultError("档案综合字段缺失或过长")
    value = redact(value.strip())
    if BAD_CLAIM.search(value) or SENSITIVE.search(value) or communication.DIAGNOSIS.search(value):
        raise AIResultError("档案综合包含不适合保存的推断")
    return value


def _references(row, key, allowed, maximum=8, required=False):
    ids = row.get(key, [])
    if not isinstance(ids, list) or len(ids) > maximum or (required and not ids):
        raise AIResultError("档案综合缺少可核查依据")
    if any(not isinstance(i, str) or i not in allowed for i in ids) or len(ids) != len(set(ids)):
        raise AIResultError("档案综合引用了不存在的依据")
    return ids


def _quote_refs(rows, bank, role, source_ids, required=True):
    if not isinstance(rows, list) or len(rows) > 6 or (required and not rows):
        raise AIResultError("画像缺少具体原文引用")
    result = []
    for e in rows:
        if not isinstance(e, dict) or e.get("source_id") not in source_ids or type(e.get("number")) is not int or not isinstance(e.get("quote"), str) or not 2 <= len(e["quote"]) <= 300:
            raise AIResultError("画像原文引用结构无效")
        source = bank[e["source_id"]]
        turn = next((t for t in source["turns"] if t["number"] == e["number"] and t["role"] == role and t["kind"] == "text" and e["quote"] in t["content"]), None)
        if turn is None:
            # IDs are bookkeeping, not psychological evidence. Correct an index
            # only when the UNCHANGED exact quote uniquely identifies a real turn
            # of this same person within the candidate's own cited sources.
            matches = [(bank[i], t) for i in source_ids for t in bank[i]["turns"] if t["role"] == role and t["kind"] == "text" and e["quote"] in t["content"]]
            unique = {(s["id"], t["number"]): (s, t) for s, t in matches}
            if len(unique) != 1:
                raise AIResultError("画像引用不是该人物的原始语言")
            source, turn = next(iter(unique.values()))
        result.append({"quote": e["quote"], "role": role, "message_number": turn["number"],
                       "chat_date": turn.get("chat_date"), "source_kind": source["kind"],
                       "time_label": turn.get("time_label"), "time_guessed": turn.get("time_guessed", False)})
    return result


def _check_action(c, known):
    if c["action_kind"] == "follow_up" and (not c["fact_ids"] or any(not live_matter(known[i]) for i in c["fact_ids"])):
        raise AIResultError("过时、已结束或未确认的事项不生成跟进任务")
    if c["action_kind"] == "topic" and (UNASKED_ARRANGEMENT.search(c["action"]) or UNASKED_ARRANGEMENT.search(c["title"])):
        raise AIResultError("兴趣接话不扩展为未经约定的线下安排")
    if c["action_kind"] == "topic" and EVENT_PROGRESS.search(c["action"]) and not any(live_matter(known[i]) for i in c["fact_ids"]):
        raise AIResultError("未核实的旧活动不生成当前进展追问")


def _personality_copy(row):
    title, text = _safe_text(row.get("title"), 12), _safe_text(row.get("text"), DESCRIPTION_LIMIT)
    if copy_issue(title, text) or EVENT_TITLE.search(title) or re.search(r"例如|比如|提到|原话|记录中|[“”「」]|^(?:本次|这次|曾经|曾)", text):
        raise AIResultError("画像需要简明性格概括，具体事情保留在依据或重要信息中")
    return title, text


def _canonical_sources(row, bank, known, role):
    """Repair fact/source namespace confusion only through exact original quotes."""
    row = copy.deepcopy(row)
    aliases = {}
    for field, evidence_field in (("source_ids", "evidence"), ("counter_source_ids", "counter_evidence")):
        for e in row.get(evidence_field, []):
            sid = e.get("source_id") if isinstance(e, dict) else None
            if sid not in known or sid in bank or known[sid].get("subject") not in {role, "relation"}:
                continue
            matches = [s["id"] for s in bank.values() if sid in s.get("fact_ids", []) and any(
                t["role"] == role and t["number"] == e.get("number") and isinstance(e.get("quote"), str)
                and e["quote"] in t["content"] for t in s["turns"])]
            if matches:
                aliases.setdefault(sid, []).append(matches[0])
                e["source_id"] = matches[0]
        if isinstance(row.get(field), list):
            row[field] = list(dict.fromkeys(actual for i in row[field] for actual in aliases.get(i,[i])))
    return row


def _topic_subject(subject, ids, known):
    """A relation label is not evidence of a shared interest or shared date."""
    owners = {known[i]["subject"] for i in ids if not known[i].get("manual") and not known[i].get("manual_locked")}
    if not owners:
        return "relation"
    if subject == "relation" and len(owners) == 1:
        subject = next(iter(owners))
    if subject == "relation" and {"self", "other"} <= owners and "relation" not in owners:
        raise AIResultError("双方各自的信息应分别保留，不能冒充已核对的共同事项")
    if subject != "relation" and owners != {subject}:
        raise AIResultError("不能把不同人物的信息合成一个主题")
    return subject


def _candidates(output, sources, facts, *, personality_style=False):
    bank, known = {s["id"]: s for s in sources}, {f["id"]: f for f in facts}
    portraits = output.get("portraits")
    if not isinstance(portraits, list) or len(portraits) > 2 or any(not isinstance(p, dict) or p.get("subject") not in {"self", "other"} for p in portraits) or len({p["subject"] for p in portraits}) != len(portraits):
        raise AIResultError("双方画像结构不完整")
    candidates, rejected = [], []
    for group in portraits:
        traits = group.get("traits")
        if not isinstance(traits, list) or len(traits) > 5:
            raise AIResultError("画像特点结构不正确")
        for row in traits:
            try:
                row = _canonical_sources(row, bank, known, group["subject"])
                source_ids = _references(row, "source_ids", bank, 8, True)
                role = group["subject"]
                if not any(t["role"] == role and t["kind"] == "text" for i in source_ids for t in bank[i]["turns"]):
                    raise AIResultError("画像缺少本人语言依据")
                counter_ids = _references(row, "counter_source_ids", bank)
                candidate = {"kind": "trait", "subject": role,
                                   **{k: _safe_text(row.get(k), n) for k, n in (("title", 24), ("text", 160), ("scope", 120), ("alternative", 120))},
                                   "source_ids": source_ids, "counter_source_ids": counter_ids,
                                   "evidence": _quote_refs(row.get("evidence"), bank, role, source_ids),
                                   "counter_evidence": _quote_refs(row.get("counter_evidence", []), bank, role, counter_ids, False)}
                if personality_style:
                    try:
                        candidate["title"], candidate["text"] = _personality_copy(candidate)
                    except AIResultError as exc:
                        # Evidence/identity checks have already passed. Allow the
                        # EXISTING independent audit to repair presentation;
                        # never repair a missing or invented quotation this way.
                        candidate["presentation_issue"] = str(exc)
                candidates.append(candidate)
            except (AIResultError, AttributeError) as exc:
                rejected.append(str(exc))
    # A modest topic-count overflow must not discard independently grounded
    # portraits. Validate the bounded overflow and audit it normally; choose
    # the visible topics afterwards. Raw facts remain in the shared store.
    for key, kind, maximum in (("topics", "topic", 24), ("suggestions", "suggestion", 3)):
        rows = output.get(key)
        if not isinstance(rows, list) or len(rows) > maximum:
            raise AIResultError("档案主题或建议结构不完整")
        for row in rows:
            try:
                c = {"kind": kind, "title": _safe_text(row.get("title"), 30),
                     "fact_ids": _references(row, "fact_ids", known, 12, kind == "topic")}
                if kind == "topic":
                    c.update(text=_safe_text(row.get("text"), 220), subject=row.get("subject"), priority=row.get("priority", "useful"))
                    if c["subject"] not in {"self", "other", "relation"} or c["priority"] not in {"core", "useful", "minor"}:
                        raise AIResultError("主题人物或优先级无效")
                    # User notes have a relation-wide scope in the shared schema.
                    # They can clarify a named interest without changing whose
                    # ORIGINAL speech supports it. Expose that provenance in UI.
                    c["subject"] = _topic_subject(c["subject"], c["fact_ids"], known)
                else:
                    c.update(why=_safe_text(row.get("why"), 140), action=_safe_text(row.get("action"), 180),
                             action_kind=row.get("kind"), source_ids=_references(row, "source_ids", bank))
                    if c["action_kind"] not in {"boundary", "follow_up", "topic", "mutual"} or not (c["fact_ids"] or c["source_ids"]):
                        raise AIResultError("建议缺少具体依据")
                    _check_action(c, known)
                candidates.append(c)
            except (AIResultError, AttributeError) as exc:
                rejected.append(str(exc))
    return [{"id": i, **c} for i, c in enumerate(candidates)], rejected


def live_matter(f):
    if f.get("validity") == "ended" or f.get("state", f.get("item_state")) in CLOSED or f.get("event_status") in CLOSED:
        return False
    # Only actual, still-current responsibilities qualify, not proposals/wishes.
    if f.get("state", f.get("item_state")) not in {"agreed", "pending"}:
        return False
    day = f.get("event_date")
    observed = f.get("chat_date", f.get("observed_on"))
    if day:
        return day >= communication.today()
    # Resolve only the already-mentioned weekday against its source date; this
    # filters stale suggestions without inventing or persisting an event date.
    text = " ".join(str(f.get(k) or "") for k in ("text", "scope", "context", "date_text"))
    weekday = re.search(r"(下|上|本|这)?(?:周|星期)([一二三四五六日天])", text)
    if weekday:
        if not observed:
            return False
        anchor = date.fromisoformat(observed)
        offset = {"下": 7, "上": -7}.get(weekday[1], 0)
        weekday_index = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}[weekday[2]]
        deadline = anchor - timedelta(days=anchor.weekday()) + timedelta(days=weekday_index + offset)
        return deadline >= date.fromisoformat(communication.today())
    return bool(observed and 0 <= (date.fromisoformat(communication.today()) - date.fromisoformat(observed)).days <= 7)


def _verify(output, candidates, *, personality_style=False):
    checks = output.get("checks")
    if not isinstance(checks, list) or len(checks) != len(candidates):
        raise AIResultError("档案核查没有覆盖全部候选")
    seen, result = set(), []
    for check in checks:
        i = check.get("id") if isinstance(check, dict) else None
        if type(i) is not int or i not in range(len(candidates)) or i in seen or check.get("verdict") not in {"supported", "narrow", "unsupported"} or not str(check.get("reason", "")).strip():
            raise AIResultError("档案核查编号或判断无效")
        seen.add(i)
        if check["verdict"] == "unsupported":
            continue
        c = copy.deepcopy(candidates[i])
        if personality_style and c["kind"] == "trait" and check.get("abstraction") not in {"personality", "interpersonal_style"}:
            continue
        if check["verdict"] == "narrow":
            if c["kind"] == "trait":
                if personality_style and not all(isinstance(check.get(k), str) and check[k].strip() for k in ("title", "text")):
                    continue
                c["title"] = _safe_text(check.get("title", "这段互动中的初步理解"), 24)
            for key, limit in (("text", 220 if c["kind"] == "topic" else 160), ("scope", 120), ("alternative", 120), ("action", 180), ("why", 140)):
                if key in check and key in c:
                    c[key] = _safe_text(check[key], limit)
        if personality_style and c["kind"] == "trait":
            if all(isinstance(check.get(k), str) and check[k].strip() for k in ("title", "text")):
                c["title"] = _safe_text(check["title"], 24)
                c["text"] = _safe_text(check["text"], 160)
            c["facet"] = check.get("facet", "other")
            try:
                c["title"], c["text"] = _personality_copy(c)
            except AIResultError:
                continue
        c.pop("presentation_issue", None)
        c["verification"] = redact(str(check["reason"])[:180])
        if c["kind"] != "trait" or not any(r["kind"] == "trait" and r["subject"] == c["subject"] and normalize(r["title"]) == normalize(c["title"]) for r in result):
            result.append(c)
    result = distinct_traits(result) if personality_style else result
    topics = [r for r in result if r["kind"] == "topic"]
    ranked = sorted(topics, key=lambda r: {"core": 0, "useful": 1, "minor": 2}[r["priority"]])
    visible_ids = {r["id"] for r in ranked[:8]}
    return [r for r in result if r["kind"] != "topic" or r["id"] in visible_ids]


def rebuild(store, profile, client, model, messages=None, chat_date=None):
    """Best-effort paid work after fact import, never a hidden read-side call."""
    if client is None:
        return profile, "没有可用的云端 AI；已保存的事实仍可查看。"
    if messages and not eligible_facts(profile) and not any(m.get("role") == "other" and len(normalize(m.get("content", ""))) >= 8 for m in messages):
        return profile, "这段只有简短回应，暂不增加画像推断；后续有具体互动时再完善。"
    from app.services.archive_extraction import request
    working = copy.deepcopy(profile)
    state = working.setdefault("archive_v8", {"sources": [], "dismissed": []})
    prune(working)
    fresh = interaction_sources(messages, chat_date, eligible_facts(working)) if messages else []
    private = {f["id"] for f in working.get("facts", []) if f.get("manual_locked") or not f.get("use_in_ai", True)}
    fresh = [s for s in fresh if not private.intersection(s["fact_ids"])]
    old = state.get("sources", []) or excerpt_sources(working)
    by_id = {s["id"]: s for s in old}
    for s in fresh:
        by_id[s["id"]] = s
    sources = list(by_id.values())
    # New material is never silently cut; historical material is bounded and its
    # limited coverage is explicitly returned. Include older examples as well as
    # recent ones to avoid a recency-only portrait.
    new_ids = {s["id"] for s in fresh}
    selected = [s for s in sources if s["id"] in new_ids]
    used = sum(len(t["content"]) for s in selected for t in s["turns"])
    older = [s for s in sources if s["id"] not in new_ids]
    ordered = older[:4] + older[-MAX_BANK:]
    for s in ordered:
        length = sum(len(t["content"]) for t in s["turns"])
        if s["id"] not in {x["id"] for x in selected} and used + length <= CONTEXT_CHARS:
            selected.append(s)
            used += length
    if used > CONTEXT_CHARS:
        return profile, "信息已保存；本段互动过长，画像请分段更新。"
    facts = _facts_payload(working)
    if not selected:
        return profile, "信息已保存；还没有可以核对的本人语言片段。"
    payload = {"stage": "archive_synthesis", "today": communication.today(), "sources": selected,
               "facts": facts, "interest_records": [f for f in facts if f["type"] in {"useful_preference", "personal_view"}],
               "user_context": [f for f in facts if f["manual"]],
               "coverage": {"history_partially_selected": len(selected) < len(sources),
               "source_kind": "exchange" if fresh else "retained_exchange" if any(s["kind"] == "exchange" for s in selected) else "excerpts"}}
    try:
        output = request(client, model, SYNTHESIZE, payload, max_tokens=6500)
        candidates, rejected = _candidates(output, selected, facts, personality_style=True)
        proposed_updates = archive_continuity.proposals(output.get("updates", []), facts)
        audit = request(client, model, VERIFY, {**payload, "stage": "archive_verify", "candidates": candidates,
                                               "proposed_updates":proposed_updates}, max_tokens=5000) if candidates or proposed_updates else {"checks":[]}
        verified = _verify(audit, candidates, personality_style=True)
        transitions = archive_continuity.apply(working, proposed_updates, audit.get("updates", []), selected)
        obsolete = {r["old_id"] for r in transitions} | {r["new_id"] for r in transitions if r["relation"] == "pending"}
        verified = [r for r in verified if r["kind"] == "trait" or not obsolete.intersection(r.get("fact_ids", []))]
        safe = []
        for c in verified:
            try:
                if c["kind"] == "suggestion":
                    _check_action(c, {f["id"]: f for f in facts})
                safe.append(c)
            except AIResultError:
                continue
        verified = safe
        chosen_ids = {i for c in verified for i in c.get("source_ids", []) + c.get("counter_source_ids", [])}
        # Retain a small set of contrasting exchanges as well as current support,
        # so a later synthesis can discover counterexamples to today's portrait.
        contrasts = [s for s in fresh if s["id"] not in chosen_ids and re.search(r"但是|不是|其实|不用|不要|不想|压力|误会|道歉|我觉得|我认为|答应", " ".join(t["content"] for t in s["turns"]))]
        if contrasts:
            for s in contrasts[:2] + contrasts[max(0, len(contrasts)//2-1):len(contrasts)//2+1] + contrasts[-2:]:
                chosen_ids.add(s["id"])
        chosen = [s for s in sources if s["id"] in chosen_ids]
        retained = [s for s in sources if s["id"] not in chosen_ids and s["id"] not in new_ids]
        kept = retained[-max(0, MAX_BANK - len(chosen)):] + chosen if len(chosen) < MAX_BANK else chosen
        state["sources"] = kept
        state["analysis"] = {"rows": verified, "mode": payload["coverage"]["source_kind"], "at": now(),
                             "portrait_style": STYLE, "transitions":transitions,
                             "includes_excerpts": any(s["kind"] == "excerpt" for s in selected),
                             "history_partial": bool(state.get("history_partial")) or payload["coverage"]["history_partially_selected"] or len(kept) < len(sources),
                             "rejected": len(rejected) + len(candidates) - len(verified)}
        state["history_partial"] = state["analysis"]["history_partial"]
        state.update(version=VERSION, status="ready")
        state["signature"] = signature(working)
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            latest = store._read(db, profile["id"])
            if latest["revision"] != profile["revision"]:
                return latest, "信息已保存；另一个操作修改了档案，已放弃过时的画像。"
            from app.services.dossier import save
            return save(store, db, working), ""
    except Exception:
        # A transient provider failure must not lose the newly consented exact
        # excerpts. Keep a bounded encrypted bank for an explicit later rebuild;
        # no generated claim or lifecycle change from the failed attempt survives.
        pending = copy.deepcopy(profile)
        pending_state = pending.setdefault("archive_v8", {"dismissed": []})
        changed_sources = selected[:MAX_BANK]
        if changed_sources != pending_state.get("sources", []):
            pending_state.update(sources=changed_sources, version=VERSION, status="needs_refresh",
                                 history_partial=bool(pending_state.get("history_partial")) or len(selected) > MAX_BANK)
            pending_state.pop("analysis", None)
            pending_state.pop("signature", None)
            try:
                with store.connection() as db:
                    db.execute("BEGIN IMMEDIATE")
                    latest = store._read(db, profile["id"])
                    if latest["revision"] == profile["revision"]:
                        from app.services.dossier import save
                        profile = save(store, db, pending)
                    else:
                        profile = latest
            except Exception:
                pass  # Already committed facts remain intact even if persistence fails.
        return profile, "信息已保存；互动画像综合暂未完成，可在加入聊天中选择‘只整理已有资料’补做。"


def refresh_personality(store, profile, client, model):
    """Refresh only portraits from retained evidence; leave memory/topics intact."""
    from app.services.archive_extraction import request
    from app.services.archive_personality import PORTRAITS_ONLY
    from app.services.dossier import save
    working = copy.deepcopy(profile)
    state = working.get("archive_v8", {})
    if not client or not state.get("analysis") or state.get("signature") != signature(working):
        return profile, "请先整理已有资料，再更新性格画像。"
    sources = copy.deepcopy(state.get("sources", []))
    for source in sources:
        for t in source["turns"]:
            if SYSTEM.search(t["content"]) or t.get("kind") == "system":
                t.update(content="[系统提示；不作为性格证据]", kind="system")
    if not sources or sum(len(t["content"]) for s in sources for t in s["turns"]) > CONTEXT_CHARS:
        return profile, "保留的互动不足或过长，请通过加入聊天重新整理。"
    payload = {"stage": "personality_synthesis", "sources": sources,
               "coverage": {"history_partial": state.get("history_partial", False)}}
    try:
        output = request(client, model, PORTRAITS_ONLY, payload, max_tokens=4800)
        output.update(topics=[], suggestions=[])
        candidates, rejected = _candidates(output, sources, [], personality_style=True)
        verified = _verify(request(client, model, VERIFY, {**payload, "stage": "archive_verify", "candidates": candidates}, max_tokens=3600), candidates, personality_style=True) if candidates else []
        analysis = state["analysis"]
        preserved = [r for r in analysis["rows"] if r["kind"] != "trait"]
        first_id = max((r["id"] for r in preserved), default=-1) + 1
        for offset, row in enumerate(verified):
            row["id"] = first_id + offset
        analysis["rows"] = preserved + verified
        analysis.update(portrait_style=STYLE, at=now(), portrait_rejected=len(rejected) + len(candidates) - len(verified))
        state["signature"] = signature(working)
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            latest = store._read(db, profile["id"])
            if latest["revision"] != profile["revision"]:
                return latest, "档案已被其他操作更新，未覆盖新的内容。"
            return save(store, db, working), ""
    except Exception:
        return profile, "性格综合暂未完成，原画像和重要信息保持不变。"


def _evidence(ids, bank, subject=None):
    result, seen = [], set()
    for i in ids:
        s = bank.get(i)
        if not s:
            continue
        turns = [t for t in s["turns"] if t.get("kind") == "text" and (subject is None or t["role"] == subject)]
        for t in turns[:6]:
            key = (t["role"], normalize(t["content"]))
            if key in seen:
                continue
            seen.add(key)
            result.append({"quote": t["content"], "role": t["role"], "message_number": t["number"],
                           "chat_date": t.get("chat_date"), "source_kind": s["kind"]})
    return result[:18]


def _fallback_topics(public):
    """No invented inference on offline/failed imports; preserve every raw fact."""
    priority = {"useful_preference": 1, "personal_view": 1, "boundary": 0, "relationship_position": 0,
                "communication_request": 0, "special_date": 1, "commitment": 2, "user_note": 2}
    rows = []
    for f in eligible_facts(public):
        kind = f.get("memory_type")
        if kind in {"situated_trait", "interaction_signal", "emotional_state"} and not f.get("continuity_from"):
            continue
        row = {"id": f["id"], "title": f.get("topic", "记录"), "text": f["text"], "subject": f.get("subject", "other"),
               "fact_ids": [f["id"]], "priority": "useful", "evidence": f.get("evidence", []),
               "historical": archive_v7.item(f).get("historical", False), "state_label": archive_v7.item(f).get("state_label", ""),
               "rank": priority.get(kind, 4), "versions":f.get("versions", []),
               "source": "我的补充" if f.get("manual_locked") else "已核对摘录"}
        if kind == "special_date":
            row["date_info"] = archive_v7.special_date(f)
        if kind in TIMED and not live_matter(f):
            row["priority"] = "minor"
        rows.append(row)
    rows.sort(key=lambda r: (r["priority"] == "minor", r["historical"], r["subject"] == "self", r["rank"]))
    return rows


def build(public, raw=None):
    raw = raw or public
    state = raw.get("archive_v8", {})
    valid = state.get("version") == VERSION and state.get("signature") == signature(raw) and bool(state.get("analysis"))
    legacy = archive_v7.build(public, raw)
    result = {**legacy, "version": VERSION, "suggestions": [], "topics": [],
              "analysis_mode": "not_generated", "history_partial": False,
              "notice": "依据已上传互动形成的可修正理解，不代表对方全部性格或真实内心。"}
    if not valid:
        result["topics"] = _fallback_topics(public)
        result["portrait_status"] = "needs_refresh" if state else legacy["portrait_status"]
        # A stale V8 inference must not be rescued by an obsolete generated cache.
        if state:
            result["portraits"] = {role: {"subject": role, "traits": [], "note": "新资料或修正后需要重新整理画像。"} for role in ("self", "other")}
    else:
        analysis = state["analysis"]
        bank = {s["id"]: s for s in state.get("sources", [])}
        facts = {f["id"]: f for f in eligible_facts(public)}
        dismissed = set(state.get("dismissed", []))
        portraits = {role: {"subject": role, "traits": [], "note": "从本人语言和双方互动推断；情境不同，表现也可能不同。"} for role in ("other", "self")}
        for row in analysis["rows"]:
            if row["kind"] == "trait":
                if analysis.get("portrait_style") == STYLE:
                    try:
                        _personality_copy(row)
                    except AIResultError:
                        continue
                key = _hash({k: row[k] for k in ("subject", "title", "source_ids")})[:24]
                if key in dismissed:
                    continue
                portraits[row["subject"]]["traits"].append({**{k: row[k] for k in ("title", "text", "scope", "alternative")},
                    "id": key, "basis_label": "基于互动的有限推断", "fact_ids": list(dict.fromkeys(i for s in row["source_ids"] for i in bank.get(s, {}).get("fact_ids", []))),
                    "evidence": row.get("evidence", []), "counter_evidence": row.get("counter_evidence", []),
                    "coverage_label": "历史摘录中的初步理解" if analysis["mode"] == "excerpts" else "限已提供的互动情境"})
            elif row["kind"] == "topic" and all(i in facts for i in row["fact_ids"]):
                try:
                    subject = _topic_subject(row["subject"], row["fact_ids"], facts)
                except AIResultError:
                    continue  # Also protect old caches; retain each underlying fact below.
                referenced = [facts[i] for i in row["fact_ids"]]
                historical = all(archive_v7.item(f).get("historical") for f in referenced)
                minor = all(f.get("memory_type") in TIMED and not live_matter(f) for f in referenced)
                minor = minor or all(f.get("memory_type") == "situated_trait" for f in referenced)
                minor = minor or (bool(MONEY_DETAIL.search(row["text"])) and not any(live_matter(f) for f in referenced))
                minor = minor or all(f.get("retention") == "temporary" and (not f.get("observed_on") or (date.fromisoformat(communication.today()) - date.fromisoformat(f["observed_on"])).days > 7) for f in referenced)
                topic = {"id": "t_" + str(row["id"]), **{k: row[k] for k in ("title", "text", "subject", "fact_ids")},
                         "subject": subject, "priority": "minor" if minor else row["priority"], "historical": historical,
                         "evidence": [e for f in referenced if not f.get("manual_locked") for e in f.get("evidence", [])][:12],
                         "contains_user_note": any(f.get("manual_locked") for f in referenced),
                         "versions":[v for f in referenced for v in f.get("versions", [])][-6:], "source": "合并后的已核对信息"}
                special = [f for f in referenced if f.get("memory_type") == "special_date"]
                if len(special) == 1:
                    topic["date_info"] = archive_v7.special_date(special[0])
                result["topics"].append(topic)
            elif row["kind"] == "suggestion":
                if any(i not in facts for i in row["fact_ids"]):
                    continue
                if row["action_kind"] == "follow_up" and any(not live_matter(facts[i]) for i in row["fact_ids"]):
                    continue
                result["suggestions"].append({**{k: row[k] for k in ("title", "why", "action", "fact_ids", "action_kind")},
                    "evidence": [e for i in row["fact_ids"] for e in facts[i].get("evidence", [])][:12] or _evidence(row["source_ids"], bank)})
        # Privately entered notes stay visible locally, without sending them to AI.
        covered = {i for t in result["topics"] for i in t["fact_ids"]}
        for r in _fallback_topics(public):
            if r["fact_ids"][0] in covered:
                continue
            f = facts[r["fact_ids"][0]]
            # A model's omission or a rejected merge must not erase an explicit
            # stance, birthday, active promise, or private user correction.
            essential = f.get("memory_type") in {"relationship_position", "special_date"} or live_matter(f) or f.get("continuity_from") or r["source"] == "我的补充"
            essential = essential or (f.get("memory_type") in {"useful_preference", "personal_view"}
                                      and f.get("retention") == "conditional" and not r["historical"])
            r["priority"] = "useful" if essential else "minor"
            result["topics"].append(r)
        result.update(portraits=portraits, portrait_style=analysis.get("portrait_style"), portrait_status="synthesized", analysis_mode=analysis["mode"], includes_excerpts=analysis.get("includes_excerpts", False), history_partial=analysis.get("history_partial", False))
    result["topics"].sort(key=lambda r: (r["priority"] == "minor", r.get("historical", False), r["subject"] == "self", {"core": 0, "useful": 1, "minor": 2}[r["priority"]]))
    result["coverage"]["topics"] = len(result["topics"])
    return result


def dismiss_trait(store, contact_id, revision, trait_id):
    from app.services.dossier import check_revision, save
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        p = store._read(db, contact_id)
        check_revision(p, revision)
        if trait_id not in {t.get("id") for v in build(p)["portraits"].values() for t in v["traits"]}:
            raise KeyError("这条画像已变化，请刷新后核对")
        state = p["archive_v8"]
        state.setdefault("dismissed", []).append(trait_id)
        state["signature"] = signature(p)
        return save(store, db, p)
