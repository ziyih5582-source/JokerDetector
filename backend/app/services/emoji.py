# -*- coding: utf-8 -*-
"""表情情绪模板匹配（可选，默认关闭）。

在 `assets/emoji/` 放按情绪命名的表情图（文件名即情绪，如 `开心.png`、`哭.png`），
识别到表情气泡时会把它与这些模板比对，取最接近的一个作为情绪标签。没有素材时
返回 `(None, 0.0)`，前端保留手动选择——即「默认关闭、放素材才启用」。

只依赖 numpy 与 Pillow，不联网、不引入新依赖。模板匹配是启发式的：同色不同表情
会靠结构网格区分，但缩放、旋转、半透明描边都可能影响结果，界面上仍可人工修改。
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import numpy as np
from PIL import Image

from app.core import config

SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
MATCH_THRESHOLD = 0.72   # 相似度低于它就不给情绪，留空由用户手选
SIZE = 64                # 归一化尺寸：抵消缩放差异


def _flatten(image: Image.Image) -> Image.Image:
    """把可能带透明通道的表情图铺到白底上，避免透明区被当成黑色。"""
    image = image.convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    return Image.alpha_composite(background, image).convert("RGB")


def _trim(image: Image.Image) -> Image.Image:
    """裁掉四周与本图背景同色的留白，抵消模板与截取气泡的取景差异。"""
    flat = _flatten(image)
    array = np.asarray(flat).astype(np.int16)
    border = np.concatenate([array[0, :, :], array[-1, :, :], array[:, 0, :], array[:, -1, :]])
    background = np.median(border, axis=0)
    mask = np.abs(array - background).max(axis=2) > 18
    if not mask.any():
        return flat
    rows, cols = np.where(mask)
    return flat.crop((int(cols.min()), int(rows.min()), int(cols.max()) + 1, int(rows.max()) + 1))


def _signature(image: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    flat = _trim(image).resize((SIZE, SIZE))
    hsv = np.asarray(flat.convert("HSV")).astype(np.int32)
    hist = np.zeros((16, 8), dtype=np.float32)
    h_bins = np.clip(hsv[:, :, 0] * 16 // 256, 0, 15).ravel()
    s_bins = np.clip(hsv[:, :, 1] * 8 // 256, 0, 7).ravel()
    np.add.at(hist, (h_bins, s_bins), 1.0)
    hist /= hist.sum() + 1e-6
    grid = np.asarray(flat.convert("L").resize((8, 8))).astype(np.float32) / 255.0
    return hist, grid


def _compare(left: tuple[np.ndarray, np.ndarray], right: tuple[np.ndarray, np.ndarray]) -> float:
    left_hist, left_grid = left
    right_hist, right_grid = right
    color = float(np.minimum(left_hist, right_hist).sum())
    structural = max(0.0, 1.0 - float(np.abs(left_grid - right_grid).mean()))
    return 0.6 * color + 0.4 * structural


def _emotion_of(filename: str) -> str:
    return os.path.splitext(filename)[0].strip()


@lru_cache(maxsize=8)
def _load(directory: str, stamp: float) -> list[tuple[str, Any]]:
    templates = []
    if not directory or not os.path.isdir(directory):
        return templates
    for name in sorted(os.listdir(directory)):
        if not name.lower().endswith(SUFFIXES):
            continue
        try:
            with Image.open(os.path.join(directory, name)) as handle:
                templates.append((_emotion_of(name), _signature(handle)))
        except Exception:
            continue
    return templates


def _cache_key() -> tuple[str, float]:
    directory = str(config.EMOJI_DIR)
    try:
        stamp = os.path.getmtime(directory)
    except OSError:
        stamp = 0.0
    return directory, stamp


def available() -> bool:
    """素材目录里是否存在可用模板。"""
    return bool(_load(*_cache_key()))


def classify(image: Image.Image) -> tuple[str | None, float]:
    """返回 (情绪, 相似度)。没有素材或都不够像时情绪为 None。"""
    templates = _load(*_cache_key())
    if not templates:
        return None, 0.0
    candidate = _signature(image)
    best_emotion, best_score = None, 0.0
    for emotion, signature in templates:
        score = _compare(candidate, signature)
        if score > best_score:
            best_emotion, best_score = emotion, score
    if best_emotion is None or best_score < MATCH_THRESHOLD:
        return None, round(best_score, 4)
    return best_emotion, round(best_score, 4)
