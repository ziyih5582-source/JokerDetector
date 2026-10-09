"""Grounded communication recognition: evidence, conditional memory and methods.

The model proposes meaning; code enforces references, scope, dates, identity,
manual constraints and atomic revision checks. No raw transcript is persisted.
"""
import copy
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone

from cryptography.fernet import InvalidToken
from pydantic import ValidationError

from app.schemas.communication import Candidate
from app.services.dossier import check_revision, import_metadata, save, topic_key
from app.services.profiles import SENSITIVE, normalize, now, redact

PROMPT_VERSION = "archive-evidence-v5.3"
POLICY_VERSION = "archive-guards-v5.3"
TYPES = {
    "communication_request": "沟通要求", "boundary": "边界", "support_need": "支持需要",
    "situated_trait": "情境特点", "shared_understanding": "共同理解与澄清",
    "stage_context": "阶段背景", "event": "重要事件", "useful_preference": "有用偏好",
    "user_note": "用户补充",
    "relationship_position": "本人关系态度", "interaction_signal": "关系中的实际互动",
    "personal_view": "兴趣与个人观点", "emotional_state": "当时的心情",
}
CATEGORY = {"communication_request": "style", "boundary": "boundary", "support_need": "value",
            "situated_trait": "trait", "shared_understanding": "style", "stage_context": "event",
            "event": "event", "useful_preference": "preference", "relationship_position": "value",
            "interaction_signal": "style", "personal_view": "value", "emotional_state": "event"}
DIAGNOSIS = re.compile(r"人格障碍|回避型|依恋型|玻璃心|控制欲|MBTI|自卑型|讨好型|天生冷漠|真实动机|本质上")
THIRD_PERSON = re.compile(r"^(?:我(?:的)?(?:室友|朋友|同学)|他朋友|她朋友|有人)(?:说|表示|觉得|喜欢|讨厌)")
OWN_TURN = re.compile(r"(?:但|但是|不过|而|至于)我(?:自己|本人|需要|希望|更|只|想|没有|不|则)")
CHANGE = re.compile(r"改到|改成|改为|现在|不再|之前.*(?:现在|以后)|最后定|最终|说错|没采用|取消|结束|交完|收到.*录用")
CORRECTION = re.compile(r"刚才.*说错|更正|不是.*是|最后定|最终|那条.*没采用")
GENERIC = {"多沟通", "互相理解", "尊重对方", "注意沟通方式", "多关心对方"}




def migrate(p):
    p.setdefault("memory_tombstones", [])
    p.setdefault("recognition_cache", [])
    for f in p["facts"]:
        if f.get("memory_version") == 3:
            f.setdefault("branches", [])
            f.setdefault("source_sessions", [])
            f.setdefault("scene", "everyday")
    p["schema_version"] = 3
    return p


