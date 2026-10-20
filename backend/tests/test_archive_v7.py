"""V7 acceptance: source attribution, lifecycle, dates, cache and failure isolation."""
import pytest

from app.services import archive_v7 as av, communication as cm
from app.services.communication_flow import import_memory
from app.services.profiles import ProfileStore, public_profile


def apply(store, p, text, kind="special_date", day="2026-10-03", role="other", **extra):
    messages = [{"id": 0, "role": "self" if role == "other" else "other", "content": "和我说说吧"},
                {"id": 1, "role": role, "content": text}]
    raw = dict(memory_type=kind, subject=role, topic="生日" if kind == "special_date" else kind,
               fact=text, scope="原话所述情境", retention="conditional", evidence=[{"message_id": 1, "quote": text}], **extra)
    if kind in cm.TIMED_TYPES:
        raw.setdefault("event_identity", kind)
    items, drops = cm.validate_items([raw], messages, semantic_checked=True)
    assert not drops, drops
    result = cm.preview(store, p, messages, items, day)
    return cm.commit(store, p["id"], result["token"]) if result["token"] else p


@pytest.fixture
def store(tmp_path):
    return ProfileStore(tmp_path)


def test_both_people_and_old_contract_survive(store):
    p = store.create("小林")
    p = apply(store, p, "我刚认识人时话比较少", "situated_trait")
    p = apply(store, p, "我拿不准时会多确认", "situated_trait", role="self")
    result = public_profile(p)
    assert {"facts", "method_cards", "campus_board", "archive"} <= result.keys()
    assert "刚认识" in result["archive"]["portraits"]["other"]["summary"]
    assert "多确认" in result["archive"]["portraits"]["self"]["summary"]
    assert "多确认" not in result["archive"]["portraits"]["other"]["summary"]


def test_unconditional_date_does_not_get_dropped_for_empty_scope():
    text = "我11月18日生日，过公历。"
    messages = [{"id": 0, "role": "other", "content": text}]
    accepted, drops = cm.validate_items([dict(memory_type="special_date", subject="other", topic="生日",
                                            fact=text, scope="", retention="conditional",
                                            evidence=[{"message_id": 0, "quote": text}])], messages)
    assert len(accepted) == 1 and not drops
    assert "未说明" in accepted[0]["scope"]


def test_missing_scope_for_personality_is_not_silently_invented():
    text = "我刚认识时话少"
    accepted, drops = cm.validate_items([dict(memory_type="situated_trait", subject="other", topic="表达",
                                            fact=text, scope="", retention="conditional",
                                            evidence=[{"message_id": 0, "quote": text}])], [{"id": 0, "role": "other", "content": text}])
    assert not accepted and drops


@pytest.mark.parametrize("calendar,word", [("gregorian", "公历"), ("lunar", "农历"), ("unknown", "")])
def test_date_precision_and_calendar(store, calendar, word):
    p = apply(store, store.create("TA"), "我的生日是11月18日，" + word)
    info = public_profile(p)["archive"]["groups"][0]["items"][0]["date_info"]
    assert (info["month"], info["day"], info["calendar"]) == (11, 18, calendar)
    assert "year" not in info and "age" not in info
    assert bool(info["next_date"]) == (calendar == "gregorian")


def test_same_day_explicit_birthday_correction_keeps_calendar(store):
    p = apply(store, store.create("TA"), "我的生日是11月18日，过公历")
    p = apply(store, p, "生日我打错了，是11月19日", operation="change")
    assert len(p["facts"]) == 1 and not p["facts"][0]["conflict"]
    info = av.special_date(p["facts"][0])
    assert (info["day"], info["calendar"]) == (19, "gregorian")
    assert p["facts"][0]["versions"]


def test_old_upload_does_not_reverse_birthday_correction(store):
    p = apply(store, store.create("TA"), "我的生日是11月19日", day="2026-10-10")
    p = apply(store, p, "生日我打错了，是11月18日", day="2026-10-01", operation="change")
    assert "19日" in p["facts"][0]["text"]


