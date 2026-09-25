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
from PIL import Image

from app.api.deps import analyzer, get_store
from app.core import config
from app.core.errors import call
from app.schemas import AnalyzeInput, ContactInput, FactEdit, Message
from app.services import ocr
from app.services.profiles import prepare_messages, public_profile
from app.services.unified import run_unified

router = APIRouter(prefix="/api/profiles", tags=["联系人档案（实验）"])

MAX_XLSX_UNPACKED_BYTES = 25 * 1024 * 1024   # xlsx 解压后的上限，防 zip 炸弹
MAX_XLSX_ENTRIES = 300
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


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


def _load_screenshot(upload: UploadFile, index: int) -> Image.Image:
    """校验并读入一张长截图；错误信息带上是第几张。"""
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise HTTPException(400, f"第 {index} 张不是支持的图片格式（仅 .png / .jpg / .jpeg / .webp）")
    content = upload.file.read(config.MAX_IMAGE_BYTES + 1)
    if len(content) > config.MAX_IMAGE_BYTES:
        raise HTTPException(413, f"第 {index} 张超过 {config.MAX_IMAGE_MB} MB，请压缩或分几次导入")
    try:
        image = Image.open(io.BytesIO(content))
    except Exception:
        raise HTTPException(400, f"第 {index} 张不是有效的图片文件") from None
    if image.width * image.height > config.MAX_IMAGE_PIXELS:
        raise HTTPException(413, f"第 {index} 张像素过大，请缩小尺寸后重试")
    try:
        image.load()
    except Exception:
        raise HTTPException(400, f"第 {index} 张图片已损坏，请换一张") from None
    return image


@router.post("/parse-image")
def parse_image(
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] = File(default=[]),
):
    """从一张或多张微信长截图里识别聊天记录，返回带时间/类型元数据的消息列表。

    多张按传入顺序拼接，并自动去掉接缝处重复的消息。元数据仅供前端校对与展示，
    提交分析时只取 speaker 与 content，因此不影响任何评分逻辑。OCR 依赖可选，
    未安装时返回 503 而不是让站点崩溃。
    """
    uploads = ([file] if file is not None else []) + list(files)
    if not uploads:
        raise HTTPException(400, "请至少上传一张长截图")
    if len(uploads) > config.MAX_IMAGES:
        raise HTTPException(400, f"一次最多 {config.MAX_IMAGES} 张截图，请分几次导入")

    batches = []
    avatars = None
    other_name = None
    for index, upload in enumerate(uploads, start=1):
        try:
            image = _load_screenshot(upload, index)
            try:
                boxes = ocr.recognize_image(image)
            except ocr.OCRUnavailable as exc:
                raise HTTPException(503, str(exc)) from None
            messages = ocr.build_messages(image, boxes)
            if not messages:
                raise HTTPException(400, f"第 {index} 张没有识别到聊天文字，请换一张更清晰的截图")
            if avatars is None:
                try:
                    avatars = ocr.detect_avatars(image, boxes, image.width, image.height)
                except Exception:
                    avatars = None
            if other_name is None:
                try:
                    other_name = ocr.detect_title(boxes, image.width)
                except Exception:
                    other_name = None
        finally:
            upload.file.close()
        batches.append(messages)

    messages, removed = ocr.merge_message_batches(batches)
    if not messages:
        raise HTTPException(400, "没有识别到有效的聊天文字，请更换截图")
    if len(messages) > config.MAX_ROWS:
        raise HTTPException(400, "单次最多识别 1000 条消息，请分几次导入")
    if sum(len(m["content"]) for m in messages) > config.MAX_CHARS:
        raise HTTPException(400, "识别出的文字过多，请分几次导入")

    warning = "表情与图片为版面启发式识别，时间按最近可见的时间分隔推测，请在校对表中核对后再分析。"
    if len(uploads) > 1:
        seam = f"，并去掉了 {removed} 条接缝重复" if removed else ""
        warning = f"已按选择顺序合并 {len(uploads)} 张截图{seam}。" + warning
    return {
        "speakers": [ocr.SELF_SPEAKER, ocr.OTHER_SPEAKER],
        "other_name": other_name,
        "messages": messages,
        "avatars": avatars,
        "image_count": len(uploads),
        "warning": warning,
    }


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
