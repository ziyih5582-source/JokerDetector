import io
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.services.profiles import ProfileStore, extract_ai, extract_local, prepare_messages, ai_error_detail


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    monkeypatch.setattr(deps.analyzer, "client", None)
    deps.get_store.cache_clear()
    with TestClient(app) as client:
        yield client
    deps.get_store.cache_clear()


def contact(client, name="小林"):
    response = client.post("/api/profiles/contacts", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def payload(text="我喜欢咖啡", **overrides):
    data = {"messages": [{"speaker": "我", "content": "周末聊聊"}, {"speaker": "小林", "content": text}],
            "self_speaker": "我", "other_speaker": "小林", "save_consent": True, "use_ai": False}
    data.update(overrides)
    return data


def analyze(client, cid, data=None):
    return client.post(f"/api/profiles/contacts/{cid}/analyze", json=data or payload())


def test_create_update_conflict_and_duplicate(client):
    cid = contact(client)
    first = analyze(client, cid).json()
    assert first["profile"]["facts"][0]["text"] == "喜欢咖啡"
    assert first["analysis"]["statistics"]["message_count"] == {"self": 1, "other": 1}
    repeat = analyze(client, cid).json()
    assert repeat["duplicate"] is True
    assert repeat["profile"]["revision"] == 1
    second = analyze(client, cid, payload("我现在不喜欢咖啡")).json()["profile"]
    assert len(second["facts"]) == 2
    assert all(f["conflict"] for f in second["facts"])
    assert len(second["batches"]) == 2


def test_no_consent_no_write(client):
    cid = contact(client)
    assert analyze(client, cid, payload(save_consent=False)).status_code == 400
    assert client.get(f"/api/profiles/contacts/{cid}").json()["revision"] == 0


def test_same_name_contacts_isolated(client):
    a, b = contact(client), contact(client)
    assert a != b
    analyze(client, a)
    assert client.get(f"/api/profiles/contacts/{b}").json()["facts"] == []

@pytest.mark.parametrize("changes", [
    {"self_speaker": "小林"}, {"other_speaker": "不存在"},
    {"messages": [{"speaker": "我", "content": "a"}, {"speaker": "小林", "content": "b"}, {"speaker": "第三人", "content": "c"}]},
])
def test_ambiguous_speakers_rejected(client, changes):
    assert analyze(client, contact(client), payload(**changes)).status_code == 400


def test_extract_only_other_not_self(client):
    cid = contact(client)
    data = payload("你好")
    data["messages"][0]["content"] = "我喜欢榴莲"
    assert analyze(client, cid, data).json()["profile"]["facts"] == []

@pytest.mark.parametrize("text", ["我喜欢咖啡吗？", "如果我喜欢咖啡", "他说我喜欢咖啡", "我以前喜欢咖啡", "我喜欢你", '“我喜欢咖啡”', "我喜欢咖啡，但是现在不喜欢了", "我的宗教信仰是佛教"])
def test_local_avoids_ambiguous_or_sensitive_statements(text):
    assert extract_local([{"id": 0, "role": "other", "content": text}]) == []


def test_corrections_survive_incremental_import_and_stale_edit(client):
    cid = contact(client)
    p = analyze(client, cid).json()["profile"]
    fid = p["facts"][0]["id"]
    url = f"/api/profiles/contacts/{cid}/facts/{fid}"
    response = client.patch(url, json={"revision": 1, "action": "correct", "text": "只在早上喝咖啡"})
    assert response.status_code == 200
    assert client.patch(url, json={"revision": 1, "action": "confirm"}).status_code == 409
    data = payload(); data["messages"].append({"speaker": "我", "content": "下次见"})
    p = analyze(client, cid, data).json()["profile"]
    assert p["facts"][0]["text"] == "只在早上喝咖啡"
    assert p["facts"][0]["status"] == "corrected"
    assert len(p["facts"][0]["evidence"]) == 1


def test_delete_fact_suppresses_reintroduction_and_clears_evidence(client):
    cid = contact(client)
    p = analyze(client, cid).json()["profile"]
    response = client.patch(f'/api/profiles/contacts/{cid}/facts/{p["facts"][0]["id"]}', json={"revision": 1, "action": "delete"})
    assert response.json()["facts"] == []
    data = payload(); data["messages"].append({"speaker": "我", "content": "再见"})
    p = analyze(client, cid, data).json()["profile"]
    assert p["facts"] == []
    assert "suppressed" not in p


def test_encryption_redaction_restart_delete(client, tmp_path):
    cid = contact(client, "隐私昵称")
    data = payload("我喜欢咖啡。我的邮箱是someone@example.com，电话13812345678")
    result = analyze(client, cid, data).json()
    encoded = json.dumps(result, ensure_ascii=False)
    assert "13812345678" not in encoded and "someone@example.com" not in encoded
    stored = (tmp_path / "profiles.sqlite3").read_bytes()
    assert "隐私昵称".encode() not in stored and "咖啡".encode() not in stored
    reopened = ProfileStore(tmp_path)
    assert reopened.get(cid)["facts"][0]["text"] == "喜欢咖啡"
    assert client.delete(f"/api/profiles/contacts/{cid}").status_code == 200
    assert client.get(f"/api/profiles/contacts/{cid}").status_code == 404
    assert reopened.list() == []


def test_deleted_contact_cannot_be_recreated_by_pending_merge(tmp_path):
    store = ProfileStore(tmp_path); cid = store.create("A")["id"]
    store.delete(cid)
    with pytest.raises(KeyError):
        store.merge(cid, [], [], "local")


def test_missing_key_does_not_silently_replace_it(tmp_path):
    ProfileStore(tmp_path).create("A")
    (tmp_path / "profile.key").unlink()
    with pytest.raises(RuntimeError, match="密钥缺失"):
        ProfileStore(tmp_path)
    assert not (tmp_path / "profile.key").exists()


def test_local_evidence_is_minimal_and_not_truncated(client):
    data = payload("无关内容" * 100 + "。我喜欢咖啡。我的工资是123456")
    p = analyze(client, contact(client), data).json()["profile"]
    assert p["facts"][0]["evidence"][0]["quote"] == "我喜欢咖啡"


def test_concurrent_updates_are_atomic_and_duplicates_idempotent(tmp_path):
    store = ProfileStore(tmp_path); cid = store.create("A")["id"]
    def update(i):
        messages = [{"id": 0, "role": "other", "content": "我喜欢" + ["咖啡", "徒步"][i % 2]}]
        return store.merge(cid, messages, extract_local(messages), "local")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(update, range(8)))
    p = store.get(cid)
    assert p["revision"] == 2 and len(p["batches"]) == 2 and len(p["facts"]) == 2


