# -*- coding: utf-8 -*-
"""系统与元信息接口。

健康检查、统一 AI 配置（只暴露「是否已配置」，绝不回传密钥）、音乐清单、
Demo 清单、解说数据源与类型定义。
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from app.api.deps import analyzer
from app.core import config
from app.schemas import AIConfigInfo
from app.services.analyzer import (
    JOKER_TYPES,
    METRIC_WEIGHTS,
    NOT_JOKER_DESC,
    SCORE_MIDPOINT,
    SCORE_STEEPNESS,
    VOICE_PENALTY,
)
from app.services.demo_data import DEMO_CASES
from app.services import ocr
from app.services.profiles import ai_error_detail, extract_ai
from app.services.report import LEVEL_THRESHOLDS, METRIC_DOCS

router = APIRouter(prefix="/api", tags=["系统"])


@router.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "ai_available": analyzer.ai_available,
        "ai_verified": getattr(analyzer, "ai_verified", False),
        "ai_model": analyzer.ai_model if analyzer.ai_available else None,
        "ai_provider": str(analyzer.client.base_url) if analyzer.ai_available else None,
        "music_available": os.path.exists(config.MUSIC_DIR),
        "ocr_available": ocr.available(),
        "version": config.APP_VERSION,
    }


@router.get("/music")
async def list_music():
    """列出所有可用音乐文件"""
    if not os.path.exists(config.MUSIC_DIR):
        return {"music": [], "url_prefix": "/music/"}
    files = sorted(
        f for f in os.listdir(config.MUSIC_DIR) if f.endswith((".mp3", ".MP3", ".wav", ".ogg"))
    )
    return {"music": files, "url_prefix": "/music/"}


@router.get("/config")
async def get_config():
    """查看当前统一的 AI 配置。只暴露「是否已配置」与模型名，绝不回传密钥。"""
    return AIConfigInfo(
        configured=analyzer.ai_available,
        model=analyzer.ai_model if analyzer.ai_available else None,
        base_url=str(analyzer.client.base_url) if analyzer.ai_available else None,
    )


@router.post("/config/reload")
async def reload_config():
    """在 .env 被改动后重新加载统一配置。"""
    ok = analyzer.reload_ai_config()
    return {
        "success": ok,
        "ai_available": analyzer.ai_available,
        "model": analyzer.ai_model if ok else None,
    }


@router.post("/config/test")
def test_ai_config():
    """Make a real extraction request using only this fixed fictional sample."""
    active_client, active_model = analyzer.client, analyzer.ai_model
    if active_client is None:
        raise HTTPException(
            400,
            "统一配置尚未生效：请在项目根目录的 .env 中填写 DEEPSEEK_API_KEY，再点“重新加载配置”",
        )
    try:
        extract_ai(
            [
                {"id": 0, "role": "self", "content": "你喜欢什么？"},
                {"id": 1, "role": "other", "content": "我喜欢徒步"},
            ],
            active_client,
            active_model,
        )
        if analyzer.client is active_client:
            analyzer.ai_verified = True
        return {
            "success": True,
            "model": active_model,
            "message": "测试成功：模型已返回有效的档案 JSON 结果",
        }
    except Exception as exc:
        if analyzer.client is active_client:
            analyzer.ai_verified = False
        return {"success": False, "model": active_model, "error": ai_error_detail(exc)}


@router.get("/demos")
async def list_demos():
    """列出所有内置 Demo 案例"""
    return {
        "demos": [
            {
                "id": i,
                "title": d["title"],
                "description": d["description"],
                "self_name": d["self_name"],
                "other_name": d["other_name"],
                "message_count": len(d["messages"]),
            }
            for i, d in enumerate(DEMO_CASES)
        ]
    }


@router.get("/guide")
async def guide():
    """解说文档的数据源：阈值、权重、指标含义、类型、上限都在这里，避免文档与代码脱节。"""
    return {
        "score_scale": {
            "formula": "score = 100 / (1 + e^(-%.1f × (Z − %.2f)))" % (SCORE_STEEPNESS, SCORE_MIDPOINT),
            "z_total": " + ".join("%.2f·%s" % (METRIC_WEIGHTS[k], k) for k in METRIC_WEIGHTS),
            "note": "每个维度先被换算成 −1～1 的相对值（这一项你比对方重多少），加权求和后过 logistic 曲线，再乘上语音/通话折扣 %.2f。中点 %.2f 意味着「五维整体略微偏向你」就正好是 50 分；曲线偏陡，所以整体稍微偏向一侧，分数就会明显离开中段。" % (VOICE_PENALTY, SCORE_MIDPOINT),
            "voice_penalty": VOICE_PENALTY,
        },
        "levels": [{"min": minimum, "key": key} for minimum, key in LEVEL_THRESHOLDS],
        "metrics": [
            {
                "key": key,
                "label": METRIC_DOCS[key]["label"],
                "desc": METRIC_DOCS[key]["desc"],
                "how": METRIC_DOCS[key]["how"],
                "weight": METRIC_WEIGHTS[key],
            }
            for key in METRIC_DOCS
        ],
        "type_rule": "谈心分析按五维里数值最高的那一项定类型：连续发送→幻恋型，衔接度→镜像型，低姿态→弄臣型，其余→殉道型；小丑鉴定所则按「六征」里得分最高的一项定类型（另有守候型、单向型）。",
        "types": JOKER_TYPES,
        "not_joker_desc": NOT_JOKER_DESC,
        "limits": {
            "upload_mb": config.MAX_UPLOAD_MB,
            "image_mb": config.MAX_IMAGE_MB,
            "images": config.MAX_IMAGES,
            "max_rows": config.MAX_ROWS,
            "max_chars": config.MAX_CHARS,
            "cloud_chars": config.MAX_CLOUD_CHARS,
            "facts_per_contact": config.FACTS_PER_CONTACT,
            "batches_per_contact": config.BATCHES_PER_CONTACT,
            "evidence_per_fact": config.EVIDENCE_PER_FACT,
            "chat_turns": config.CHAT_TURNS,
            "chat_chars": config.CHAT_CHARS,
        },
    }


@router.get("/joker_types")
async def joker_types():
    """获取所有小丑类型定义"""
    return {"types": JOKER_TYPES, "not_joker_desc": NOT_JOKER_DESC}
