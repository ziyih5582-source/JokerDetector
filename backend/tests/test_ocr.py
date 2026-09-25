# -*- coding: utf-8 -*-
"""长截图识别的版面重建测试：不依赖真实 OCR，用构造坐标与合成图片覆盖逻辑。"""

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.api import deps
from app.core import config
from app.main import app
from app.services import ocr


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    deps.get_store.cache_clear()
    with TestClient(app) as client:
        yield client
    deps.get_store.cache_clear()


def box(text, cx, cy, w=120.0, h=20.0):
    return {
        "text": text,
        "left": cx - w / 2, "right": cx + w / 2,
        "top": cy - h / 2, "bottom": cy + h / 2,
        "cx": float(cx), "cy": float(cy), "h": float(h), "score": 0.99,
    }


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_time_marker_and_noise_detection():
    assert ocr.is_time_marker("20:13")
    assert ocr.is_time_marker("昨天 20:13")
    assert ocr.is_time_marker("5月1日 下午3:00")
    assert not ocr.is_time_marker("我20:13到")
    assert ocr.is_noise("以下是新消息")
    assert ocr.is_noise("你撤回了一条消息")
    assert not ocr.is_noise("我们撤回了一条消息吗")


def test_classify_text_kind():
    assert ocr.classify_text_kind("3''") == "voice"
    assert ocr.classify_text_kind('12"') == "voice"
    assert ocr.classify_text_kind("你好") == "text"


def test_assemble_groups_lines_and_assigns_sides_and_times():
    boxes = [
        box("20:13", 300, 150, w=60),
        box("我喜欢", 120, 200, w=100),
        box("徒步", 110, 226, w=80),
        box("那一起去吧", 460, 300, w=140),
        box("以下是新消息", 300, 350, w=160),
    ]
    messages = ocr.assemble_messages(boxes, image_width=600)
    assert [m["speaker"] for m in messages] == ["对方", "我"]
    assert messages[0]["content"] == "我喜欢徒步"
    assert messages[1]["content"] == "那一起去吧"
    assert all(m["time"] == "20:13" for m in messages)
    assert messages[0]["time_guessed"] is False
    assert messages[1]["time_guessed"] is True


def test_assemble_voice_bubble_kind():
    boxes = [box("3''", 460, 200, w=40)]
    messages = ocr.assemble_messages(boxes, image_width=600)
    assert messages[0]["kind"] == "voice"
    assert messages[0]["speaker"] == "我"


def test_status_bar_title_and_input_bar_are_not_messages():
    boxes = [
        box("20:13", 300, 30, w=60),
        box("小林", 300, 90, w=80),
        box("你好", 120, 300, w=120),
        box("在", 460, 380, w=80),
        box("按住 说话", 300, 770, w=160),
    ]
    messages = ocr.assemble_messages(boxes, image_width=600, image_height=800)
    assert [m["content"] for m in messages] == ["你好", "在"]
    assert ocr.detect_title(boxes, 600) == "小林"


def test_nickname_below_narrow_band_is_not_a_message():
    boxes = [
        box("20:13", 450, 30, w=60),
        box("小林", 450, 180, w=80),
        box("你好", 120, 320, w=120),
    ]
    messages = ocr.assemble_messages(boxes, image_width=900, image_height=1200)
    assert ocr.detect_title(boxes, 900) == "小林"
    assert [m["content"] for m in messages] == ["你好"]


def test_bottom_bar_icon_is_not_treated_as_sticker():
    pytest.importorskip("cv2")
    image = Image.new("RGB", (600, 800), (237, 237, 237))
    draw = ImageDraw.Draw(image)
    draw.rectangle([250, 740, 310, 790], fill=(120, 120, 120))
    draw.rectangle([450, 300, 530, 380], fill=(255, 0, 0))
    found = ocr.detect_nontext_bubbles(image, [], 600, 800)
    assert [f["kind"] for f in found] == ["sticker"]


def message(speaker, content):
    return {"speaker": speaker, "content": content, "time": None, "time_guessed": False,
            "kind": "text", "emoji_emotion": None}


def test_merge_message_batches_removes_seam_overlap():
    first = [message("对方", "第一句"), message("我", "第二句")]
    second = [message("我", "第二句"), message("对方", "第三句")]
    merged, removed = ocr.merge_message_batches([first, second])
    assert [m["content"] for m in merged] == ["第一句", "第二句", "第三句"]
    assert removed == 1


def test_merge_message_batches_removes_adjacent_duplicates():
    batch = [message("我", "在吗"), message("我", "在吗"), message("对方", "在")]
    merged, removed = ocr.merge_message_batches([batch])
    assert [m["content"] for m in merged] == ["在吗", "在"]
    assert removed == 1