class FakeAI:
    base_url = "https://example.invalid"
    def __init__(self, content):
        self.content = content; self.calls = []; self.chat = SimpleNamespace(completions=self)
    def with_options(self, **kwargs):
        return self
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def test_cloud_opt_in_redacted_prompt_and_duplicate_skips_cloud(client, monkeypatch):
    ai = FakeAI(json.dumps({"items": [{"kind": "communication", "topic": "表达偏好", "polarity": "neutral", "text": "本片段直接表达个人偏好", "evidence_ids": [1]}]}))
    monkeypatch.setattr(deps.analyzer, "client", ai)
    cid = contact(client, "绝不能进入云端的昵称")
    data = payload("我喜欢咖啡。电话13812345678", use_ai=True)
    result = analyze(client, cid, data)
    assert result.status_code == 200
    assert len(ai.calls) == 1
    prompt = ai.calls[0]["messages"][1]["content"]
    assert "13812345678" not in prompt and "绝不能进入云端的昵称" not in prompt
    assert "小林" not in prompt and "[电话]" in prompt
    facts = result.json()["profile"]["facts"]
    assert any(f["certainty"] == "tentative" for f in facts)
    assert analyze(client, cid, data).json()["duplicate"] is True
    assert len(ai.calls) == 1
    analyze(client, contact(client), payload("我喜欢徒步"))
    assert len(ai.calls) == 1


def test_invalid_ai_evidence_and_sensitive_output_filtered():
    items = [
        {"kind": "communication", "topic": "健康", "polarity": "neutral", "text": "患有抑郁症", "evidence_ids": [1]},
        {"kind": "preference", "topic": "咖啡", "polarity": "like", "text": "喜欢咖啡", "evidence_ids": [999]},
        {"kind": "preference", "topic": "咖啡", "polarity": "like", "text": "喜欢咖啡", "evidence_ids": [0]},
    ]
    prepared = prepare_messages(payload()["messages"], "我", "小林")
    assert extract_ai(prepared, FakeAI(json.dumps({"items": items})), "test") == []


def test_ai_invalid_json_falls_back_visibly(client, monkeypatch):
    monkeypatch.setattr(deps.analyzer, "client", FakeAI("not-json"))
    result = analyze(client, contact(client), payload(use_ai=True)).json()
    assert result["warning"]
    assert result["profile"]["batches"][0]["mode"] == "local_fallback"
    assert result["profile"]["facts"][0]["text"] == "喜欢咖啡"


