# -*- coding: utf-8 -*-
"""
小丑监测器 Web 版 - FastAPI 后端
"""

import os
import tempfile
from urllib.parse import urlsplit
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
import uvicorn

from analyzer import (JokerAnalyzer, JOKER_TYPES, NOT_JOKER_DESC, METRIC_WEIGHTS,
                       SCORE_MIDPOINT, SCORE_STEEPNESS, VOICE_PENALTY)
from demo_data import DEMO_CASES
from fisherman import install_routes as install_fisherman
from profile_routes import install_routes, run_unified, get_store
from profiles import extract_ai, ai_error_detail

# ================== App 初始化 ==================
app = FastAPI(
    title="🃏 Joker Detector API",
    description="小丑监测器 - 聊天记录分析引擎",
    version="2.2.0-experimental"
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])


@app.middleware("http")
async def local_privacy(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
            return JSONResponse({"detail": "不接受跨站修改请求"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "不接受跨站修改请求"}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path in {"/", "/profiles", "/index.html"}:
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response

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
    """统一工作台：情感分析与联系人档案已融合为同一条流程。"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "前端文件未找到"}


@app.get("/profiles")
def serve_profiles():
    """旧入口保留：直接指向融合后的同一页面。"""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ================== API 路由 ==================

@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "ai_available": analyzer.ai_available,
        "ai_verified": getattr(analyzer, "ai_verified", False),
        "ai_model": analyzer.ai_model if analyzer.ai_available else None,
        "ai_provider": str(analyzer.client.base_url) if analyzer.ai_available else None,
        "music_available": os.path.exists(MUSIC_DIR),
        "version": "2.2.0-experimental"
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
    config.model = config.model.strip()
    config.base_url = config.base_url.strip()
    if not config.model:
        raise HTTPException(400, "请输入完整模型 ID")
    if urlsplit(config.base_url).scheme != "https":
        raise HTTPException(400, "AI 服务地址必须使用 HTTPS")
    ok = analyzer.update_ai_config(config.api_key, config.model, config.base_url)
    return {
        "success": ok,
        "ai_available": analyzer.ai_available,
        "model": analyzer.ai_model if analyzer.ai_available else None
    }


@app.post("/api/config/test")
def test_ai_config():
    """Make a real extraction request using only this fixed fictional sample."""
    active_client, active_model = analyzer.client, analyzer.ai_model
    if active_client is None:
        raise HTTPException(400, "请先保存 API Key、模型 ID 和 API 地址")
    try:
        extract_ai([{"id": 0, "role": "self", "content": "你喜欢什么？"},
                    {"id": 1, "role": "other", "content": "我喜欢徒步"}], active_client, active_model)
        if analyzer.client is active_client:
            analyzer.ai_verified = True
        return {"success": True, "model": active_model, "message": "测试成功：模型已返回有效的档案 JSON 结果"}
    except Exception as exc:
        if analyzer.client is active_client:
            analyzer.ai_verified = False
        return {"success": False, "model": active_model, "error": ai_error_detail(exc)}


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
def analyze_demo(
    demo_id: int,
    cloud_consent: bool = Query(False),
    contact_id: Optional[str] = Query(None, description="同时更新该联系人档案；不传则只分析"),
    save_consent: bool = Query(False),
    include_guidance: bool = Query(False),
):
    """使用内置 Demo 数据走统一流程，返回结构与 /api/analyze/unified 一致。

    cloud_consent 在本接口里同时表示「生成 AI 情感长文」，与旧版行为一致。
    """
    if demo_id < 0 or demo_id >= len(DEMO_CASES):
        raise HTTPException(status_code=404, detail="Demo 案例不存在")

    demo = DEMO_CASES[demo_id]
    return run_unified(
        analyzer, _format_response, demo["messages"], demo["self_name"], demo["other_name"],
        contact_id=contact_id, save_consent=save_consent,
        use_ai=cloud_consent, include_guidance=bool(include_guidance or cloud_consent),
        source=demo["title"],
    )


@app.post("/api/analyze/upload")
async def analyze_upload(
    file: UploadFile = File(...),
    self_index: int = Query(0, ge=0, le=1, description="0=发言最多者, 1=另一位发言者"),
    cloud_consent: bool = Query(False)
):
    """上传 Excel 文件进行分析"""
    if not (file.filename or '').lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 格式")

    content = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, detail="文件不能超过 5 MB")
    # 保存临时文件
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from starlette.concurrency import run_in_threadpool
        if cloud_consent and not analyzer.ai_available:
            raise HTTPException(400, detail="请先在首页保存 AI 配置并测试调用")
        result = await run_in_threadpool(analyzer.full_analysis, tmp_path, self_index, allow_ai=cloud_consent)
    except HTTPException:
        os.unlink(tmp_path)
        raise
    except Exception:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail="解析失败，请检查文件，或使用联系人档案页面核对发言者")

    os.unlink(tmp_path)
    return _format_response(result, file.filename)


@app.get("/api/guide")
async def guide():
    """解说文档的数据源：阈值、权重、指标含义、类型、上限都在这里，避免文档与代码脱节。"""
    from profile_routes import get_store  # 仅用于提示档案目录，不读取内容
    return {
        "score_scale": {
            "formula": "score = 100 / (1 + e^(-%.1f × (Z − %.2f)))" % (SCORE_STEEPNESS, SCORE_MIDPOINT),
            "z_total": " + ".join("%.2f·%s" % (METRIC_WEIGHTS[k], k) for k in METRIC_WEIGHTS),
            "note": "每个维度先被换算成 −1～1 的相对值（这一项你比对方重多少），加权求和后过 logistic 曲线，再乘上语音/通话折扣 %.2f。中点 %.2f 意味着「五维整体略微偏向你」就正好是 50 分；曲线偏陡，所以整体稍微偏向一侧，分数就会明显离开中段。" % (VOICE_PENALTY, SCORE_MIDPOINT),
            "voice_penalty": VOICE_PENALTY,
        },
        "levels": [{"min": minimum, "key": key} for minimum, key in LEVEL_THRESHOLDS],
        "metrics": [
            {"key": key, "label": METRIC_DOCS[key]["label"], "desc": METRIC_DOCS[key]["desc"],
             "how": METRIC_DOCS[key]["how"], "weight": METRIC_WEIGHTS[key]}
            for key in METRIC_DOCS
        ],
        "type_rule": "取五维里数值最高的那一项：连续发送→幻恋型，衔接度→镜像型，低姿态→弄臣型，其余→殉道型。",
        "types": JOKER_TYPES,
        "not_joker_desc": NOT_JOKER_DESC,
        "limits": {
            "upload_mb": 5,
            "max_rows": 1000,
            "max_chars": 120000,
            "cloud_chars": 40000,
            "facts_per_contact": 500,
            "batches_per_contact": 200,
            "evidence_per_fact": 10,
            "chat_turns": 40,
            "chat_chars": 24000,
        },
    }


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
            key: {"value": z[key], "label": METRIC_DOCS[key]["label"], "desc": METRIC_DOCS[key]["desc"],
                  "weight": METRIC_WEIGHTS[key]}
            for key in METRIC_DOCS
        },
        "guidance": result.get('guidance'),
        "guidance_error": result.get('guidance_error'),
        "keyword_matches": stats.get('self_keyword_matches', {})
    }


# 判定阈值：/api/guide 的解说页读的就是这张表，改这里等于同时改文档
LEVEL_THRESHOLDS = [
    (75, "confirmed"),
    (60, "high_risk"),
    (45, "suspicious"),
    (30, "mild"),
    (0, "healthy"),
]

# 五个维度的说明：结果页与解说页共用
METRIC_DOCS = {
    "SSDT": {
        "label": "连续发送倾向",
        "desc": "你是否连续发消息不给对方插话机会",
        "how": "统计一方连续发言的最长段数，取你与对方的相对差",
    },
    "PFI": {
        "label": "自我中心指数",
        "desc": "你对话中「我」的使用密度对比",
        "how": "比较「我 / 俺」与「我们 / 咱们」的出现比例，再看双方的相对差",
    },
    "PLD": {
        "label": "低姿态语言密度",
        "desc": "道歉、语气词、犹豫词的使用频率",
        "how": "统计「可能 / 有点 / 对不起 / 好吗 / ？」这类词在总字数里的占比",
    },
    "EPEG": {
        "label": "情感表达差",
        "desc": "你与对方的情绪表达强度差异",
        "how": "统计情绪词与感叹号数量，取双方对数差（相差约 2 倍即达到满值）",
    },
    "CONV": {
        "label": "对话衔接度",
        "desc": "双方回应对方话题的投入程度",
        "how": "看接话时是否复用对方上一句里的连接词，比较两个方向的接话率",
    },
}


def _get_level(score: float) -> str:
    for minimum, key in LEVEL_THRESHOLDS:
        if score >= minimum:
            return key
    return "healthy"


def _safe_ratio(a, b):
    if b == 0:
        return 99.0 if a > 0 else 0.0
    return round(a / b, 2)


install_routes(app, analyzer, _format_response)
install_fisherman(app, analyzer, get_store)

# ================== 启动入口 ==================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
