# -*- coding: utf-8 -*-
"""小丑鉴定所 /api/analyze/joker/detect 的回归测试：本地六征判定，不调用云端 AI。"""

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.services.analyzer import JokerAnalyzer, JOKER_TYPES


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    monkeypatch.setattr(deps.analyzer, "client", None)
    deps.get_store.cache_clear()
    with TestClient(app) as client:
        yield client
    deps.get_store.cache_clear()


def detect(messages, self_speaker="我", other_speaker="对方"):
    return {
        "messages": [{"speaker": s, "content": c} for s, c in messages],
        "self_speaker": self_speaker,
        "other_speaker": other_speaker,
    }


# ------------------------------------------------------------ 类型定义

def test_two_new_types_are_registered():
    """六型体系：原有四型 + 守候型 + 单向型。"""
    assert set(JOKER_TYPES) >= {"殉道型", "镜像型", "弄臣型", "幻恋型", "守候型", "单向型"}
    for name in ("守候型", "单向型"):
        assert JOKER_TYPES[name]["desc"] and JOKER_TYPES[name]["suggestion"]
        assert JOKER_TYPES[name]["keywords"]


# ------------------------------------------------------------ 判定正例

def test_one_sided_chat_is_diagnosed(client):
    """单向推进 + 自贬话术：应判为小丑，并给出类型与六征明细。"""
    response = client.post("/api/analyze/joker/detect", json=detect([
        ("我", "在忙吗"),
        ("对方", "嗯"),
        ("我", "忙完了吗"),
        ("我", "在吗"),
        ("我", "我就是个小丑，我太菜了"),
        ("我", "我这种人真是丢人"),
        ("对方", "……"),
        ("我", "我不配，救命"),
        ("我", "我这种人真是废物"),
    ]))
    assert response.status_code == 200
    data = response.json()
    assert data["is_joker"] is True
    assert data["type"] in JOKER_TYPES
    assert data["score"] >= 45
    assert set(data["signs"]) == {"one_way", "self_moved", "fantasy", "boundary",
                                  "no_accept_reject", "self_mockery"}
    assert data["signs"]["one_way"]["hit"] is True
    assert data["signs"]["self_mockery"]["hit"] is True


def test_waiting_after_rejection_maps_to_waiter_type(client):
    """反复挽留 + 拒绝后仍纠缠，应归入守候型。"""
    response = client.post("/api/analyze/joker/detect", json=detect([
        ("阿泽", "周末有空吗"),
        ("小鹿", "我们不合适"),
        ("阿泽", "再给我一次机会好不好"),
        ("阿泽", "我再等等，万一你改变主意呢"),
        ("小鹿", "别等了"),
        ("阿泽", "我不会放弃，我等你"),
    ], self_speaker="阿泽", other_speaker="小鹿"))
    data = response.json()
    assert data["is_joker"] is True
    assert data["type"] == "守候型"
    assert data["signs"]["no_accept_reject"]["hit"] is True


def test_healthy_chat_is_not_a_joker(client):
    """势均力敌的对话不应被误伤。"""
    data = client.post("/api/analyze/joker/detect", json=detect([
        ("我", "周六下午可以，上午有个会"),
        ("对方", "行，那先喝咖啡再过去"),
        ("我", "我发现一家新咖啡馆"),
        ("对方", "好呀，几点"),
        ("我", "两点吧"),
        ("对方", "收到，周六见"),
        ("我", "到时候见"),
        ("对方", "好"),
    ])).json()
    assert data["is_joker"] is False
    assert data["type"] is None


def test_detection_needs_single_side_and_another_sign(client):
    """防误伤门槛：只有单向性一项命中也必须放行（不能仅凭消息多就判小丑）。"""
    # 双方轮流、字数也不悬殊，只是自己略多几条 —— 不存在第二项征状
    data = client.post("/api/analyze/joker/detect", json=detect([
        ("我", "今天天气不错"),
        ("对方", "是啊"),
        ("我", "要出去走走吗"),
        ("对方", "可以呀"),
    ])).json()
    assert data["is_joker"] is False


# ------------------------------------------------------------ 输入校验

def test_same_speaker_is_rejected(client):
    response = client.post("/api/analyze/joker/detect", json=detect(
        [("我", "你好"), ("我", "在吗")], self_speaker="我", other_speaker="我"))
    assert response.status_code == 400


def test_third_speaker_is_rejected(client):
    response = client.post("/api/analyze/joker/detect", json=detect([
        ("我", "你好"), ("对方", "嗯"), ("路人", "路过"),
    ]))
    assert response.status_code == 400


def test_too_few_messages_are_rejected_by_schema(client):
    response = client.post("/api/analyze/joker/detect", json=detect([("我", "你好")]))
    assert response.status_code == 422


# ------------------------------------------------------------ 引擎直测

def test_detector_reports_after_reject_ratio():
    analyzer = JokerAnalyzer()
    data = [("我", "在吗"), ("对方", "别再给我发消息了"),
            ("我", "我不会放弃"), ("我", "我等你")]
    result = analyzer.detect_joker_profile(data, "我", "对方")
    # 最后一条拒绝之后，我方仍有 2 条消息
    assert result["signs"]["no_accept_reject"]["detail"].startswith("拒绝后继续发送比例")


def test_detector_does_not_touch_network(monkeypatch):
    """纯本地判定：即便把 client 设为会抛异常的哨兵，也不应被调用。"""
    analyzer = JokerAnalyzer()

    class Boom:
        def __getattr__(self, name):
            raise AssertionError("本地判定不得触碰 AI 客户端")

    analyzer.client = Boom()
    result = analyzer.detect_joker_profile([("我", "在吗"), ("对方", "嗯"), ("我", "我等你")], "我", "对方")
    assert "is_joker" in result
