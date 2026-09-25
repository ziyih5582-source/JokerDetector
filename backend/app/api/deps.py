# -*- coding: utf-8 -*-
"""进程级单例：分析引擎（含统一 AI 配置）与本机档案库。

只有这一处实例化，路由、融合流程与问钓翁都用同一份，避免出现两套 AI 状态。
"""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import HTTPException

from app.core import config
from app.services.analyzer import JokerAnalyzer
from app.services.profiles import ProfileStore

# 全局单例 analyzer；AI 客户端统一由 .env / 环境变量配置
analyzer = JokerAnalyzer()


@lru_cache
def get_store() -> ProfileStore:
    """本机加密档案库。目录可用环境变量 JOKER_PROFILE_DIR 覆盖。"""
    directory = os.environ.get("JOKER_PROFILE_DIR") or str(config.PRIVATE_DATA_DIR)
    try:
        return ProfileStore(directory)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