def test_failed_ai_can_retry_same_fragment_without_duplicate_batch(client, monkeypatch):
    ai = FakeAI("invalid")
    monkeypatch.setattr(deps.analyzer, "client", ai)
    cid = contact(client)
    first = analyze(client, cid, payload(use_ai=True)).json()["profile"]
    fid = first["facts"][0]["id"]
    client.patch(f'/api/profiles/contacts/{cid}/facts/{fid}', json={"revision": 1, "action": "correct", "text": "人工修正应保留"})
    ai.content = json.dumps({"items": [{"kind": "communication", "topic": "表达偏好", "polarity": "neutral", "text": "直接表达偏好", "evidence_ids": [1]}]})
    retry = analyze(client, cid, payload(use_ai=True)).json()
    assert not retry["duplicate"] and retry["warning"] is None
    p = retry["profile"]
    assert len(p["batches"]) == 1 and p["batches"][0]["mode"] == "ai"
    assert p["batches"][0]["id"] == first["batches"][0]["id"]
    assert p["facts"][0]["text"] == "人工修正应保留"
    assert len(p["facts"][0]["evidence"]) == 1
    assert analyze(client, cid, payload(use_ai=True)).json()["duplicate"]
    assert len(ai.calls) == 2

@pytest.mark.parametrize("status,code", [(401, "authentication"), (402, "balance"), (404, "not_found"), (429, "rate_limit"), (503, "provider_error")])
def test_safe_ai_errors_never_echo_provider_secrets(status, code):
    exc = Exception("sk-private-secret: original chat content")
    exc.status_code = status
    detail = ai_error_detail(exc)
    assert detail["code"] == code
    assert "sk-private" not in json.dumps(detail)


def test_network_permission_chain_and_timeout():
    exc = Exception("Connection error")
    exc.__cause__ = PermissionError("sensitive request must not leak")
    assert ai_error_detail(exc)["code"] == "network_permission"
    assert ai_error_detail(TimeoutError())["code"] == "timeout"


def test_config_test_uses_fictional_data_and_distinguishes_verification(client, monkeypatch):
    assert client.post('/api/config/test').status_code == 400
    ai = FakeAI('{"items":[]}')
    monkeypatch.setattr(deps.analyzer, "client", ai)
    monkeypatch.setattr(deps.analyzer, "ai_verified", False)
    response = client.post('/api/config/test')
    assert response.json()["success"] and deps.analyzer.ai_verified
    prompt = json.loads(ai.calls[0]["messages"][1]["content"])
    assert prompt == [{"id": 0, "role": "self", "content": "你喜欢什么？"}, {"id": 1, "role": "other", "content": "我喜欢徒步"}]
    assert client.get('/api/profiles/contacts').json()["contacts"] == []
    ai.content = "invalid json"
    response = client.post('/api/config/test')
    assert not response.json()["success"] and not deps.analyzer.ai_verified
    assert response.json()["error"]["code"] == "invalid_output"


def test_deepseek_v4_requests_final_json_without_default_thinking():
    ai = FakeAI('{"items":[]}')
    ai.base_url = 'https://api.deepseek.com/v1/'
    extract_ai([{"id": 0, "role": "other", "content": "我喜欢徒步"}], ai, 'deepseek-v4-pro')
    assert ai.calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}
    ai.base_url = 'https://another-provider.invalid/v1/'
    extract_ai([{"id": 0, "role": "other", "content": "我喜欢徒步"}], ai, 'custom-model')
    assert "extra_body" not in ai.calls[1]


def test_ai_not_configured_is_actionable(client):
    response = analyze(client, contact(client), payload(use_ai=True))
    assert response.status_code == 400 and "尚未配置" in response.json()["detail"]


def excel(rows):
    output = io.BytesIO()
    pd.DataFrame(rows).to_excel(output, header=False, index=False, engine="openpyxl")
    return output.getvalue()


def test_excel_preview_header_role_selection_and_no_persistence(client):
    response = client.post('/api/profiles/parse', files={"file": ("chat.XLSX", excel([["发言者", "内容"], ["对方昵称", "我喜欢咖啡"], ["我的昵称", "你好"]]))})
    assert response.status_code == 200
    parsed = response.json()
    assert parsed["speakers"] == ["对方昵称", "我的昵称"]
    assert len(parsed["messages"]) == 2
    assert client.get('/api/profiles/contacts').json()["contacts"] == []

