# -*- coding: utf-8 -*-
"""表情/图片识别：把裁块交给支持多模态的云端模型，产出类型、主角与一句概述。

只在用户明确勾选、且配置了 `DEEPSEEK_VISION_MODEL` 时使用。模型同时负责：
- 判断这是「表情包」还是「普通图片」（比按气泡大小猜准得多）；
- 表情包必须点明主角（小猫 / 柴犬 / 熊猫头 / 金馆长 / 网络梗等）；
- 图片则客观描述画面内容。

任何失败都由调用方降级为保留原来的 `[表情]/[图片]`，不影响其它功能与评分。
"""

from __future__ import annotations

import base64
import io
import json
import os
import time

import httpx
import numpy as np
from PIL import Image
from openai import OpenAI

from app.core import config
from app.services.profiles import ai_request_options

PROMPT = (
    "你在看微信聊天里的一张气泡图，它可能是表情包，也可能是普通图片。\n"
    "第一步，判断类型：\n"
    "- 表情包：卡通角色、真人表情截图、网络热门梗图、表情涂鸦等，用来表达情绪或玩梗；\n"
    "- 普通图片：照片、风景、实物、文档或聊天截图等。\n"
    "第二步，按类型概述：\n"
    "- 表情包：必须点明主角是谁。凡是认得的网络热梗、表情角色、动漫/影视角色，要直接点名，"
    "不要只描述外形。常见形象对照（帮助识别，认不出出处才描述外形）：\n"
    "  奶龙＝黄色圆滚滚小恐龙；doge/柴犬＝黄色柴犬；熊猫头＝黑白熊猫脸配各种内容；"
    "蘑菇头＝黑色蘑菇头小人；金馆长＝夸张表情的真人脸；黑人问号＝一脸困惑的黑人；"
    "悲伤蛙 Pepe＝绿色青蛙；猫 meme＝橘猫/白猫照片配文字；Hello Kitty＝白色小猫；"
    "皮卡丘＝黄色电气鼠；杰尼龟＝蓝色乌龟；可达鸭＝黄色鸭子；喜羊羊/小猪佩奇等卡通角色。\n"
    "  另一个重要线索：很多表情包上带标题文字（如「小发雷霆」「勃然小怒」），"
    "把标题读出来并结合它判断梗与情绪。\n"
    "  有点把握但不确定就写「疑似 XX」，完全认不出才描述外形（如「黄色卡通小人」）；"
    "再概括它表达的情绪或梗。\n"
    "- 普通图片：客观描述画面内容（画的是什么、有什么、正在发生什么），不需要主角。\n"
    "注意：summary 里不要再重复主角名称（主角已单独放在 character）。\n"
    "只输出 JSON，不要任何多余文字：\n"
    '{"kind":"sticker 或 image","character":"表情包主角/梗名（普通图片留空）","summary":"不超过30字的概述"}'
)
TIMEOUT = 20
RETRY_WAITS = (5.0, 10.0, 20.0, 30.0)   # 网关会限流/冷却，失败后按这个节奏重试，最多 5 次尝试
MIN_INTERVAL = 7.5                # 交大网关限额：每分钟 10 次请求（按 API key 计）→ 两次调用至少间隔 7.5 秒
PERSONAL_WORKERS = 4              # 用自己 API 时不节流，并行跑，最多同时 4 张
MAX_CHARS = 60
MAX_CHARACTER = 20


def using_personal_api() -> bool:
    """是否配了自己的识图 API：设了 VISION_API_KEY 或 VISION_BASE_URL 就算。"""
    return bool(os.getenv("VISION_API_KEY", "").strip()) or bool(os.getenv("VISION_BASE_URL", "").strip())


def min_interval() -> float:
    """自己的 API 不节流；沿用交大网关时保持每分钟 10 次的节流。"""
    return 0.0 if using_personal_api() else MIN_INTERVAL


def parallel_workers() -> int:
    """自己的 API 并行识别（快很多）；共享网关仍串行以守限额。"""
    return PERSONAL_WORKERS if using_personal_api() else 1

_last_call = 0.0
_CACHE: list[tuple[np.ndarray, dict]] = []
_CACHE_LIMIT = 300
_NEAR_DIFF = 0.012   # 16×16 灰度图平均差小于它就算同一张图（裁块坐标差一两像素也能命中）