def today():
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def validate_items(raw, messages, *, semantic_checked=False, precheck=False):
    by_id = {m["id"]: m for m in messages}
    accepted, rejected = [], []
    for item in raw:
        if isinstance(item,dict) and item.get("subject")=="both":
            item={**item,"subject":"relation"}  # Semantic alias; still requires both speakers below.
        if isinstance(item,dict) and isinstance(item.get("evidence"),list) and any(
                not isinstance(e,dict) or type(e.get("message_id")) is not int for e in item["evidence"]):
            rejected.append("消息引用必须使用实际整数ID")
            continue
        try:
            c = Candidate.model_validate(item).model_dump()
        except (ValidationError, TypeError, ValueError):
            rejected.append("格式不符合沟通信息结构")
            continue
        fact_text = c["fact"] + c["topic"] + c["scope"]
        if SENSITIVE.search(fact_text) or DIAGNOSIS.search(fact_text):
            rejected.append("敏感或无依据的人格判断")
            continue
        ids, roles, seen = [], set(), set()
        for e in c["evidence"]:
            m = by_id.get(e["message_id"])
            if not m or e["quote"] not in m["content"] or SENSITIVE.search(e["quote"]):
                break
            if e["message_id"] in seen:
                break
            seen.add(e["message_id"])
            ids.append(e["message_id"])
            roles.add(m["role"])
        if len(ids) != len(c["evidence"]):
            rejected.append("引用不存在、重复或含敏感内容")
            continue
        expected_role = c["subject"] if c["subject"] != "relation" else None
        if not precheck and expected_role and expected_role not in roles:
            rejected.append("人物归属与引用不一致")
            continue
        if not precheck and (c["source_level"] == "interaction" or c["subject"] == "relation"
                or c["memory_type"] in {"shared_understanding", "interaction_signal"}) and roles != {"self", "other"}:
            rejected.append("互动结论缺少双方依据")
            continue
        relevant = [e["quote"] for e in c["evidence"] if by_id[e["message_id"]]["role"] == c["subject"]]
        if relevant and all(THIRD_PERSON.search(q.strip()) and not OWN_TURN.search(q) for q in relevant):
            rejected.append("只有第三人转述，不能给本人建事实")
            continue
        if c["memory_type"] == "emotional_state" and not semantic_checked and not re.search(r"开心|高兴|快乐|兴奋|期待|难过|伤心|烦|紧张|焦虑|失落|委屈|难受|累|疲惫|沮丧|尴尬|压力|轻松|放松|郁闷|生气|愤怒|害怕|担心|无聊|安心|平静", " ".join(relevant)):
            rejected.append("心情记录缺少本人明确的感受表达")
            continue
        if c["memory_type"] == "relationship_position":
            # This section is for explicit personal stances, not model-inferred attraction.
            own = " ".join(relevant)
            own_messages = [by_id[e["message_id"]]["content"] for e in c["evidence"] if by_id[e["message_id"]]["role"] == c["subject"]]
            if not semantic_checked and any(re.search(r"台词|只是在读|只是转述|小说里|假设|如果有人", message) for message in own_messages):
                rejected.append("关系态度的完整发言包含台词、转述或假设，不能只截取其中一句确认")
                continue
            if c["subject"] == "relation" or (not semantic_checked and not re.search(r"喜欢你|对你有好感|想.*了解|了解.*你|谈恋爱|恋爱|交往|在一起|做朋友|当朋友|只是朋友|普通朋友|发展.*关系|约会|单身", own)):
                rejected.append("关系态度缺少本人明确表达")
                continue
            if re.match(r"\s*(?:如果|假如|假设|要是|例如|比如|你说|他说|她说|书里|台词)", own):
                rejected.append("假设或转述不能确认为本人关系态度")
                continue
        all_generated = " ".join(c.get(k, "") for k in ("fact", "interpretation", "method", "example", "scope"))
        if re.search(r"(?:好感|喜欢你|成功率|脱单率).{0,10}\d+\s*[%％]|\d+\s*[%％].{0,8}(?:好感|喜欢|成功)|欲擒故纵|故意冷落|让[他她]吃醋|吊着[他她]|服从性测试|一定喜欢你|肯定喜欢你", all_generated):
            rejected.append("未保存量化好感或操控建议")
            continue
        c["topic"] = redact(c["topic"].strip())
        c["fact"] = redact(c["fact"].strip())
        c["scope"] = redact(c["scope"].strip())
        if c["memory_type"] == "relationship_position" and "[号码]" in c["scope"] and re.search(r"对话|聊天", c["scope"]):
            c["scope"] = "这次对话中本人表达的关系态度"
        if not c["topic"] or not c["fact"] or not c["scope"]:
            rejected.append("必要字段为空")
            continue
        for k in ("interpretation", "method", "example", "limitation", "event_identity", "alternative", "verification_reason"):
            c[k] = redact(c[k].strip())
        if SENSITIVE.search(c["method"]+c["example"]) or DIAGNOSIS.search(c["method"]+c["example"]):
            c["method"] = c["example"] = ""
        if c["method"] in GENERIC:
            c["method"] = c["example"] = ""
        if c["retention"] == "pending":
            c["method"] = c["example"] = ""
        if c["memory_type"] in {"shared_understanding", "interaction_signal"}:
            c["source_level"] = "interaction"
            if c["retention"] == "conditional":
                c["retention"] = "episode"
        if c["memory_type"] in {"stage_context", "emotional_state"} and c["retention"] == "conditional":
            c["retention"] = "temporary"
        if c["memory_type"] == "boundary" and re.search(r"(?:等|直到).*(?:看完|完成|结束).*(?:再|才)|(?:看完|完成|结束)之前", " ".join(relevant)):
            # Condition expiry is not calendar expiry. A spoiler boundary remains
            # applicable until the viewing condition is explicitly updated.
            if c["retention"] != "pending":
                c["retention"] = "conditional"
        own_quotes=" ".join(e["quote"] for e in c["evidence"] if by_id[e["message_id"]]["role"]==c["subject"])
        if (c["memory_type"]=="boundary" and "群" in own_quotes
                and re.search(r"拿我开玩笑|被拿来开玩笑",own_quotes)
                and re.search(r"别|不要|不喜欢|不接受",own_quotes)):
            c["topic"]="群内个人玩笑"
            c["scope"]="群内针对本人的玩笑"
            c["method"]=("群内可正常讨论任务，避免针对对方个人的玩笑" if "任务没关系" in own_quotes
                         else "群内避免针对对方个人的玩笑")
            c["limitation"]="不扩展为禁止群聊、禁止讨论任务或禁止所有私下玩笑"
        c["last_message_id"] = max(ids)
        accepted.append(c)
    return accepted, rejected


def existing_context(profile, limit=60):
    """Private human notes are never silently sent for extraction."""
    rows = []
    for f in profile["facts"]:
        if f.get("memory_version") != 3:
            continue
        row = {k: f.get(k) for k in ("id", "memory_type", "subject", "scene", "topic", "context", "retention", "origin",
                                   "observed_on", "event_date", "event_identity", "manual_locked", "validity")}
        if not f.get("manual_locked"):
            row["fact"] = f["text"]
            row["interpretation"] = f.get("interpretation", "")
            row["claim_basis"] = f.get("claim_basis", "stated")
        elif f.get("use_in_ai"):
            row["user_note"] = f["text"]
        rows.append({k:v for k,v in row.items() if v is not None and v != "" and v is not False})
    return rows[-limit:]


