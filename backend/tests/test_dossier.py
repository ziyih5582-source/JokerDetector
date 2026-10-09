"""Regression tests for progressive dossier updates, independent of live providers."""
import copy
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.routes.fisherman import context_for
from app.main import app
from app.services.dossier import migrate, validate_candidates
from app.services.profiles import ProfileStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    monkeypatch.setattr(deps.analyzer, "client", None)
    deps.get_store.cache_clear()
    with TestClient(app) as c:
        yield c
    deps.get_store.cache_clear()


def create(client):
    return client.post("/api/profiles/contacts", json={"name": "小林"}).json()


def draft(p, texts, day="2026-10-01", **overrides):
    data = dict(revision=p["revision"], messages=[dict(speaker="我", content="今天聊聊安排")]
        + [dict(speaker="小林", content=t) for t in texts], self_speaker="我", other_speaker="小林",
        chat_date=day, scene="", use_ai=False, cloud_consent=False)
    data.update(overrides)
    return data


def preview(client, p, data):
    r = client.post(f'/api/profiles/contacts/{p["id"]}/imports/preview', json=data)
    assert r.status_code == 200, r.text
    return r.json()


def commit(client, p, pr, ids=None):
    return client.post(f'/api/profiles/contacts/{p["id"]}/imports/commit', json=dict(
        token=pr["token"], selected_ids=ids if ids is not None else [c["id"] for c in pr["changes"]], save_consent=True))


def upload(client, p, texts, day):
    pr = preview(client, p, draft(p, texts, day))
    r = commit(client, p, pr)
    assert r.status_code == 200, r.text
    return r.json(), pr


def manual(p, **overrides):
    data = dict(revision=p["revision"], category="value", topic="任务与截止时间", text="先明确哪一部分和截止时间",
        context="任务分工", event_date=None, event_status="unknown")
    data.update(overrides)
    return data


def test_four_uploads_and_manual_protection(client):
    p = create(client)
    p, first = upload(client, p, ["我比较慢热，刚认识的时候不太爱说话。", "分工直接告诉我做什么、几点前要。",
        "别在群里拿我开玩笑。", "我10月12号有面试。"], "2026-10-01")
    assert len(p["facts"]) == 4
    p, second = upload(client, p, ["别只说快点交，告诉我哪一部分、截止几点。",
        "群里说任务没关系，我是不喜欢被拿来开玩笑。"], "2026-10-03")
    assert len(p["facts"]) == 4
    assert {c["action"] for c in second["changes"]} == {"evidence", "refine"}
    value = next(f for f in p["facts"] if f["category"] == "value")
    assert len(value["evidence"]) == 2
    p, _ = upload(client, p, ["最近忙的时候短语音可以，重要安排还是文字发我。", "面试改到10月15号了。"], "2026-10-05")
    event = next(f for f in p["facts"] if f["category"] == "event")
    assert event["event_date"] == "2026-10-15"
    assert event["versions"][0]["event_date"] == "2026-10-12"
    p, old = upload(client, p, ["面试定在10月12号。"], "2026-09-29")
    assert old["changes"][0]["action"] == "historical"
    assert next(f for f in p["facts"] if f["category"] == "event")["event_date"] == "2026-10-15"
    trait = next(f for f in p["facts"] if f["category"] == "trait")
    r = client.put(f'/api/profiles/contacts/{p["id"]}/facts/{trait["id"]}', json=manual(p,
        category="trait", topic=trait["topic"], context="刚认识时", text="熟悉之后很健谈，只是刚认识慢热"))
    p = r.json()
    p, pr = upload(client, p, ["我比较慢热，刚认识的时候不太爱说话，熟了就好多了。"], "2026-10-06")
    assert pr["changes"][0]["action"] == "evidence"
    assert next(f for f in p["facts"] if f["category"] == "trait")["text"] == "熟悉之后很健谈，只是刚认识慢热"


def test_tags_revision_and_same_name_isolation(client):
    p, other = create(client), create(client)
    r = client.patch(f'/api/profiles/contacts/{p["id"]}', json=dict(revision=0, name="小林", relationship_tags=["同学", "室友", "同学"], background="地址：某地"))
    assert r.status_code == 200
    assert r.json()["relationship_tags"] == ["同学", "室友"]
    assert r.json()["background"] == "[隐私信息]"
    assert client.get(f'/api/profiles/contacts/{other["id"]}').json()["relationship_tags"] == []
    assert client.patch(f'/api/profiles/contacts/{p["id"]}', json=dict(revision=0, name="小林", relationship_tags=[], background="")).status_code == 409


