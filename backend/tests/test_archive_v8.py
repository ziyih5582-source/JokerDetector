"""Evidence access, cache invalidation, lifecycle and privacy regressions."""
import copy

import pytest

from app.services import archive_v8 as av, communication as cm
from app.services.communication_flow import import_memory
from app.services.profiles import ProfileStore, public_profile


@pytest.fixture
def store(tmp_path):
    return ProfileStore(tmp_path)


def messages():
    return [{"id": 0, "role": "self", "content": "我帮你订车票吧？"},
            {"id": 1, "role": "other", "content": "真的不用啦，我已经挑好车次了，按自己的计划来。"},
            {"id": 2, "role": "self", "content": "那你准备什么活动？"},
            {"id": 3, "role": "other", "content": "星桥线下，我提前两周画了应援卡，想聊新剧情里的角色选择。"}]


def fact(store, p):
    m = messages()
    raw = dict(memory_type="useful_preference", subject="other", topic="星桥线下与剧情",
               fact=m[3]["content"], scope="这次兴趣交流", retention="conditional",
               evidence=[{"message_id": 3, "quote": m[3]["content"]}])
    accepted, drops = cm.validate_items([raw], m, semantic_checked=True)
    assert not drops
    result = cm.preview(store, p, m, accepted, "2026-10-18")
    return cm.commit(store, p["id"], result["token"])


def fake_model(monkeypatch, p, transform=None, reject=False):
    calls = []
    def request(client, model, prompt, payload, **kwargs):
        calls.append(copy.deepcopy(payload))
        if payload["stage"] == "archive_verify":
            return {"checks": [{"id": c["id"], "verdict": "unsupported" if reject else "supported", "abstraction": "interpersonal_style" if c["kind"] == "trait" else "not_applicable", "reason": "人物与原始互动相符，限定在此次安排和兴趣交流"} for c in payload["candidates"]]}
        sid = payload["sources"][0]["id"]
        output = {"portraits": [{"subject": "other", "traits": [{"title": "温和有主见", "text": "表达柔和，同时保留自己的判断和决定。相处时顾及对方的心意，也愿意说明自己的取舍。",
                   "scope": "这次车票安排", "source_ids": [sid], "evidence": [{"source_id": sid, "number": payload["sources"][0]["turns"][0]["number"], "quote": payload["sources"][0]["turns"][0]["content"]}], "counter_source_ids": [], "alternative": "也可能是车次早已选好，不代表所有事情都如此。"}]}, {"subject": "self", "traits": []}],
                   "topics": [], "suggestions": [{"title": "先接住已明确的安排", "why": "对方已经拒绝代订并说明有自己的计划", "action": "不再追加代订，若继续聊活动可以回应她提到的剧情。", "kind": "boundary", "fact_ids": [], "source_ids": [sid]}]}
        other = next(t for t in payload["sources"][0]["turns"] if t["role"] == "other")
        output["portraits"][0]["traits"][0]["evidence"] = [{"source_id": sid, "number": other["number"], "quote": other["content"]}]
        if p.get("facts"):
            output["topics"] = [{"title": "星桥线下与角色讨论", "text": "参与星桥线下，提前准备应援卡，也想聊剧情中的角色选择。", "subject": "other", "fact_ids": [p["facts"][0]["id"]], "priority": "core"}]
        return transform(output, payload) if transform else output
    monkeypatch.setattr("app.services.archive_extraction.request", request)
    return calls


def test_infers_from_exchange_without_any_personality_fact(store, monkeypatch):
    p = fact(store, store.create("TA"))
    calls = fake_model(monkeypatch, p)
    updated, notice = av.rebuild(store, p, object(), "test", messages())
    assert not notice and len(calls) == 2
    assert calls[0]["sources"][0]["turns"][1]["content"] == messages()[1]["content"]
    view = public_profile(updated)["archive"]
    assert view["portraits"]["other"]["traits"][0]["title"] == "温和有主见"
    assert not view["portraits"]["self"]["traits"]
    assert len(view["topics"]) == 1 and len(view["suggestions"]) == 1
    assert view["analysis_mode"] == "exchange"


def test_empty_fact_extraction_still_builds_portrait(store, monkeypatch):
    p = store.create("TA")
    monkeypatch.setattr(cm, "extract_ai", lambda *args: ([], []))
    calls = fake_model(monkeypatch, p)
    result = import_memory(store, p["id"], messages(), use_ai=True, client=object(), model="test")
    assert result["profile_updated"] and len(calls) == 2
    assert result["profile"]["archive"]["portraits"]["other"]["traits"]
    before = result["profile"]["revision"]
    again = import_memory(store, p["id"], messages(), use_ai=True, client=object(), model="test")
    assert again["duplicate"] and len(calls) == 2 and again["profile"]["revision"] == before