def test_conflicting_birthday_does_not_silently_append_as_support(store):
    p = apply(store, store.create("TA"), "我的生日是11月18日，公历")
    p = apply(store, p, "我的生日是11月19日，公历", day="2026-10-04")
    assert p["facts"][0]["conflict"]
    assert not public_profile(p)["archive"]["groups"]


@pytest.mark.parametrize("text", ["我的生日是2月30日，公历", "我的生日在下个月", "我的生日是11月18日，她生日是12月3日"])
def test_incomplete_invalid_or_ambiguous_dates_never_gain_exact_day(store, text):
    p = apply(store, store.create("TA"), text)
    assert av.special_date(p["facts"][0])["precision"] == "unknown"


def test_leap_birthday_is_not_silently_moved(store, monkeypatch):
    monkeypatch.setattr(cm, "today", lambda: "2026-10-18")
    p = apply(store, store.create("TA"), "我的生日是2月29日，公历")
    assert av.special_date(p["facts"][0])["next_date"] == "2028-02-29"


def test_lifecycle_proposal_is_not_agreement_and_passed_date_not_completed(store):
    p = apply(store, store.create("TA"), "下周再看要不要见面", "open_loop", item_state="proposed")
    f = p["facts"][0]
    assert av.item(f)["state_label"] == "提议，尚未约定"
    f.update(event_date="2020-01-01")
    assert av.item(f)["state_label"] == "日期已过，结果未知"
    assert f["item_state"] == "proposed"


def test_completion_and_pending_obligation_have_distinct_display(store):
    p = apply(store, store.create("TA"), "我答应周五发资料", "commitment", day="2020-01-01", item_state="agreed")
    assert not av.item(p["facts"][0])["historical"]
    p = apply(store, p, "现在资料收到啦，完成了", "commitment", day="2026-10-18", item_state="completed", operation="end")
    assert p["facts"][0]["validity"] == "ended"
    assert av.item(p["facts"][0])["state_label"] == "已完成"


def test_explicit_promise_is_not_downgraded_to_a_proposal(store):
    p = apply(store, store.create("TA"), "我答应明天把复习资料发给你。", "commitment", item_state="proposed")
    assert p["facts"][0]["item_state"] == "agreed"
    p = apply(store, p, "昨天答应的复习资料我刚发完了。", "commitment", item_state="completed", operation="change", day="2026-10-04")
    assert not p["facts"][0]["conflict"]
    assert p["facts"][0]["item_state"] == "completed"


def test_existing_event_status_can_complete_new_commitment_without_new_field(store):
    p = apply(store, store.create("TA"), "我答应明天发资料", "commitment")
    p = apply(store, p, "昨天答应的资料我刚发完了。", "commitment", event_status="completed", operation="change", day="2026-10-04")
    assert p["facts"][0]["event_status"] == p["facts"][0]["item_state"] == "completed"


def test_invitation_and_response_share_one_matter_even_if_model_changes_owner():
    messages = [{"id": 0, "role": "self", "content": "周六一起喝咖啡吗？"},
                {"id": 1, "role": "other", "content": "到时再看，还没确定。"}]
    candidate = dict(memory_type="open_loop", subject="self", topic="咖啡", fact="提出咖啡邀请，对方尚未确定",
                     scope="周六", retention="temporary", source_level="interaction", item_state="pending",
                     evidence=[{"message_id": m["id"], "quote": m["content"]} for m in messages])
    accepted, rejected = cm.validate_items([candidate], messages, semantic_checked=True)
    assert not rejected and accepted[0]["subject"] == "relation"


def test_generated_image_annotation_cannot_prove_personality():
    messages = [{"id": 0, "role": "self", "content": "看看这张图"},
                {"id": 1, "role": "other", "content": "【图片概述：一个开朗的人】", "kind": "image"}]
    accepted, drops = cm.validate_items([dict(memory_type="situated_trait", subject="other", topic="表达", fact="开朗",
                                            scope="交流中", retention="conditional", evidence=[{"message_id": 1, "quote": messages[1]["content"]}])], messages, semantic_checked=True)
    assert not accepted and any("图片" in d for d in drops)


