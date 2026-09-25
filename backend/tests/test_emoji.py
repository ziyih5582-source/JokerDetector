# -*- coding: utf-8 -*-
"""表情情绪模板匹配测试：用合成模板与合成表情，不依赖任何外部素材。"""

from PIL import Image, ImageDraw

from app.core import config
from app.services import emoji


def red_circle():
    image = Image.new("RGB", (64, 64), (255, 255, 255))
    ImageDraw.Draw(image).ellipse([8, 8, 56, 56], fill=(220, 30, 30))
    return image


def blue_square():
    image = Image.new("RGB", (64, 64), (255, 255, 255))
    ImageDraw.Draw(image).rectangle([10, 10, 54, 54], fill=(30, 60, 220))
    return image


def green_triangle():
    image = Image.new("RGB", (64, 64), (255, 255, 255))
    ImageDraw.Draw(image).polygon([(32, 8), (56, 56), (8, 56)], fill=(40, 200, 60))
    return image


def use_directory(monkeypatch, directory, with_templates=True):
    if with_templates:
        red_circle().save(directory / "开心.png")
        blue_square().save(directory / "伤心.png")
    monkeypatch.setattr(config, "EMOJI_DIR", directory)
    emoji._load.cache_clear()


def test_without_templates_returns_none(monkeypatch, tmp_path):
    use_directory(monkeypatch, tmp_path, with_templates=False)
    emotion, score = emoji.classify(red_circle())
    assert emotion is None
    assert score == 0.0
    assert emoji.available() is False


def test_matches_matching_template(monkeypatch, tmp_path):
    use_directory(monkeypatch, tmp_path)
    assert emoji.available() is True
    emotion, score = emoji.classify(red_circle())
    assert emotion == "开心"
    assert score >= emoji.MATCH_THRESHOLD


def test_matches_other_template(monkeypatch, tmp_path):
    use_directory(monkeypatch, tmp_path)
    assert emoji.classify(blue_square())[0] == "伤心"


def test_unknown_sticker_returns_none(monkeypatch, tmp_path):
    use_directory(monkeypatch, tmp_path)
    assert emoji.classify(green_triangle())[0] is None
