# -*- coding: utf-8 -*-
"""小丑社区 /api/community/* 的回归测试：账号、榜单与评论。

读取不需要登录；上传小丑值与发表评论需要先登录。
"""

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    deps.get_auth_store.cache_clear()
    deps.get_leaderboard_store.cache_clear()
    with TestClient(app) as client:
        yield client
    deps.get_auth_store.cache_clear()
    deps.get_leaderboard_store.cache_clear()


def register(client, username="小明", password="123456", avatar_type="殉道型"):
    return client.post(
        "/api/community/auth/register",
        json={"username": username, "password": password, "avatar_type": avatar_type},
    )


def auth_header(token):
    return {"Authorization": "Bearer " + token}


# ------------------------------------------------------------ 账号

def test_register_and_login(client):
    r = register(client)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "小明"
    assert body["token"]
    assert body["avatar_type"] == "殉道型"

    # 退出后再登录
    r = client.post("/api/community/auth/login", json={"username": "小明", "password": "123456"})
    assert r.status_code == 200
    assert r.json()["username"] == "小明"
    assert r.json()["avatar_type"] == "殉道型"


def test_avatar_options_listed(client):
    r = client.get("/api/community/avatars")
    assert r.status_code == 200
    assert set(r.json()["avatars"]) == {"殉道型", "镜像型", "弄臣型", "幻恋型", "守候型", "单向型"}


def test_register_requires_valid_avatar(client):
    r = register(client, "无头像", avatar_type="不存在的型")
    assert r.status_code == 400
    assert "头像" in r.json()["detail"]


def test_me_includes_avatar(client):
    token = register(client, "阿花", avatar_type="幻恋型").json()["token"]
    me = client.get("/api/community/auth/me", headers=auth_header(token)).json()
    assert me["username"] == "阿花"
    assert me["avatar_type"] == "幻恋型"


def test_duplicate_username_rejected(client):
    register(client)
    r = register(client)
    assert r.status_code == 400
    assert "已经被注册" in r.json()["detail"]


def test_password_must_be_six_digits(client):
    r = register(client, "小红", password="12345")
    assert r.status_code == 400
    r = register(client, "小红", password="abcdef")
    assert r.status_code == 400
    assert "6 位数字" in r.json()["detail"]


def test_wrong_password_rejected(client):
    register(client)
    r = client.post("/api/community/auth/login", json={"username": "小明", "password": "000000"})
    assert r.status_code == 400


def test_me_reflects_login_state(client):
    assert client.get("/api/community/auth/me").json()["username"] is None
    token = register(client).json()["token"]
    assert client.get("/api/community/auth/me", headers=auth_header(token)).json()["username"] == "小明"


# ------------------------------------------------------------ 榜单写入需登录

def test_submit_requires_login(client):
    r = client.post("/api/community/submit", json={"score": 80, "joker_type": "殉道型"})
    assert r.status_code == 401


def test_submit_uses_login_username(client):
    token = register(client, "阿强").json()["token"]
    r = client.post(
        "/api/community/submit",
        json={"score": 82.5, "joker_type": "幻恋型"},
        headers=auth_header(token),
    )
    assert r.status_code == 200
    assert r.json()["username"] == "阿强"

    entries = client.get("/api/community/leaderboard").json()["entries"]
    assert len(entries) == 1
    assert entries[0]["user_name"] == "阿强"
    assert entries[0]["score"] == 82.5


def test_leaderboard_includes_avatar(client):
    token = register(client, "带头像", avatar_type="守候型").json()["token"]
    client.post("/api/community/submit", json={"score": 70, "joker_type": "守候型"}, headers=auth_header(token))
    entry = client.get("/api/community/leaderboard").json()["entries"][0]
    assert entry["avatar_type"] == "守候型"
    # 条目详情也应带头像
    detail = client.get(f"/api/community/entries/{entry['id']}").json()
    assert detail["avatar_type"] == "守候型"


def test_leaderboard_avatar_defaults_for_unknown_user(client):
    """历史数据里可能有没有账号的条目，头像应回退到默认值而不是报错。"""
    store = deps.get_leaderboard_store()
    store.submit_entry("幽灵用户", 55.0, "殉道型")
    entry = client.get("/api/community/leaderboard").json()["entries"][0]
    assert entry["avatar_type"] == "殉道型"


def test_leaderboard_sorted_desc(client):
    token = register(client, "u1").json()["token"]
    for score in (60, 90, 75):
        client.post("/api/community/submit", json={"score": score, "joker_type": "殉道型"}, headers=auth_header(token))
    scores = [e["score"] for e in client.get("/api/community/leaderboard").json()["entries"]]
    assert scores == sorted(scores, reverse=True)


def test_leaderboard_read_is_public(client):
    r = client.get("/api/community/leaderboard")
    assert r.status_code == 200
    assert r.json()["entries"] == []


# ------------------------------------------------------------ 评论

def test_comment_requires_login(client):
    token = register(client).json()["token"]
    entry_id = client.post(
        "/api/community/submit", json={"score": 70, "joker_type": "弄臣型"}, headers=auth_header(token)
    ).json()["entry_id"]

    r = client.post("/api/community/comments", json={"entry_id": entry_id, "content": "太真实了"})
    assert r.status_code == 401


def test_comment_and_read(client):
    token = register(client, "评论员").json()["token"]
    entry_id = client.post(
        "/api/community/submit", json={"score": 70, "joker_type": "弄臣型"}, headers=auth_header(token)
    ).json()["entry_id"]

    r = client.post(
        "/api/community/comments",
        json={"entry_id": entry_id, "content": "太真实了"},
        headers=auth_header(token),
    )
    assert r.status_code == 200
    assert r.json()["username"] == "评论员"

    comments = client.get(f"/api/community/entries/{entry_id}/comments").json()["comments"]
    assert len(comments) == 1
    assert comments[0]["user_name"] == "评论员"
    assert comments[0]["content"] == "太真实了"


def test_comment_length_limit(client):
    token = register(client).json()["token"]
    entry_id = client.post(
        "/api/community/submit", json={"score": 70, "joker_type": "弄臣型"}, headers=auth_header(token)
    ).json()["entry_id"]
    r = client.post(
        "/api/community/comments",
        json={"entry_id": entry_id, "content": "x" * 51},
        headers=auth_header(token),
    )
    assert r.status_code == 422


def test_only_author_can_delete_comment(client):
    t1 = register(client, "作者").json()["token"]
    t2 = register(client, "路人").json()["token"]
    entry_id = client.post(
        "/api/community/submit", json={"score": 70, "joker_type": "弄臣型"}, headers=auth_header(t1)
    ).json()["entry_id"]
    cid = client.post(
        "/api/community/comments",
        json={"entry_id": entry_id, "content": "你好"},
        headers=auth_header(t1),
    ).json()["comment_id"]

    # 别人删不掉
    assert client.delete(f"/api/community/comments/{cid}", headers=auth_header(t2)).status_code == 403
    # 本人可以删
    assert client.delete(f"/api/community/comments/{cid}", headers=auth_header(t1)).status_code == 200


def test_logout_invalidates_token(client):
    token = register(client).json()["token"]
    client.post("/api/community/auth/logout", headers=auth_header(token))
    r = client.post("/api/community/submit", json={"score": 80, "joker_type": "殉道型"}, headers=auth_header(token))
    assert r.status_code == 401