def extract_ai(messages, profile, client, model, chat_date=None, scene=""):
    from app.services.archive_extraction import extract
    return extract(messages, profile, client, model, chat_date, scene, validate_items, existing_context)


def extract_local(messages):
    """Explicit statements only. Do not pretend rules understand arbitrary dialogue."""
    items = []
    for m in messages:
        text = m["content"].strip()
        if len(text) > 200 or SENSITIVE.search(text) or THIRD_PERSON.search(text) or any(q in text for q in ["“", "”", '"']):
            continue
        kind, topic, scope, retention, method = None, None, None, "conditional", ""
        if m["role"] == "other" and re.search(r"(?:哪部分|哪一部分|做什么|任务|时间地点|具体).*(?:几点|截止|时间|地点)|时间.*地点", text) and re.search(r"告诉|说清|写清|发|请|能不能|分工|希望", text):
            kind, topic, scope = "communication_request", "任务与安排说明", "任务分工或安排"
            method = "说明需要哪部分、什么时间或地点，再确认是否方便"
        elif re.search(r"别|不要|不希望|不喜欢", text) and "群" in text and "开玩笑" in text:
            kind, topic, scope = "boundary", "群内个人玩笑", "群内针对本人的玩笑"
            method = "在群内讨论事情时避免把本人作为玩笑对象"
        elif re.search(r"重要安排.*文字|文字.*重要安排", text):
            kind, topic, scope = "communication_request", "重要安排的接收方式", "重要安排"
            method = "将重要安排写成文字，便于核对"
        elif re.search(r"先听.*说完|暂时.*不.*建议", text):
            kind, topic, scope, retention = "support_need", "本次倾诉需要", "本次倾诉", "temporary"
            method = "先听完本次具体经历，再询问是否需要一起讨论办法"
        elif m["role"] == "other" and "刚认识" in text and "慢热" in text:
            kind, topic, scope = "situated_trait", "熟悉程度与表达", "刚认识时"
        elif re.search(r"这两天|今天|最近", text) and re.search(r"论文|排练|答辩|实验", text):
            kind, topic, scope, retention = "stage_context", "本次阶段安排", "原话所述当前阶段", "temporary"
        elif m["role"] == "other" and re.search(r"面试|考试", text) and re.search(r"\d.*[月号日]|明天|结束|改到", text):
            kind, topic, scope, retention = "event", "面试" if "面试" in text else "考试", "原话所述事件", "temporary"
        if kind:
            c = {"memory_type":kind,"subject":m["role"],"topic":topic,"fact":text,"scope":scope,
                 "retention":retention,"method":method,"limitation":"本地规则仅摘录明确原话，不推断完整人格",
                 "evidence":[{"message_id":m["id"],"quote":text}]}
            if kind == "event":
                names = re.findall(r"[A-Za-z一-龥]{1,8}公司", text)
                c["event_identity"] = " ".join(names)+topic
                c["operation"] = "change" if "改到" in text else "end" if "结束" in text else "add"
            items.append(c)
    return validate_items(items[:20], messages)


