# -*- coding: utf-8 -*-
"""问钓翁对话接口的请求模型。"""

from __future__ import annotations

from pydantic import Field

from app.core import config
from app.schemas.base import StrictModel

MAX_CHARS_PER_TURN = 4000


class Turn(StrictModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=MAX_CHARS_PER_TURN)


class ChatInput(StrictModel):
    messages: list[Turn] = Field(min_length=1, max_length=config.CHAT_TURNS)
    contact_id: str | None = Field(default=None, max_length=64)
    use_profile: bool = False


class ContextInput(StrictModel):
    contact_id: str = Field(min_length=1, max_length=64)
