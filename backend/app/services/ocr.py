# -*- coding: utf-8 -*-
"""微信长截图识别：本地 OCR + 版面重建。

只把图片转成与 Excel 解析同构的消息列表 `[{speaker, content}]`（并附带
时间、类型等仅供展示的元数据），不参与评分。OCR 与图像处理依赖都是可选的：
未安装时抛出 `OCRUnavailable`，由接口层翻译成 503，不影响站点的其余功能。

设计上刻意把「纯函数」与「重型依赖」分开：本模块顶层只依赖 numpy 与 Pillow，
RapidOCR 与 OpenCV 都在真正调用时才导入，因此没有装 OCR 依赖的环境也能
import 本模块并测试版面重建逻辑。
"""

from __future__ import annotations

import base64
import io
import re
from typing import Any

import numpy as np
from PIL import Image

from app.services import emoji

SELF_SPEAKER = "我"
OTHER_SPEAKER = "对方"

# 版面重建参数：均为经验值，调参只需改这里
GROUP_GAP_RATIO = 0.6        # 同侧相邻文本行间距超过「行高 × 该值」即视作新气泡
GROUP_ALIGN_RATIO = 2.0      # 同侧气泡边缘错位超过「行高 × 该值」即视作新气泡
BUBBLE_DIFF = 18             # 与页面背景色的通道差超过它才算气泡像素
MIN_BUBBLE_W_RATIO = 0.04
MIN_BUBBLE_H_RATIO = 0.008
AVATAR_EDGE_RATIO = 0.1      # 贴在最左/最右这么宽内、且尺寸像头像的组件视为头像
AVATAR_MIN_RATIO = 0.025     # 头像方块最小边宽占比
AVATAR_MAX_RATIO = 0.18      # 头像方块最大边宽占比
AVATAR_SQUARE_TOL = 0.35     # 长宽差超过「较长边 × 该值」就不算头像
COUPLE_THRESHOLD = 0.72      # 两个头像的相似度超过它才提示「疑似情侣头像」
STICKER_MAX_RATIO = 0.22     # 非文字气泡最大边小于该占比判为表情，否则判为图片
TOP_MARGIN_RATIO = 0.02
BOTTOM_MARGIN_RATIO = 0.02

# 手机界面区域（按图宽做 DPI 代理，不用图高，否则超长图会失准）：
# 顶部是状态栏 + 聊天标题栏（时间/WiFi/电量/昵称/返回箭头），底部是输入栏（输入框/语音/表情/更多）
# 真机顶部（状态栏+标题栏）约占 0.22×图宽，取小了会让昵称漏检、被当成第一条消息
HEADER_BAND_RATIO = 0.22
FOOTER_BAND_RATIO = 0.16
HEADER_PAD_RATIO = 0.015     # 标题下沿再留一点空隙
UI_TITLES = {"微信", "通讯录", "发现", "我", "聊天信息", "朋友圈", "通讯录管理"}

# 超长截图：纵向分块识别，块间留重叠，避免整图被过度缩放
TILE_HEIGHT = 2000
TILE_OVERLAP = 240
# 版面检测（连通域）先降采样到这么多像素以内，控制内存与耗时；坐标会换算回原图
MAX_LAYOUT_PIXELS = 8_000_000
THUMB_MAX_SIDE = 480         # 表情/图片随消息返回的缩略图最长边


class OCRUnavailable(RuntimeError):
    """OCR 依赖缺失或引擎无法初始化。"""


_TIME_ONLY = r"\d{1,2}:\d{2}(?::\d{2})?"
_TIME_MARKER_PATTERNS = [
    re.compile(r"^" + _TIME_ONLY + r"$"),
    re.compile(r"^(?:昨天|前天|今天|凌晨|早上|上午|中午|下午|晚上|傍晚)\s*" + _TIME_ONLY + r"$"),
    re.compile(r"^(?:周[一二三四五六日天]|星期[一二三四五六日天])\s*" + _TIME_ONLY + r"$"),
    re.compile(r"^\d{1,2}月\d{1,2}日(?:\s*(?:凌晨|早上|上午|中午|下午|晚上|傍晚))?(?:\s*" + _TIME_ONLY + r")?$"),
    re.compile(r"^\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?(?:\s*(?:凌晨|早上|上午|中午|下午|晚上|傍晚))?(?:\s*" + _TIME_ONLY + r")?$"),
]

