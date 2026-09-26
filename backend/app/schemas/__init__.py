# -*- coding: utf-8 -*-
"""请求 / 响应模型：所有进出后端的 JSON 形状都在这里定义。"""

from app.schemas.base import StrictModel
from app.schemas.fisherman import ChatInput, ContextInput, Turn
from app.schemas.profiles import AnalyzeInput, ContactInput, FactEdit, JokerDetectInput, Message, UnifiedInput
from app.schemas.system import AIConfigInfo

__all__ = [
    "StrictModel",
    "AIConfigInfo",
    "AnalyzeInput",
    "ChatInput",
    "ContactInput",
    "ContextInput",
    "FactEdit",
    "JokerDetectInput",
    "Message",
    "Turn",
    "UnifiedInput",
]
