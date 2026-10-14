# -*- coding: utf-8 -*-
"""融合入口 /api/analyze/unified 的回归测试：一条流程同时产出情感分析与档案更新。"""

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    monkeypatch.setattr(deps.analyzer, "client", None)
    deps.get_store.cache_clear()
    with TestClient(app) as client:
        yield client
    deps.get_store.cache_clear()


def body(**overrides):
    data = {
        "messages": [{"speaker": "我", "content": "周末有什么安排？"},
                     {"speaker": "小林", "content": "我喜欢徒步"},
                     {"speaker": "我", "content": "好呀"}],
        "self_speaker": "我",
        "other_speaker": "小林",
        "profile_engine": "legacy",  # Preserve explicit v1 API compatibility checks.
    }
    data.update(overrides)
    return data


def test_analysis_only_does_not_touch_the_profile_store(client):
    """不传 contact_id 时是纯分析：返回完整情感分析，且不创建任何档案。"""
    response = client.post("/api/analyze/unified", json=body())
    assert response.status_code == 200
    data = response.json()
    assert data["profile"] is None
    assert data["duplicate"] is False
    assert data["analysis"]["statistics"]["message_count"] == {"self": 2, "other": 1}
    assert data["analysis"]["verdict"]["score"] >= 0
    assert client.get("/api/profiles/contacts").json()["contacts"] == []


def test_one_submission_returns_both_analysis_and_profile_update(client):
    """融合重点：一次提交同时拿到情感分析与档案条目。"""
    created = client.post("/api/profiles/contacts", json={"name": "小林"}).json()
    response = client.post("/api/analyze/unified", json=body(contact_id=created["id"], save_consent=True))
    assert response.status_code == 200
    data = response.json()
    assert data["profile_updated"] is True
    assert [f["text"] for f in data["profile"]["facts"]] == ["喜欢徒步"]
    assert data["analysis"]["statistics"]["message_count"] == {"self": 2, "other": 1}
    # 档案里保存的是脱敏依据，不保存完整聊天
    assert "guidance" not in data["profile"]


def test_saving_to_a_profile_still_requires_consent(client):
    created = client.post("/api/profiles/contacts", json={"name": "小林"}).json()
    response = client.post("/api/analyze/unified", json=body(contact_id=created["id"]))
    assert response.status_code == 400
    assert "本机保存" in response.json()["detail"]
    assert client.get(f'/api/profiles/contacts/{created["id"]}').json()["facts"] == []


def test_repeat_fragment_does_not_write_twice(client):
    created = client.post("/api/profiles/contacts", json={"name": "小林"}).json()
    first = client.post("/api/analyze/unified", json=body(contact_id=created["id"], save_consent=True)).json()
    second = client.post("/api/analyze/unified", json=body(contact_id=created["id"], save_consent=True)).json()
    assert first["profile_updated"] is True
    assert second["duplicate"] is True
    assert second["profile_updated"] is False
    assert second["analysis"] is None
    assert len(second["profile"]["batches"]) == 1


def test_unknown_contact_is_rejected(client):
    response = client.post("/api/analyze/unified", json=body(contact_id="deadbeef", save_consent=True))
    assert response.status_code == 404


def test_cloud_flags_without_configuration_are_rejected(client):
    response = client.post("/api/analyze/unified", json=body(use_ai=True, include_guidance=True))
    assert response.status_code == 400
    assert "AI" in response.json()["detail"]


def test_single_speaker_input_is_rejected(client):
    response = client.post("/api/analyze/unified", json=body(
        messages=[{"speaker": "我", "content": "你好"}, {"speaker": "我", "content": "在吗"}]))
    assert response.status_code == 400


