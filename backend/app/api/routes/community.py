# -*- coding: utf-8 -*-
"""小丑社区 API 路由：账号、排行榜与评论。

读取（榜单、评论）不需要登录；写入（上传小丑值、发表评论）需要先登录。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from typing import Optional

from app.api.deps import get_auth_store, get_leaderboard_store, require_user
from app.schemas import auth as auth_schemas
from app.schemas import leaderboard as schemas
from app.services.auth import AuthError

router = APIRouter(prefix="/api/community", tags=["小丑社区"])


def get_leaderboard():
    """获取排行榜实例（进程级单例，目录可被 JOKER_PROFILE_DIR 覆盖）。"""
    return get_leaderboard_store()


# ------------------------------------------------------------ 账号

@router.post("/auth/register", response_model=auth_schemas.AuthResponse)
async def register(body: auth_schemas.RegisterInput):
    """注册并直接登录。密码为 6 位数字，需选择头像类型。"""
    try:
        return get_auth_store().register(body.username, body.password, body.avatar_type)
    except AuthError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/auth/login", response_model=auth_schemas.AuthResponse)
async def login(body: auth_schemas.Credentials):
    """登录，返回会话 token。"""
    username = body.username
    password = body.password
    try:
        return get_auth_store().login(username, password)
    except AuthError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(default=None)):
    """退出登录：作废当前 token。"""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    get_auth_store().logout(token)
    return {"ok": True}


@router.get("/auth/me")
async def me(authorization: Optional[str] = Header(default=None)):
    """返回当前登录用户；未登录返回 {username: null}。"""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    current = get_auth_store().verify(token)
    avatar = None
    if current:
        info = get_auth_store().get_user_info(current)
        avatar = info["avatar_type"] if info else None
    return {"username": current, "avatar_type": avatar}


# ------------------------------------------------------------ 榜单（读取）

@router.get("/avatars")
async def avatar_options():
    """返回可选的头像列表。"""
    from app.services.auth import AVATAR_TYPES
    return {"avatars": list(AVATAR_TYPES)}


@router.get("/leaderboard")
async def get_ranking(
    limit: int = Query(default=50, ge=1, le=200, description="返回条目数量"),
    offset: int = Query(default=0, ge=0, description="偏移量")
):
    """获取排行榜（按分数降序）。"""
    service = get_leaderboard()
    entries = service.get_leaderboard(limit, offset)
    
    # 获取每个条目的用户头像类型
    auth_store = get_auth_store()
    usernames = [e["user_name"] for e in entries]
    avatars = auth_store.get_avatars(usernames)
    for entry in entries:
        entry["avatar_type"] = avatars.get(entry["user_name"], "殉道型")
    
    return {"entries": entries}


@router.get("/entries/{entry_id}")
async def get_entry_detail(entry_id: int):
    """获取某条排行榜记录的详情。"""
    service = get_leaderboard()
    entry = service.get_entry(entry_id)
    if not entry:
        raise HTTPException(404, "排行榜条目不存在")
    
    # 添加头像信息
    auth_store = get_auth_store()
    user_info = auth_store.get_user_info(entry["user_name"])
    if user_info:
        entry["avatar_type"] = user_info["avatar_type"]
    else:
        entry["avatar_type"] = "殉道型"
    
    return entry


@router.get("/entries/{entry_id}/comments")
async def get_entry_comments(entry_id: int):
    """获取某条记录的所有评论。"""
    service = get_leaderboard()
    comments = service.get_comments(entry_id)
    return {"comments": comments}


# ------------------------------------------------------------ 榜单（写入，需登录）

@router.post("/submit")
async def submit_score(body: schemas.ScoreSubmitInput, username: str = Depends(require_user)):
    """上传小丑值到排行榜。昵称取自登录账号。"""
    service = get_leaderboard()
    entry_id = service.submit_entry(username, body.score, body.joker_type)
    return {"entry_id": entry_id, "username": username}


@router.post("/comments")
async def add_comment(body: schemas.CommentInput, username: str = Depends(require_user)):
    """发表评论。昵称取自登录账号。"""
    service = get_leaderboard()
    try:
        comment_id = service.add_comment(body.entry_id, username, body.content)
        return {"comment_id": comment_id, "username": username}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: int, username: str = Depends(require_user)):
    """删除评论（仅作者本人可删）。"""
    service = get_leaderboard()
    comment = service.get_comment(comment_id)
    if not comment:
        raise HTTPException(404, "评论不存在")
    if comment["user_name"] != username:
        raise HTTPException(403, "只能删除自己的评论")
    service.delete_comment(comment_id)
    return {"deleted": True}
