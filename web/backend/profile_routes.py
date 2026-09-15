"""Experimental single-user API; mounted by the existing FastAPI app."""
import io
import os
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from profiles import ProfileStore, extract_ai, extract_local, prepare_messages, public_profile, ai_error_detail

router = APIRouter(prefix="/api/profiles", tags=["联系人档案（实验）"])


@lru_cache
def get_store():
    default = Path(__file__).resolve().parents[1] / "private_data"
    try:
        return ProfileStore(os.environ.get("JOKER_PROFILE_DIR", str(default)))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ContactInput(InputModel):
    name: str = Field(min_length=1, max_length=60)


class Message(InputModel):
    speaker: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=5000)


class AnalyzeInput(InputModel):
    messages: list[Message] = Field(min_length=2, max_length=1000)
    self_speaker: str = Field(min_length=1, max_length=100)
    other_speaker: str = Field(min_length=1, max_length=100)
    save_consent: bool = False
    use_ai: bool = False
    include_guidance: bool = False


class FactEdit(InputModel):
    revision: int = Field(ge=0)
    action: Literal["confirm", "correct", "delete"]
    text: str | None = Field(default=None, max_length=200)


class UnifiedInput(InputModel):
    """一次提交同时驱动情感分析与联系人档案两个模式。"""

    messages: list[Message] = Field(min_length=2, max_length=1000)
    self_speaker: str = Field(min_length=1, max_length=100)
    other_speaker: str = Field(min_length=1, max_length=100)
    contact_id: str | None = Field(default=None, max_length=64)
    save_consent: bool = False
    use_ai: bool = False
    include_guidance: bool = False


def call(operation, *args):
    try:
        return operation(*args)
    except KeyError:
        raise HTTPException(404, "联系人或档案条目不存在") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None


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


def run_unified(analyzer, format_response, messages, self_speaker, other_speaker, *,
                contact_id=None, save_consent=False, use_ai=False, include_guidance=False,
                source="本次聊天片段"):
    """两个模式融合的唯一入口：一次提交同时产出情感分析与档案更新。

    - 情感分析（本地统计 + 可选 AI 情感长文）始终执行，是本项目原本的核心结果。
    - 传入 contact_id 且勾选本机保存时，同一次调用顺带提取喜好并更新联系人档案。
    - 不传 contact_id 时就是纯粹的「只分析不建档」，不触碰档案库。
    """
    if contact_id and not save_consent:
        raise HTTPException(400, "请先确认在本机保存此联系人的脱敏档案依据")
    prepared = call(prepare_messages, [dict(m) for m in messages], self_speaker, other_speaker)
    if use_ai and not analyzer.client:
        raise HTTPException(400, "尚未配置 AI，请先配置服务或取消云端 AI 选项")
    if use_ai and sum(len(m["content"]) for m in prepared) > 40000:
        raise HTTPException(400, "云端单次最多 4 万字，请拆分或取消云端 AI")
    want_report = bool(use_ai and include_guidance)

    profile = None
    duplicate = False
    report_regenerated = False
    profile_updated = False
    warning = None
    mode = "ai" if use_ai else "local"

    if contact_id:
        store = get_store()
        existing = call(store.get, contact_id)
        fingerprint = store.digest(prepared)
        prior = next((b for b in existing["batches"] if b["fingerprint"] == fingerprint), None)
        retry_failed = bool(prior and prior["mode"] == "local_fallback" and use_ai)
        duplicate = prior is not None and not retry_failed
        if duplicate:
            # 片段已导入：档案不重复写入，但仍可重新生成一次情感长文。
            profile = public_profile(existing)
            report_regenerated = want_report
            if not want_report:
                warning = "此片段已导入，未重复保存或发送给 AI"
        else:
            candidates = extract_local(prepared)
            if use_ai:
                active_client, active_model = analyzer.client, analyzer.ai_model
                try:
                    candidates.extend(extract_ai(prepared, active_client, active_model))
                    mode = "ai"
                    if analyzer.client is active_client:
                        analyzer.ai_verified = True
                except Exception as exc:
                    if analyzer.client is active_client:
                        analyzer.ai_verified = False
                    warning = ai_error_detail(exc)["message"] + "。本次仅保存本地结果；修复后重新提交同一片段并勾选云端 AI 即可重试"
                    mode = "local_fallback"
            profile, _repeated = call(store.merge, contact_id, prepared, candidates, mode, warning, retry_failed)
            profile = public_profile(profile)
            profile_updated = True

    # 情感分析：本地统计始终执行；云端长文只在需要时额外调用一次。
    result = analyzer.analyze_demo(
        [{"speaker": "自己" if m["role"] == "self" else "对方", "content": m["content"]} for m in prepared],
        "自己", "对方", allow_ai=False,
    )
    if want_report:
        if mode == "local_fallback":
            # 云端提取已失败，不再追加第二次必然失败的调用。
            result["guidance_error"] = warning
        else:
            analyzer.add_ai_guidance(result)
            if duplicate:
                warning = result.get("guidance_error")

    if duplicate and not want_report:
        analysis = None
    else:
        analysis = format_response(result, source)

    return {
        "analysis": analysis,
        "profile": profile,
        "duplicate": duplicate,
        "report_regenerated": report_regenerated,
        "profile_updated": profile_updated,
        "warning": warning,
    }


