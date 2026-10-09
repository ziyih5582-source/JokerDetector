"""Grounding, time and integration checks for the actual communication engine."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.services import communication as cm
from app.services.communication_flow import import_memory
from app.services.profiles import ProfileStore, prepare_messages, public_profile


@pytest.fixture
def store(tmp_path):
    return ProfileStore(tmp_path)


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv("JOKER_PROFILE_DIR",str(tmp_path))
    monkeypatch.setattr(deps.analyzer,"client",None)
    deps.get_store.cache_clear()
    with TestClient(app) as c:
        yield c
    deps.get_store.cache_clear()


def messages(text="能不能以后把哪部分、几点前要一起说清楚？",other=None):
    return prepare_messages([{ "speaker":"我","content":"这次分工怎么安排？"},
                             {"speaker":"小林","content":text}]+(other or []),"我","小林")


def item(quote="能不能以后把哪部分、几点前要一起说清楚？",**kw):
    data={"memory_type":"communication_request","subject":"other","topic":"任务与截止时间",
          "fact":"对方要求分工时明确任务内容和截止时间","scope":"任务分工","retention":"conditional",
          "source_level":"direct","method":"先写明需要负责的部分和截止时间，再确认能否完成",
          "limitation":"限定任务合作，不推广到所有聊天","evidence":[{"message_id":1,"quote":quote}]}
    data.update(kw)
    return data


def candidates(raw,msgs):
    rows,drop=cm.validate_items(raw,msgs)
    assert not drop,drop
    return rows


def apply(store,p,msgs,raw,day="2026-09-20",origin="ai"):
    pr=cm.preview(store,p,msgs,candidates(raw,msgs),day,"",origin)
    if pr["token"]:
        p=cm.commit(store,p["id"],pr["token"])
    return p,pr


def fake_provider(items,captured):
    def create(**kwargs):
        captured.append(kwargs)
        payload=json.loads(kwargs["messages"][1]["content"])
        output={"items":items}
        if payload.get("stage")=="verify":
            output={"checks":[{"candidate_id":i,"verdict":"supported","reason":"原文明确表达此项要求",
                               "method":items[i].get("method","")} for i in range(len(payload["candidates"]))]}
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(output,ensure_ascii=False)),finish_reason="stop")])
    obj=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    obj.with_options=lambda **kwargs:obj
    return obj


@pytest.mark.parametrize("text",["能不能以后把哪部分、几点前要一起说清楚？","如果要改时间，请提前一天告诉我。"])
def test_requests_and_conditionals_not_blanket_filtered(text):
    rows,drop=cm.validate_items([item(quote=text)],messages(text))
    assert len(rows)==1 and drop==[]


def test_role_and_interaction_requirements():
    msgs=messages()
    assert cm.validate_items([item(evidence=[{"message_id":0,"quote":msgs[0]["content"]}])],msgs)[0]==[]
    assert cm.validate_items([item(memory_type="shared_understanding",source_level="interaction")],msgs)[0]==[]
    assert cm.validate_items([item(fact="对方是回避型人格")],msgs)[0]==[]
    assert cm.validate_items([item(evidence=[{"message_id":1,"quote":"伪造了一句"}])],msgs)[0]==[]


def test_model_both_alias_preserves_pair_grounding():
    msgs=messages()
    raw=item(subject="both",memory_type="shared_understanding",retention="episode",
             evidence=[{"message_id":0,"quote":msgs[0]["content"]},{"message_id":1,"quote":msgs[1]["content"]}])
    valid,_=cm.validate_items([raw],msgs)
    assert valid[0]["subject"]=="relation" and valid[0]["source_level"]=="interaction"
    raw["evidence"]=raw["evidence"][:1]
    assert cm.validate_items([raw],msgs)[0]==[]


def test_pure_third_party_report_is_rejected_but_own_turn_is_not():
    pure="我室友说最讨厌别人发语音。"
    assert cm.validate_items([item(quote=pure)],messages(pure))[0]==[]
    mixed="我室友说最讨厌语音，不过我自己只希望重要安排文字发我。"
    valid,_=cm.validate_items([item(quote=mixed,fact="本人希望重要安排使用文字",scope="重要安排")],messages(mixed))
    assert len(valid)==1


def test_same_topic_updates_and_source_quotes(store):
    p=store.create("小林");p,_=apply(store,p,messages(),[item()])
    text="之后分工请继续把具体哪一部分和几点前交写清。"
    p,_=apply(store,p,messages(text),[item(quote=text,target_id=p["facts"][0]["id"],operation="evidence")],"2026-09-23")
    assert len(p["facts"])==1 and len(p["facts"][0]["evidence"])==2
    assert all(e["role"]=="other" for e in p["facts"][0]["evidence"])
    assert public_profile(p)["method_cards"][0]["finding"]==p["facts"][0]["text"]


def test_scenario_branches_have_their_own_evidence(store):
    p=store.create("小林");p,_=apply(store,p,messages(),[item()])
    text="简单的闲聊短语音也可以，重要安排仍用文字。"
    p,_=apply(store,p,messages(text),[item(quote=text,operation="branch",scope="简单闲聊",fact="简单闲聊可以短语音",
        method="简单闲聊可先确认是否方便听短语音",target_id=p["facts"][0]["id"])],"2026-09-23")
    cards=public_profile(p)["method_cards"]
    assert len(cards)==2 and len(cards[1]["evidence"])==1
    assert cards[1]["evidence"][0]["quote"]==text


def event_item(text,**kw):
    return item(quote=text,memory_type="event",topic="A公司第一轮面试",fact=text,scope="A公司第一轮面试",retention="temporary",
                event_identity="A公司第一轮",method="",**kw)


def test_event_updates_and_late_old_record(store):
    p=store.create("小林");text="A公司第一轮今年10月12号。"
    p,_=apply(store,p,messages(text),[event_item(text)],"2026-09-20")
    text="A公司第一轮改到今年10月15号了。"
    p,_=apply(store,p,messages(text),[event_item(text,operation="change",target_id=p["facts"][0]["id"])],"2026-09-25")
    assert p["facts"][0]["event_date"]=="2026-10-15"
    assert p["facts"][0]["versions"][0]["event_date"]=="2026-10-12"
    text="A公司第一轮定在今年10月12号。"
    p,pr=apply(store,p,messages(text),[event_item(text)],"2026-09-19")
    assert pr["changes"][0]["action"]=="historical"
    assert p["facts"][0]["event_date"]=="2026-10-15"


def test_same_day_uncertain_change_and_within_chunk_correction(store):
    p=store.create("小林");text="A公司第一轮今年10月12号。"
    p,_=apply(store,p,messages(text),[event_item(text)])
    text="A公司第一轮改到今年10月15号。"
    p,_=apply(store,p,messages(text),[event_item(text,operation="change")])
    assert p["facts"][0]["event_date"]=="2026-10-12" and p["facts"][0]["conflict"]
    p2=store.create("另一个人")
    msgs=[{"id":0,"role":"other","content":"A公司第一轮今年10月12号。"},
          {"id":1,"role":"other","content":"刚才说错了，A公司第一轮是今年10月15号。"},
          {"id":2,"role":"self","content":"好，15号。"}]
    first=event_item(msgs[0]["content"],evidence=[{"message_id":0,"quote":msgs[0]["content"]}])
    second=event_item(msgs[1]["content"],operation="change",evidence=[{"message_id":1,"quote":msgs[1]["content"]}])
    p2,_=apply(store,p2,msgs,[first,second])
    assert len(p2["facts"])==1 and p2["facts"][0]["event_date"]=="2026-10-15"


def test_unknown_date_and_two_events_never_invent_dates():
    c=candidates([event_item("A公司明天面试。")],messages("A公司明天面试。"))[0]
    assert cm.source_date(c,None)==(None,"明天")
    assert cm.source_date(c,"2026-09-20")[0]=="2026-09-21"
    c=candidates([event_item("A公司今年10月12号，B公司今年10月16号。")],messages("A公司今年10月12号，B公司今年10月16号。"))[0]
    assert cm.source_date(c,"2026-09-20")[0] is None


def test_event_status_needs_separate_evidence_and_keeps_date(store):
    p=store.create("小林");text="A公司第一轮今年9月22号。"
    p,_=apply(store,p,messages(text),[event_item(text,event_status="planned")])
    text="A公司第一轮已经结束了，结果还没收到。"
    p,_=apply(store,p,messages(text),[event_item(text,event_status="completed",operation="end")],"2026-09-27")
    assert p["facts"][0]["validity"]=="ended"
    assert p["facts"][0]["event_date"]=="2026-09-22"
    c=event_item("A公司面试还没结束。",event_status="completed")
    assert cm.normalized_status(c)=="unknown"


def test_duplicate_and_empty_success_do_not_bill_twice(store):
    p=store.create("小林");calls=[];provider=fake_provider([],calls)
    first=import_memory(store,p["id"],messages("好的。"),revision=p["revision"],use_ai=True,client=provider,model="fake")
    second=import_memory(store,p["id"],messages("好的。"),revision=p["revision"],use_ai=True,client=provider,model="fake")
    assert len(calls)==1 and second["duplicate"]
    assert first["profile"]["revision"]==0 and first["profile"]["batches"]==[]
    assert "recognition_cache" not in first["profile"]


def test_local_then_ai_can_upgrade_without_inflating_evidence(store):
    p=store.create("小林");raw=item()
    p,_=apply(store,p,messages(),[raw],origin="local")
    raw["method"]="先写明负责部分、截止时间，再询问是否来得及"
    p,_=apply(store,p,messages(),[raw],origin="ai")
    assert p["facts"][0]["origin"]=="ai" and len(p["facts"][0]["evidence"])==1


def test_manual_correction_deletion_and_stale_preview(store):
    p=store.create("小林");p,_=apply(store,p,messages(),[item()])
    fact_id=p["facts"][0]["id"]
    p=store.edit_fact(p["id"],fact_id,p["revision"],"correct","熟悉后可以随意聊，任务仍需明确时间")
    assert public_profile(p)["method_cards"]==[] and p["facts"][0]["manual_locked"]
    raw=item(quote="以后请继续明确任务时间。")
    pr=cm.preview(store,p,messages(raw["evidence"][0]["quote"]),candidates([raw],messages(raw["evidence"][0]["quote"])),"2026-09-25")
    p=store.edit_fact(p["id"],fact_id,p["revision"],"delete")
    with pytest.raises(RuntimeError):
        cm.commit(store,p["id"],pr["token"])
    pr=cm.preview(store,p,messages(),candidates([item()],messages()),"2026-09-26")
    assert pr["changes"]==[]


def test_private_manual_notes_not_sent_to_extraction(store):
    p=store.create("小林");p,_=apply(store,p,messages(),[item()])
    p=store.edit_fact(p["id"],p["facts"][0]["id"],p["revision"],"correct","PRIVATE_NOTE_DO_NOT_SEND")
    captures=[]
    cm.extract_ai(messages(),p,fake_provider([],captures),"fake")
    encoded=captures[0]["messages"][1]["content"]
    assert "PRIVATE_NOTE_DO_NOT_SEND" not in encoded
    assert '"role": "self"' in encoded and '"role": "other"' in encoded


def test_profile_route_and_default_normal_upload_use_same_engine(client):
    p=client.post("/api/profiles/contacts",json={"name":"小林"}).json()
    data={"messages":[{"speaker":"我","content":"分工怎么安排？"},{"speaker":"小林","content":"能不能以后把哪部分、几点前要一起说清楚？"}],
          "self_speaker":"我","other_speaker":"小林","contact_id":p["id"],"save_consent":True}
    result=client.post("/api/analyze/unified",json=data)
    assert result.status_code==200,result.text
    result=result.json()
    assert result["profile"]["facts"][0]["memory_version"]==3
    assert result["profile"]["method_cards"] and result["analysis"]["statistics"]
    legacy=client.post("/api/analyze/unified",json={**data,"contact_id":None,"profile_engine":"legacy"}).json()
    assert result["analysis"]["verdict"]["score"]==legacy["analysis"]["verdict"]["score"]


def test_no_plain_preferences_in_new_default(client):
    p=client.post("/api/profiles/contacts",json={"name":"小林"}).json()
    data={"messages":[{"speaker":"我","content":"最近看什么？"},{"speaker":"小林","content":"我喜欢咖啡"}],
          "self_speaker":"我","other_speaker":"小林","contact_id":p["id"],"save_consent":True}
    r=client.post("/api/analyze/unified",json=data).json()
    assert r["profile"]["facts"]==[] and not r["profile_updated"]


def test_preview_consent_and_failure_leave_data_untouched(client,monkeypatch):
    p=client.post("/api/profiles/contacts",json={"name":"小林"}).json()
    data={"revision":0,"messages":[{"speaker":"我","content":"分工怎么安排？"},{"speaker":"小林","content":"能不能以后把哪部分、几点前要一起说清楚？"}],
          "self_speaker":"我","other_speaker":"小林","use_ai":True,"cloud_consent":False,"save_consent":True}
    path=f'/api/profiles/contacts/{p["id"]}/memory/import'
    assert client.post(path,json=data).status_code==400
    calls=[];monkeypatch.setattr(deps.analyzer,"client",fake_provider([item(evidence=[{"message_id":1,"quote":"伪造引用"}])],calls))
    data["cloud_consent"]=True
    assert client.post(path,json=data).status_code==400
    unchanged=client.get(f'/api/profiles/contacts/{p["id"]}').json()
    assert unchanged["revision"]==0 and unchanged["facts"]==[]


def test_saved_real_model_outputs_with_scope_and_time_guards(store):
    data=json.loads((Path(__file__).parent/"fixtures/communication_model_recordings.json").read_text(encoding="utf-8"))
    profiles={};mapping={}
    for r in data["records"]:
        cid=r["case_id"]
        if cid not in profiles:
            profiles[cid]=store.create(cid)
        p=profiles[cid];b=r["batch"]
        msgs=prepare_messages([{"speaker":"我" if m["speaker"]=="self" else "小林","content":m["text"]} for m in b["messages"]],"我","小林")
        raw=json.loads(json.dumps(r["model_items"]))
        for c in raw:
            if c.get("target_id") in mapping:
                c["target_id"]=mapping[c["target_id"]]
        valid,rejected=cm.validate_items(raw,msgs)
        assert valid and not rejected,(cid,rejected)
        pr=cm.preview(store,p,msgs,valid,b["occurred_at"],"")
        p=cm.commit(store,p["id"],pr["token"])
        profiles[cid]=p
        for old,current in zip(r["original_state_ids"],p["facts"],strict=True):
            mapping[old]=current["id"]
    assert len(profiles["C01"]["facts"])==2
    assert {f["memory_type"] for f in profiles["C01"]["facts"]}=={"communication_request","shared_understanding"}
    boundary=profiles["C02"]["facts"][0]
    assert "群" in boundary["context"] and "任务" in boundary["text"]
    assert boundary["branches"] and "私" in boundary["branches"][0]["scope"]
    assert len(public_profile(profiles["C02"])["method_cards"])==2
    event=profiles["C05"]["facts"][0]
    assert event["event_date"]=="2026-10-15" and not event["conflict"]
    assert event["evidence"][-1]["historical"]


def test_new_context_selects_topic_and_binds_preview_to_sent_background(client,monkeypatch):
    from app.api.routes.fisherman import context_for
    from test_fisherman import FakeClient
    store=deps.get_store();p=store.create("小林")
    p,_=apply(store,p,messages(),[item()])
    quote="A公司第一轮今年10月12号。"
    p,_=apply(store,p,messages(quote),[event_item(quote)])
    assert "任务内容" in context_for(p,"小组分工怎么说")[0]
    assert "10月12" not in context_for(p,"小组分工怎么说")[0]
    assert "10月12" in context_for(p,"面试安排怎么问")[0]
    provider=FakeClient();monkeypatch.setattr(deps.analyzer,"client",provider)
    query="小组分工怎么说"
    preview=client.post('/api/fisherman/context',json={"contact_id":p["id"],"query":query}).json()
    r=client.post('/api/fisherman/chat',json={"messages":[{"role":"user","content":query}],"contact_id":p["id"],"use_profile":True,"context_token":preview["token"]})
    assert r.status_code==200 and preview["text"] in provider.calls[-1]["messages"][0]["content"]
    wrong=client.post('/api/fisherman/chat',json={"messages":[{"role":"user","content":"另一问题"}],"contact_id":p["id"],"use_profile":True,"context_token":preview["token"]})
    assert wrong.status_code==400
    p=store.edit_fact(p["id"],p["facts"][0]["id"],p["revision"],"delete")
    stale=client.post('/api/fisherman/chat',json={"messages":[{"role":"user","content":query}],"contact_id":p["id"],"use_profile":True,"context_token":preview["token"]})
    assert stale.status_code==409


def test_uncorrected_roles_and_summary_cannot_trigger_model_or_archive(client,monkeypatch):
    p=client.post('/api/profiles/contacts',json={"name":"小林"}).json()
    calls=[];monkeypatch.setattr(deps.analyzer,"client",fake_provider([item()],calls))
    data={"revision":0,"messages":[{"speaker":"我","content":"分工怎么安排？"},{"speaker":"小林","content":"能不能以后把哪部分、几点前要一起说清楚？"}],
          "self_speaker":"我","other_speaker":"小林","use_ai":True,"cloud_consent":True,"save_consent":True}
    url=f'/api/profiles/contacts/{p["id"]}/memory/import'
    assert client.post(url,json={**data,"role_reliability":"unverified"}).status_code==400
    response=client.post(url,json={**data,"source_kind":"ai_summary"}).json()
    assert response["profile"]["facts"]==[] and calls==[]


def test_new_repair_keeps_overlapping_context_and_both_speakers(store):
    p=store.create("小林")
    first=[{"id":0,"role":"self","content":"这周能给我最终版吗？"},
           {"id":1,"role":"other","content":"我以为这周只要初稿。"},
           {"id":2,"role":"self","content":"我说清楚：周三初稿，周五最终版。"}]
    raw=item(quote=first[1]["content"],fact="对方说明先前理解为本周初稿",retention="episode")
    p,_=apply(store,p,first,[raw])
    newer=first+[{"id":3,"role":"other","content":"哦，那周三我给初稿，周五最终版。"}]
    raw=item(memory_type="shared_understanding",subject="relation",source_level="interaction",topic="交付类型澄清",
             fact="双方澄清初稿和最终版时间，对方确认安排",retention="episode",
             evidence=[{"message_id":i,"quote":m["content"]} for i,m in enumerate(newer)])
    p,_=apply(store,p,newer,[raw])
    episode=next(f for f in p["facts"] if f["memory_type"]=="shared_understanding")
    assert {e["role"] for e in episode["evidence"]}=={"self","other"}
    assert sum(e.get("context_only",False) for e in episode["evidence"])==3
