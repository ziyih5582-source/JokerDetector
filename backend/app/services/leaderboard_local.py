# -*- coding: utf-8 -*-
"""小丑社区排行榜 - SQLite 本地实现。

数据存储在 data/private/leaderboard.db，与现有档案库在一起。
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from app.core import config


class LocalLeaderboardSQLite:
    """基于 SQLite 的本地排行榜实现。"""

    def __init__(self, directory: Optional[Path] = None):
        if directory is not None:
            base = Path(directory)
        else:
            base = Path(os.environ.get("JOKER_PROFILE_DIR") or config.PRIVATE_DATA_DIR)
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / "leaderboard.db"
        self._init_db()

    @contextmanager
    def connection(self):
        """数据库连接上下文管理器。"""
        db = sqlite3.connect(str(self.path), timeout=15)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def _init_db(self):
        """初始化数据库表结构。"""
        with self.connection() as db:
            # 排行榜条目表
            db.execute("""
                CREATE TABLE IF NOT EXISTS leaderboard_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_name TEXT NOT NULL,
                    joker_score REAL NOT NULL CHECK(joker_score >= 0 AND joker_score <= 100),
                    joker_type TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 评论表
            db.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id INTEGER NOT NULL,
                    user_name TEXT NOT NULL,
                    content TEXT NOT NULL CHECK(length(content) <= 50),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entry_id) REFERENCES leaderboard_entries(id) ON DELETE CASCADE
                )
            """)
            
            # 创建索引
            db.execute("CREATE INDEX IF NOT EXISTS idx_score ON leaderboard_entries(joker_score DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_entry_id ON comments(entry_id)")
            db.commit()

    def submit_entry(self, user_name: str, score: float, joker_type: str) -> int:
        """提交新评分，返回 entry_id。"""
        with self.connection() as db:
            cursor = db.execute(
                "INSERT INTO leaderboard_entries (user_name, joker_score, joker_type) VALUES (?, ?, ?)",
                (user_name.strip(), score, joker_type.strip())
            )
            db.commit()
            return cursor.lastrowid

    def get_leaderboard(self, limit: int = 50, offset: int = 0) -> List[dict]:
        """获取排行榜（按分数降序）。"""
        with self.connection() as db:
            cursor = db.execute(
                """SELECT id, user_name, joker_score AS score, joker_type, timestamp 
                   FROM leaderboard_entries 
                   ORDER BY joker_score DESC 
                   LIMIT ? OFFSET ?""",
                (limit, offset)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_comments(self, entry_id: int) -> List[dict]:
        """获取某条记录的所有评论。"""
        with self.connection() as db:
            cursor = db.execute(
                "SELECT id, user_name, content, timestamp FROM comments WHERE entry_id = ? ORDER BY timestamp ASC",
                (entry_id,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def add_comment(self, entry_id: int, user_name: str, content: str) -> int:
        """发表评论，返回 comment_id。"""
        if len(content.strip()) == 0:
            raise ValueError("评论内容不能为空")
        if len(content) > 50:
            raise ValueError("评论不能超过 50 字")
        
        with self.connection() as db:
            cursor = db.execute(
                "INSERT INTO comments (entry_id, user_name, content) VALUES (?, ?, ?)",
                (entry_id, user_name.strip(), content.strip())
            )
            db.commit()
            return cursor.lastrowid

    def delete_comment(self, comment_id: int) -> bool:
        """删除评论。"""
        with self.connection() as db:
            cursor = db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
            db.commit()
            return cursor.rowcount > 0

    def get_comment(self, comment_id: int) -> Optional[dict]:
        """获取单条评论。"""
        with self.connection() as db:
            cursor = db.execute(
                "SELECT id, entry_id, user_name, content, timestamp FROM comments WHERE id = ?",
                (comment_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_entry(self, entry_id: int) -> Optional[dict]:
        """获取某条排行榜记录的详情。"""
        with self.connection() as db:
            cursor = db.execute(
                "SELECT id, user_name, joker_score AS score, joker_type, timestamp FROM leaderboard_entries WHERE id = ?",
                (entry_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