def test_merge_message_batches_keeps_non_seam_repeats():
    first = [message("我", "在吗"), message("对方", "嗯")]
    second = [message("我", "在吗"), message("对方", "在")]
    merged, removed = ocr.merge_message_batches([first, second])
    assert [m["content"] for m in merged] == ["在吗", "嗯", "在吗", "在"]
    assert removed == 0


def test_detect_nontext_bubbles_flags_image_without_text():
    pytest.importorskip("cv2")
    image = Image.new("RGB", (600, 800), (200, 200, 200))
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 100, 300, 200], fill=(255, 255, 255))
    draw.rectangle([410, 290, 470, 310], fill=(0, 0, 0))
    draw.rectangle([400, 300, 480, 380], fill=(255, 0, 0))
    boxes = [box("你好", 170, 150, w=120)]
    found = ocr.detect_nontext_bubbles(image, boxes, 600, 800)
    assert len(found) == 1
    assert found[0]["kind"] == "sticker"
    assert found[0]["content"] == "[表情]"
    assert found[0]["speaker"] == "我"
    assert found[0]["image"].startswith("data:image/png;base64,")


def test_detect_nontext_bubbles_finds_normal_sticker_on_tall_image():
    pytest.importorskip("cv2")
    image = Image.new("RGB", (900, 20000), (237, 237, 237))
    ImageDraw.Draw(image).rounded_rectangle([560, 12000, 700, 12140], radius=16, fill=(250, 210, 120))
    found = ocr.detect_nontext_bubbles(image, [], 900, 20000)
    assert found, "超长图里的正常大小表情不应因为「图太高」被判太小"
    assert found[0]["kind"] == "sticker"
    assert found[0]["image"].startswith("data:image/png;base64,")


def test_dedup_boxes_removes_overlap_duplicate():
    first = box("同一句", 120, 100)
    repeated = box("同一句", 121, 102)
    other = box("另一句", 120, 140)
    kept = ocr._dedup_boxes([first, repeated, other])
    assert [b["text"] for b in kept] == ["同一句", "另一句"]


def test_recognize_image_tiles_tall_image(monkeypatch):
    class FakeEngine:
        def __init__(self):
            self.calls = 0

        def __call__(self, _array):
            self.calls += 1
            points = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
            return ([[points, "t" + str(self.calls), 0.9]], None)

    engine = FakeEngine()
    monkeypatch.setattr(ocr, "_engine", lambda: engine)
    boxes = ocr.recognize_image(Image.new("RGB", (200, 5000), "white"))
    assert engine.calls == 3
    assert [b["text"] for b in boxes] == ["t1", "t2", "t3"]
    assert 1700 <= boxes[1]["cy"] <= 1850
    assert 3500 <= boxes[2]["cy"] <= 3620


def test_layout_components_scales_back_to_original():
    pytest.importorskip("cv2")
    image = Image.new("RGB", (400, 30000), (200, 200, 200))
    ImageDraw.Draw(image).rectangle([50, 20000, 300, 20200], fill=(255, 255, 255))
    components = ocr._layout_components(image)
    target = [c for c in components if c["left"] < 350 and c["top"] > 19000]
    assert target, components[:5]
    assert abs(target[0]["top"] - 20000) <= 40
    assert abs(target[0]["left"] - 50) <= 40


def test_crop_data_url_bounds_size():
    url = ocr._crop_data_url(Image.new("RGB", (2000, 1000), (10, 20, 30)), max_side=480)
    assert url.startswith("data:image/png;base64,")
    raw = base64.b64decode(url.split(",", 1)[1])
    with Image.open(io.BytesIO(raw)) as decoded:
        assert max(decoded.size) <= 480


def test_detect_nontext_bubbles_attaches_emoji_emotion(monkeypatch):
    pytest.importorskip("cv2")
    from app.services import emoji
    monkeypatch.setattr(emoji, "classify", lambda _image: ("开心", 0.9))
    image = Image.new("RGB", (600, 800), (200, 200, 200))
    ImageDraw.Draw(image).rectangle([400, 300, 480, 380], fill=(255, 0, 0))
    found = ocr.detect_nontext_bubbles(image, [], 600, 800)
    assert found and found[0]["emoji_emotion"] == "开心"


def test_avatar_not_treated_as_sticker_even_when_not_square():
    pytest.importorskip("cv2")
    image = Image.new("RGB", (600, 800), (237, 237, 237))
    draw = ImageDraw.Draw(image)
    draw.rectangle([20, 100, 90, 200], fill=(120, 150, 180))
    draw.rectangle([450, 300, 530, 380], fill=(255, 0, 0))
    found = ocr.detect_nontext_bubbles(image, [], 600, 800)
    assert [f["kind"] for f in found] == ["sticker"]
    assert found[0]["speaker"] == "我"


