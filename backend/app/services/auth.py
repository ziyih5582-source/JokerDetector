# -*- coding: utf-8 -*-
"""小丑社区的用户与会话（本机 SQLite）。

用途很窄：只在「上传小丑值」和「发表评论」两个写操作前要求登录。
账号只在本机，密码是 6 位数字，用 PBKDF2 加盐哈希后保存，绝不明文落盘。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from app.core import config

PBKDF2_ITERATIONS = 120_000
USERNAME_MIN = 2
USERNAME_MAX = 20

# 可选头像：与六型小丑一一对应（前端 clown.js 里有同名形象）
AVATAR_TYPES = ("殉道型", "镜像型", "弄臣型", "幻恋型", "守候型", "单向型")
DEFAULT_AVATAR = "殉道型"


class AuthError(ValueError):
    """登录/注册失败：用户名或密码不满足要求。"""


class AuthStore:
    """用户与会话的本地存储。"""

    def __init__(self, directory: Optional[Path] = None):
        base = Path(directory) if directory else config.PRIVATE_DATA_DIR
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / "community_auth.db"
        self._init_db()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _init_db(self):
        with self.connection() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    avatar_type TEXT NOT NULL DEFAULT '殉道型',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # 兼容早期没有 avatar_type 列的库：补上这一列
            cols = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
            if "avatar_type" not in cols:
                db.execute(
                    f"ALTER TABLE users ADD COLUMN avatar_type TEXT NOT NULL DEFAULT '{DEFAULT_AVATAR}'"
                )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(username)")

    # ---------- 内部工具 ----------

    @staticmethod
    def _hash(password: str, salt_hex: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
        ).hex()

    @staticmethod
    def _check_username(username: str) -> str:
        name = (username or "").strip()
        if not (USERNAME_MIN <= len(name) <= USERNAME_MAX):
            raise AuthError(f"用户名需 {USERNAME_MIN}–{USERNAME_MAX} 个字符")
        return name

    @staticmethod
    def _check_password(password: str) -> str:
        pwd = password or ""
        if len(pwd) != 6 or not pwd.isdigit():
            raise AuthError("密码必须是 6 位数字")
        return pwd

    @staticmethod
    def _check_avatar(avatar_type: str) -> str:
        avatar = (avatar_type or "").strip()
        if avatar not in AVATAR_TYPES:
            raise AuthError("请选择一个小丑头像")
        return avatar

    # ---------- 对外接口 ----------

    def register(self, username: str, password: str, avatar_type: str = DEFAULT_AVATAR) -> dict:
        name = self._check_username(username)
        pwd = self._check_password(password)
        avatar = self._check_avatar(avatar_type)
        salt = secrets.token_hex(16)
        with self.connection() as db:
            exists = db.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone()
            if exists:
                raise AuthError("这个用户名已经被注册了")
            db.execute(
                "INSERT INTO users (username, salt, password_hash, avatar_type) VALUES (?, ?, ?, ?)",
                (name, salt, self._hash(pwd, salt), avatar),
            )
        # 注册成功直接登录
        return self.login(name, pwd)

    def login(self, username: str, password: str) -> dict:
        name = (username or "").strip()
        pwd = password or ""
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE username = ?", (name,)).fetchone()
            if row is None or not hmac.compare_digest(row["password_hash"], self._hash(pwd, row["salt"])):
                raise AuthError("用户名或密码不正确")
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessions (token, username) VALUES (?, ?)", (token, row["username"]))
        return {"token": token, "username": row["username"], "avatar_type": row["avatar_type"]}

    def verify(self, token: str) -> Optional[str]:
        if not token:
            return None
        with self.connection() as db:
            row = db.execute("SELECT username FROM sessions WHERE token = ?", (token,)).fetchone()
        return row["username"] if row else None

    def get_user_info(self, username: str) -> Optional[dict]:
        """按用户名取头像信息（供榜单渲染头像用）。"""
        if not username:
            return None
        with self.connection() as db:
            row = db.execute(
                "SELECT username, avatar_type FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def get_avatars(self, usernames) -> dict:
        """批量取 {用户名: 头像类型}，一次查询避免榜单逐条查库。"""
        names = [n for n in dict.fromkeys(usernames or []) if n]
        if not names:
            return {}
        placeholders = ",".join("?" for _ in names)
        with self.connection() as db:
            rows = db.execute(
                f"SELECT username, avatar_type FROM users WHERE username IN ({placeholders})",
                names,
            ).fetchall()
        return {row["username"]: row["avatar_type"] for row in rows}

    def logout(self, token: str) -> None:
        if not token:
            return
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE token = ?", (token,))
