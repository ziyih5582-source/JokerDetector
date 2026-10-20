# -*- coding: utf-8 -*-
"""联系人档案接口：名册增删、条目人工修正、Excel 解析与预览。

档案只存在本机（默认 `data/private/`）。完整聊天不在此持久化；经同意的脱敏原话片段会加密留作核查依据。
"""

from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from app.api.deps import analyzer, get_store
from app.core import config
from app.core.errors import call
from app.schemas import AnalyzeInput, ContactInput, DescribeInput, FactEdit, Message
from app.services import ocr
from app.services import vision
from app.services.analyzer import build_ai_payload
from app.services.profiles import prepare_messages, public_profile
from app.services.unified import run_unified
from app.schemas.dossier import ContactDetails, DossierImport, ImportCommit, ManualFact
from app.services import dossier
from app.services.profiles import ai_error_detail
from app.schemas.communication import ArchiveRebuild, ArchiveDismiss
from app.schemas.communication import MemoryCommit, MemoryImport, MemoryNote, MemoryResolution
from app.services import communication
from app.services.communication_flow import import_memory, recognize

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


@router.post("/contacts/{contact_id}/memory/preview")
def preview_memory(contact_id: str, body: MemoryImport):
    if body.role_reliability!="confirmed":
        raise HTTPException(400,"请先核对自己和对方的归属，暂不提炼人物信息")
    if body.source_kind=="ai_summary":
        return {"token":None,"changes":[],"duplicate":False,"revision":call(get_store().get,contact_id)["revision"],
                "rejected_count":0,"notice":"AI摘要只能用于比较，不能作为新的本人原文依据"}
    if body.use_ai and not body.cloud_consent:
        raise HTTPException(400,"请确认将脱敏聊天与必要的非私人背景交给当前AI服务")
    messages,chat_date,scene=call(dossier.prepare_import,body.model_dump(mode="json"))
    if body.time_reliability!="confirmed":
        chat_date=None
    result=recognize(get_store(),contact_id,messages,revision=body.revision,chat_date=chat_date,scene=scene,
                     use_ai=body.use_ai,client=analyzer.client,model=analyzer.ai_model)
    result.pop("empty_metadata",None)
    return result


@router.post("/contacts/{contact_id}/memory/commit")
def commit_memory(contact_id: str, body: MemoryCommit):
    if not body.save_consent:
        raise HTTPException(400,"请先确认保存本次沟通信息")
    return public_profile(call(communication.commit,get_store(),contact_id,body.token))


@router.post("/contacts/{contact_id}/memory/import")
def update_memory(contact_id: str, body: MemoryImport):
    if not body.save_consent or (body.use_ai and not body.cloud_consent):
        raise HTTPException(400,"请确认保存；使用云端时还需确认发送脱敏资料")
    if body.role_reliability!="confirmed":
        raise HTTPException(400,"请先核对自己和对方的归属，暂不提炼人物信息")
    if body.source_kind=="ai_summary":
        return {"profile":public_profile(call(get_store().get,contact_id)),"changes":[],"duplicate":False,"profile_updated":False,
                "rejected_count":0,"notice":"AI摘要不作为新证据，档案保持原有内容"}
    messages,chat_date,scene=call(dossier.prepare_import,body.model_dump(mode="json"))
    if body.time_reliability!="confirmed":
        chat_date=None
    return import_memory(get_store(),contact_id,messages,revision=body.revision,chat_date=chat_date,scene=scene,
                         use_ai=body.use_ai,client=analyzer.client,model=analyzer.ai_model)


@router.post("/contacts/{contact_id}/memory/notes")
def memory_note(contact_id: str, body: MemoryNote):
    return public_profile(call(communication.save_note,get_store(),contact_id,body.revision,body.text,body.fact_id,body.use_in_ai))


@router.post("/contacts/{contact_id}/archive/rebuild")
def rebuild_archive(contact_id: str, body: ArchiveRebuild):
    if not body.cloud_consent or not body.save_consent:
        raise HTTPException(400, "请确认将已有脱敏依据交给当前云端AI，并保存整理结果")
    if not analyzer.client:
        raise HTTPException(400, "尚未配置云端AI")
    from app.services.archive_v8 import rebuild
    store = get_store()
    p = call(store.get, contact_id)
    call(dossier.check_revision, p, body.revision)
    p, notice = rebuild(store, p, analyzer.client, analyzer.ai_model)
    return {"profile": public_profile(p), "notice": notice or "已重新整理；历史摘录不等于完整聊天，后续上传可继续完善。"}


@router.post("/contacts/{contact_id}/archive/dismiss")
def dismiss_archive_trait(contact_id: str, body: ArchiveDismiss):
    from app.services.archive_v8 import dismiss_trait
    return public_profile(call(dismiss_trait, get_store(), contact_id, body.revision, body.trait_id))


