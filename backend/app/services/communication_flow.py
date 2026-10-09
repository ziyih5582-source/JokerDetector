"""Shared recognition flow used by normal analysis and the profile page."""
from fastapi import HTTPException

from app.core.errors import call
from app.services import communication
from app.services.dossier import check_revision
from app.services.profiles import ai_error_detail, public_profile


def recognize(store, contact_id, messages, *, revision=None, chat_date=None, scene="", use_ai=False, client=None, model=""):
    p=call(store.get,contact_id)
    if revision is not None:
        call(check_revision,p,revision)
    metadata,duplicate,_=communication.metadata_for(store,p,messages,chat_date,scene,"ai" if use_ai else "local")
    if duplicate:
        return {"token":None,"changes":[],"duplicate":True,"revision":p["revision"],"rejected_count":0,"notice":"完整重复，不再调用模型或计数"}
    if len(p["batches"])>=200:
        raise HTTPException(400,"档案更新记录已达上限，请先导出；本次未调用模型")
    try:
        if use_ai:
            candidates,rejected=communication.extract_ai(messages,p,client,model,chat_date,scene)
        else:
            candidates,rejected=communication.extract_local(messages)
        result=call(communication.preview,store,p,messages,candidates,chat_date,scene,"ai" if use_ai else "local")
    except HTTPException:
        raise
    except ValueError as exc:
        if not client and use_ai:
            raise HTTPException(400,"尚未配置AI，完整沟通识别需要先配置服务端API") from None
        raise HTTPException(400,ai_error_detail(exc)["message"]) from None
    except Exception as exc:
        raise HTTPException(502,ai_error_detail(exc)["message"]+"；档案未改变，可以重试") from None
    result.update(rejected_count=len(rejected),
                  notice="AI理解仍可能有偏差，原文与适用范围可展开核对" if use_ai else "当前是有限规则摘录，完整语义理解请开启云端AI")
    result["empty_metadata"]=metadata if not result["changes"] else None
    return result


def import_memory(store, contact_id, messages, **options):
    preview=recognize(store,contact_id,messages,**options)
    if preview.get("token"):
        p=call(communication.commit,store,contact_id,preview["token"])
    else:
        if preview.get("empty_metadata"):
            p=call(communication.cache_empty,store,contact_id,preview["revision"],preview["empty_metadata"],"ai" if options.get("use_ai") else "local")
        else:
            p=call(store.get,contact_id)
    return {"profile":public_profile(p),"changes":preview["changes"],"duplicate":preview["duplicate"],
            "profile_updated":bool(preview.get("token")),"notice":preview["notice"],"rejected_count":preview["rejected_count"]}