_NOISE_PATTERNS = [
    re.compile(r"^以下是新消息$"),
    re.compile(r"^以上是打招呼的内容$"),
    re.compile(r"^.{0,24}撤回了一条消息$"),
    re.compile(r"^.{0,24}拍了拍.{0,24}$"),
    re.compile(r"^你已添加了.{0,24}$"),
    re.compile(r"^对方正在输入"),
    re.compile(r"^按住\s*说话$"),
    re.compile(r"^微信$"),
]

_VOICE_PATTERN = re.compile(r"^\d{1,3}\s*['\"\u2019\u2032]{1,2}\s*$")


def is_time_marker(text: str) -> bool:
    text = (text or "").strip()
    return any(p.match(text) for p in _TIME_MARKER_PATTERNS)


def is_noise(text: str) -> bool:
    text = (text or "").strip()
    return any(p.match(text) for p in _NOISE_PATTERNS)


def classify_text_kind(text: str) -> str:
    """从文本本身能判断的消息类型。图片/表情靠图像版面另判。"""
    text = (text or "").strip()
    if _VOICE_PATTERN.match(text):
        return "voice"
    return "text"


def _title_box(boxes: list[dict], image_width: int) -> dict | None:
    """聊天标题栏里的对方昵称（严格居中、位于顶部区域、不是时间/噪音/页面名）。

    取最靠上的一条：昵称在状态栏下方、第一条消息上方；消息通常不严格居中，
    所以把居中容差收紧到 0.12×图宽，避免把靠中间的气泡误当标题。
    """
    band = HEADER_BAND_RATIO * image_width
    candidates = []
    for box in boxes:
        text = (box["text"] or "").strip()
        if not text or len(text) > 30 or box["cy"] > band:
            continue
        if abs(box["cx"] - image_width / 2.0) > 0.12 * image_width:
            continue
        if (box["right"] - box["left"]) > 0.7 * image_width:
            continue
        if is_time_marker(text) or is_noise(text) or text in UI_TITLES:
            continue
        candidates.append(box)
    if not candidates:
        return None
    return min(candidates, key=lambda b: (b["cy"], -(b["right"] - b["left"])))


def detect_title(boxes: list[dict], image_width: int) -> str | None:
    """返回识别到的对方昵称；没有就返回 None。"""
    box = _title_box(boxes, image_width)
    return box["text"].strip() if box else None


def _header_cut(boxes: list[dict], image_width: int) -> float:
    """消息内容的顶部界线：有标题就取标题下沿，否则取固定顶栏高度。"""
    box = _title_box(boxes, image_width)
    if box is not None:
        return box["bottom"] + HEADER_PAD_RATIO * image_width
    return HEADER_BAND_RATIO * image_width


def _footer_cut(image_width: int, image_height: int) -> float:
    return image_height - FOOTER_BAND_RATIO * image_width


def _is_text_chrome(box: dict, boxes: list[dict], image_width: int, image_height: int) -> bool:
    return box["cy"] <= _header_cut(boxes, image_width) or box["cy"] >= _footer_cut(image_width, image_height)


def _is_component_chrome(component: dict, boxes: list[dict], image_width: int, image_height: int) -> bool:
    center_y = (component["top"] + component["bottom"]) / 2.0
    return center_y <= _header_cut(boxes, image_width) or center_y >= _footer_cut(image_width, image_height)


_ENGINE: Any = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception as exc:  # pragma: no cover - 取决于可选依赖
            raise OCRUnavailable(
                "未安装 OCR 依赖，请在项目根目录运行 "
                ".venv/Scripts/python -m pip install -r backend/requirements-ocr.txt"
            ) from exc
        try:
            _ENGINE = RapidOCR()
        except Exception as exc:  # pragma: no cover - 取决于运行环境
            raise OCRUnavailable(f"OCR 引擎初始化失败：{exc}") from exc
    return _ENGINE