def test_preview_no_write_full_duplicate_no_cloud(client, monkeypatch):
    p = create(client)
    data = draft(p, ["我10月12号有面试。"])
    pr = preview(client, p, data)
    assert client.get(f'/api/profiles/contacts/{p["id"]}').json()["revision"] == 0
    p = commit(client, p, pr).json()
    data["revision"] = p["revision"]
    data.update(use_ai=True, cloud_consent=True)
    pr = preview(client, p, data)  # no configured provider; exact duplicate avoids the provider
    assert pr["duplicate"] and pr["token"] is None
    assert p["revision"] == 1


def test_partial_overlap_retains_only_new_evidence(client):
    p = create(client)
    old = ["分工直接告诉我做什么、几点前要。", "别在群里拿我开玩笑。"]
    p, _ = upload(client, p, old, "2026-10-01")
    pr = preview(client, p, draft(p, old + ["我10月12号有面试。"], "2026-10-01"))
    assert pr["overlap_count"] == 3
    assert len(pr["changes"]) == 1 and pr["changes"][0]["category"] == "event"
    p = commit(client, p, pr).json()
    assert len(p["facts"]) == 3
    assert all(len(f["evidence"]) == 1 for f in p["facts"])


def test_same_greeting_is_not_duplicate_event(client):
    p = create(client)
    p, _ = upload(client, p, ["我10月12号有面试。"], "2026-10-01")
    pr = preview(client, p, draft(p, ["我10月20号有考试。"], "2026-10-01"))
    assert len(pr["changes"]) == 1 and pr["changes"][0]["topic"] == "考试"


@pytest.mark.parametrize("day", [None, "2026-10-01"])
def test_unreliable_or_same_day_changes_require_confirmation(client, day):
    p = create(client)
    p, _ = upload(client, p, ["我10月12号有面试。"], "2026-10-01")
    p, pr = upload(client, p, ["面试改到10月15号了。"], day)
    assert pr["changes"][0]["action"] == "conflict"
    f = p["facts"][0]
    assert f["event_date"] == "2026-10-12" and f["conflict"]
    assert "15" in f["alternatives"][0]["text"]


def test_missing_year_and_relative_dates_never_use_upload_time():
    from app.services.dossier import event_date_from_quotes
    assert event_date_from_quotes(["我10月12号有面试"], None) == (None, "10月12号")
    assert event_date_from_quotes(["明天面试"], None) == (None, "明天")
    assert event_date_from_quotes(["明天面试"], "2026-10-01")[0] == "2026-10-02"
    assert event_date_from_quotes(["2027年1月2日面试"], None)[0] == "2027-01-02"


def test_stale_modified_tampered_and_cross_contact_preview(client):
    p = create(client)
    pr = preview(client, p, draft(p, ["我10月12号有面试。"])); other = create(client)
    assert commit(client, other, pr).status_code == 400
    broken = copy.deepcopy(pr); broken["token"] = "broken"
    assert commit(client, p, broken).status_code == 400
    assert commit(client, p, pr, ["not-in-preview"]).status_code == 400
    client.post(f'/api/profiles/contacts/{p["id"]}/facts', json=manual(p))
    assert commit(client, p, pr).status_code == 409


def test_expired_preview(client, monkeypatch):
    p = create(client); pr = preview(client, p, draft(p, ["我10月12号有面试。"])); store = deps.get_store()
    issued = store.cipher.extract_timestamp(pr["token"].encode())
    monkeypatch.setattr("cryptography.fernet.time.time", lambda: issued + 1801)
    assert commit(client, p, pr).status_code == 400


def test_save_requires_consent_and_deleted_contact_stays_deleted(client):
    p = create(client); pr = preview(client, p, draft(p, ["我10月12号有面试。"])); path = f'/api/profiles/contacts/{p["id"]}'
    assert client.post(path + '/imports/commit', json=dict(token=pr["token"], selected_ids=[pr["changes"][0]["id"]], save_consent=False)).status_code == 400
    client.delete(path)
    assert commit(client, p, pr).status_code == 404


def test_deleted_fact_suppresses_old_quotes_and_cleans_history(client):
    p = create(client); p, _ = upload(client, p, ["我10月12号有面试。"], "2026-10-01")
    p = client.patch(f'/api/profiles/contacts/{p["id"]}/facts/{p["facts"][0]["id"]}', json=dict(revision=p["revision"], action="delete")).json()
    assert p["facts"] == [] and p["batches"][0]["changes"] == []
    pr = preview(client, p, draft(p, ["我10月12号有面试。"], "2026-10-02"))
    assert pr["changes"] == []
    assert all(k not in p for k in ["suppressed", "suppressed_topics", "deleted_quotes"])
    assert "message_keys" not in p["batches"][0]


def test_partial_selection_allows_reimport_of_omitted_item(client):
    p = create(client); data = draft(p, ["我10月12号有面试。", "别在群里拿我开玩笑。"])
    pr = preview(client, p, data); p = commit(client, p, pr, [pr["changes"][0]["id"]]).json()
    data["revision"] = p["revision"]; again = preview(client, p, data)
    assert not again["duplicate"] and len(again["changes"]) == 1
    assert again["changes"][0]["category"] == "boundary"


