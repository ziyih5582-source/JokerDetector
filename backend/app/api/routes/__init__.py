# -*- coding: utf-8 -*-
"""路由聚合：main.py 只需 include 这一个 router。"""

from fastapi import APIRouter

from app.api.routes import analysis, fisherman, profiles, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(analysis.router)
api_router.include_router(profiles.router)
api_router.include_router(fisherman.router)

__all__ = ["api_router"]