def install_routes(app, analyzer, format_response):
    unified = APIRouter(prefix="/api/analyze", tags=["统一分析"])

    @unified.post("/unified")
    def unified_analyze(body: UnifiedInput):
        """融合入口：情感分析 + 联系人档案，一次提交一起返回。"""
        return run_unified(
            analyzer, format_response, [m.model_dump() for m in body.messages],
            body.self_speaker, body.other_speaker,
            contact_id=body.contact_id, save_consent=body.save_consent,
            use_ai=body.use_ai, include_guidance=body.include_guidance,
            source="本次聊天片段",
        )

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
            content = file.file.read(5 * 1024 * 1024 + 1)
            if len(content) > 5 * 1024 * 1024:
                raise HTTPException(413, "文件不能超过 5 MB")
            if suffix == ".xlsx":
                try:
                    with zipfile.ZipFile(io.BytesIO(content)) as archive:
                        if sum(e.file_size for e in archive.infolist()) > 25 * 1024 * 1024 or len(archive.infolist()) > 300:
                            raise HTTPException(413, "Excel 解压后过大，请分段导出")
                except zipfile.BadZipFile:
                    raise HTTPException(400, "不是有效的 Excel 文件") from None
            try:
                frame = pd.read_excel(io.BytesIO(content), header=None, engine="xlrd" if suffix == ".xls" else "openpyxl", nrows=1001)
                if len(frame) > 1000:
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
                if not 2 <= len(parsed) <= 1000:
                    raise HTTPException(400, "请导入 2–1000 条有效消息")
                speakers = list(dict.fromkeys(m["speaker"] for m in parsed))
                if len(speakers) != 2:
                    raise HTTPException(400, "必须是双人聊天；群聊或识别到多位发言者时请先整理")
                if sum(len(m["content"]) for m in parsed) > 120000:
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
        # 保留原路径与返回结构，内部与统一入口共用同一条流程。
        result = run_unified(
            analyzer, format_response, [m.model_dump() for m in body.messages],
            body.self_speaker, body.other_speaker,
            contact_id=contact_id, save_consent=body.save_consent,
            use_ai=body.use_ai, include_guidance=body.include_guidance,
        )
        return {"profile": result["profile"], "duplicate": result["duplicate"],
                "warning": result["warning"], "analysis": result["analysis"],
                "report_regenerated": result["report_regenerated"]}

    app.include_router(router)
    app.include_router(unified)