def test_detect_avatars_flags_similar_colors():
    pytest.importorskip("cv2")
    image = Image.new("RGB", (600, 800), (237, 237, 237))
    draw = ImageDraw.Draw(image)
    draw.rectangle([12, 100, 80, 168], fill=(90, 120, 180))
    draw.rectangle([520, 300, 588, 368], fill=(90, 120, 180))
    result = ocr.detect_avatars(image, [], 600, 800)
    assert result is not None
    assert result["couple_suspected"] is True
    assert result["similarity"] >= ocr.COUPLE_THRESHOLD
    assert result["self"]["image"].startswith("data:image/png;base64,")
    assert result["other"]["image"].startswith("data:image/png;base64,")


def test_detect_avatars_different_colors_not_suspected():
    pytest.importorskip("cv2")
    image = Image.new("RGB", (600, 800), (237, 237, 237))
    draw = ImageDraw.Draw(image)
    draw.rectangle([12, 100, 80, 168], fill=(200, 30, 30))
    draw.rectangle([520, 300, 588, 368], fill=(30, 30, 200))
    result = ocr.detect_avatars(image, [], 600, 800)
    assert result is not None
    assert result["couple_suspected"] is False


def test_detect_avatars_missing_one_side_returns_none():
    pytest.importorskip("cv2")
    image = Image.new("RGB", (600, 800), (237, 237, 237))
    ImageDraw.Draw(image).rectangle([12, 100, 80, 168], fill=(90, 120, 180))
    assert ocr.detect_avatars(image, [], 600, 800) is None


def test_parse_image_merges_multiple_in_order(client, monkeypatch):
    monkeypatch.setattr(ocr, "detect_nontext_bubbles", lambda *a, **k: [])
    calls = {"n": 0}

    def fake_recognize(_image):
        calls["n"] += 1
        if calls["n"] == 1:
            return [box("20:13", 300, 60, w=60),
                    box("第一句", 120, 200, w=140),
                    box("第二句", 460, 260, w=140)]
        return [box("第二句", 460, 260, w=140),
                box("第三句", 120, 320, w=140)]

    monkeypatch.setattr(ocr, "recognize_image", fake_recognize)
    files = [("files", ("a.png", png_bytes(Image.new("RGB", (600, 800), "white")), "image/png")),
             ("files", ("b.png", png_bytes(Image.new("RGB", (600, 800), "white")), "image/png"))]
    response = client.post("/api/profiles/parse-image", files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["image_count"] == 2
    assert [m["content"] for m in body["messages"]] == ["第一句", "第二句", "第三句"]
    assert "接缝" in body["warning"]


def test_parse_image_rejects_too_many(client):
    files = [("files", (f"{i}.png", b"x", "image/png")) for i in range(config.MAX_IMAGES + 1)]
    response = client.post("/api/profiles/parse-image", files=files)
    assert response.status_code == 400


def test_parse_image_rejects_bad_suffix(client):
    response = client.post("/api/profiles/parse-image",
                           files={"file": ("chat.gif", b"whatever", "image/gif")})
    assert response.status_code == 400


def test_parse_image_rejects_oversize(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGE_BYTES", 10)
    response = client.post("/api/profiles/parse-image",
                           files={"file": ("chat.png", b"x" * 11, "image/png")})
    assert response.status_code == 413


def test_parse_image_rejects_invalid_image(client):
    response = client.post("/api/profiles/parse-image",
                           files={"file": ("chat.png", b"not an image", "image/png")})
    assert response.status_code == 400


def test_parse_image_reports_missing_ocr(client, monkeypatch):
    def unavailable(_image):
        raise ocr.OCRUnavailable("未安装 OCR 依赖")

    monkeypatch.setattr(ocr, "recognize_image", unavailable)
    image = Image.new("RGB", (200, 200), "white")
    response = client.post("/api/profiles/parse-image",
                           files={"file": ("chat.png", png_bytes(image), "image/png")})
    assert response.status_code == 503


def test_parse_image_returns_reviewable_messages(client, monkeypatch):
    monkeypatch.setattr(ocr, "recognize_image", lambda _image: [
        box("小林", 300, 70, w=80),
        box("20:13", 300, 150, w=60),
        box("周末有空吗", 120, 220, w=140),
        box("应该有", 460, 280, w=100),
    ])
    monkeypatch.setattr(ocr, "detect_nontext_bubbles", lambda *a, **k: [])
    image = Image.new("RGB", (600, 800), "white")
    response = client.post("/api/profiles/parse-image",
                           files={"file": ("chat.png", png_bytes(image), "image/png")})
    assert response.status_code == 200
    body = response.json()
    assert body["speakers"] == ["我", "对方"]
    assert body["other_name"] == "小林"
    assert [m["speaker"] for m in body["messages"]] == ["对方", "我"]
    assert body["messages"][0]["content"] == "周末有空吗"
    assert body["messages"][0]["time"] == "20:13"
    assert body["image_count"] == 1
    assert "avatars" in body
    assert "warning" in body
