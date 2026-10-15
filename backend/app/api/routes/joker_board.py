# -*- coding: utf-8 -*-
"""小丑看板接口：给「页面右上角那块小丑看板」提供数据。

与 ``/api/analyze/joker/detect`` 的区别：
- detect 回答「是不是小丑」（总分、类型、六征命中）；
- 本接口在同一份判定之上补齐「每个维度多少分、权重多少、依据是哪几句话」，
  供常驻看板与六维雷达直接渲染。两者共用同一个本地引擎，都不调用云端 AI。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import analyzer
from app.core import config
from app.schemas import JokerDetectInput
from app.services.joker_board import build_board

router = APIRouter(prefix="/api/joker", tags=["小丑看板"])


@router.post("/board")
def joker_board(body: JokerDetectInput):
    """六维分值 + 权重 + 依据原句 + 下一步建议。纯本地计算，不写档案库。"""
    if body.self_speaker == body.other_speaker:
        raise HTTPException(400, "「我」和「对方」不能是同一个人")
    if sum(len(m.content) for m in body.messages) > config.MAX_CHARS:
        raise HTTPException(400, "单次聊天内容不能超过 12 万字，请分段导入")
    data = [(m.speaker, m.content) for m in body.messages]
    speakers = {speaker for speaker, _ in data}
    if speakers != {body.self_speaker, body.other_speaker}:
        raise HTTPException(400, "只支持明确的双人聊天，请选择文件中实际的两位发言者")
    return build_board(analyzer, data, body.self_speaker, body.other_speaker)