def _normalize(result) -> list[dict]:
    boxes = []
    for item in result or []:
        points, text, score = item[0], str(item[1]), float(item[2])
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        boxes.append({
            "text": text.strip(),
            "left": min(xs),
            "right": max(xs),
            "top": min(ys),
            "bottom": max(ys),
            "cx": (min(xs) + max(xs)) / 2.0,
            "cy": (min(ys) + max(ys)) / 2.0,
            "h": max(ys) - min(ys),
            "score": score,
        })
    return [b for b in boxes if b["text"]]


def _dedup_boxes(boxes: list[dict], tolerance: float = 40.0) -> list[dict]:
    """合并分块结果时，去掉重叠带里被识别两次的同一行文字。"""
    kept: list[dict] = []
    for current in sorted(boxes, key=lambda b: (b["cy"], b["left"])):
        duplicate = False
        for other in kept[-40:]:
            if (
                other["text"] == current["text"]
                and abs(other["cy"] - current["cy"]) <= tolerance
                and abs(other["left"] - current["left"]) <= tolerance
            ):
                duplicate = True
                break
        if not duplicate:
            kept.append(current)
    return kept


def recognize_image(image: Image.Image) -> list[dict]:
    """对单张图片跑 OCR，返回带坐标的文本框。

    图片过高时按纵向切块、块间留重叠，再合并各块结果并去重：否则整图会被
    检测模型压到极扁，文字全部糊掉（实测 4 万像素高时几乎认不出东西）。
    """
    engine = _engine()
    rgb = image if image.mode == "RGB" else image.convert("RGB")
    width, height = rgb.size
    if height <= TILE_HEIGHT:
        result, _elapsed = engine(np.asarray(rgb))
        return _normalize(result)

    boxes: list[dict] = []
    step = TILE_HEIGHT - TILE_OVERLAP
    top = 0
    while top < height:
        bottom = min(top + TILE_HEIGHT, height)
        tile = rgb.crop((0, top, width, bottom))
        result, _elapsed = engine(np.asarray(tile))
        for box in _normalize(result):
            box["top"] += top
            box["bottom"] += top
            box["cy"] += top
            boxes.append(box)
        if bottom >= height:
            break
        top += step
    return _dedup_boxes(boxes)


