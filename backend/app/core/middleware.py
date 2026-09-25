# -*- coding: utf-8 -*-
"""横切关注点：本机单用户应用的访问边界。

这个服务假定「只在自己电脑上跑、只有自己访问」，因此：
  - 只接受本机 Host，避免 DNS rebinding 之类的玩法；
  - 拒绝跨站发起的写请求（浏览器里的其它页面不能替用户改档案）；
  - 给 API 响应加上 no-store，并把前端页面锁在严格 CSP 下。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

# 前端不使用任何外部脚本、字体与内联脚本，所以可以直接上最严的 CSP
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'self'"
)

PAGE_PATHS = {"/", "/profiles", "/index.html"}

CROSS_SITE_WRITE_MESSAGE = "不接受跨站修改请求"


def install_middleware(app: FastAPI) -> None:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.middleware("http")
    async def local_privacy(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
                return JSONResponse({"detail": CROSS_SITE_WRITE_MESSAGE}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": CROSS_SITE_WRITE_MESSAGE}, status_code=403)

        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path in PAGE_PATHS:
            response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        return response
