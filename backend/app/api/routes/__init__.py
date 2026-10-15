# -*- coding: utf-8 -*-
"""路由聚合：main.py 只需 include 这一个 router。"""

from fastapi import APIRouter

from app.api.routes import (
    analysis,
    campus_preview,
    community,
    fisherman,
    joker_board,
    profiles,
    system,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(analysis.router)
api_router.include_router(profiles.router)
api_router.include_router(fisherman.router)
api_router.include_router(campus_preview.router)
api_router.include_router(community.router)
api_router.include_router(joker_board.router)

__all__ = ["api_router"]