def test_demo_can_feed_the_same_unified_flow(client):
    """内置示例也能一次拿到分析 + 建档结果，不需要第二个页面。"""
    created = client.post("/api/profiles/contacts", json={"name": "演示联系人"}).json()
    response = client.post(f'/api/analyze/demo/0?contact_id={created["id"]}&save_consent=true')
    assert response.status_code == 200
    data = response.json()
    assert data["analysis"]["source"]
    assert data["profile_updated"] is True
    assert data["profile"]["batches"][0]["message_count"] > 0


def test_demo_without_extra_flags_uses_the_unified_shape(client):
    """示例接口现在也返回融合结构，前端只需读 analysis。"""
    response = client.post("/api/analyze/demo/0")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"analysis", "profile", "duplicate", "report_regenerated",
                         "profile_updated", "warning"}
    assert data["profile"] is None
    assert data["profile_updated"] is False
    assert data["analysis"]["verdict"]["is_joker"] is True
    assert data["analysis"]["guidance"] is None
    assert client.get("/api/profiles/contacts").json()["contacts"] == []


def test_demo_cloud_consent_still_generates_the_long_report(client, monkeypatch):
    """cloud_consent 在示例接口里同时表示「生成长文」，保持旧语义。"""
    calls = []

    def fake_guidance(self, records, self_id, is_joker, joker_type):
        calls.append(1)
        return "长文" * 600

    monkeypatch.setattr(deps.analyzer, "client", object())
    monkeypatch.setattr(deps.analyzer, "ai_model", "fake-model")
    monkeypatch.setattr(type(deps.analyzer), "ai_guidance", fake_guidance, raising=False)
    data = client.post("/api/analyze/demo/0?cloud_consent=true").json()
    assert calls, "应调用一次长文生成"
    assert len(data["analysis"]["guidance"]) > 1000
    assert data["analysis"]["guidance_error"] is None


def test_unified_page_is_served_at_both_entry_points(client):
    for path in ("/", "/profiles"):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "script-src 'self'" in response.headers["content-security-policy"]


def test_emotion_reaches_preview_but_does_not_change_score(client):
    """表情情绪作为独立字段进入脱敏片段，但不参与本地评分。"""
    with_emotion = body(messages=[
        {"speaker": "我", "content": "[表情]", "emotion": "开心"},
        {"speaker": "小林", "content": "我喜欢徒步"},
        {"speaker": "我", "content": "好呀"},
    ])
    without_emotion = body(messages=[
        {"speaker": "我", "content": "[表情]"},
        {"speaker": "小林", "content": "我喜欢徒步"},
        {"speaker": "我", "content": "好呀"},
    ])
    first = client.post("/api/analyze/unified", json=with_emotion)
    second = client.post("/api/analyze/unified", json=without_emotion)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["analysis"]["verdict"]["score"] == second.json()["analysis"]["verdict"]["score"]

    preview = client.post("/api/profiles/preview", json={
        "messages": [{"speaker": "我", "content": "[表情]", "emotion": "开心"},
                     {"speaker": "小林", "content": "在"}],
        "self_speaker": "我", "other_speaker": "小林",
    })
    assert preview.status_code == 200
    assert preview.json()["messages"][0]["emotion"] == "开心"


def test_preview_returns_ai_json_payload(client):
    """脱敏预览同时给出将发给云端 AI 的 JSON（所见即所发）。"""
    preview = client.post("/api/profiles/preview", json={
        "messages": [
            {"speaker": "我", "content": "[表情]", "emotion": "开心", "kind": "sticker"},
            {"speaker": "小林", "content": "在", "time": "20:13", "time_guessed": True},
        ],
        "self_speaker": "我", "other_speaker": "小林",
    })
    assert preview.status_code == 200
    import json as _json
    payload = _json.loads(preview.json()["ai_payload"])
    assert payload["messages"][0] == {
        "id": 0, "speaker": "自己", "text": "[表情]", "emotion": "开心", "kind": "sticker"}
    assert payload["messages"][1]["speaker"] == "对方"
    assert payload["messages"][1]["time"] == "20:13"
    assert payload["messages"][1]["time_guessed"] is True
    assert "kind" not in payload["messages"][1]


