"""Resumeable paid evaluation: shared 200-request/3.5M-token ledger, no retries."""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
import httpx
from app.core import config
from app.services import communication as cm
from app.services.archive_extraction import request
from app.services.campus_prompt import SYSTEM
from app.services.profiles import (
    ProfileStore,
    ai_error_detail,
    prepare_messages,
    public_profile,
)
from openai import OpenAI


class BudgetStop(RuntimeError):
    pass


class Ledger:
    def __init__(self, path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "max_calls":200,"max_tokens":3500000,"calls":[],"results":[],"contacts":{}}
        self.label = ""

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(self.path)

    def tokens(self):
        return sum(r.get("usage",{}).get("total_tokens",r["reserved_tokens"]) for r in self.data["calls"])

    def create(self, provider, kwargs):
        reservation = sum(len(m["content"].encode("utf-8")) for m in kwargs["messages"]) + kwargs["max_tokens"] + 512
        if len(self.data["calls"])>=200 or self.tokens()+reservation>3500000:
            raise BudgetStop("本轮请求或token上限保护已停止")
        payload = json.loads(kwargs["messages"][1]["content"])
        row={"label":self.label,"stage":payload.get("stage","baseline"),"reserved_tokens":reservation,"status":"started",
             "prompt_sha256":hashlib.sha256(kwargs["messages"][0]["content"].encode()).hexdigest(),
             "payload":payload,"version":cm.PROMPT_VERSION}
        self.data["calls"].append(row)
        self.save()
        start=time.monotonic()
        try:
            out=provider(**kwargs)
            row["status"]="completed"
            if out.usage and out.usage.total_tokens is not None:
                row["usage"]={k:getattr(out.usage,k) for k in ("prompt_tokens","completion_tokens","total_tokens")}
            row["response"]=out.choices[0].message.content if out.choices else ""
            return out
        except Exception as exc:
            row.update(status="failed",error=ai_error_detail(exc)["message"])
            raise
        finally:
            row["seconds"]=round(time.monotonic()-start,2)
            self.save()


class Client:
    def __init__(self, real, ledger, reuse=False):
        self.real,self.ledger,self.base_url=real,ledger,real.base_url
        self.reuse=reuse
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self,**kwargs):
        payload=json.loads(kwargs['messages'][1]['content'])
        if self.reuse and payload.get('stage')=='extract':
            _,cid,number=self.ledger.label.split(':')
            cached=next((c for c in self.ledger.data['calls'] if c['label']=='new:'+cid+':'+number
                         and c['stage']=='extract' and c.get('status')=='completed'
                         and c['payload']['messages']==payload['messages']),None)
            if cached:
                self.ledger.data.setdefault('cache_reuses',[]).append({'label':self.ledger.label,'source_label':cached['label'],
                    'stage':'extract','source_prompt_sha256':cached['prompt_sha256']})
                self.ledger.save()
                return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=cached['response']))])
            raise BudgetStop('没有同一输入的提取缓存，避免额外消费')
        return self.ledger.create(self.real.chat.completions.create,kwargs)

    def with_options(self,**kwargs):
        return Client(self.real.with_options(**kwargs),self.ledger,self.reuse)


def prepare(step):
    rows=[]
    for line in step["text"].splitlines():
        name,text=line.split("：",1)
        rows.append({"speaker":"我" if name=="我" else "TA","content":text})
    return prepare_messages(rows,"我","TA")


