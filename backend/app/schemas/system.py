# -*- coding: utf-8 -*-
"""系统类接口的响应模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AIConfigInfo(BaseModel):
    """只读的 AI 配置状态：不接收也不回传任何密钥。"""

    configured: bool
    model: Optional[str] = None
    base_url: Optional[str] = None
