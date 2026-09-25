# -*- coding: utf-8 -*-
"""Joker Detector 后端应用包。

分层约定：
  core/      配置、中间件、错误映射——不含业务逻辑
  schemas/   请求与响应模型
  services/  分析引擎、档案库、结果格式化、融合流程
  api/       路由与进程级单例（唯一把 service 暴露成 HTTP 的地方）

前端是独立的静态站点（项目根目录的 frontend/），由本服务一并挂载，
也可以拆到任意静态托管；两者之间只通过 /api/* 通信。
"""

__all__ = ["__version__"]

from app.core import config

__version__ = config.APP_VERSION