@router.post("/contacts/{contact_id}/memory/{fact_id}/resolve")
def resolve_memory(contact_id: str, fact_id: str, body: MemoryResolution):
    return public_profile(call(communication.resolve, get_store(), contact_id, fact_id, body.revision, body.decision))


@router.patch("/contacts/{contact_id}")
def contact_details(contact_id: str, body: ContactDetails):
    return public_profile(call(dossier.update_contact, get_store(), contact_id, body.model_dump()))


@router.post("/contacts/{contact_id}/facts", status_code=201)
def add_manual_fact(contact_id: str, body: ManualFact):
    return public_profile(call(dossier.manual_fact, get_store(), contact_id, body.model_dump(mode="json")))


@router.put("/contacts/{contact_id}/facts/{fact_id}")
def correct_manual_fact(contact_id: str, fact_id: str, body: ManualFact):
    return public_profile(call(dossier.manual_fact, get_store(), contact_id, body.model_dump(mode="json"), fact_id))


@router.post("/contacts/{contact_id}/imports/redact")
def redact_import(contact_id: str, body: DossierImport):
    p = call(get_store().get, contact_id)
    call(dossier.check_revision, p, body.revision)
    messages, chat_date, scene = call(dossier.prepare_import, body.model_dump(mode="json"))
    return {"messages": messages, "chat_date": chat_date, "scene": scene}


@router.post("/contacts/{contact_id}/imports/preview")
def dossier_preview(contact_id: str, body: DossierImport):
    store = get_store()
    p = call(store.get, contact_id)
    call(dossier.check_revision, p, body.revision)
    messages, chat_date, scene = call(dossier.prepare_import, body.model_dump(mode="json"))
    metadata, duplicate, overlap = dossier.import_metadata(store, p, messages, chat_date, scene)
    if duplicate:
        return {"revision": p["revision"], "changes": [], "duplicate": True, "token": None, "overlap_count": len(messages)}
    dropped = 0
    if body.use_ai:
        if not body.cloud_consent:
            raise HTTPException(400, "请先确认将脱敏聊天和已有非人工摘要发送给云端 AI")
        if analyzer.client is None:
            raise HTTPException(400, "尚未配置 AI，请先在设置中配置服务端 API Key，或取消云端选项使用本地提炼")
        try:
            candidates, dropped = dossier.extract_cloud_dossier(messages, p, analyzer.client, analyzer.ai_model, chat_date, scene)
        except ValueError as exc:
            detail = ai_error_detail(exc)
            raise HTTPException(400, detail["message"]) from None
        except Exception as exc:
            detail = ai_error_detail(exc)
            raise HTTPException(502, detail["message"] + "；旧档案未改变，可以重试或改用本地提炼") from None
    else:
        candidates = dossier.extract_local_dossier(messages, chat_date, scene)
    changes = dossier.plan_changes(store, p, candidates, metadata, overlap)
    metadata["overlap_ids"] = sorted(overlap)
    preview = dossier.make_preview(store, p, metadata, changes, "ai" if body.use_ai else "local")
    preview["dropped_count"] = dropped
    preview["notice"] = "本地模式只支持少量明确表达，完整语义提炼请选择云端 AI。" if not body.use_ai else "AI 提炼仍可能误解，请检查来源与更新范围。"
    return preview


@router.post("/contacts/{contact_id}/imports/commit")
def dossier_commit(contact_id: str, body: ImportCommit):
    if not body.save_consent:
        raise HTTPException(400, "保存前请确认将勾选信息写入本机加密档案")
    p = call(dossier.commit_import, get_store(), contact_id, body.token, body.selected_ids)
    return public_profile(p)


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: str):
    call(get_store().delete, contact_id)
    return {"deleted": True}


@router.patch("/contacts/{contact_id}/facts/{fact_id}")
def edit_fact(contact_id: str, fact_id: str, body: FactEdit):
    return public_profile(call(get_store().edit_fact, contact_id, fact_id, body.revision, body.action, body.text))


@router.post("/preview")
def preview(body: AnalyzeInput):
    """脱敏预览：既返回消息列表，也返回将发给云端 AI 的 JSON 文本（所见即所发）。"""
    prepared = call(prepare_messages, [m.model_dump() for m in body.messages], body.self_speaker, body.other_speaker)
    records = [{
        "id": m["id"],
        "speaker": "自己" if m["role"] == "self" else "对方",
        "text": m["content"],
        "emotion": m.get("emotion"),
        "time": m.get("time"),
        "time_guessed": m.get("time_guessed"),
        "kind": m.get("kind"),
    } for m in prepared]
    return {"messages": prepared, "ai_payload": build_ai_payload(records)}


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


