# -*- coding: utf-8 -*-
"""系统类接口的响应模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.base import StrictModel


class AIConfigInfo(BaseModel):
    """只读的 AI 配置状态：不接收也不回传任何密钥。"""

    configured: bool
    model: Optional[str] = None
    base_url: Optional[str] = None
    vision_configured: bool = False
    vision_model: Optional[str] = None
    vision_base_url: Optional[str] = None
    vision_key_set: bool = False


class VisionConfigInput(StrictModel):
    """网页里修改识图 API：None=不修改，空串=清空（回落主服务商）。"""

    model: str | None = Field(default=None, max_length=128)
    base_url: str | None = Field(default=None, max_length=300)
    api_key: str | None = Field(default=None, max_length=300)