def _median_height(boxes: list[dict]) -> float:
    heights = sorted(b["h"] for b in boxes if b["h"] > 0)
    if not heights:
        return 10.0
    return heights[len(heights) // 2]


def _group_text_boxes(boxes: list[dict], image_width: int) -> list[dict]:
    gap_limit = max(_median_height(boxes) * GROUP_GAP_RATIO, 4.0)
    align_tol = max(_median_height(boxes) * GROUP_ALIGN_RATIO, 8.0)
    ordered = sorted(boxes, key=lambda b: (b["cy"], b["cx"]))

    groups: list[dict] = []
    current: dict | None = None
    for box in ordered:
        left_margin = box["left"]
        right_margin = float(image_width) - box["right"]
        side = OTHER_SPEAKER if left_margin <= right_margin else SELF_SPEAKER
        anchor = box["left"]
        if current is None or side != current["side"]:
            current = None
        else:
            gap = box["top"] - current["bottom"]
            drifted = abs(anchor - current["anchor"]) > align_tol
            if gap > gap_limit or drifted:
                current = None
        if current is None:
            current = {
                "side": side,
                "lines": [box["text"]],
                "top": box["top"],
                "bottom": box["bottom"],
                "anchor": anchor,
            }
            groups.append(current)
        else:
            current["lines"].append(box["text"])
            current["bottom"] = max(current["bottom"], box["bottom"])
    return groups


def _propagate_times(messages: list[dict], markers: list[dict]) -> None:
    """把最近可见的时间分隔向前传播；紧邻分隔的第一条视为该时刻（非推测）。"""
    ordered_markers = sorted(markers, key=lambda m: m["cy"])
    for marker in ordered_markers:
        marker["_used"] = False
    index = 0
    active: dict | None = None
    for message in sorted(messages, key=lambda m: m["_y"]):
        while index < len(ordered_markers) and ordered_markers[index]["cy"] <= message["_y"]:
            active = ordered_markers[index]
            index += 1
        if active is not None:
            message["time"] = active["text"]
            message["time_guessed"] = active["_used"]
            active["_used"] = True
        elif ordered_markers:
            message["time"] = ordered_markers[0]["text"]
            message["time_guessed"] = True
        else:
            message["time"] = None
            message["time_guessed"] = False


def _text_messages(boxes: list[dict], image_width: int, image_height: int | None = None) -> list[dict]:
    content = [
        b for b in boxes
        if not is_time_marker(b["text"]) and not is_noise(b["text"])
        and (image_height is None or not _is_text_chrome(b, boxes, image_width, image_height))
    ]
    messages = []
    for group in _group_text_boxes(content, image_width):
        text = "".join(group["lines"]).strip()
        if not text:
            continue
        messages.append({
            "speaker": group["side"],
            "content": text,
            "time": None,
            "time_guessed": False,
            "kind": classify_text_kind(text),
            "emoji_emotion": None,
            "_y": group["top"],
        })
    return messages


def assemble_messages(boxes: list[dict], image_width: int, image_height: int | None = None) -> list[dict]:
    """把 OCR 文本框重建成带时间与类型标记的消息列表（不含图像类型检测）。"""
    markers = [
        b for b in boxes
        if is_time_marker(b["text"])
        and (image_height is None or not _is_text_chrome(b, boxes, image_width, image_height))
    ]
    messages = _text_messages(boxes, image_width, image_height)
    _propagate_times(messages, markers)
    return _strip(messages)


def _strip(messages: list[dict]) -> list[dict]:
    return [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages]


def _overlaps_text(bubble: dict, boxes: list[dict]) -> bool:
    """气泡与任一 OCR 文本框有重叠即视为文字气泡（文字像素可能被拆成多个组件）。"""
    for box in boxes:
        if box["right"] < bubble["left"] or box["left"] > bubble["right"]:
            continue
        if box["bottom"] < bubble["top"] or box["top"] > bubble["bottom"]:
            continue
        return True
    return False


def _layout_components(image: Image.Image) -> list[dict]:
    """把「与页面背景不同」的像素做连通域，返回候选矩形（原图坐标）。缺少 OpenCV 时返回空列表。

    超大图先按比例降采样再算连通域，算完把坐标换算回原图，控制内存与耗时。
    """
    try:
        import cv2
    except Exception:  # pragma: no cover - 取决于可选依赖
        return []

    width, height = image.size
    scale = 1.0
    if width * height > MAX_LAYOUT_PIXELS:
        scale = (MAX_LAYOUT_PIXELS / float(width * height)) ** 0.5
    small = image if image.mode == "RGB" else image.convert("RGB")
    if scale < 1.0:
        small = small.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.BILINEAR)

    array = np.asarray(small)
    border = np.concatenate([array[0, :, :], array[-1, :, :], array[:, 0, :], array[:, -1, :]])
    background = np.median(border, axis=0)
    diff = np.abs(array.astype(np.int16) - background.astype(np.int16)).max(axis=2)
    mask = (diff > BUBBLE_DIFF).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    inverse = 1.0 / scale
    components = []
    for i in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[i])
        components.append({
            "left": int(round(x * inverse)), "right": int(round((x + w) * inverse)),
            "top": int(round(y * inverse)), "bottom": int(round((y + h) * inverse)),
            "w": max(1, int(round(w * inverse))), "h": max(1, int(round(h * inverse))),
            "area": int(round(area * inverse * inverse)),
        })
    return components


def _is_avatar_component(component: dict, image_width: int) -> bool:
    """判断一个连通域是不是头像：贴着某一侧外缘、且最大边在头像尺寸范围内。

    不再要求「近似方形」——真实头像可能是异形、或带角标导致长宽不等，
    以前正是这个方形条件让头像漏过排除、被当成表情。
    """
    outer = min(component["left"], image_width - component["right"])
    side = max(component["w"], component["h"])
    return outer <= AVATAR_EDGE_RATIO * image_width and side <= AVATAR_MAX_RATIO * image_width