def source_date(c, chat_date, target=None):
    """A date must be recoverable from source text and a reliable anchor."""
    text = " ".join(e["quote"] for e in c["evidence"])
    iso = list(re.finditer(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", text))
    matches = list(re.finditer(r"(?:(\d{4})年|(今年|明年|去年))?(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?", text))
    if iso:
        try:
            return date.fromisoformat(iso[-1][1]).isoformat(), iso[-1][1]
        except ValueError:
            return None, iso[-1][1]
    if len(matches)>1 and not CORRECTION.search(text) and not re.search(r"改到|改成|改为",text):
        return None,"多段日期需核对事件归属"
    if matches:
        m = matches[-1]
        year, relative, month, day = m.groups()
        # Plain month/day may cross years. Retain it without guessing a year.
        if not year and not (relative and chat_date):
            if target and target.get("event_date") and chat_date and c["operation"] in {"change","refine"}:
                year=target["event_date"][:4]
            else:
                return None, m.group(0)
        anchor_year = int(year) if year else int(chat_date[:4])+{"今年":0,"明年":1,"去年":-1}[relative]
        try:
            return date(anchor_year,int(month),int(day)).isoformat(),m.group(0)
        except ValueError:
            return None,m.group(0)
    for word, offset in (("后天",2),("明天",1),("今天",0)):
        if word in text:
            return ((date.fromisoformat(chat_date)+timedelta(days=offset)).isoformat() if chat_date else None),word
    day = re.search(r"(?:改到|改成|定在)(\d{1,2})号", text)
    if day:
        if target and target.get("event_date") and chat_date:
            anchor = date.fromisoformat(target["event_date"])
            try:
                return anchor.replace(day=int(day[1])).isoformat(), day.group(0)
            except ValueError:
                pass
        return None, day.group(0)
    return None,""


def normalized_status(c):
    text = " ".join(e["quote"] for e in c["evidence"])
    status = c["event_status"]
    if status == "cancelled" and not re.search(r"取消|不去了",text):
        return "unknown"
    if status == "completed" and not re.search(r"结束|完成|面试完|考完",text):
        return "unknown"
    if status in {"completed","cancelled"} and re.search(r"(?:没|未|尚未|还没)(?:有|能)?(?:结束|完成|取消|面试完|考完)|如果.*(?:结束|完成|取消)",text):
        return "unknown"
    if status == "offer_received" and (not re.search(r"录用通知|offer",text,re.I) or re.search(r"没.*(?:offer|录用)|担心|如果",text,re.I)):
        return "unknown"
    return status


def select_target(p, c):
    target = next((f for f in p["facts"] if f["id"] == c["target_id"]),None)
    if target and (target.get("memory_type") != c["memory_type"] or target.get("subject") != c["subject"]):
        target = None
    if target is None:
        matches = [f for f in p["facts"] if f.get("memory_version") == 3
                   and f["memory_type"] == c["memory_type"] and f["subject"] == c["subject"]
                   and normalize(f["topic"]) == normalize(c["topic"])]
        if c["memory_type"] == "event":
            matches = [f for f in matches if c["event_identity"] and normalize(f.get("event_identity", "")) == normalize(c["event_identity"])]
        target = matches[0] if len(matches)==1 else None
    if target and c["memory_type"] == "event":
        if not c["event_identity"] or normalize(target.get("event_identity", "")) != normalize(c["event_identity"]):
            target = None
    return target


def new_fact(store, c, observed_on):
    category = CATEGORY[c["memory_type"]]
    return {"id":uuid.uuid4().hex,"key":topic_key(store,category,c["topic"],c["scope"]),
            "memory_version":3,"kind":"communication","category":category,"polarity":"neutral",
            "memory_type":c["memory_type"],"subject":c["subject"],"topic":c["topic"],"text":c["fact"],
            "scene":c.get("scene","everyday"),
            "context":c["scope"],"retention":c["retention"],"source_level":c["source_level"],
            "interpretation":c["interpretation"],"method":c["method"],"example":c["example"],
            "limitation":c["limitation"],"event_identity":c["event_identity"],
            "claim_basis":c.get("claim_basis","stated"),"alternative":c.get("alternative",""),
            "verification_reason":c.get("verification_reason",""),
            "event_date":None,"date_text":"","event_status":normalized_status(c),
            "origin":"ai","certainty":"stated" if c["source_level"]=="direct" and c.get("claim_basis","stated")=="stated" else "tentative",
            "status":"unreviewed","validity":"needs_confirmation" if c["retention"]=="pending" else "current",
            "manual_locked":False,"use_in_ai":True,"observed_on":observed_on,"first_seen":now(),"last_seen":now(),
            "evidence":[],"versions":[],"alternatives":[],"branches":[],"source_sessions":[],"conflict":False}


def snapshot(f):
    return {k:copy.deepcopy(f.get(k)) for k in ("text","context","scene","observed_on","event_date","event_status","retention","method","example","branches","interpretation","limitation","claim_basis","alternative")}


def metadata_for(store, profile, messages, chat_date, scene, origin):
    # v2 and local extraction must not prevent an explicit semantic upgrade.
    modes={"communication_ai","communication_local"} if origin=="local" else {"communication_ai"}
    prior={**profile,"batches":[b for b in profile["batches"] if b["mode"] in modes]}
    metadata,duplicate,overlap=import_metadata(store,prior,messages,chat_date,scene)
    metadata["fingerprint"]=store.digest([metadata["fingerprint"],PROMPT_VERSION,POLICY_VERSION])
    duplicate=any(b["fingerprint"]==metadata["fingerprint"] for b in prior["batches"])
    duplicate=duplicate or any(c["fingerprint"]==metadata["fingerprint"] and c["origin"]==origin
                               for c in profile.get("recognition_cache",[]))
    return metadata,duplicate,overlap


def plan(store, profile, messages, candidates, chat_date=None, scene="", origin="ai"):
    p = copy.deepcopy(profile)
    metadata, duplicate, overlap = metadata_for(store,p,messages,chat_date,scene,origin)
    metadata["engine"] = PROMPT_VERSION
    metadata["policy_version"]=POLICY_VERSION
    if duplicate:
        return [],metadata,True
    by_id = {m["id"]:m for m in messages}
    changes = []
    for c in sorted(candidates,key=lambda x:x["last_message_id"]):
        c = copy.deepcopy(c)
        # Overlapping context may be essential to a newly completed repair episode.
        # Skip old-only observations, but retain context when new evidence completes it.
        if all(e["message_id"] in overlap for e in c["evidence"]):
            continue
        c["evidence"] = [e for e in c["evidence"]
                         if store.digest(normalize(e["quote"])) not in p["deleted_quotes"]]
        if not c["evidence"]:
            continue
        roles={by_id[e["message_id"]]["role"] for e in c["evidence"]}
        if (c["subject"]=="relation" or c["memory_type"] in {"shared_understanding","interaction_signal"} or c["source_level"]=="interaction") and roles!={"self","other"}:
            continue
        c["last_message_id"]=max(e["message_id"] for e in c["evidence"])
        target = select_target(p,c)
        deleted_key = topic_key(store,CATEGORY[c["memory_type"]],c["topic"],c["scope"])
        if deleted_key in p["suppressed_topics"]:
            c.update(retention="pending",method="",example="")
        if any(t["memory_type"]==c["memory_type"] and normalize(t["topic"])==normalize(c["topic"])
               and t["subject"]==c["subject"] for t in p["memory_tombstones"]):
            c.update(retention="pending",method="",example="")
        adding = target is None
        if adding:
            target = new_fact(store,c,chat_date)
            target["origin"] = origin
            p["facts"].append(target)
        action, reason = "add","新的有用沟通信息"
        if not adding:
            if target["manual_locked"]:
                action,reason = "evidence","保留用户补充，只追加对应来源"
            elif chat_date and target.get("observed_on") and chat_date < target["observed_on"]:
                action,reason = "historical","较早聊天，只保留历史来源"
            elif c["operation"] == "conflict" or c["retention"] == "pending":
                action,reason = "conflict","信息归属或先后仍需确认"
            elif c["operation"] in {"change","end"}:
                newer = bool(chat_date and target.get("observed_on") and chat_date > target["observed_on"])
                quoted = " ".join(e["quote"] for e in c["evidence"])
                within = target.get("_last_message_id",-1) < c["last_message_id"] and target.get("_current_batch")
                if (newer and CHANGE.search(quoted)) or (within and CORRECTION.search(quoted)):
                    action,reason = c["operation"],"明确变化或片段内自我纠正，保留旧版本"
                else:
                    action,reason = "conflict","时间或变化依据不足，不按上传顺序覆盖"
            elif c["operation"] == "branch":
                action,reason = "branch","不同条件或场景分别适用"
            elif c["operation"] == "refine":
                if chat_date and target.get("observed_on") and chat_date >= target["observed_on"]:
                    action,reason = "refine","补充适用条件，保留旧版本"
                else:
                    action,reason = "evidence","先保留补充原话，不覆盖时间不明的内容"
            else:
                action,reason = "evidence","同主题追加原文来源"
            if action=="refine" and normalize(c["fact"])==normalize(target["text"]) and normalize(c["scope"])==normalize(target["context"]):
                action,reason="evidence","同义重复，只追加不同原文，不产生无用的新版本"
            # A private exception cannot silently replace an explicit public boundary.
            private=any("私下" in e["quote"] or "私聊" in e["quote"] for e in c["evidence"])
            old_public=bool(re.search(r"群|公开|当众",target.get("context","")+target["text"]))
            if c["memory_type"]=="boundary" and private and old_public and action in {"refine","evidence"}:
                action,reason="branch","保留公开场景边界，同时增加私下条件"
            if target.get("origin")=="local" and origin=="ai" and not target["manual_locked"]:
                action,reason="refine","同一原始资料改用AI完善理解，不增加原文次数"
        edate, date_text = source_date(c,chat_date,target) if c["memory_type"]=="event" else (None,"")
        if c["memory_type"]=="event" and not adding and not date_text:
            edate=target.get("event_date")
            date_text=target.get("date_text","")
        if action=="end" and normalized_status(c) not in {"completed","cancelled"}:
            action,reason="conflict","结束状态没有明确支持，先保留未知"
        if not adding and c["memory_type"]=="event" and target.get("event_date") and edate and edate!=target["event_date"] and action=="evidence":
            action,reason = "conflict","同一事件日期不同，但无可靠变化依据"
        if c["memory_type"]=="event" and c["operation"]=="end" and normalized_status(c) in {"completed","cancelled"} and adding:
            action = "end"
        if (not adding and not target["manual_locked"] and c.get("review_required")
                and c["memory_type"] in {"relationship_position","boundary","situated_trait"}
                and action in {"change","refine","end","conflict"}):
            action,reason = "conflict","新内容可能明显改变之前的认识，请确认后采用"
        evidence = []
        session_key = store.digest([chat_date,metadata["message_keys"]])
        for e in c["evidence"]:
            role = by_id[e["message_id"]]["role"]
            key = store.digest([role,normalize(e["quote"]),chat_date])
            if any(old.get("key")==key for old in target["evidence"]):
                continue
            evidence.append({"key":key,"quote":e["quote"],"role":role,"message_number":e["message_id"]+1,
                "chat_date":chat_date,"at":now(),"scene":scene,"historical":action=="historical",
                "context_only":e["message_id"] in overlap,
                "source_session":session_key})
        upgrading=not adding and target.get("origin")=="local" and origin=="ai" and not target["manual_locked"]
        if not evidence and not upgrading:
            if adding:
                p["facts"].remove(target)
            continue
        if len(target["evidence"])+len(evidence)>100:
            raise ValueError("该信息的来源已过多，请先导出档案")
        before = snapshot(target) if not adding else None
        if action in {"refine","change","end"} and not target["manual_locked"]:
            if before:
                target["versions"].append({**before,"reason":action,"validity":"superseded","at":now()})
            for k,field in (("text","fact"),("context","scope"),("retention","retention"),
                            ("interpretation","interpretation"),("method","method"),("example","example"),("limitation","limitation"),
                            ("claim_basis","claim_basis"),("alternative","alternative"),("verification_reason","verification_reason")):
                target[k]=c[field]
            target.update(observed_on=chat_date,status="unreviewed",source_level=c["source_level"],scene=c.get("scene","everyday"))
            target["certainty"] = "stated" if c["source_level"]=="direct" and c.get("claim_basis","stated")=="stated" else "tentative"
            if action in {"change","end"}:
                target["branches"] = []
                for old in target["evidence"]:
                    old["historical"] = True
            target["origin"]=origin
            if c["memory_type"]=="event":
                target.update(event_date=edate,event_status=normalized_status(c),date_text=date_text)
        if adding and c["memory_type"]=="event":
            target.update(event_date=edate,date_text=date_text)
        if action == "branch":
            branch = {"scope":c["scope"],"fact":c["fact"],"method":c["method"],"example":c["example"],
                      "scene":c.get("scene","everyday"),
                      "limitation":c["limitation"],"observed_on":chat_date,"evidence_keys":[e["key"] for e in evidence]}
            if not any(normalize(b["scope"])==normalize(branch["scope"]) and normalize(b["fact"])==normalize(branch["fact"]) for b in target["branches"]):
                target["branches"].append(branch)
        if action == "conflict":
            target["alternatives"].append({"text":c["fact"],"context":c["scope"],"event_date":edate,"observed_on":chat_date,
                "retention":c["retention"],"method":c["method"],"example":c["example"],"limitation":c["limitation"],
                "interpretation":c["interpretation"],"claim_basis":c.get("claim_basis","stated"),
                "alternative":c.get("alternative",""),"verification_reason":c.get("verification_reason",""),
                "source_level":c["source_level"],"event_status":normalized_status(c),
                "evidence_keys":[e["key"] for e in evidence]})
            target.update(conflict=True,validity="needs_confirmation")
        elif action in {"change","refine"}:
            target.update(conflict=False,validity="current")
        elif action=="end" and not target["manual_locked"]:
            target["validity"]="ended"
        elif action=="evidence" and chat_date and not target["manual_locked"]:
            target["observed_on"]=max(target.get("observed_on") or "",chat_date)
        target["evidence"].extend(evidence)
        target["last_seen"]=now()
        target["_current_batch"]=True
        target["_last_message_id"]=c["last_message_id"]
        # Session count remains a display hint, never a confidence probability.
        if session_key not in target["source_sessions"]:
            target["source_sessions"].append(session_key)
        if len(target["versions"])>100:
            raise ValueError("信息版本过多，请先导出")
        clean = {k:v for k,v in target.items() if not k.startswith("_")}
        changes.append({"id":uuid.uuid4().hex,"fact_id":target["id"],"action":action,"reason":reason,
                        "before":before,"state":copy.deepcopy(clean)})
    if len(p["facts"])>500:
        raise ValueError("每位联系人最多500条档案信息")
    return changes,metadata,False


def preview(store, profile, messages, candidates, chat_date=None, scene="", origin="ai"):
    changes,metadata,duplicate = plan(store,profile,messages,candidates,chat_date,scene,origin)
    token = None
    if changes:
        payload={"purpose":"communication-v3","contact_id":profile["id"],"revision":profile["revision"],
                 "changes":changes,"metadata":metadata,"origin":origin}
        token=store.cipher.encrypt(json.dumps(payload,ensure_ascii=False).encode()).decode()
        if len(token)>500000:
            raise ValueError("本次更新过大，请拆分聊天")
    visible=[]
    for change in changes:
        f=change["state"]
        visible.append({"id":change["id"],"fact_id":f["id"],"action":change["action"],"reason":change["reason"],
                        "text":f["text"],"topic":f["topic"],"scope":f["context"],"memory_type":f["memory_type"],
                        "retention":f["retention"],"before":change["before"],"method":f["method"]})
    return {"token":token,"changes":visible,"duplicate":duplicate,"revision":profile["revision"],"engine":PROMPT_VERSION}


def commit(store, contact_id, token):
    try:
        payload=json.loads(store.cipher.decrypt(token.encode(),ttl=1800))
    except (InvalidToken,ValueError,TypeError):
        raise ValueError("预览已失效，请重新识别") from None
    if payload.get("purpose")!="communication-v3" or payload.get("contact_id")!=contact_id:
        raise ValueError("预览不属于当前档案")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        p=store._read(db,contact_id)
        check_revision(p,payload["revision"])
        if len(p["batches"])>=200:
            raise ValueError("每位联系人最多200次更新，请先导出")
        batch_id=uuid.uuid4().hex
        for change in payload["changes"]:
            f=change["state"]
            for e in f["evidence"]:
                e.setdefault("batch_id",batch_id)
            index=next((i for i,old in enumerate(p["facts"]) if old["id"]==f["id"]),None)
            if index is None:
                p["facts"].append(f)
            else:
                p["facts"][index]=f
        meta=payload["metadata"]
        p["batches"].append({"id":batch_id,"fingerprint":meta["fingerprint"],"message_keys":meta["message_keys"],
            "chat_date":meta["chat_date"],"scene":meta["scene"],"message_count":meta["message_count"],"at":now(),
            "mode":"communication_"+payload["origin"],"warning":None,
            "changes":[{"fact_id":c["fact_id"],"action":c["action"],"text":c["state"]["text"]} for c in payload["changes"]]})
        return save(store,db,p)


def resolve(store, contact_id, fact_id, revision, decision):
    """Explicitly choose the latest competing reading without another model call."""
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        p = store._read(db, contact_id)
        check_revision(p, revision)
        f = next((r for r in p["facts"] if r["id"] == fact_id), None)
        if not f or not f.get("conflict") or not f.get("alternatives") or f.get("manual_locked"):
            raise ValueError("这条记录没有可确认的变更")
        incoming = f["alternatives"][-1]
        keys = set(incoming.get("evidence_keys", []))
        if decision == "accept":
            f["versions"].append({**snapshot(f), "reason": "confirmed_change", "at": now(), "validity": "superseded"})
            for key in ("text", "context", "event_date", "observed_on", "retention", "method", "example", "limitation",
                        "interpretation", "claim_basis", "alternative", "verification_reason", "source_level", "event_status"):
                if key in incoming:
                    f[key] = incoming[key]
            f["branches"] = []
            for e in f["evidence"]:
                e["historical"] = e.get("key") not in keys
        elif decision == "keep":
            for e in f["evidence"]:
                if e.get("key") in keys:
                    e["historical"] = True
        else:
            raise ValueError("确认选项无效")
        f.update(conflict=False, validity="current", alternatives=[], last_seen=now())
        f["certainty"] = "stated" if f.get("claim_basis","stated")=="stated" and f.get("source_level")=="direct" else "tentative"
        return save(store, db, p)


def cache_empty(store, contact_id, revision, metadata, origin):
    """Cache only keyed input identity. No transcript, evidence or batch is created."""
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        p=store._read(db,contact_id)
        check_revision(p,revision)
        p["recognition_cache"]=[c for c in p["recognition_cache"]
                                if c["fingerprint"]!=metadata["fingerprint"] or c["origin"]!=origin][-49:]
        p["recognition_cache"].append({"fingerprint":metadata["fingerprint"],"origin":origin})
        store._write(db,p)
    return p


def cards_for(p):
    cards=[]
    for f in p["facts"]:
        if f.get("memory_version")!=3 or f.get("validity")!="current" or f.get("conflict") or f.get("retention")=="pending":
            continue
        # Old single-event needs are history, not today's prescription.
        if f["retention"]=="temporary" and f.get("observed_on")!=today():
            continue
        if f["memory_type"]=="event" and f.get("event_date") and f["event_date"]<today():
            continue
        variants=[{"scope":f["context"],"fact":f["text"],"method":f.get("method",""),"example":f.get("example",""),"limitation":f.get("limitation","")}]+f.get("branches",[])
        branch_keys={key for branch in f.get("branches",[]) for key in branch.get("evidence_keys",[])}
        for i,b in enumerate(variants):
            if not b.get("method") and not f.get("manual_locked"):
                if (f.get("source_level")=="direct" and f.get("claim_basis","stated")=="stated"
                        and f["memory_type"] in {"boundary","communication_request","support_need"}):
                    b={**b,"method":"按这条明确要求把握分寸："+b["fact"],
                       "limitation":b.get("limitation") or "只适用于原话中的情境；新表达出现后重新核对。"}
                elif f.get("subject") in {"other","relation"} and f["memory_type"] in {"useful_preference","personal_view"}:
                    b={**b,"method":"可以围绕这条具体兴趣或看法接话："+b["fact"],
                       "limitation":b.get("limitation") or "这是接话方向，是否继续以对方的回应为准；不表示恋爱意愿。"}
            if not b.get("method"):
                continue
            keys=set(b.get("evidence_keys",[]))
            if i==0:
                evidence=[e for e in f["evidence"] if e.get("key") not in branch_keys and not e.get("historical")]
            else:
                evidence=[e for e in f["evidence"] if e.get("key") in keys
                          or (f["memory_type"]=="boundary" and e.get("key") not in branch_keys)]
            cards.append({"id":f["id"]+":"+str(i),"fact_id":f["id"],"title":b["scope"],"finding":b["fact"],
                "method":b["method"],"example":b.get("example",""),"limitation":b.get("limitation",""),
                "scene":b.get("scene",f.get("scene","everyday")),"memory_type":f["memory_type"],
                "source_level":f["source_level"],"retention":f["retention"],"evidence":evidence,
                "claim_basis":f.get("claim_basis","stated"),"interpretation":f.get("interpretation",""),"alternative":f.get("alternative",""),
                "observed_on":b.get("observed_on",f.get("observed_on")),"profile_revision":p["revision"]})
    return cards[:60]


def save_note(store,contact_id,revision,text,fact_id=None,use_in_ai=False):
    text=redact(text.strip())
    if not text:
        raise ValueError("补充内容不能为空")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        p=store._read(db,contact_id)
        check_revision(p,revision)
        f=next((f for f in p["facts"] if f["id"]==fact_id),None)
        if fact_id and f is None:
            raise KeyError("信息不存在")
        if f is None:
            if len(p["facts"])>=500:
                raise ValueError("档案信息过多，请先导出")
            c={"memory_type":"situated_trait","subject":"relation","topic":"用户补充","fact":text,
               "scope":"用户对这段关系的补充","retention":"conditional","source_level":"user_note",
               "interpretation":"","method":"","example":"","limitation":"用户看法，不是对方原话",
               "event_identity":"","event_status":"unknown"}
            f=new_fact(store,c,None)
            f["memory_type"]="user_note"
            p["facts"].append(f)
        else:
            f["versions"].append({**snapshot(f),"reason":"manual_correction","at":now()})
        f.update(text=text,manual_locked=True,source_level="user_note",origin="manual",status="corrected",
                 method="",example="",branches=[],interpretation="",use_in_ai=use_in_ai,validity="current",conflict=False)
        return save(store,db,p)


def relevant_facts(p, query="", limit=12):
    candidates=[f for f in p["facts"] if f.get("use_in_ai",True) and f.get("validity","current") not in {"needs_confirmation","superseded"}
                and f.get("retention")!="pending"]
    words=set(re.findall(r"[A-Za-z]{2,}|[一-龥]{2,}",query))
    words.update(s[i:i+2] for s in re.findall(r"[一-龥]{2,}",query) for i in range(len(s)-1))
    # Chinese clauses also need subword matches for common life scenes.
    words.update(w for w in ("分工","任务","时间","安排","面试","考试","群","私下","私聊","玩笑","语音","文字","倾诉","建议","反馈","上课","见面") if w in query)
    intents = set()
    if re.search(r"暧昧|crush|约会|追求|喜欢[他她]|邀[他她]|约[他她]|表白|继续了解|进一步了解", query, re.I):
        intents.add("romance")
    if re.search(r"安慰|吐槽|倾诉|开心|难过|烦恼|好消息", query):
        intents.add("everyday")
    if re.search(r"游戏|动漫|番剧|文学|小说|运动|共同话题|兴趣|聊什么", query):
        intents.add("interests")
    if re.search(r"长辈|长者|前辈|学长|学姐|叔叔|阿姨", query):
        intents.add("intergenerational")
    if re.search(r"任务|作业|截止|交付|分工|老师|导师", query):
        intents.add("coordination")
    general = bool(re.search(r"怎么.{0,5}(?:聊天|相处)|注意什么|怎么继续了解|有什么.*注意|聊什么|怎么和.{0,6}聊", query))
    stable = {"boundary", "situated_trait", "communication_request", "useful_preference", "personal_view", "relationship_position"}
    def semantic(f):
        if f.get("memory_type") == "relationship_position" and ("romance" in intents or general):
            return 3  # Dated explicit stances are useful history, not current emotional truth.
        if f.get("validity") == "ended" or f.get("retention") == "temporary":
            return 0  # Only explicit lexical matches bring historical states into context.
        scene, kind = f.get("scene", "everyday"), f.get("memory_type")
        if "romance" in intents and scene in {"romance", "everyday", "interests"} and kind in stable:
            return 4 if kind in {"relationship_position", "boundary"} else 2
        if "romance" in intents and kind == "event" and re.search(r"约会|邀约|一起.*(?:书店|电影)", f["text"]):
            return 1  # Retrieve the concrete episode without treating it as hidden feelings.
        if scene in intents:
            return 3 if kind == "boundary" else 2
        if general and not intents and scene in {"romance", "everyday", "interests"} and kind in stable:
            return 2
        return 0
    def score(f):
        text=f["text"]+f.get("context","")+f["topic"]+" ".join(b["scope"]+b["fact"] for b in f.get("branches",[]))
        return (sum(1 for w in words if w in text)*3+semantic(f), f.get("memory_version")==3, f.get("observed_on") or "")
    candidates.sort(key=score,reverse=True)
    if words:
        candidates=[f for f in candidates if score(f)[0]>0]
    else:
        candidates=[f for f in candidates if f.get("validity","current")!="ended" and f.get("retention")!="temporary"]
    return candidates[:limit]
