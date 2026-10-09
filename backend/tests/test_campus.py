"""Campus memory acceptance: saved real responses plus adversarial state changes."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.routes.fisherman import context_for
from app.main import app
from app.services import campus_demo as demo, communication as cm
from app.services.profiles import ProfileStore, prepare_messages, public_profile


@pytest.fixture
def store(tmp_path):
    return ProfileStore(tmp_path)


def raw(text, kind="relationship_position", **kw):
    data = {"memory_type": kind, "subject": "other", "topic": "对这段关系的态度", "fact": text,
            "scope": "这段关系", "retention": "conditional", "scene": "romance",
            "evidence": [{"message_id": 1, "quote": text}]}
    data.update(kw)
    return data


def messages(text):
    return prepare_messages([{"speaker": "我", "content": "你怎么想？"}, {"speaker": "TA", "content": text}], "我", "TA")


def apply(store, p, text, data=None, day="2026-10-01"):
    msgs = messages(text)
    items, dropped = cm.validate_items([data or raw(text)], msgs)
    assert not dropped
    pr = cm.preview(store, p, msgs, items, day)
    return cm.commit(store, p["id"], pr["token"]) if pr["token"] else p


@pytest.mark.parametrize("case", demo.catalog(), ids=lambda c: c["id"])
def test_live_recording_replay_keeps_sources_and_unknowns(store, case):
    result = demo.start(store, case["id"])
    for _ in range(case["count"]):
        result = demo.advance(store, result["profile"]["id"], result["profile"]["revision"])
        for item in result.get("items", []):
            original = next(r for r in demo.recordings() if r["label"] == case["id"] + ":" + str(result["step"]))
            by_id = {m["id"]: m for m in original["fictional_payload"]["messages"]}
            assert all(e["quote"] in by_id[e["message_id"]]["content"] for e in item["evidence"])
    p = result["profile"]
    if case["id"] in {"N01", "N02", "N03", "N04"}:
        assert not p["facts"]
    if case["id"] == "N03":
        assert any("台词" in text for text in result["rejected"])
    if case["id"] == "R01":
        context, count, _ = context_for(store.get(p["id"]), "怎么继续了解她？")
        assert count >= 3 and "慢热" in context and "群" in context and "星露谷" in context
        assert "不预测当前真实感情" in context
    if case["id"] == "R02":
        stances = p["campus_board"]["stances"]
        assert len(stances) == 1 and "愿意" in stances[0]["text"]
        assert p["campus_board"]["timeline"] and "朋友" in p["campus_board"]["timeline"][0]["before"]
    if case["id"] == "R06":
        assert p["campus_board"]["unknowns"]  # single is not an attitude towards the user
    if case["id"] == "E01":
        page = p["campus_board"]
        assert "scenes" not in page and "default_scene" not in page
        assert any(s["items"] for s in page["sections"])
    if case["id"] == "L01":
        assert not any("暗示" in f["text"] for f in p["facts"] if f.get("memory_type") == "emotional_state")
    if case["id"] == "I01":
        assert any("剧透" in c["finding"] for c in p["method_cards"])
    if case["id"] == "W01":
        assert any(f.get("event_date") == "2026-10-15" and not f["conflict"] for f in p["facts"])
    if case["id"] == "W02":
        assert len({f["event_date"] for f in p["facts"] if f["memory_type"] == "event"}) == 2
    serialized = json.dumps(p["campus_board"])
    for internal in ('"source_session"', '"evidence_keys"', '"source_sessions"', '"fingerprint"'):
        assert internal not in serialized


@pytest.mark.parametrize("full,quote", [
    ("小说里的台词是‘我想和你在一起’，我只是在读台词。", "我想和你在一起"),
    ("室友说她喜欢你，我只是转述。", "喜欢你"),
    ("如果有人说喜欢你，你会怎样？", "喜欢你"),
    ("假设我想和你在一起呢？", "我想和你在一起"),
])
def test_quote_true_does_not_make_relationship_inference_true(full, quote):
    items, dropped = cm.validate_items([raw(quote)], messages(full))
    assert not items and dropped


def test_implicit_emotion_not_stored_as_disclosure():
    text = "今天我想解决报告问题了，能一起列提纲吗？"
    items, dropped = cm.validate_items([raw(text, "emotional_state", fact="对方暗示自己很烦")], messages(text))
    assert not items and dropped


@pytest.mark.parametrize("claim", ["对方对你有95%好感", "建议故意冷落对方", "让她吃醋以后再回应", "对方肯定喜欢你"])
def test_no_numeric_attraction_or_manipulative_memory(claim):
    text = "我想先慢慢了解你。"
    items, dropped = cm.validate_items([raw(text, method=claim)], messages(text))
    assert not items and dropped


def test_user_correction_is_not_shown_as_partner_stance(store):
    p = apply(store, store.create("TA"), "我想先和你做朋友。")
    p = cm.save_note(store, p["id"], p["revision"], "我觉得对方已经喜欢我了", p["facts"][0]["id"])
    public = public_profile(p)
    assert not public["campus_board"]["stances"]
    assert public["campus_board"]["unknowns"]
    visible = [r for s in public["campus_board"]["sections"] for r in s["items"]]
    assert any(r["text"] == "我觉得对方已经喜欢我了" and r["source"] == "我的补充 / 修正" for r in visible)
    assert "已经喜欢" not in context_for(p, "怎么继续了解她")[0]


def test_boundary_change_removes_old_exception_and_keeps_history(store):
    text = "别在群里拿我开玩笑。"
    p = apply(store, store.create("TA"), text, raw(text, "boundary", topic="个人玩笑", scope="群内玩笑", method="群里不拿对方开玩笑"))
    text = "私下可以拿我开玩笑。"
    p = apply(store, p, text, raw(text, "boundary", target_id=p["facts"][0]["id"], operation="branch", scope="私下", method="私下可以玩笑"), "2026-10-02")
    assert p["facts"][0]["branches"]
    text = "现在私下也不要拿我开玩笑。"
    p = apply(store, p, text, raw(text, "boundary", target_id=p["facts"][0]["id"], operation="change", scope="公开与私下", method="公开私下都避免个人玩笑"), "2026-10-03")
    assert not p["facts"][0]["branches"]
    assert p["facts"][0]["versions"][-1]["branches"]
    assert all("私下可以玩笑" != c["method"] for c in public_profile(p)["method_cards"])


def test_timeline_links_adjacent_revisions(store):
    p = apply(store, store.create("TA"), "我想先和你做朋友。")
    p = apply(store, p, "我现在想和你约会了解。", raw("我现在想和你约会了解。", target_id=p["facts"][0]["id"], operation="change"), "2026-10-03")
    p = apply(store, p, "我现在还是只想和你做朋友。", raw("我现在还是只想和你做朋友。", target_id=p["facts"][0]["id"], operation="change"), "2026-10-06")
    rows = public_profile(p)["campus_board"]["timeline"]
    assert len(rows) == 2 and "约会" in rows[0]["before"] and "约会" in rows[1]["after"]


def test_interaction_needs_both_sides():
    text = "周六不行，周日下午可以。"
    rows, drop = cm.validate_items([raw(text, "interaction_signal", subject="other")], messages(text))
    assert not rows and drop


def test_replay_endpoint_is_opt_in_and_revision_checked(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    monkeypatch.delenv("JOKER_CAMPUS_PREVIEW", raising=False)
    monkeypatch.setattr(deps.analyzer, "client", None)
    deps.get_store.cache_clear()
    try:
        with TestClient(app) as client:
            assert client.get("/api/campus-preview/cases").status_code == 404
            monkeypatch.setenv("JOKER_CAMPUS_PREVIEW", "1")
            initial = client.post("/api/campus-preview/start", json={"case_id": "R02"}).json()
            body = {"contact_id": initial["profile"]["id"], "revision": initial["profile"]["revision"]}
            first = client.post("/api/campus-preview/next", json=body)
            assert first.status_code == 200 and first.json()["step"] == 1
            assert client.post("/api/campus-preview/next", json=body).status_code == 409
    finally:
        deps.get_store.cache_clear()


def test_old_message_does_not_revert_new_relationship_position(store):
    p = apply(store, store.create("TA"), "我想先和你做朋友。", day="2026-09-25")
    p = apply(store, p, "我现在想和你约会了解。", raw("我现在想和你约会了解。", target_id=p["facts"][0]["id"], operation="change"), "2026-10-05")
    p = apply(store, p, "我只想和你做朋友。", raw("我只想和你做朋友。", target_id=p["facts"][0]["id"], operation="change"), "2026-09-20")
    assert "约会" in p["facts"][0]["text"] and not p["facts"][0]["conflict"]
    before = copy.deepcopy(p)
    p = apply(store, p, "我只想和你做朋友。", raw("我只想和你做朋友。", target_id=p["facts"][0]["id"], operation="change"), "2026-09-20")
    assert p == before
