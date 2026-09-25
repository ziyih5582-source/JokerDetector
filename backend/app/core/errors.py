# -*- coding: utf-8 -*-
"""领域异常 → HTTP 状态码。

档案库只抛出普通的 KeyError / ValueError / RuntimeError，翻译成 HTTP 语义是
API 边界的事。放在 core 里，routes 与融合流程共用同一份映射，不会各写一套。
"""

from __future__ import annotations

from fastapi import HTTPException


def call(operation, *args):
    """执行一次档案库操作，把领域异常映射成合适的 HTTP 状态码。"""
    try:
        return operation(*args)
    except KeyError:
        raise HTTPException(404, "联系人或档案条目不存在") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
