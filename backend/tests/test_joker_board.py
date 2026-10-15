# -*- coding: utf-8 -*-
"""小丑看板（/api/joker/board）的回归测试：六维分值、权重与依据原句，全程本地。"""

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.services.analyzer import JokerAnalyzer
from app.services.joker_board import (
    CLEAR_STEP,
    LEVEL_LABEL,
    SIGN_ORDER,
    SIGN_WEIGHT,
    build_board,
)

ONE_SIDED = [
    ("我", "在忙吗"),
    ("对方", "嗯"),
    ("我", "忙完了吗"),
    ("我", "在吗"),
    ("我", "我就是个小丑，我太菜了"),
    ("我", "我这种人真是丢人"),
    ("对方", "……"),
    ("我", "我不配，救命"),
    ("我", "我这种人真是废物"),
]

HEALTHY = [
    ("我", "周六下午可以，上午有个会"),
    ("对方", "行，那先喝咖啡再过去"),
    ("我", "我发现一家新咖啡馆"),
    ("对方", "好呀，几点"),
    ("我", "两点吧"),
    ("对方", "收到，周六见"),
    ("我", "到时候见"),
    ("对方", "好"),
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    monkeypatch.setattr(deps.analyzer, "client", None)
    deps.get_store.cache_clear()
    with TestClient(app) as client:
        yield client
    deps.get_store.cache_clear()


def board_of(messages, self_speaker="我", other_speaker="对方"):
    return build_board(JokerAnalyzer(), messages, self_speaker, other_speaker)


# ------------------------------------------------------------ 维度与权重

def test_six_dimensions_are_in_the_same_order_as_the_judge_room():
    board = board_of(ONE_SIDED)
    assert [item["key"] for item in board["dimensions"]] == list(SIGN_ORDER)
    assert len(board["radar"]) == len(SIGN_ORDER)


def test_weights_are_a_normalized_distribution():
    assert abs(sum(SIGN_WEIGHT.values()) - 1.0) < 1e-9


def test_every_dimension_reports_points_weight_and_contribution():
    board = board_of(ONE_SIDED)
    for item in board["dimensions"]:
        assert 0.0 <= item["score"] <= 1.0
        assert 0.0 <= item["points"] <= 100.0
        assert item["weight"] == SIGN_WEIGHT[item["key"]]
        assert abs(item["contribution"] - item["score"] * item["weight"] * 100) < 0.11
        assert item["label"] and item["detail"]


def test_weighted_score_stays_inside_the_scale():
    board = board_of(ONE_SIDED)
    assert 0.0 <= board["weighted_score"] <= 100.0


# ------------------------------------------------------------ 与鉴定所保持同一口径

def test_board_score_matches_the_local_detector():
    analyzer = JokerAnalyzer()
    detected = analyzer.detect_joker_profile(ONE_SIDED, "我", "对方")
    board = board_of(ONE_SIDED)
    assert board["score"] == detected["score"]
    assert board["is_joker"] is detected["is_joker"]
    assert board["type"] == detected["type"]
    assert board["level_label"] == LEVEL_LABEL[detected["level"]]


def test_hit_count_equals_hit_dimensions():
    board = board_of(ONE_SIDED)
    assert board["hit_count"] == sum(1 for item in board["dimensions"] if item["hit"])


# ------------------------------------------------------------ 依据

def test_evidence_quotes_are_taken_from_the_users_own_lines():
    board = board_of(ONE_SIDED)
    by_key = {item["key"]: item for item in board["dimensions"]}
    mockery = by_key["self_mockery"]
    assert mockery["hit"] is True
    assert mockery["evidence"], "命中的维度必须给出依据原句"
    assert any("小丑" in quote or "我不配" in quote for quote in mockery["evidence"])
    # 依据只能是本人说的话，不能引用对方
    assert all("……" not in quote for item in board["dimensions"] for quote in item["evidence"])


def test_one_way_evidence_quotes_the_longest_streak():
    board = board_of(ONE_SIDED)
    one_way = next(item for item in board["dimensions"] if item["key"] == "one_way")
    assert one_way["hit"] is True
    assert one_way["evidence"], "单向推进要引用连续发送的那几句"
    assert one_way["evidence"][0] == "「忙完了吗」"


def test_dimensions_without_hit_do_not_quote_lines():
    """未命中的维度只留统计口径，不引用原句，免得看板上到处是「证据」。"""
    board = board_of(ONE_SIDED)
    assert all(not item["evidence"] for item in board["dimensions"] if not item["hit"])


def test_healthy_chat_has_no_hits_and_gives_a_keep_going_step():
    board = board_of(HEALTHY)
    assert board["is_joker"] is False
    assert board["hit_count"] == 0
    assert board["next_steps"] == [CLEAR_STEP]
    assert all(not item["evidence"] for item in board["dimensions"])


def test_summary_mentions_the_top_dimensions():
    board = board_of(ONE_SIDED)
    assert board["summary"]
    if board["hit_count"]:
        assert "命中" in board["summary"]


def test_message_counts_follow_the_two_speakers():
    board = board_of(ONE_SIDED)
    assert board["message_counts"]["self"] == 7
    assert board["message_counts"]["other"] == 2
    assert board["message_counts"]["total"] == len(ONE_SIDED)


# ------------------------------------------------------------ 纯本地

def test_board_never_touches_the_ai_client(monkeypatch):
    class Boom:
        def __getattr__(self, name):
            raise AssertionError("小丑看板不得触碰 AI 客户端")

    analyzer = JokerAnalyzer()
    analyzer.client = Boom()
    board = build_board(analyzer, ONE_SIDED, "我", "对方")
    assert board["engine"].startswith("本地六征")


# ------------------------------------------------------------ HTTP 接口

def detect_body(messages, self_speaker="我", other_speaker="对方"):
    return {
        "messages": [{"speaker": s, "content": c} for s, c in messages],
        "self_speaker": self_speaker,
        "other_speaker": other_speaker,
    }


def test_board_endpoint_returns_dimensions_and_evidence(client):
    response = client.post("/api/joker/board", json=detect_body(ONE_SIDED))
    assert response.status_code == 200
    data = response.json()
    assert len(data["dimensions"]) == 6
    assert data["dimensions"][0]["evidence"]
    assert data["score"] >= 45
    assert data["level_label"]


def test_board_endpoint_accepts_a_healthy_chat(client):
    data = client.post("/api/joker/board", json=detect_body(HEALTHY)).json()
    assert data["is_joker"] is False
    assert data["type"] is None


def test_board_endpoint_rejects_same_speaker(client):
    response = client.post("/api/joker/board", json=detect_body(
        [("我", "你好"), ("我", "在吗")], self_speaker="我", other_speaker="我"))
    assert response.status_code == 400


def test_board_endpoint_rejects_a_third_speaker(client):
    response = client.post("/api/joker/board", json=detect_body([
        ("我", "你好"), ("对方", "嗯"), ("路人", "路过"),
    ]))
    assert response.status_code == 400
