# -*- coding: utf-8 -*-
"""联系人档案与统一分析流程的请求模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.core import config
from app.schemas.base import StrictModel


class ContactInput(StrictModel):
    name: str = Field(min_length=1, max_length=60)


class Message(StrictModel):
    speaker: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=5000)
    emotion: str | None = Field(default=None, max_length=32)


class AnalyzeInput(StrictModel):
    messages: list[Message] = Field(min_length=2, max_length=config.MAX_ROWS)
    self_speaker: str = Field(min_length=1, max_length=100)
    other_speaker: str = Field(min_length=1, max_length=100)
    save_consent: bool = False
    use_ai: bool = False
    include_guidance: bool = False


class FactEdit(StrictModel):
    revision: int = Field(ge=0)
    action: Literal["confirm", "correct", "delete"]
    text: str | None = Field(default=None, max_length=200)


class UnifiedInput(StrictModel):
    """一次提交同时驱动情感分析与联系人档案两个模式。"""

    messages: list[Message] = Field(min_length=2, max_length=config.MAX_ROWS)
    self_speaker: str = Field(min_length=1, max_length=100)
    other_speaker: str = Field(min_length=1, max_length=100)
    contact_id: str | None = Field(default=None, max_length=64)
    save_consent: bool = False
    use_ai: bool = False
    include_guidance: bool = False