def test_get_does_not_call_model_or_expose_internal_bank(store, monkeypatch):
    p = fact(store, store.create("TA"))
    calls = fake_model(monkeypatch, p)
    p, _ = av.rebuild(store, p, object(), "test", messages())
    for _ in range(3):
        result = public_profile(store.get(p["id"]))
        assert "archive_v8" not in result and "signature" not in result["archive"]
        assert "sources" not in result["archive"]
    assert len(calls) == 2


def test_delete_support_removes_retained_exchange_and_generated_cache(store, monkeypatch):
    p = fact(store, store.create("TA"))
    fake_model(monkeypatch, p)
    p, _ = av.rebuild(store, p, object(), "test", messages())
    assert p["archive_v8"]["sources"]
    p = store.edit_fact(p["id"], p["facts"][0]["id"], p["revision"], "delete")
    assert not p["archive_v8"]["sources"]
    assert "analysis" not in p["archive_v8"]
    assert not public_profile(p)["archive"]["portraits"]["other"]["traits"]


def test_private_correction_never_returns_to_model_as_old_quote(store, monkeypatch):
    p = fact(store, store.create("TA"))
    fake_model(monkeypatch, p)
    p, _ = av.rebuild(store, p, object(), "test", messages())
    p = cm.save_note(store, p["id"], p["revision"], "这是朋友的安排，不是对方的爱好", p["facts"][0]["id"], False)
    assert not p["archive_v8"]["sources"] and not av._facts_payload(p)
    assert not av.excerpt_sources(p)
    assert any(t["source"] == "我的补充" for t in public_profile(p)["archive"]["topics"])


def test_legacy_rebuild_is_explicitly_partial_and_not_complete_transcript(store, monkeypatch):
    p = fact(store, store.create("TA"))
    calls = fake_model(monkeypatch, p)
    p, _ = av.rebuild(store, p, object(), "test")
    assert all(s["kind"] == "excerpt" for s in calls[0]["sources"])
    assert public_profile(p)["archive"]["analysis_mode"] == "excerpts"


def test_image_annotation_is_not_speaker_personality_evidence():
    source = av.interaction_sources([{"id": 0, "role": "other", "kind": "sticker", "content": "[表情：可爱的人，表示很外向]"}], None, [])[0]
    assert source["turns"][0]["kind"] == "visual"
    assert "外向" not in source["turns"][0]["content"]
    output = {"portraits": [{"subject": "other", "traits": [{"title": "外向", "text": "很外向", "scope": "聊天", "source_ids": [source["id"]], "alternative": "也可能是玩笑"}]}, {"subject": "self", "traits": []}], "topics": [], "suggestions": []}
    candidates, dropped = av._candidates(output, [source], [])
    assert not candidates and dropped


@pytest.mark.parametrize("state,day,validity,expected", [
    ("agreed", "2099-01-01", "current", True), ("proposed", "2099-01-01", "current", False),
    ("pending", None, "current", False), ("completed", "2099-01-01", "ended", False),
    ("agreed", "2020-01-01", "current", False), ("cancelled", None, "ended", False)])
def test_followup_cannot_revive_old_refused_or_completed_matter(state, day, validity, expected):
    assert av.live_matter({"state": state, "event_date": day, "validity": validity}) == expected


def test_independent_verifier_can_reject_fluent_inference(store, monkeypatch):
    p = fact(store, store.create("TA"))
    fake_model(monkeypatch, p, reject=True)
    p, notice = av.rebuild(store, p, object(), "test", messages())
    assert not notice
    assert not public_profile(p)["archive"]["portraits"]["other"]["traits"]


def test_unknown_source_and_wrong_person_cannot_be_accepted(store, monkeypatch):
    p = store.create("TA")
    def wrong(output, payload):
        output["portraits"][0]["traits"][0]["source_ids"] = ["invented-id"]
        return output
    fake_model(monkeypatch, p, wrong)
    p, _ = av.rebuild(store, p, object(), "test", messages())
    assert not public_profile(p)["archive"]["portraits"]["other"]["traits"]