def check_gold(step, items, p):
    # Transparent operational checks, NOT a full semantic accuracy estimator.
    text=" ".join(" ".join(str(i.get(k,"")) for k in ("fact","scope","interpretation","method")) for i in items)
    kinds={i["memory_type"] for i in items}
    missing=[pattern for pattern in step.get("expected",[]) if not re.search(pattern,text)]
    forbidden=[]
    for pattern in step.get("forbidden",[]):
        hit=pattern[5:] in kinds if pattern.startswith("TYPE:") else bool(re.search(pattern,text))
        if hit:
            forbidden.append(pattern)
    if step.get("empty") and items:
        forbidden.append("expected_empty")
    required=set(step.get("required",[]))
    if "support_need" in required and kinds & {"communication_request","boundary"}:
        required.remove("support_need")
    missing+=['TYPE:'+kind for kind in required-kinds]
    events=[f for f in p["facts"] if f.get("memory_type")=="event"]
    if step.get("event_date") and not any(f.get("event_date")==step["event_date"] and not f.get("conflict") for f in events):
        missing.append('DATE:'+step["event_date"])
    if len(events)<step.get("minimum_events",0):
        missing.append("distinct_events")
    return {"missing":missing,"forbidden":forbidden,"expected_count":len(step.get("expected",[]))+len(required),
            "has_gold":bool(step.get("expected") or step.get("required") or step.get("forbidden") or step.get("empty"))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--cases",default="")
    parser.add_argument("--mode",default="new",choices=["new","baseline","recheck","final","acceptance","cached"])
    parser.add_argument("--max-uploads",type=int,default=10)
    parser.add_argument("--retry-failed",action="store_true",help="Explicit manual rerun; failures remain charged in ledger")
    parser.add_argument("--reuse-extractions",action="store_true",help="Use already-paid independent extraction; only verification is charged")
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    lock=args.output.with_suffix('.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        config.load_env_file(args.config)
        if config.is_placeholder_key(config.api_key()):
            raise ValueError("本地API配置不可用")
        ledger=Ledger(args.output)
        ledger.data['model']=config.model_name()
        ledger.save()
        store=ProfileStore(args.output.parent/'archive-v5-evaluation-data')
        corpus=json.loads((Path(__file__).resolve().parents[1]/'backend/tests/fixtures/archive_suite.json').read_text(encoding='utf-8'))
        chosen=set(args.cases.split(',')) if args.cases else set()
        done={r['label'] for r in ledger.data['results'] if not args.retry_failed or not r.get('error')}
        count,errors=0,0
        with OpenAI(api_key=config.api_key(),base_url=config.base_url(),max_retries=0,http_client=httpx.Client(trust_env=False)) as real:
            client=Client(real,ledger,args.reuse_extractions)
            for case in corpus:
                if chosen and case['id'] not in chosen:
                    continue
                key=args.mode+':'+case['id']
                if key not in ledger.data['contacts']:
                    ledger.data['contacts'][key]=store.create(case['name'])['id']
                    ledger.save()
                for index,step in enumerate(case['steps']):
                    label=key+':'+str(index+1)
                    if label in done:
                        continue
                    if count>=args.max_uploads:
                        return
                    ledger.label=label
                    p=store.get(ledger.data['contacts'][key])
                    msgs=prepare(step)
                    try:
                        if args.mode=='baseline':
                            raw=request(client,config.model_name(),SYSTEM,{'messages':msgs,'existing':cm.existing_context(p),
                                        'chat_date':step['day'],'scene_hint':case['scene']},max_tokens=2200)
                            items,rejected=cm.validate_items(raw.get('items',[]),msgs)
                        else:
                            items,rejected=cm.extract_ai(msgs,p,client,config.model_name(),step['day'],case['scene'])
                        view=cm.preview(store,p,msgs,items,step['day'],case['scene'],'ai')
                        if view['token']:
                            p=cm.commit(store,p['id'],view['token'])
                        reviews=sum(bool(f.get('conflict')) for f in p['facts'])
                        if step.get('resolve'):
                            for f in p['facts']:
                                if f.get('conflict') and f.get('alternatives') and not f.get('manual_locked'):
                                    p=cm.resolve(store,p['id'],f['id'],p['revision'],step['resolve'])
                        gold=check_gold(step,items,p)
                        ledger.data['results'].append({'label':label,'source':case['source'],'chars':len(step['text']),
                            'messages':len(msgs),'items':items,'rejected':rejected,'checks':gold,'changes':view['changes'],
                            'reviews':reviews,'simulated_user_resolution':step.get('resolve'),'profile':public_profile(p)})
                        print(label,'items',len(items),'missing',gold['missing'],'forbidden',gold['forbidden'],
                              'calls',len(ledger.data['calls']),'tokens',ledger.tokens(),flush=True)
                    except BudgetStop as exc:
                        print(str(exc),flush=True)
                        return
                    except Exception as exc:  # noqa: BLE001 - record safely, never auto-retry billed calls
                        ledger.data['results'].append({'label':label,'error':ai_error_detail(exc)['message'],
                            'source':case['source'],'chars':len(step['text'])})
                        errors+=1
                        print(label,'ERROR',ai_error_detail(exc)['message'],flush=True)
                        if errors>=2:
                            print('Two request/output failures; stopped for review',flush=True)
                            ledger.save()
                            return
                    ledger.save()
                    count+=1
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


if __name__=='__main__':
    main()