def detect_nontext_bubbles(image: Image.Image, boxes: list[dict], image_width: int, image_height: int) -> list[dict]:
    """用连通域找没有文字的气泡，判为表情或图片。

    尺寸下限按「图宽」而不是「图高」算：长截图的图高可以非常大，若按比例算，
    正常大小的表情会被误判为太小而漏掉。
    """
    min_w = MIN_BUBBLE_W_RATIO * image_width
    min_h = MIN_BUBBLE_H_RATIO * image_width
    min_area = min_w * min_h
    found = []
    for component in _layout_components(image):
        x, y, w, h, area = (component["left"], component["top"], component["w"], component["h"], component["area"])
        if area < min_area or w < min_w or h < min_h:
            continue
        if y <= TOP_MARGIN_RATIO * image_height or y + h >= (1 - BOTTOM_MARGIN_RATIO) * image_height:
            continue
        if w >= 0.98 * image_width and h >= 0.98 * image_height:
            continue
        if _is_component_chrome(component, boxes, image_width, image_height):
            continue
        side = SELF_SPEAKER if (x + w / 2) >= image_width / 2 else OTHER_SPEAKER
        if _is_avatar_component(component, image_width):
            continue
        bubble = {"left": x, "right": x + w, "top": y, "bottom": y + h, "side": side}
        if _overlaps_text(bubble, boxes):
            continue
        crop = image.crop((x, y, x + w, y + h))
        if max(w, h) <= STICKER_MAX_RATIO * image_width:
            kind, content = "sticker", "[表情]"
            try:
                emotion, _score = emoji.classify(crop)
            except Exception:  # pragma: no cover - 模板匹配失败不应影响主流程
                emotion = None
        else:
            kind, content, emotion = "image", "[图片]", None
        found.append({
            "speaker": side,
            "content": content,
            "time": None,
            "time_guessed": False,
            "kind": kind,
            "emoji_emotion": emotion,
            "image": _crop_data_url(crop),
            "_y": float(y),
        })
    return found


def _looks_like_avatar(component: dict, image_width: int) -> bool:
    side_length = max(component["w"], component["h"])
    if side_length <= 0:
        return False
    if not (AVATAR_MIN_RATIO * image_width <= component["w"] <= AVATAR_MAX_RATIO * image_width):
        return False
    if not (AVATAR_MIN_RATIO * image_width <= component["h"] <= AVATAR_MAX_RATIO * image_width):
        return False
    if abs(component["w"] - component["h"]) > AVATAR_SQUARE_TOL * side_length:
        return False
    return _is_avatar_component(component, image_width)


