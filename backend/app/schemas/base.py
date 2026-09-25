# -*- coding: utf-8 -*-
"""模型基类：统一去掉首尾空白，并且禁止多余字段。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
