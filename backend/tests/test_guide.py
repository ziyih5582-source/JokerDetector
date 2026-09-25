# -*- coding: utf-8 -*-
"""解说页数据源的回归测试：文档里的数字必须永远等于代码里的数字。"""

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.services import report
from app.services.analyzer import METRIC_WEIGHTS, SCORE_MIDPOINT, SCORE_STEEPNESS, VOICE_PENALTY, JOKER_TYPES


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    monkeypatch.setattr(deps.analyzer, "client", None)
    deps.get_store.cache_clear()
    with TestClient(app) as client:
        yield client
    deps.get_store.cache_clear()


def test_guide_exposes_every_section(client):
    data = client.get("/api/guide").json()
    assert set(data) == {"score_scale", "levels", "metrics", "type_rule", "types",
                         "not_joker_desc", "limits"}
    assert data["types"] == JOKER_TYPES
    assert data["type_rule"]


def test_guide_thresholds_are_the_ones_actually_used(client):
    levels = client.get("/api/guide").json()["levels"]
    assert [(l["min"], l["key"]) for l in levels] == report.LEVEL_THRESHOLDS
    for minimum, key in report.LEVEL_THRESHOLDS:
        assert report.level_for(minimum) == key              # 阈值处属于这一档
        if minimum > 0:
            assert report.level_for(minimum - 0.01) != key    # 差一点就掉到下一档
    assert report.level_for(100) == "confirmed"
    assert report.level_for(0) == "healthy"


def test_guide_weights_match_the_scoring_code(client):
    metrics = client.get("/api/guide").json()["metrics"]
    assert {m["key"]: m["weight"] for m in metrics} == METRIC_WEIGHTS
    assert abs(sum(METRIC_WEIGHTS.values()) - 1.0) < 1e-9
    assert all(m["label"] and m["desc"] and m["how"] for m in metrics)


def test_guide_formula_matches_the_constants(client):
    scale = client.get("/api/guide").json()["score_scale"]
    assert str(SCORE_STEEPNESS) in scale["formula"] and str(SCORE_MIDPOINT) in scale["formula"]
    assert str(VOICE_PENALTY) in scale["note"]
    for key in METRIC_WEIGHTS:
        assert key in scale["z_total"]


def test_analysis_and_guide_agree_on_metric_metadata(client):
    """结果页拿到的 z_metrics 必须和解说页讲的是同一批指标。"""
    guide = {m["key"]: m for m in client.get("/api/guide").json()["metrics"]}
    analysis = client.post("/api/analyze/demo/0").json()["analysis"]
    assert set(analysis["z_metrics"]) == set(guide)
    for key, metric in analysis["z_metrics"].items():
        assert metric["label"] == guide[key]["label"]
        assert metric["desc"] == guide[key]["desc"]
        assert metric["weight"] == guide[key]["weight"]


def test_guide_limits_cover_the_real_caps(client):
    limits = client.get("/api/guide").json()["limits"]
    assert limits["upload_mb"] == 5
    assert limits["max_rows"] == 1000
    assert limits["max_chars"] == 120000
    assert limits["cloud_chars"] == 40000
    # 与问钓翁的实际限制保持一致
    from app.api.routes import fisherman
    assert limits["chat_turns"] == fisherman.MAX_TURNS
    assert limits["chat_chars"] == fisherman.MAX_TOTAL_CHARS