def test_schema_migration_is_idempotent_and_preserves_unknown_dates(tmp_path):
    store = ProfileStore(tmp_path); p = store.create("旧档案")
    p = dict(schema_version=1, id=p["id"], name=p["name"], created_at=p["created_at"], updated_at=p["updated_at"], revision=7,
        facts=[dict(id="old", key="private", kind="preference", polarity="like", topic="咖啡", text="喜欢咖啡", origin="local", certainty="stated", status="corrected", evidence=[], conflict=False)], batches=[], suppressed=[])
    before = copy.deepcopy(p)
    with store.connection() as db:
        db.execute("UPDATE contacts SET payload=? WHERE id=?", (store.cipher.encrypt(json.dumps(p).encode()), p["id"]))
    migrated = store.get(p["id"])
    assert migrated["revision"] == 7 and migrated["facts"][0]["manual_locked"]
    assert migrated["facts"][0]["observed_on"] is None
    assert migrate(copy.deepcopy(migrated)) == migrated
    assert migrated["facts"][0]["text"] == before["facts"][0]["text"]


@pytest.mark.parametrize("text", ["我朋友很慢热", "如果我10月12号有面试", "我10月12号有面试？", "我今天心情不好"])
def test_ambiguous_chats_do_not_produce_local_profile(client, text):
    p = create(client); pr = preview(client, p, draft(p, [text]))
    assert pr["changes"] == []


def fake_provider(items, captured):
    def create(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(dict(items=items))), finish_reason="stop")])
    obj = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    obj.with_options = lambda **kwargs: obj
    return obj


def test_cloud_semantic_match_and_untrusted_evidence_validation(client, monkeypatch):
    p = create(client); p, _ = upload(client, p, ["分工直接告诉我做什么、几点前要。"], "2026-10-01")
    target = p["facts"][0]; captures = []
    items = [dict(category="value", topic="分工清晰度", text="希望任务要求清楚", context="任务分工", operation="evidence",
        target_id=target["id"], evidence=[dict(message_id=1, quote="请说清具体事项与交付时间")])]
    monkeypatch.setattr(deps.analyzer, "client", fake_provider(items, captures))
    pr = preview(client, p, draft(p, ["请说清具体事项与交付时间"], "2026-10-03", use_ai=True, cloud_consent=True))
    assert pr["changes"][0]["action"] == "evidence"
    p = commit(client, p, pr).json()
    assert len(p["facts"]) == 1 and len(p["facts"][0]["evidence"]) == 2
    messages = [dict(id=0, role="self", content="请说清具体事项与交付时间"), dict(id=1, role="other", content="实际不是这句话")]
    assert validate_candidates(items, messages, "2026-10-03", "", "ai") == []
    assert captures[0]["response_format"] == {"type": "json_object"}


def test_cloud_consent_and_failure_leave_dossier_unchanged(client, monkeypatch):
    p = create(client); data = draft(p, ["我10月12号有面试。"], use_ai=True)
    path = f'/api/profiles/contacts/{p["id"]}/imports/preview'
    assert client.post(path, json=data).status_code == 400
    def fail(**kwargs):
        raise ConnectionError("SECRET key provider body")
    obj = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail))); obj.with_options = lambda **kwargs: obj
    monkeypatch.setattr(deps.analyzer, "client", obj)
    data["cloud_consent"] = True
    response = client.post(path, json=data)
    assert response.status_code == 502 and "SECRET" not in response.text
    assert client.get(f'/api/profiles/contacts/{p["id"]}').json()["revision"] == 0


def test_new_information_is_not_sent_to_fisherman_yet(client):
    p = create(client); p = client.post(f'/api/profiles/contacts/{p["id"]}/facts', json=manual(p)).json()
    text, count, _ = context_for(p)
    assert count == 0 and "先明确哪一部分" not in text


def test_new_manual_editor_does_not_send_updated_legacy_fact_to_ai(client):
    p = create(client)
    result = client.post(f'/api/profiles/contacts/{p["id"]}/analyze', json=dict(
        messages=[dict(speaker="我", content="喜欢什么？"), dict(speaker="小林", content="我喜欢咖啡")],
        self_speaker="我", other_speaker="小林", save_consent=True, use_ai=False)).json()
    p = result["profile"]
    assert context_for(p)[1] == 1
    f = p["facts"][0]
    p = client.put(f'/api/profiles/contacts/{p["id"]}/facts/{f["id"]}', json=manual(p,
        category="preference", topic="咖啡", context="", text="仅保留本机的私人备注")).json()
    assert context_for(p)[1] == 0
