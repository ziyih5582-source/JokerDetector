"""Acceptance of evidence/meaning separation and explicit change confirmation."""
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import communication as cm
from app.services.archive_extraction import focus_messages, request, windows
from app.services.communication_flow import import_memory
from app.api.routes.fisherman import context_for
from app.services.profiles import AIResultError, ProfileStore, public_profile


def candidate(text="别把聊天截图发群里。", **extra):
    return {"memory_type":"boundary","subject":"other","topic":"聊天截图",
            "fact":text,"scope":"将聊天截图发群里","retention":"conditional",
            "evidence":[{"message_id":1,"quote":text}],**extra}


def messages(text):
    return [{"id":0,"role":"self","content":"你怎么想？"},{"id":1,"role":"other","content":text}]


def provider(raw, check, calls, fail_verify=False):
    def create(**kwargs):
        payload=json.loads(kwargs["messages"][1]["content"])
        calls.append(payload)
        if payload["stage"]=="verify" and fail_verify:
            raise AIResultError("核查失败")
        out={"items":raw} if payload["stage"]=="extract" else {"checks":[check]}
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",message=SimpleNamespace(content=json.dumps(out)))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.with_options=lambda **kw:client
    return client


def test_quote_exists_but_checker_rejects_attribution(tmp_path):
    p=ProfileStore(tmp_path).create("TA");calls=[]
    quote="我喜欢你"
    raw=candidate(quote,memory_type="relationship_position",fact="对方喜欢我")
    check={"candidate_id":0,"verdict":"unsupported","reason":"完整发言是在转述小说台词"}
    items,rejected=cm.extract_ai(messages("小说里那句是‘我喜欢你’，我在念台词。"),p,provider([raw],check,calls),"fake")
    assert not items and rejected and len(calls)==2
    assert calls[0].get("existing") is None  # Old image cannot bias first-stage extraction.


def test_genuine_stance_with_movie_reference_survives(tmp_path):
    p=ProfileStore(tmp_path).create("TA");calls=[]
    quote="说我自己，我想继续了解你"
    raw=candidate(quote,memory_type="relationship_position",fact="对方想继续了解我")
    check={"candidate_id":0,"verdict":"supported","reason":"转折明确区分电影与本人态度"}
    items,_=cm.extract_ai(messages("电影台词让我想到这个。"+quote+"。"),p,provider([raw],check,calls),"fake")
    assert items and items[0]["verification_reason"]


@pytest.mark.parametrize("complete",[True,False])
def test_limited_inference_requires_alternative_and_limit(tmp_path,complete):
    p=ProfileStore(tmp_path).create("TA");calls=[]
    text="这段游戏剧情我还想接着说。"
    raw=candidate(text,memory_type="situated_trait",claim_basis="observed",fact="私聊中主动继续分享游戏剧情")
    check={"candidate_id":0,"verdict":"supported","reason":"主动延续该私聊话题",
           "claim_basis":"inferred","interpretation":"私聊熟悉话题时可能更愿意展开",
           "alternative":"尚不能排除当时较空闲或话题熟悉度的影响","limitation":"一次片段，不能推为固定人格或好感"}
    if not complete:
        check.pop("alternative")
    items,_=cm.extract_ai(messages(text),p,provider([raw],check,calls),"fake")
    assert bool(items)==complete
    if complete:
        assert items[0]["retention"]=="episode"


def test_failed_second_stage_never_commits_first_stage(tmp_path):
    store=ProfileStore(tmp_path);p=store.create("TA");calls=[]
    with pytest.raises(HTTPException):
        import_memory(store,p["id"],messages("别把聊天截图发群里。"),revision=0,use_ai=True,
                      client=provider([candidate()],{},calls,True),model="fake")
    assert store.get(p["id"])["facts"]==[] and len(calls)==2


def test_long_window_preserves_adjacent_context_and_all_messages():
    rows=[{"id":i,"role":"self" if i%2==0 else "other","content":"讨论课程细节。"*150} for i in range(30)]
    chunks=windows(rows)
    assert len(chunks)>1 and {m["id"] for c in chunks for m in c}==set(range(30))
    for before,after in zip(chunks,chunks[1:],strict=False):
        assert before[-2:]==after[:2]


def test_long_attention_does_not_confuse_fenbie_with_boundary():
    filler=[{"id":i,"role":"other","content":"通知里的两处标注分别说明位置和内容。"*20} for i in range(30)]
    target={"id":30,"role":"other","content":"群里不认识的人多且话题很快，我插不上话。"}
    assert focus_messages(filler+[target])==[target]