def _avatar_similarity(left: Image.Image, right: Image.Image) -> float:
    """颜色直方图相关度 + 感知哈希，合成 0～1 的相似度。缺少 OpenCV 时返回 0。"""
    try:
        import cv2
    except Exception:  # pragma: no cover - 取决于可选依赖
        return 0.0

    left_rgb, right_rgb = np.asarray(left), np.asarray(right)
    left_hsv = cv2.cvtColor(left_rgb, cv2.COLOR_RGB2HSV)
    right_hsv = cv2.cvtColor(right_rgb, cv2.COLOR_RGB2HSV)
    left_hist = cv2.calcHist([left_hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    right_hist = cv2.calcHist([right_hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    cv2.normalize(left_hist, left_hist)
    cv2.normalize(right_hist, right_hist)
    correlation = float(cv2.compareHist(left_hist, right_hist, cv2.HISTCMP_CORREL))
    color = (correlation + 1.0) / 2.0

    left_gray = cv2.resize(cv2.cvtColor(left_rgb, cv2.COLOR_RGB2GRAY), (9, 8)).astype(int)
    right_gray = cv2.resize(cv2.cvtColor(right_rgb, cv2.COLOR_RGB2GRAY), (9, 8)).astype(int)
    left_hash = (left_gray[:, 1:] > left_gray[:, :-1]).flatten()
    right_hash = (right_gray[:, 1:] > right_gray[:, :-1]).flatten()
    hamming = float(np.count_nonzero(left_hash != right_hash)) / left_hash.size
    return round(0.65 * color + 0.35 * (1.0 - hamming), 4)


def _avatar_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.resize((64, 64)).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _crop_data_url(image: Image.Image, max_side: int = THUMB_MAX_SIDE) -> str:
    """把表情/图片气泡裁块转成 data URL，供前端校对时查看。"""
    image = image if image.mode == "RGB" else image.convert("RGB")
    if max(image.size) > max_side:
        ratio = max_side / float(max(image.size))
        image = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))), Image.BILINEAR)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def detect_avatars(image: Image.Image, boxes: list[dict], image_width: int, image_height: int) -> dict | None:
    """定位左右两侧头像并给出「疑似情侣头像」的启发式判断（需要 OpenCV）。"""
    left = right = None
    for component in _layout_components(image):
        if not _looks_like_avatar(component, image_width):
            continue
        if _is_component_chrome(component, boxes, image_width, image_height):
            continue
        if _overlaps_text(component, boxes):
            continue
        if component["left"] <= AVATAR_EDGE_RATIO * image_width:
            if left is None or component["top"] < left["top"]:
                left = component
        elif component["right"] >= (1 - AVATAR_EDGE_RATIO) * image_width:
            if right is None or component["top"] < right["top"]:
                right = component
    if left is None or right is None:
        return None

    left_image = image.crop((left["left"], left["top"], left["right"], left["bottom"])).convert("RGB")
    right_image = image.crop((right["left"], right["top"], right["right"], right["bottom"])).convert("RGB")
    similarity = _avatar_similarity(left_image, right_image)
    suspected = similarity >= COUPLE_THRESHOLD
    return {
        "self": {"side": SELF_SPEAKER, "image": _avatar_data_url(right_image)},
        "other": {"side": OTHER_SPEAKER, "image": _avatar_data_url(left_image)},
        "similarity": similarity,
        "couple_suspected": suspected,
        "note": (
            "两侧头像配色/结构相近，疑似情侣头像。" if suspected
            else "两侧头像没有明显相似，未判为情侣头像。"
        ) + "这只是基于图片相似度的猜测，请在下方自行确认；该信息不参与评分。",
    }


def build_messages(image: Image.Image, boxes: list[dict]) -> list[dict]:
    """完整流程：文字消息 + 无文字气泡，合并后统一传播时间。"""
    width, height = image.size
    markers = [
        b for b in boxes
        if is_time_marker(b["text"]) and not _is_text_chrome(b, boxes, width, height)
    ]
    text_messages = _text_messages(boxes, width, height)
    try:
        extra = detect_nontext_bubbles(image, boxes, width, height)
    except Exception:  # pragma: no cover - 版面检测失败不应拖垮主流程
        extra = []
    merged = text_messages + extra
    _propagate_times(merged, markers)
    return _strip(sorted(merged, key=lambda m: m["_y"]))


def _same_message(left: dict, right: dict) -> bool:
    return (
        left.get("speaker") == right.get("speaker")
        and str(left.get("content", "")).strip() == str(right.get("content", "")).strip()
    )


def _overlap_length(existing: list[dict], incoming: list[dict], window: int = 50) -> int:
    """已合并结尾与下一张开头的最长重合长度（按「发言者 + 内容」精确匹配）。"""
    if not existing or not incoming:
        return 0
    for size in range(min(len(existing), len(incoming), window), 0, -1):
        if all(_same_message(existing[-size + i], incoming[i]) for i in range(size)):
            return size
    return 0


def merge_message_batches(batches: list[list[dict]]) -> tuple[list[dict], int]:
    """按顺序拼接多张截图的消息，并去掉接缝处与图内相邻的重复。返回 (消息, 去掉条数)。

    只把「上一张结尾」与「下一张开头」的重叠认定为接缝重复，不会误删对话里本来
    就重复出现的一句。
    """
    merged: list[dict] = []
    removed = 0
    for batch in batches:
        deduped: list[dict] = []
        for message in batch:
            if deduped and _same_message(deduped[-1], message):
                removed += 1
                continue
            deduped.append(message)
        overlap = _overlap_length(merged, deduped)
        removed += overlap
        merged.extend(deduped[overlap:])
    return merged, removed
