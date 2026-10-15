# -*- coding: utf-8 -*-
"""后端入口：把各层装配成一个 FastAPI 应用。

启动（在 backend/ 目录下）：
    python -m app.main
    uvicorn app.main:app --host 127.0.0.1 --port 8000

前端页面与静态资源由本服务一起挂载（/、/static、/music），
前后端之间只通过 /api/* 通信，因此 frontend/ 也可以单独部署。
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.core import config
from app.core.middleware import install_middleware


def _mount_frontend(app: FastAPI) -> None:
    """挂载前端静态资源与页面入口。"""
    index_path = config.FRONTEND_DIR / "index.html"
    app.mount(config.STATIC_URL_PATH, StaticFiles(directory=config.FRONTEND_DIR), name="static")
    if config.MUSIC_DIR.exists():
        app.mount("/music", StaticFiles(directory=config.MUSIC_DIR), name="music")

    @app.get("/")
    async def serve_frontend():
        """统一工作台：情感分析与联系人档案已融合为同一条流程。"""
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "前端文件未找到"}

    @app.get("/profiles")
    def serve_profiles():
        """旧入口保留：直接指向融合后的同一页面。"""
        return FileResponse(index_path)

    # 单页应用的其它视图路径：交回同一张页面，由前端按 path 切换视图。
    @app.get("/community")
    def serve_community():
        """小丑社区：直接访问 /community 也能进入榜单页。"""
        return FileResponse(index_path)

    @app.get("/joker")
    def serve_joker():
        """小丑鉴定所：直接访问 /joker 也能进入。"""
        return FileResponse(index_path)


def create_app() -> FastAPI:
    app = FastAPI(
        title=config.APP_TITLE,
        description=config.APP_DESCRIPTION,
        version=config.APP_VERSION,
    )
    install_middleware(app)
    _mount_frontend(app)
    app.include_router(api_router)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=config.host(), port=config.port(), reload=True)