def test_build_ai_payload_maps_speakers_and_limits():
    from app.services.analyzer import build_ai_payload
    records = [
        {"id": 0, "speaker": "我", "text": "在吗"},
        {"id": 1, "speaker": "对方", "text": "在", "emotion": "开心"},
    ]
    payload = build_ai_payload(records, self_id="我")
    assert '"speaker": "自己"' in payload and '"speaker": "对方"' in payload
    limited = build_ai_payload(records, self_id="我", limit=1)
    assert '"text": "在"' in limited and '"text": "在吗"' not in limited


def test_guidance_prompt_carries_json_payload(monkeypatch):
    """长文 AI 收到的对话是 JSON（含情绪/时间/类型），不再是一行行文本。"""
    from types import SimpleNamespace
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="长文"), finish_reason="stop")])

    fake_client = SimpleNamespace(with_options=lambda **kwargs: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(deps.analyzer, "client", fake_client)
    monkeypatch.setattr(deps.analyzer, "ai_model", "fake-model")
    text = deps.analyzer.ai_guidance(
        [{"speaker": "自己", "text": "在吗", "emotion": "开心", "time": "20:13", "kind": "sticker"}],
        "自己", False, None)
    assert text == "长文"
    prompt = captured["messages"][-1]["content"]
    assert '"messages"' in prompt
    assert '"text": "在吗"' in prompt and '"emotion": "开心"' in prompt and '"kind": "sticker"' in prompt


def test_health_reports_ocr_availability(client):
    """前端据此在未安装 OCR 依赖时置灰「导入长截图」入口。"""
    data = client.get("/api/health").json()
    assert isinstance(data["ocr_available"], bool)
    assert isinstance(data["vision_available"], bool)


def test_vision_config_can_be_saved_from_the_page(client, tmp_path, monkeypatch):
    """网页里保存识图 API：写进 .env、保留其它行、立即生效、绝不回传密钥。"""
    from app.core import config
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=sk-main\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    for key in ("VISION_API_KEY", "VISION_BASE_URL", "VISION_MODEL", "DEEPSEEK_VISION_MODEL"):
        monkeypatch.delenv(key, raising=False)
    response = client.post("/api/config/vision", json={
        "model": "qwen-vl-max", "base_url": "https://example.com/v1", "api_key": "sk-test-123"})
    assert response.status_code == 200
    body = response.json()
    assert body["vision_model"] == "qwen-vl-max"
    assert body["vision_key_set"] is True
    text = env_file.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-main" in text          # 其它行保留
    assert "VISION_MODEL=qwen-vl-max" in text
    assert "VISION_API_KEY=sk-test-123" in text
    assert config.vision_model() == "qwen-vl-max"
    assert config.vision_base_url() == "https://example.com/v1"
    assert config.vision_api_key() == "sk-test-123"
    assert "sk-test-123" not in response.text          # 密钥不回传


def test_vision_config_rejects_bad_base_url(client):
    response = client.post("/api/config/vision", json={"base_url": "ftp://example.com"})
    assert response.status_code == 400


def test_vision_test_endpoint_uses_fixed_image(client, monkeypatch):
    from app.core import config
    from app.services import vision
    monkeypatch.setattr(config, "vision_model", lambda: "qwen-vl-max")
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "interpret_data_url",
                        lambda url, hint_kind="sticker", **kwargs: {"kind": "sticker",
                                                                    "character": "笑脸", "summary": "黄色笑脸"})
    data = client.post("/api/config/vision/test").json()
    assert data["success"] is True
    assert data["model"] == "qwen-vl-max"
    assert data["summary"] == "黄色笑脸"


def test_vision_test_endpoint_without_model(client, monkeypatch):
    from app.core import config
    monkeypatch.setattr(config, "vision_model", lambda: "")
    data = client.post("/api/config/vision/test").json()
    assert data["success"] is False
