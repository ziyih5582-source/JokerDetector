# -*- coding: utf-8 -*-
"""视觉识别服务测试：用假客户端确认请求与解析，不发真实调用。"""

from types import SimpleNamespace
import time

import pytest

from app.core import config
from app.services import vision


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch):
    """测试里不要真的等待每分钟 10 次的节流，也不要用到别人的缓存。"""
    monkeypatch.setattr(vision, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr(vision, "_last_call", 0.0)
    monkeypatch.setattr(vision, "_CACHE", [])
    monkeypatch.setattr(vision, "_client", None)
    monkeypatch.setattr(vision, "_client_signature", None)


def fake_client(reply):
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])

    client = SimpleNamespace(with_options=lambda **kwargs: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    return client, captured


def test_interpret_sticker_returns_character_and_summary():
    client, captured = fake_client('{"kind":"sticker","character":"小猫","summary":"吐舌卖萌，很得意"}')
    result = vision.interpret_data_url("data:image/png;base64,AAAA", client, "qwen", "sticker")
    assert result == {"kind": "sticker", "character": "小猫", "summary": "吐舌卖萌，很得意"}
    assert captured["model"] == "qwen"
    content = captured["messages"][0]["content"]
    assert content[1]["image_url"]["url"] == "data:image/png;base64,AAAA"
    assert "表情包" in content[0]["text"] and "主角" in content[0]["text"]


def test_interpret_image_uses_model_kind():
    client, _captured = fake_client('{"kind":"image","character":"","summary":"蓝天下的草地和红顶小屋"}')
    result = vision.interpret_data_url("data:image/png;base64,AAAA", client, "qwen", "sticker")
    assert result["kind"] == "image"
    assert result["summary"] == "蓝天下的草地和红顶小屋"


def test_interpret_accepts_fenced_json():
    client, _captured = fake_client('```json\n{"kind":"sticker","character":"柴犬","summary":"doge 式惊讶"}\n```')
    result = vision.interpret_data_url("data:image/png;base64,AAAA", client, "qwen", "sticker")
    assert result["kind"] == "sticker"
    assert result["character"] == "柴犬"


def test_interpret_falls_back_to_plain_text():
    client, _captured = fake_client("一只小猫在吐舌")
    result = vision.interpret_data_url("data:image/png;base64,AAAA", client, "qwen", "image")
    assert result == {"kind": "image", "character": "", "summary": "一只小猫在吐舌"}


def test_interpret_caches_identical_images():
    """同一张裁块第二次直接命中缓存，不再发请求。"""
    import base64
    import io

    from PIL import Image
    image = Image.new("RGB", (80, 80), (200, 40, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    client, _captured = fake_client('{"kind":"sticker","character":"红方块","summary":"纯红色块"}')

    class Boom:
        def with_options(self, **kwargs):
            raise AssertionError("缓存命中时不应再请求")

    first = vision.interpret_data_url(url, client, "qwen", "sticker")
    second = vision.interpret_data_url(url, Boom(), "qwen", "sticker")
    assert first == second == {"kind": "sticker", "character": "红方块", "summary": "纯红色块"}


def test_interpret_requires_configuration(monkeypatch):
    monkeypatch.setattr(config, "vision_api_key", lambda: "")
    monkeypatch.setattr(config, "vision_model", lambda: "")
    monkeypatch.setattr(vision, "_client", None)
    with pytest.raises(vision.VisionUnavailable):
        vision.interpret_data_url("data:image/png;base64,AAAA")
    with pytest.raises(vision.VisionUnavailable):
        vision.interpret_data_url("", object(), "qwen")


def test_available_reads_config(monkeypatch):
    monkeypatch.setattr(config, "vision_model", lambda: "qwen3.8-27b")
    monkeypatch.setattr(config, "vision_api_key", lambda: "sk-test")
    monkeypatch.setattr(vision, "_client", None)
    monkeypatch.setattr(vision, "_client_signature", None)
    assert vision.available() is True
    monkeypatch.setattr(config, "vision_model", lambda: "")
    assert vision.available() is False


def test_personal_api_skips_throttle_and_runs_parallel(monkeypatch):
    """用自己 API 时：不节流、并行跑。"""
    monkeypatch.setenv("VISION_API_KEY", "sk-personal")
    monkeypatch.setattr(vision, "MIN_INTERVAL", 5.0)
    monkeypatch.setattr(vision, "_last_call", time.monotonic())
    start = time.monotonic()
    vision._throttle()
    assert time.monotonic() - start < 0.2
    assert vision.parallel_workers() > 1


def test_gateway_keeps_throttle_and_serial(monkeypatch):
    """沿用交大网关时：保持每分钟 10 次的节流、串行。"""
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    monkeypatch.delenv("VISION_BASE_URL", raising=False)
    monkeypatch.setattr(vision, "MIN_INTERVAL", 0.4)
    monkeypatch.setattr(vision, "_last_call", time.monotonic())
    start = time.monotonic()
    vision._throttle()
    assert time.monotonic() - start >= 0.3
    assert vision.parallel_workers() == 1