def _vision_content(kind: str, character: str, summary: str) -> str:
    """把视觉结果拼成消息内容：表情=主角+情绪，图片=内容概述。"""
    if kind == "image":
        return f"[图片：{summary}]" if summary else "[图片]"
    if character and character not in summary:
        text = f"{character}，{summary}".strip("，")
    else:
        text = summary or character
    return f"[表情：{text}]" if text else "[表情]"


def _describe_visual(messages: list[dict], budget: int, deadline: float) -> tuple[dict[int, dict], int, int, int]:
    """识别一批表情/图片：自己的 API 并行跑，交大网关串行并守限额。

    返回 (结果, 已处理数, 失败数, 未处理数)，结果按传入下标索引。
    """
    targets = messages[:budget]
    results: dict[int, dict] = {}
    failed = 0
    workers = vision.parallel_workers()
    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for index, message in enumerate(targets):
                if time.monotonic() >= deadline:
                    break
                futures[pool.submit(vision.interpret_data_url, message["image"],
                                    hint_kind=message["kind"])] = index
            for future, index in futures.items():
                try:
                    results[index] = future.result()
                except Exception:
                    failed += 1
    else:
        for index, message in enumerate(targets):
            if time.monotonic() >= deadline:
                break
            try:
                results[index] = vision.interpret_data_url(message["image"], hint_kind=message["kind"])
            except Exception:
                failed += 1
    processed = len(results) + failed
    skipped = len(messages) - processed
    return results, processed, failed, skipped


@router.post("/parse-image")
def parse_image(
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] = File(default=[]),
    describe: bool = Form(default=False),
):
    """从一张或多张微信长截图里识别聊天记录，返回带时间/类型元数据的消息列表。

    多张按传入顺序拼接，并自动去掉接缝处重复的消息。元数据仅供前端校对与展示，
    提交分析时只取 speaker 与 content，因此不影响任何评分逻辑。OCR 依赖可选，
    未安装时返回 503 而不是让站点崩溃。

    describe=True 且配置了 DEEPSEEK_VISION_MODEL 时，会用多模态模型给表情/图片
    各写一句内容描述（需要用户明确同意把裁块发给云端）；失败就保留原样。
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

    visual_messages = [m for m in messages if m.get("kind") in ("sticker", "image") and m.get("image")]
    described = 0
    vision_note = ""
    if describe and visual_messages:
        if not vision.available():
            vision_note = "未配置视觉识别（VISION_API_KEY / VISION_MODEL），表情/图片内容未识别。"
        else:
            deadline = time.monotonic() + 420
            results, processed, failed, skipped = _describe_visual(
                visual_messages, config.MAX_VISION_IMAGES, deadline)
            for index, result in results.items():
                message = visual_messages[index]
                kind = result["kind"]
                message["kind"] = kind
                message["content"] = _vision_content(kind, result["character"], result["summary"])
                described += 1
            if described or failed or skipped:
                vision_note = f"视觉识别：成功 {described} 个"
                if failed:
                    vision_note += f"，失败 {failed} 个"
                if skipped:
                    vision_note += f"，未处理 {skipped} 个（数量较多，可再导入一次）"
                vision_note += "（可在校对表中修改）。"
            else:
                vision_note = "视觉识别没有成功，表情/图片内容保持原样。"

    warning = "表情与图片为版面启发式识别，时间按最近可见的时间分隔推测，请在校对表中核对后再分析。"
    if vision_note:
        warning = vision_note + warning
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


@router.post("/describe")
def describe_images(body: DescribeInput):
    """重新识别一批表情/图片：给导入时没识别成功的条目补一遍（前端「重新识别」按钮用）。"""
    if not vision.available():
        raise HTTPException(400, "未配置视觉识别（VISION_API_KEY / VISION_MODEL），无法识别")
    items = [{"id": item.id, "image": item.image, "kind": item.kind or "sticker"} for item in body.items]
    deadline = time.monotonic() + 420
    found, _processed, _failed, skipped = _describe_visual(items, config.MAX_VISION_IMAGES, deadline)
    attempted = len(items) - skipped
    results = []
    for index, item in enumerate(items):
        if index >= attempted:
            results.append({"id": item["id"], "error": "本次没处理完，请稍后再点一次"})
            continue
        result = found.get(index)
        if result:
            results.append({"id": item["id"], "kind": result["kind"],
                            "content": _vision_content(result["kind"], result["character"], result["summary"])})
        else:
            results.append({"id": item["id"], "error": "识别失败，请稍后再试"})
    return {"results": results}


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
        profile_engine=body.profile_engine,
        chat_date=body.chat_date.isoformat() if body.chat_date else None,
        scene=body.scene,
    )
    return {
        "profile": result["profile"],
        "duplicate": result["duplicate"],
        "warning": result["warning"],
        "analysis": result["analysis"],
        "report_regenerated": result["report_regenerated"],
    }
