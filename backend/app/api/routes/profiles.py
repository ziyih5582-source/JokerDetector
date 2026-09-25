# -*- coding: utf-8 -*-
"""联系人档案接口：名册增删、条目人工修正、Excel 解析与预览。

档案只存在本机（`data/private/`，脱敏后加密），不随聊天原文一起落盘。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.deps import analyzer, get_store
from app.core import config
from app.core.errors import call
from app.schemas import AnalyzeInput, ContactInput, FactEdit, Message
from app.services.profiles import prepare_messages, public_profile
from app.services.unified import run_unified

router = APIRouter(prefix="/api/profiles", tags=["联系人档案（实验）"])

MAX_XLSX_UNPACKED_BYTES = 25 * 1024 * 1024   # xlsx 解压后的上限，防 zip 炸弹
MAX_XLSX_ENTRIES = 300


@router.get("/contacts")
def contacts():
    return {"contacts": get_store().list()}


@router.post("/contacts", status_code=201)
def create_contact(body: ContactInput):
    return public_profile(call(get_store().create, body.name))


@router.get("/contacts/{contact_id}")
def contact(contact_id: str):
    return public_profile(call(get_store().get, contact_id))


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: str):
    call(get_store().delete, contact_id)
    return {"deleted": True}


@router.patch("/contacts/{contact_id}/facts/{fact_id}")
def edit_fact(contact_id: str, fact_id: str, body: FactEdit):
    return public_profile(call(get_store().edit_fact, contact_id, fact_id, body.revision, body.action, body.text))


@router.post("/preview")
def preview(body: AnalyzeInput):
    prepared = call(prepare_messages, [m.model_dump() for m in body.messages], body.self_speaker, body.other_speaker)
    return {"messages": prepared}


@router.post("/parse")
def parse(file: UploadFile = File(...)):
    try:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".xls", ".xlsx"}:
            raise HTTPException(400, "仅支持 .xls / .xlsx 文件")
        content = file.file.read(config.MAX_UPLOAD_BYTES + 1)
        if len(content) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "文件不能超过 5 MB")
        if suffix == ".xlsx":
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    if sum(e.file_size for e in archive.infolist()) > MAX_XLSX_UNPACKED_BYTES or len(archive.infolist()) > MAX_XLSX_ENTRIES:
                        raise HTTPException(413, "Excel 解压后过大，请分段导出")
            except zipfile.BadZipFile:
                raise HTTPException(400, "不是有效的 Excel 文件") from None
        try:
            frame = pd.read_excel(
                io.BytesIO(content),
                header=None,
                engine="xlrd" if suffix == ".xls" else "openpyxl",
                nrows=config.MAX_ROWS + 1,
            )
            if len(frame) > config.MAX_ROWS:
                raise HTTPException(400, "单次最多读取 1000 行，请分段导出")
            # Simple two-column template, optional header, plus original WeChat layouts.
            if len(frame.columns) == 2:
                rows = [[str(v).strip() if pd.notna(v) else "" for v in row] for row in frame.values]
                if rows and rows[0][0].lower() in {"speaker", "发言者", "发送人"} and rows[0][1].lower() in {"content", "内容", "消息"}:
                    rows = rows[1:]
                data = [(a, b) for a, b in rows if a and b]
            else:
                data = analyzer.parse_frame(frame)
            parsed = [Message(speaker=a, content=b).model_dump() for a, b in data]
            if not 2 <= len(parsed) <= config.MAX_ROWS:
                raise HTTPException(400, "请导入 2–1000 条有效消息")
            speakers = list(dict.fromkeys(m["speaker"] for m in parsed))
            if len(speakers) != 2:
                raise HTTPException(400, "必须是双人聊天；群聊或识别到多位发言者时请先整理")
            if sum(len(m["content"]) for m in parsed) > config.MAX_CHARS:
                raise HTTPException(400, "单次最多 12 万字，请分段导入")
            return {"speakers": speakers, "messages": parsed}
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(400, "无法解析文件，请使用“发言者、内容”两列，或检查原微信导出格式") from None
    finally:
        file.file.close()


@router.post("/contacts/{contact_id}/analyze")
def analyze(contact_id: str, body: AnalyzeInput):
    """保留旧路径与返回结构，内部与统一入口共用同一条流程。"""
    result = run_unified(
        analyzer,
        [m.model_dump() for m in body.messages],
        body.self_speaker,
        body.other_speaker,
        store_factory=get_store,
        contact_id=contact_id,
        save_consent=body.save_consent,
        use_ai=body.use_ai,
        include_guidance=body.include_guidance,
    )
    return {
        "profile": result["profile"],
        "duplicate": result["duplicate"],
        "warning": result["warning"],
        "analysis": result["analysis"],
        "report_regenerated": result["report_regenerated"],
    }