@pytest.mark.parametrize("name,content,code", [("x.txt", b"hi", 400), ("x.xlsx", b"invalid", 400), ("x.xls", b"0" * (5 * 1024 * 1024 + 1), 413)], ids=["unsupported-type", "invalid-excel", "oversized"])
def test_bad_or_oversized_upload(client, name, content, code):
    assert client.post('/api/profiles/parse', files={"file": (name, content)}).status_code == code


def test_group_excel_rejected(client):
    response = client.post('/api/profiles/parse', files={"file": ("group.xlsx", excel([["a", "hi"], ["b", "hi"], ["c", "hi"]]))})
    assert response.status_code == 400


def test_security_headers_cross_origin_and_legacy_local_only(client, monkeypatch):
    assert client.post('/api/profiles/contacts', json={"name": "x"}, headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert client.get('/api/profiles/contacts', headers={"Host": "evil.invalid"}).status_code == 400
    assert client.get('/api/profiles/contacts').headers["cache-control"] == "no-store"
    assert "script-src 'self'" in client.get('/profiles').headers["content-security-policy"]
    ai = FakeAI("should not run"); monkeypatch.setattr(deps.analyzer, "client", ai)
    demo = client.post('/api/analyze/demo/0')
    upload = client.post('/api/analyze/upload', files={"file": ("chat.xlsx", excel([["A", "你好"], ["B", "我喜欢咖啡"]]))})
    assert demo.status_code == upload.status_code == 200
    assert 'messages_for_display' not in demo.json()
    assert 'messages_for_display' not in upload.json()
    assert '我喜欢咖啡' not in upload.text
    assert not ai.calls


class ReportAI(FakeAI):
    def create(self, **kwargs):
        if kwargs.get('response_format'):
            self.content = '{"items":[]}'
        elif kwargs['max_tokens'] == 100:
            self.content = 'NOT_JOKER'
        else:
            self.content = '这是一篇测试用情感分析长文。\n\n' + '结合双方交流，表达需要并尊重彼此的节奏。' * 80
        return super().create(**kwargs)


def test_legacy_upload_restores_long_report_and_redacts_outbound(client, monkeypatch):
    ai = ReportAI('')
    monkeypatch.setattr(deps.analyzer, 'client', ai)
    content = excel([["小张", "我喜欢咖啡，电话13812345678"], ["小王", "周末聊聊"], ["小张", "可以呀"]])
    result = client.post('/api/analyze/upload?cloud_consent=true', files={'file':('chat.xlsx',content)}).json()
    assert len(result['guidance']) > 1000
    assert result['guidance_error'] is None
    assert len(ai.calls) == 2
    outgoing = json.dumps(ai.calls, ensure_ascii=False)
    assert '13812345678' not in outgoing and '小张' not in outgoing and '小王' not in outgoing
    assert client.get('/api/profiles/contacts').json()['contacts'] == []


def test_legacy_demo_report_opt_in_and_missing_config(client, monkeypatch):
    assert client.post('/api/analyze/demo/0?cloud_consent=true').status_code == 400
    ai = ReportAI('')
    monkeypatch.setattr(deps.analyzer, 'client', ai)
    # 示例接口已改用融合结构：长文在 analysis 里
    assert client.post('/api/analyze/demo/0').json()['analysis']['guidance'] is None
    assert not ai.calls
    assert len(client.post('/api/analyze/demo/0?cloud_consent=true').json()['analysis']['guidance']) > 1000


def test_failed_long_report_keeps_stats_and_shows_safe_reason(client, monkeypatch):
    class BrokenAI(ReportAI):
        def create(self, **kwargs):
            if kwargs['max_tokens'] == 5000:
                raise TimeoutError('must not echo private request')
            return super().create(**kwargs)
    monkeypatch.setattr(deps.analyzer, 'client', BrokenAI(''))
    result = client.post('/api/analyze/demo/0?cloud_consent=true').json()['analysis']
    assert result['guidance'] is None and '超时' in result['guidance_error']
    assert result['statistics']['message_count']['self'] > 0
    assert 'private' not in result['guidance_error']


def test_profile_report_and_regeneration_do_not_duplicate_or_store_report(client, monkeypatch):
    ai = ReportAI('')
    monkeypatch.setattr(deps.analyzer, 'client', ai)
    cid = contact(client)
    data = payload(use_ai=True, include_guidance=True)
    first = analyze(client, cid, data).json()
    assert len(first['analysis']['guidance']) > 1000
    assert 'guidance' not in first['profile'] and len(ai.calls) == 2
    second = analyze(client, cid, data).json()
    assert second['duplicate'] and second['report_regenerated']
    assert second['profile']['revision'] == first['profile']['revision']
    assert len(second['profile']['batches']) == 1 and len(ai.calls) == 3
