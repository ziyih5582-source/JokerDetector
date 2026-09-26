# -*- coding: utf-8 -*-
"""统一分析入口：内置 Demo、Excel 上传，以及「分析与建档一次提交」的融合流程。"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.deps import analyzer, get_store
from app.core import config
from app.schemas import JokerDetectInput, UnifiedInput
from app.services.demo_data import DEMO_CASES
from app.services.report import build_report
from app.services.unified import run_unified

router = APIRouter(prefix="/api/analyze", tags=["统一分析"])


@router.post("/joker/detect")
def joker_detect(body: JokerDetectInput):
    """小丑鉴定所：本地「六征」判定，不调用云端 AI。

    防误伤规则：单向性命中 + 其余五项至少命中一项 + 综合分 ≥ 45 才判定为小丑。
    """
    if body.self_speaker == body.other_speaker:
        raise HTTPException(400, "「我」和「对方」不能是同一个人")
    if sum(len(m.content) for m in body.messages) > config.MAX_CHARS:
        raise HTTPException(400, "单次聊天内容不能超过 12 万字，请分段导入")
    data = [(m.speaker, m.content) for m in body.messages]
    speakers = {sp for sp, _ in data}
    if speakers != {body.self_speaker, body.other_speaker}:
        raise HTTPException(400, "只支持明确的双人聊天，请选择文件中实际的两位发言者")
    return analyzer.detect_joker_profile(data, body.self_speaker, body.other_speaker)


@router.post("/unified")
def unified_analyze(body: UnifiedInput):
    """融合入口：情感分析 + 联系人档案，一次提交一起返回。"""
    return run_unified(
        analyzer,
        [m.model_dump() for m in body.messages],
        body.self_speaker,
        body.other_speaker,
        store_factory=get_store,
        contact_id=body.contact_id,
        save_consent=body.save_consent,
        use_ai=body.use_ai,
        include_guidance=body.include_guidance,
        source="本次聊天片段",
    )


@router.post("/demo/{demo_id}")
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
        analyzer,
        demo["messages"],
        demo["self_name"],
        demo["other_name"],
        store_factory=get_store,
        contact_id=contact_id,
        save_consent=save_consent,
        use_ai=cloud_consent,
        include_guidance=bool(include_guidance or cloud_consent),
        source=demo["title"],
    )


@router.post("/upload")
async def analyze_upload(
    file: UploadFile = File(...),
    self_index: int = Query(0, ge=0, le=1, description="0=发言最多者, 1=另一位发言者"),
    cloud_consent: bool = Query(False),
):
    """上传 Excel 文件进行分析"""
    if not (file.filename or "").lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 格式")

    content = await file.read(config.MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail="文件不能超过 5 MB")

    # 保存临时文件
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if cloud_consent and not analyzer.ai_available:
            raise HTTPException(400, detail="请先到「设置」确认云端 AI 已就绪，再勾选云端分析")
        result = await run_in_threadpool(analyzer.full_analysis, tmp_path, self_index, allow_ai=cloud_consent)
    except HTTPException:
        os.unlink(tmp_path)
        raise
    except Exception:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail="解析失败，请检查文件，或使用联系人档案页面核对发言者")

    os.unlink(tmp_path)
    return build_report(result, file.filename)