def test_model_failure_keeps_existing_facts(store, monkeypatch):
    p = fact(store, store.create("TA"))
    def fail(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr("app.services.archive_extraction.request", fail)
    after, notice = av.rebuild(store, p, object(), "test", messages())
    assert notice and after["revision"] == p["revision"] + 1
    assert store.get(p["id"])["facts"] == p["facts"]
    assert after["archive_v8"]["status"] == "needs_refresh"
    assert not after["archive_v8"].get("analysis")
    assert after["archive_v8"]["sources"]


def test_failed_synthesis_retains_exact_context_for_explicit_rebuild_without_reimport(store, monkeypatch):
    p = store.create("TA")
    monkeypatch.setattr(cm, "extract_ai", lambda *args: ([], []))
    def fail(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr("app.services.archive_extraction.request", fail)
    result = import_memory(store, p["id"], messages(), use_ai=True, client=object(), model="test")
    after = store.get(p["id"])
    assert not after["facts"] and result["archive_notice"]
    again = import_memory(store, p["id"], messages(), use_ai=True, client=object(), model="test")
    assert again["duplicate"] and again["profile"]["revision"] == after["revision"]
    calls = fake_model(monkeypatch, after)
    rebuilt, notice = av.rebuild(store, after, object(), "test")
    assert not notice and len(calls) == 2
    assert public_profile(rebuilt)["archive"]["portraits"]["other"]["traits"]
    assert any(t["content"] == messages()[1]["content"] for s in calls[0]["sources"] for t in s["turns"])


def test_dismiss_is_local_and_does_not_trigger_paid_call(store, monkeypatch):
    p = fact(store, store.create("TA"))
    calls = fake_model(monkeypatch, p)
    p, _ = av.rebuild(store, p, object(), "test", messages())
    trait = public_profile(p)["archive"]["portraits"]["other"]["traits"][0]
    p = av.dismiss_trait(store, p["id"], p["revision"], trait["id"])
    assert not public_profile(p)["archive"]["portraits"]["other"]["traits"]
    assert len(calls) == 2


def test_concurrent_edit_discards_stale_model_result(store, monkeypatch):
    p = fact(store, store.create("TA"))
    def edit_while_running(output, payload):
        latest = store.get(p["id"])
        cm.save_note(store, p["id"], latest["revision"], "我补充一条不同的认识", None, False)
        return output
    fake_model(monkeypatch, p, edit_while_running)
    p, notice = av.rebuild(store, p, object(), "test", messages())
    assert "过时" in notice and "analysis" not in p.get("archive_v8", {})


def test_segments_preserve_overlap_without_fabricating_dates():
    turns = [{"id": i, "role": "other" if i % 2 else "self", "content": str(i) + "正常聊天" * 75} for i in range(25)]
    parts = av.interaction_sources(turns, None, [])
    assert len(parts) > 2 and all(s["chat_date"] is None for s in parts)
    assert {t["number"] for s in parts for t in s["turns"]} == set(range(1, 26))
    assert parts[0]["turns"][-1] in parts[1]["turns"]


def test_weekday_deadline_is_not_mistaken_for_a_live_task(monkeypatch):
    monkeypatch.setattr(cm, "today", lambda: "2026-10-18")
    item = {"state": "agreed", "chat_date": "2026-10-15", "text": "答应周五前发清单"}
    assert not av.live_matter(item)
    assert av.live_matter({**item, "text": "答应下周五前发清单"})
    assert not av.live_matter({**item, "chat_date": None})


def test_exact_quote_must_belong_to_target_not_neighbor():
    sources = av.interaction_sources(messages(), None, [])
    bank = {s["id"]: s for s in sources}
    with pytest.raises(Exception, match="该人物"):
        av._quote_refs([{"source_id": sources[0]["id"], "number": 1, "quote": messages()[0]["content"]}], bank, "other", list(bank))


def test_new_private_note_stays_local_and_can_be_saved(store):
    p = store.create("TA")
    p = cm.save_note(store, p["id"], p["revision"], "这件事需要先问清楚", None, False)
    assert p["facts"][0]["manual_locked"] and not p["facts"][0]["use_in_ai"]
    assert not av._facts_payload(p)


def test_wrong_number_can_only_be_resolved_by_unique_unchanged_same_person_quote():
    sources = av.interaction_sources(messages(), None, [])
    bank = {s["id"]: s for s in sources}
    fixed = av._quote_refs([{"source_id": sources[0]["id"], "number": 999, "quote": messages()[1]["content"]}], bank, "other", list(bank))
    assert fixed[0]["message_number"] == 2 and fixed[0]["quote"] == messages()[1]["content"]
    with pytest.raises(Exception, match="该人物"):
        av._quote_refs([{"source_id": sources[0]["id"], "number": 999, "quote": "我就是独立的人"}], bank, "other", list(bank))


def test_message_time_is_preserved_as_a_clue_not_guessed_as_today():
    source = av.interaction_sources([{**messages()[0], "time": "8/18/25 10:30 PM", "time_guessed": True}, messages()[1]], None, [])[0]
    assert source["turns"][0]["time_label"] == "8/18/25 10:30 PM"
    assert source["turns"][0]["chat_date"] is None


def test_sunday_deadline_is_not_mapped_to_monday(monkeypatch):
    monkeypatch.setattr(cm, "today", lambda: "2026-10-18")
    for word in ("周天", "周日", "星期天"):
        assert av.live_matter({"state": "agreed", "chat_date": "2026-10-15", "text": f"答应{word}前发清单"})


def test_user_name_correction_can_join_interest_without_changing_speaker(store, monkeypatch):
    p = fact(store, store.create("TA"))
    p = cm.save_note(store, p["id"], p["revision"], "我补充：对方谈论的作品叫星桥，不是星河。", None, True)
    def add_context(output, payload):
        output["topics"][0]["fact_ids"].append(p["facts"][-1]["id"])
        return output
    fake_model(monkeypatch, p, add_context)
    p, notice = av.rebuild(store, p, object(), "test", messages())
    topics = public_profile(p)["archive"]["topics"]
    assert not notice and topics[0]["subject"] == "other" and topics[0]["contains_user_note"]
    assert all("我补充" not in e["quote"] for e in topics[0]["evidence"])


def test_narrowed_trait_cannot_keep_a_broader_negative_title():
    candidates = [{"id": 0, "kind": "trait", "title": "易情绪化", "text": "情绪化", "scope": "所有场景", "alternative": "可能是玩笑"}]
    rows = av._verify({"checks": [{"id": 0, "verdict": "narrow", "reason": "只能描述一次玩笑表达", "text": "这次用玩笑表达希望得到回应", "scope": "这次玩笑"}]}, candidates)
    assert rows[0]["title"] != "易情绪化" and rows[0]["scope"] == "这次玩笑"


def test_old_interest_does_not_generate_unverified_next_event_status_question():
    c = {"action_kind": "topic", "title": "聊兴趣", "action": "可以问下次线下活动的准备进展", "fact_ids": []}
    with pytest.raises(Exception, match="旧活动"):
        av._check_action(c, {})


def test_portrait_refresh_preserves_every_fact_topic_and_suggestion(store, monkeypatch):
    p = fact(store, store.create("TA"))
    calls = fake_model(monkeypatch, p)
    p, _ = av.rebuild(store, p, object(), "test", messages())
    before = copy.deepcopy(p)
    p, notice = av.refresh_personality(store, p, object(), "test")
    assert not notice and p["facts"] == before["facts"] and p["batches"] == before["batches"]
    assert [r for r in p["archive_v8"]["analysis"]["rows"] if r["kind"] != "trait"] == [r for r in before["archive_v8"]["analysis"]["rows"] if r["kind"] != "trait"]
    assert public_profile(p)["archive"]["portrait_style"] == "personality-v3"
    assert calls[-2]["stage"] == "personality_synthesis"


def test_failed_portrait_refresh_preserves_previous_portrait_and_memories(store, monkeypatch):
    p = fact(store, store.create("TA"))
    fake_model(monkeypatch, p)
    p, _ = av.rebuild(store, p, object(), "test", messages())
    before = copy.deepcopy(p)
    def fail(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr("app.services.archive_extraction.request", fail)
    after, notice = av.refresh_personality(store, p, object(), "test")
    assert notice and after == before and store.get(p["id"]) == before


def test_system_notifications_are_not_personality_evidence():
    source = av.interaction_sources([{"id": 0, "role": "other", "content": "Itickled 小林's 喜欢星桥"}], None, [])[0]
    assert source["turns"][0]["kind"] == "system"
    with pytest.raises(Exception, match="该人物"):
        av._quote_refs([{"source_id": source["id"], "number": 1, "quote": "喜欢星桥"}], {source["id"]: source}, "other", [source["id"]])


@pytest.mark.parametrize("title,text", [("追星准备认真", "提前准备应援装备。"), ("兴趣社群中积极分享", "在兴趣社群中分享创作并计划继续参加活动。"), ("这段互动中的初步理解", "这次拒绝了酒店。"), ("表达直爽", "例如对方说“直接告诉我”。"), ("投入专注", "愿意反复打磨兴趣作品。提到应援卡修改三稿，显示对细节的重视。")])
def test_event_recaps_are_not_accepted_as_personality_descriptors(title, text):
    with pytest.raises(Exception, match="画像|档案综合"):
        av._personality_copy({"title": title, "text": text})


def test_personality_audit_cannot_replace_trait_with_a_generic_placeholder():
    candidate = {"id": 0, "kind": "trait", "title": "随性松弛", "text": "不急于回应每一个请求。", "scope": "目前聊天", "alternative": "可能当时较忙"}
    audit = {"checks": [{"id": 0, "verdict": "narrow", "reason": "没有足够依据推断更广性格", "text": "当时说晚点再看。"}]}
    assert not av._verify(audit, [candidate], personality_style=True)


def test_personality_interpretation_can_explain_the_trait_without_changing_its_label():
    text = "更习惯直接表达自己的想法和感受，不太依赖委婉暗示。认同与不认同都比较容易从话语中看出来，交流时较少让对方反复猜测。表达直接与语气友好可以同时存在，不必然等于说话生硬。"
    assert 60 < len(text) <= 140
    assert av._personality_copy({"title": "表达直爽", "text": text}) == ("表达直爽", text)
