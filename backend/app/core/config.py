# -*- coding: utf-8 -*-
"""全局配置：路径、版本、统一 AI 配置与各项硬性上限。

这里是唯一解析项目路径的地方，全部以项目根为基准。因此 `backend/` 可以整体
单独部署，前端也可以换成任意静态托管，只要把 `frontend/` 一起带走即可。
"""

from __future__ import annotations

import os
from pathlib import Path

# core/config.py -> core -> app -> backend -> 项目根
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

# 前端与静态资源
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_URL_PATH = "/static"
MUSIC_DIR = PROJECT_ROOT / "assets" / "music"
PICTURES_DIR = PROJECT_ROOT / "assets" / "pictures"
# 表情情绪模板库（可选）：按情绪命名的表情图，如 assets/emoji/开心.png
EMOJI_DIR = PROJECT_ROOT / "assets" / "emoji"

# 运行时数据与样例
DATA_DIR = PROJECT_ROOT / "data"
PRIVATE_DATA_DIR = DATA_DIR / "private"
SAMPLES_DIR = DATA_DIR / "samples"
ENV_FILE = PROJECT_ROOT / ".env"

APP_TITLE = "🃏 Joker Detector API"
APP_DESCRIPTION = "小丑监测器 - 聊天记录分析引擎"
APP_VERSION = "2.2.0-experimental"

# 统一 AI 配置的默认值（Key 只从 .env / 环境变量读，绝不写进代码）
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
PLACEHOLDER_KEY_PREFIXES = ("sk-xxx", "sk-你的")

# 各项硬性上限：/api/guide 的 limits 与各接口的校验共用同一份，不会互相脱节
MAX_UPLOAD_MB = 5
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_ROWS = 1000
MAX_CHARS = 120_000
MAX_CLOUD_CHARS = 40_000
# 微信长截图识别：图片与解压后像素上限，防止超大图/解压炸弹拖垮进程
MAX_IMAGE_MB = 20
MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024
MAX_IMAGE_PIXELS = 80_000_000
MAX_IMAGES = 20  # 单次最多同时导入的截图张数
FACTS_PER_CONTACT = 500
BATCHES_PER_CONTACT = 200
EVIDENCE_PER_FACT = 10
CHAT_TURNS = 40
CHAT_CHARS = 24_000

# 由 .env 注入的变量名：refresh 时只回收这些，真实进程环境变量始终优先
_env_file_keys: set[str] = set()


def load_env_file(path: Path | None = None, *, refresh: bool = False) -> None:
    """把 .env 的键值对读进 os.environ，已存在的变量不覆盖。

    refresh=True 时先撤掉上一次由 .env 注入的变量再重新读，这样在网页上点
    「重新加载配置」就能拿到改过的 .env，而不必重启服务；真正的进程环境变量
    优先级最高，任何时候都不会被 .env 覆盖。
    """
    env_path = ENV_FILE if path is None else path
    if refresh:
        for key in list(_env_file_keys):
            os.environ.pop(key, None)
        _env_file_keys.clear()
    if not env_path.exists():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or key in os.environ:
            continue
        os.environ[key] = value
        _env_file_keys.add(key)


def api_key() -> str:
    return os.getenv("DEEPSEEK_API_KEY", "").strip()


def base_url() -> str:
    return os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL


def model_name() -> str:
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def is_placeholder_key(key: str) -> bool:
    """占位符与空值都视为「未配置」。"""
    return not key or key.startswith(PLACEHOLDER_KEY_PREFIXES)


# 进程启动时先加载一次，保证 ImportError 之前配置就已就位
load_env_file()
