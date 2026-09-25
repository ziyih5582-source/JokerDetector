# -*- coding: utf-8 -*-
"""融合流程：一次提交同时产出情感分析与联系人档案更新。

这是两个模式合流后唯一的实现，`/api/analyze/unified`、
`/api/analyze/demo/{id}` 与保留的 `/api/profiles/contacts/{id}/analyze`
都走这里，不存在第二份判定逻辑。
"""

from __future__ import annotations

from fastapi import HTTPException

from app.core import config
from app.core.errors import call
from app.services.profiles import (
    ai_error_detail,
    extract_ai,
    extract_local,
    prepare_messages,
    public_profile,
)
from app.services.report import build_report


def run_unified(
    analyzer,
    messages,
    self_speaker: str,
    other_speaker: str,
    *,
    store_factory,
    contact_id: str | None = None,
    save_consent: bool = False,
    use_ai: bool = False,
    include_guidance: bool = False,
    source: str = "本次聊天片段",
) -> dict:
    """融合入口。

    - 情感分析（本地统计 + 可选 AI 情感长文）始终执行，是本项目原本的核心结果。
    - 传入 contact_id 且勾选本机保存时，同一次调用顺带提取喜好并更新联系人档案。
    - 不传 contact_id 时就是纯粹的「只分析不建档」，不触碰档案库。
    """
    if contact_id and not save_consent:
        raise HTTPException(400, "请先确认在本机保存此联系人的脱敏档案依据")

    prepared = call(prepare_messages, [dict(m) for m in messages], self_speaker, other_speaker)
    if use_ai and not analyzer.client:
        raise HTTPException(400, "尚未配置 AI，请先配置服务或取消云端 AI 选项")
    if use_ai and sum(len(m["content"]) for m in prepared) > config.MAX_CLOUD_CHARS:
        raise HTTPException(400, "云端单次最多 4 万字，请拆分或取消云端 AI")
    want_report = bool(use_ai and include_guidance)

    profile = None
    duplicate = False
    report_regenerated = False
    profile_updated = False
    warning = None
    mode = "ai" if use_ai else "local"

    if contact_id:
        store = store_factory()
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
                    warning = (
                        ai_error_detail(exc)["message"]
                        + "。本次仅保存本地结果；修复后重新提交同一片段并勾选云端 AI 即可重试"
                    )
                    mode = "local_fallback"
            profile, _repeated = call(store.merge, contact_id, prepared, candidates, mode, warning, retry_failed)
            profile = public_profile(profile)
            profile_updated = True

    # 情感分析：本地统计始终执行；云端长文只在需要时额外调用一次。
    result = analyzer.analyze_demo(
        [{"speaker": "自己" if m["role"] == "self" else "对方", "content": m["content"]} for m in prepared],
        "自己",
        "对方",
        allow_ai=False,
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
        analysis = build_report(result, source)

    return {
        "analysis": analysis,
        "profile": profile,
        "duplicate": duplicate,
        "report_regenerated": report_regenerated,
        "profile_updated": profile_updated,
        "warning": warning,
    }
