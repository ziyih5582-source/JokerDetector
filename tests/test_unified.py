# -*- coding: utf-8 -*-
"""融合入口 /api/analyze/unified 的回归测试：一条流程同时产出情感分析与档案更新。"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))
import main
import profile_routes


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    monkeypatch.setattr(main.analyzer, "client", None)
    profile_routes.get_store.cache_clear()
    with TestClient(main.app) as client:
        yield client
    profile_routes.get_store.cache_clear()


def body(**overrides):
    data = {
        "messages": [{"speaker": "我", "content": "周末有什么安排？"},
                     {"speaker": "小林", "content": "我喜欢徒步"},
                     {"speaker": "我", "content": "好呀"}],
        "self_speaker": "我",
        "other_speaker": "小林",
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

    def fake_guidance(self, data, self_id, is_joker, joker_type):
        calls.append(1)
        return "长文" * 600

    monkeypatch.setattr(main.analyzer, "client", object())
    monkeypatch.setattr(main.analyzer, "ai_model", "fake-model")
    monkeypatch.setattr(type(main.analyzer), "ai_guidance", fake_guidance, raising=False)
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