def _throttle() -> None:
    """全局节流：保证任意两次请求间隔 ≥ min_interval()，避免撞上交大网关每分钟 10 次的限额。"""
    global _last_call
    interval = min_interval()
    if interval <= 0:
        _last_call = time.monotonic()
        return
    wait = interval - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _signature(image_url: str):
    """把裁块归一化成 16×16 灰度指纹；解析失败返回 None。"""
    try:
        raw = base64.b64decode(image_url.split(",", 1)[1] if "," in image_url else image_url)
        with Image.open(io.BytesIO(raw)) as img:
            small = img.convert("L").resize((16, 16))
            return np.asarray(small, dtype=np.float32) / 255.0
    except Exception:
        return None


def _cache_lookup(image_url: str):
    signature = _signature(image_url)
    if signature is None:
        return None, None
    for cached_signature, result in _CACHE:
        if float(np.abs(cached_signature - signature).mean()) < _NEAR_DIFF:
            return signature, dict(result)
    return signature, None


class VisionUnavailable(RuntimeError):
    """没有配置视觉模型，或客户端不可用。"""


def available() -> bool:
    """是否配置了可用的视觉识别（模型名 + 有效的 Key）。"""
    return bool(config.vision_model()) and _engine_client() is not None


_client = None
_client_signature = None


def reset_client() -> None:
    """配置变化后丢弃旧客户端，下次调用按新配置重建。"""
    global _client, _client_signature
    _client = None
    _client_signature = None


def _engine_client():
    """视觉识别用的客户端：按 VISION_* 配置构建，未单独配置时沿用主服务商。"""
    global _client, _client_signature
    key = config.vision_api_key()
    if config.is_placeholder_key(key):
        return None
    signature = (key, config.vision_base_url(), config.vision_model())
    if _client is None or _client_signature != signature:
        try:
            _client = OpenAI(
                api_key=key,
                base_url=config.vision_base_url(),
                http_client=httpx.Client(trust_env=False),
            )
            _client_signature = signature
        except Exception:
            return None
    return _client


def _parse_json(raw: str) -> dict | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1] if "{" in text else ""):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return None


def _clean(value: str, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _store(signature, result: dict) -> dict:
    if signature is not None:
        if len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.pop(0)
        _CACHE.append((signature, dict(result)))
    return result


def interpret_data_url(image_url: str, client=None, model: str | None = None, hint_kind: str = "sticker") -> dict:
    """返回 {"kind": "sticker"|"image", "character": str, "summary": str}。失败抛异常。

    不传 client/model 时用 VISION_* 配置的客户端（可指向自己的多模态 API）。
    hint_kind 只在模型没按 JSON 返回时用来兜底类型。相同裁块命中进程内缓存，
    不重复请求（聊天里同一张表情反复出现很常见，能省下大量额度）。
    """
    client = client or _engine_client()
    model = model or config.vision_model()
    if not client:
        raise VisionUnavailable("未配置视觉识别：请在 .env 设置 VISION_API_KEY（或主 Key）")
    if not model:
        raise VisionUnavailable("未配置视觉模型：请在 .env 设置 VISION_MODEL")
    if not image_url:
        raise VisionUnavailable("没有可识别的图片裁块")
    signature, cached = _cache_lookup(image_url)
    if cached is not None:
        return cached

    last_error: Exception | None = None
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            _throttle()
            response = client.with_options(timeout=TIMEOUT, max_retries=0).chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]}],
                temperature=0.2,
                max_tokens=160,
                **ai_request_options(client, model),
            )
            if not response.choices or not response.choices[0].message.content:
                raise VisionUnavailable("视觉模型没有返回内容")
            raw = response.choices[0].message.content.strip()
            data = _parse_json(raw)
            if data is None:
                summary = _clean(raw.strip('“”"\''), MAX_CHARS)
                if not summary:
                    raise VisionUnavailable("视觉模型返回空描述")
                return _store(signature, {"kind": hint_kind, "character": "", "summary": summary})
            kind = "image" if str(data.get("kind", "")).strip().lower() == "image" else "sticker"
            character = _clean(data.get("character"), MAX_CHARACTER)
            summary = _clean(data.get("summary"), MAX_CHARS)
            if not summary and not character:
                raise VisionUnavailable("视觉模型返回空描述")
            return _store(signature, {"kind": kind, "character": character, "summary": summary})
        except Exception as exc:  # 限流/超时/格式问题都重试，最后仍失败就交给调用方降级
            last_error = exc
            if attempt < len(RETRY_WAITS):
                time.sleep(RETRY_WAITS[attempt])
    raise last_error if last_error else VisionUnavailable("视觉识别失败")
