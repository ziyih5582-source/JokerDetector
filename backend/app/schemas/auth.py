# -*- coding: utf-8 -*-
"""小丑社区账号相关的请求/响应模型。"""

from __future__ import annotations

from pydantic import Field

from app.schemas.base import StrictModel


class Credentials(StrictModel):
    """注册与登录共用：用户名 + 6 位数字密码。

    这里只做基本的非空限制，具体规则（用户名长度、6 位数字密码）由
    AuthStore 校验，好给出统一的中文提示。
    """
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=64)


class RegisterInput(StrictModel):
    """注册输入：在登录信息之外，还需从六型小丑形象里选一个作为头像。"""
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=64)
    avatar_type: str = Field(min_length=1, max_length=10)


class AuthResponse(StrictModel):
    """注册/登录成功后的会话信息。"""
    token: str
    username: str
    avatar_type: str