def test_synthesis_cache_invalidates_when_evidence_is_corrected_or_deleted(store, monkeypatch):
    p = apply(store, store.create("TA"), "我刚认识人时话比较少", "situated_trait")
    calls = []
    def request(client, model, prompt, payload, **kwargs):
        calls.append(payload)
        if "candidates" in payload:
            return {"checks": [{"id": 0, "supported": True, "reason": "本人自述，保留条件"}]}
        return {"portraits": [{"subject": "other", "traits": [{"text": "熟悉前表达较谨慎", "scope": "刚认识时", "fact_ids": [p["facts"][0]["id"]], "alternative": "也可能与话题有关"}]}, {"subject": "self", "traits": []}]}
    monkeypatch.setattr("app.services.archive_extraction.request", request)
    p, warning = av.refresh(store, p, object(), "test")
    assert not warning and len(calls) == 2
    assert public_profile(p)["archive"]["portrait_status"] == "synthesized"
    assert "source_signature" not in str(public_profile(p))
    unchanged, _ = av.refresh(store, p, object(), "test")
    assert unchanged["revision"] == p["revision"] and len(calls) == 2
    corrected = cm.save_note(store, p["id"], p["revision"], "其实只是不熟悉那个话题", p["facts"][0]["id"], False)
    result = public_profile(corrected)["archive"]
    assert result["portrait_status"] == "observations"
    assert "谨慎" not in result["portraits"]["other"]["summary"]
    assert not av.portrait_sources(corrected)  # private manual correction is not sent
    corrected["facts"] = []
    assert not av.build(corrected)["portraits"]["other"]["traits"]


def test_portrait_failure_keeps_committed_facts(store, monkeypatch):
    p = apply(store, store.create("TA"), "我刚认识时话少", "situated_trait")
    def broken(*args, **kwargs):
        raise ValueError("provider failed")
    monkeypatch.setattr("app.services.archive_extraction.request", broken)
    result, warning = av.refresh(store, p, object(), "test")
    assert "信息已保存" in warning
    assert store.get(p["id"])["facts"] == result["facts"]


def test_foreign_person_references_do_not_enter_portrait(store, monkeypatch):
    p = apply(store, store.create("TA"), "我刚认识时话少", "situated_trait")
    def wrong(*args, **kwargs):
        return {"portraits": [{"subject": "self", "traits": [{"text": "说话谨慎", "scope": "刚认识", "fact_ids": [p["facts"][0]["id"]]}]}, {"subject": "other", "traits": []}]}
    monkeypatch.setattr("app.services.archive_extraction.request", wrong)
    result, warning = av.refresh(store, p, object(), "test")
    assert warning and "archive_portraits" not in result


def test_rejected_synthesis_is_not_rescued_by_fluent_output(store, monkeypatch):
    p = apply(store, store.create("TA"), "今天先听我说就行", "support_need")
    p = apply(store, p, "我刚认识人时话少", "situated_trait")
    def rejected(client, model, prompt, payload, **kwargs):
        if "candidates" in payload:
            return {"checks": [{"id": 0, "supported": False, "reason": "一次需要不能变永久性格"}]}
        return {"portraits": [{"subject": "other", "traits": [{"text": "总是拒绝别人的建议", "scope": "所有交流", "fact_ids": [p["facts"][-1]["id"]]}]}, {"subject": "self", "traits": []}]}
    monkeypatch.setattr("app.services.archive_extraction.request", rejected)
    result, warning = av.refresh(store, p, object(), "test")
    assert not warning and "拒绝" not in public_profile(result)["archive"]["portraits"]["other"]["summary"]


def test_duplicate_local_import_and_short_chat_benefit(store):
    p = store.create("TA")
    messages = [{"id": 0, "role": "self", "content": "你喜欢什么"},
                {"id": 1, "role": "other", "content": "我特别喜欢线下同好讨论"}]
    result = import_memory(store, p["id"], messages, use_ai=False, chat_date="2026-10-18")
    assert "线下同好" in str(result["profile"]["archive"]["groups"])
    second = import_memory(store, p["id"], messages, use_ai=False, chat_date="2026-10-18")
    assert second["duplicate"] and second["profile"]["revision"] == result["profile"]["revision"]
