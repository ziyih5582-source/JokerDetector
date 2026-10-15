# -*- coding: utf-8 -*-
"""小丑社区排行榜的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import Field

from app.schemas.base import StrictModel


class ScoreSubmitInput(StrictModel):
    """提交评分的请求模型。用户名取自登录会话，不由前端传入。"""
    score: float = Field(ge=0, le=100, description="小丑值（0-100）")
    joker_type: str = Field(min_length=1, max_length=10)


class CommentInput(StrictModel):
    """发表评论的请求模型。用户名取自登录会话，不由前端传入。"""
    entry_id: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=50)


class LeaderboardEntryResponse(StrictModel):
    """排行榜条目响应。"""
    id: int
    user_name: str
    score: float
    joker_type: str
    timestamp: datetime


class CommentsListResponse(StrictModel):
    """评论列表响应。"""
    comments: List[dict]


class SubmitResponse(StrictModel):
    """提交成功响应。"""
    entry_id: int


class DeleteResponse(StrictModel):
    """删除成功响应。"""
    deleted: bool