def test_provider_fences_are_removed_without_repairing_content():
    obj=SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",message=SimpleNamespace(content='{"items":[]}```'))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:obj)))
    client.with_options=lambda **kw:client
    assert request(client,"fake","json",{})=={"items":[]}
    obj.choices[0].message.content='{"items":['
    with pytest.raises(AIResultError):
        request(client,"fake","json",{})


def test_empty_long_read_gets_one_smaller_read_and_full_context_verification(tmp_path):
    calls=[];quote="群里不认识的人多，我插不上话。"
    rows=[{"id":i,"role":"self" if i%2==0 else "other","content":"两处通知分别说明位置和内容。"*30} for i in range(18)]
    rows[9]["content"]=quote
    raw=candidate(quote,memory_type="situated_trait",evidence=[{"message_id":9,"quote":quote}])
    def create(**kwargs):
        payload=json.loads(kwargs['messages'][1]['content']);calls.append(payload)
        output={'items':[]} if payload['stage']=='extract' else {'items':[raw]} if payload['stage']=='extract_focus' else {
            'checks':[{'candidate_id':0,'verdict':'supported','reason':'本人表达了这次群聊难插话的情境'}]}
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(output)))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.with_options=lambda **kw:client
    items,_=cm.extract_ai(rows,ProfileStore(tmp_path).create('TA'),client,'fake')
    assert items and [c['stage'] for c in calls]==['extract','extract_focus','verify']
    assert len(calls[1]['messages'])<len(rows) and calls[2]['messages']==rows


def test_major_change_waits_but_other_facts_save_and_resolution_has_revision_guard(tmp_path):
    store=ProfileStore(tmp_path);p=store.create("TA")
    def save(p,text,raw,day):
        items,_=cm.validate_items(raw,messages(text))
        pr=cm.preview(store,p,messages(text),items,day)
        return cm.commit(store,p["id"],pr["token"])
    p=save(p,"别把聊天截图发群里。",[candidate(method="不把聊天截图发群里")],"2026-10-01")
    fid=p["facts"][0]["id"]
    text="现在可以发这张截图。我喜欢星露谷种田。"
    change=candidate("现在可以发这张截图。",target_id=fid,operation="change",review_required=True,method="仅分享这张截图")
    pref=candidate("我喜欢星露谷种田。",memory_type="useful_preference",topic="星露谷玩法",scope="游戏",fact="喜欢星露谷种田")
    p=save(p,text,[change,pref],"2026-10-07")
    assert len(p["facts"])==2 and p["facts"][0]["conflict"]
    assert not any(c["fact_id"]==fid for c in public_profile(p)["method_cards"])
    assert public_profile(p)["campus_board"]["reviews"]
    with pytest.raises(RuntimeError):
        cm.resolve(store,p["id"],fid,p["revision"]-1,"accept")
    p=cm.resolve(store,p["id"],fid,p["revision"],"accept")
    assert "现在可以" in p["facts"][0]["text"] and not p["facts"][0]["conflict"]
    assert p["facts"][0]["versions"] and all(not e.get("historical") for e in public_profile(p)["method_cards"][0]["evidence"])


def test_older_explicit_stance_stays_dated_and_inspectable(tmp_path):
    store=ProfileStore(tmp_path);p=store.create('TA')
    text='我想先和你做朋友。'
    raw=candidate(text,memory_type='relationship_position',topic='关系态度',scope='当时的关系',retention='temporary')
    items,_=cm.validate_items([raw],messages(text))
    preview=cm.preview(store,p,messages(text),items,'2026-09-01')
    p=cm.commit(store,p['id'],preview['token'])
    row=public_profile(p)['campus_board']['stances'][0]
    assert row['historical'] and row['observed_on']=='2026-09-01'
    text,count,_=context_for(p,'怎么继续了解她？')
    assert count==1 and '2026年9月1日' in text and '不预测当前真实感情' in text


def test_blank_model_method_uses_concrete_request_and_user_correction_disables_it(tmp_path):
    store=ProfileStore(tmp_path);p=store.create('TA')
    text='刚认识时别每天追问我在干嘛。'
    raw=candidate(text,scope='刚认识时的聊天频率')
    items,_=cm.validate_items([raw],messages(text))
    view=cm.preview(store,p,messages(text),items,'2026-10-01')
    p=cm.commit(store,p['id'],view['token'])
    cards=public_profile(p)['method_cards']
    assert len(cards)==1 and text in cards[0]['method'] and cards[0]['evidence']
    p=cm.save_note(store,p['id'],p['revision'],'实际想法仍待确认',p['facts'][0]['id'])
    assert public_profile(p)['method_cards']==[]
