# -*- coding: utf-8 -*-
"""
小丑监测器 Web 版 - FastAPI 后端
"""

import os
import tempfile
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from analyzer import JokerAnalyzer, JOKER_TYPES, NOT_JOKER_DESC
from demo_data import DEMO_CASES

# ================== App 初始化 ==================
app = FastAPI(
    title="🃏 Joker Detector API",
    description="小丑监测器 - 聊天记录分析引擎",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局单例 analyzer
analyzer = JokerAnalyzer()

# 静态文件（前端）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
PROJECT_ROOT = os.path.join(BASE_DIR, "..", "..")
MUSIC_DIR = os.path.join(PROJECT_ROOT, "music")

# 挂载前端静态资源
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
# 挂载音乐文件
if os.path.exists(MUSIC_DIR):
    app.mount("/music", StaticFiles(directory=MUSIC_DIR), name="music")

# Pydantic 模型
class AIConfig(BaseModel):
    api_key: str = ""
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"


@app.get("/")
async def serve_frontend():
    """返回前端首页"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "前端文件未找到"}


# ================== API 路由 ==================

@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "ai_available": analyzer.ai_available,
        "ai_model": analyzer.ai_model if analyzer.ai_available else None,
        "music_available": os.path.exists(MUSIC_DIR),
        "version": "2.1.0"
    }


@app.get("/api/music")
async def list_music():
    """列出所有可用音乐文件"""
    if not os.path.exists(MUSIC_DIR):
        return {"music": [], "url_prefix": "/music/"}
    files = sorted([f for f in os.listdir(MUSIC_DIR) if f.endswith(('.mp3', '.MP3', '.wav', '.ogg'))])
    return {"music": files, "url_prefix": "/music/"}


@app.post("/api/config")
async def update_config(config: AIConfig):
    """更新 AI 配置"""
    ok = analyzer.update_ai_config(config.api_key, config.model, config.base_url)
    return {
        "success": ok,
        "ai_available": analyzer.ai_available,
        "model": analyzer.ai_model if analyzer.ai_available else None
    }


@app.get("/api/demos")
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
                "message_count": len(d["messages"])
            }
            for i, d in enumerate(DEMO_CASES)
        ]
    }


@app.post("/api/analyze/demo/{demo_id}")
async def analyze_demo(demo_id: int):
    """使用内置 Demo 数据进行分析"""
    if demo_id < 0 or demo_id >= len(DEMO_CASES):
        raise HTTPException(status_code=404, detail="Demo 案例不存在")

    demo = DEMO_CASES[demo_id]
    try:
        result = analyzer.analyze_demo(
            demo["messages"],
            demo["self_name"],
            demo["other_name"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return _format_response(result, demo["title"])


@app.post("/api/analyze/upload")
async def analyze_upload(
    file: UploadFile = File(...),
    self_index: int = Query(0, ge=0, le=1, description="0=第一个发言者, 1=第二个发言者")
):
    """上传 Excel 文件进行分析"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 格式")

    # 保存临时文件
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = analyzer.full_analysis(tmp_path, self_index)
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))

    os.unlink(tmp_path)
    return _format_response(result, file.filename)


@app.get("/api/joker_types")
async def joker_types():
    """获取所有小丑类型定义"""
    return {"types": JOKER_TYPES, "not_joker_desc": NOT_JOKER_DESC}


# ================== 响应格式化 ==================

def _format_response(result: dict, source_name: str) -> dict:
    """将内部分析结果转换为前端友好的 JSON"""
    stats = result['stats']
    z = stats['z_metrics']

    # 判定结果
    if result['is_joker'] and result['joker_type']:
        verdict = {
            "is_joker": True,
            "level": _get_level(stats['jokernum_alg']),
            "type": result['joker_type'],
            "type_info": JOKER_TYPES.get(result['joker_type'], {}),
            "score": stats['jokernum_alg'],
            "label": "🤡 确诊小丑"
        }
    else:
        verdict = {
            "is_joker": False,
            "level": "healthy",
            "type": None,
            "type_info": None,
            "score": stats['jokernum_alg'],
            "label": "👑 清醒玩家",
            "desc": NOT_JOKER_DESC
        }

    # 聊天数据摘要（不返回完整聊天内容，只给统计）
    return {
        "source": source_name,
        "verdict": verdict,
        "speakers": {
            "self": result['self_id'],
            "other": result['other_id']
        },
        "statistics": {
            "message_count": {
                "self": stats['self_msg_count'],
                "other": stats['other_msg_count']
            },
            "sticker_count": {
                "self": stats['self_sticker_count'],
                "other": stats['other_sticker_count']
            },
            "picture_count": {
                "self": stats['self_pic_count'],
                "other": stats['other_pic_count']
            },
            "total_chars": {
                "self": stats['self_total_chars'],
                "other": stats['other_total_chars']
            },
            "max_streak": {
                "self": stats['max_self_cont'],
                "other": stats['max_other_cont']
            },
            "avg_chars": {
                "self": round(stats['self_avg_chars'], 1),
                "other": round(stats['other_avg_chars'], 1)
            },
            "has_voice_or_call": stats['has_voice_or_call'],
            "ratios": {
                "message": _safe_ratio(stats['self_msg_count'], stats['other_msg_count']),
                "sticker": _safe_ratio(stats['self_sticker_count'], stats['other_sticker_count']),
                "picture": _safe_ratio(stats['self_pic_count'], stats['other_pic_count']),
                "chars": _safe_ratio(stats['self_total_chars'], stats['other_total_chars']),
                "streak": _safe_ratio(stats['max_self_cont'], stats['max_other_cont']),
            }
        },
        "z_metrics": {
            "SSDT": {"value": z['SSDT'], "label": "连续发送倾向", "desc": "你是否连续发消息不给对方插话机会"},
            "PFI": {"value": z['PFI'], "label": "自我中心指数", "desc": "你对话中'我'的使用密度对比"},
            "PLD": {"value": z['PLD'], "label": "低姿态语言密度", "desc": "道歉、语气词、犹豫词的使用频率"},
            "EPEG": {"value": z['EPEG'], "label": "情感表达差", "desc": "你与对方的情绪表达强度差异"},
            "CONV": {"value": z['CONV'], "label": "对话衔接度", "desc": "双方回应对方话题的投入程度"}
        },
        "guidance": result.get('guidance'),
        "keyword_matches": stats.get('self_keyword_matches', {}),
        "messages_for_display": [
            {"speaker": sp, "is_self": sp == result['self_id'], "content": msg}
            for sp, msg in result['data']
        ]
    }


def _get_level(score: float) -> str:
    if score > 75:
        return "confirmed"
    elif score >= 60:
        return "high_risk"
    elif score >= 45:
        return "suspicious"
    elif score >= 30:
        return "mild"
    else:
        return "healthy"


def _safe_ratio(a, b):
    if b == 0:
        return 99.0 if a > 0 else 0.0
    return round(a / b, 2)


# ================== 启动入口 ==================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
