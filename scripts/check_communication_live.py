"""Bounded, opt-in model check with fictional cases. No real profiles are loaded."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
sys.stdout.reconfigure(encoding="utf-8")

from openai import OpenAI  # noqa: E402
import httpx  # noqa: E402
from app.core import config  # noqa: E402
from app.services import communication as cm, dossier  # noqa: E402
from app.services.profiles import ProfileStore, ai_error_detail, prepare_messages  # noqa: E402


class CheckStopped(RuntimeError):
    pass


class Budget:
    def __init__(self,path,maximum):
        self.path=path
        self.data=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"maximum":maximum,"calls":[],"results":[],"contacts":{}}
        self.maximum=min(maximum,self.data["maximum"])
        self.label=""

    def save(self):
        self.path.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding="utf-8")

    def request(self,create,kwargs):
        if len(self.data["calls"])>=self.maximum:
            raise ValueError("本次授权请求预算已用完")
        system=kwargs.get("messages",[{}])[0].get("content","")
        row={"label":self.label,"status":"started","prompt_sha256":hashlib.sha256(system.encode()).hexdigest()}
        self.data["calls"].append(row)
        self.save()  # Reserve before sending. Failed requests count as well.
        start=time.monotonic()
        try:
            response=create(**kwargs)
            row["status"]="completed"
            # This tool accepts fictional fixtures only; never enable on real chats.
            if response.choices:
                row["fictional_response_json"]=response.choices[0].message.content
            usage=getattr(response,"usage",None)
            if usage:
                row["usage"]={k:getattr(usage,k,None) for k in ("prompt_tokens","completion_tokens","total_tokens")}
            return response
        except Exception as exc:
            row.update(status="failed",error=ai_error_detail(exc)["message"])
            raise
        finally:
            row["seconds"]=round(time.monotonic()-start,2)
            self.save()


class BudgetClient:
    def __init__(self,client,budget):
        self.client,self.budget=client,budget
        self.base_url=client.base_url
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:budget.request(client.chat.completions.create,kw)))

    def with_options(self,**kwargs):
        return BudgetClient(self.client.with_options(**kwargs),self.budget)


def prepared(batch):
    return prepare_messages([{"speaker":"我" if m["speaker"]=="self" else "小林","content":m["text"]}
                             for m in batch["messages"]],"我","小林")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--config",type=Path,default=config.ENV_FILE)
    parser.add_argument("--cases-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--max-calls",type=int,choices=range(1,13),default=12)
    parser.add_argument("--stage",choices=["initial","continuous","heldout"],default="initial")
    args=parser.parse_args()
    if not args.live:
        print("Dry run only. Use --live to authorize fictional API requests; charges apply.")
        return
    config.load_env_file(args.config)
    if config.is_placeholder_key(config.api_key()):
        raise ValueError("服务端未配置真实API Key")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    budget=Budget(args.output,args.max_calls)
    budget.data["model"]=config.model_name()
    budget.data["provider_host"]=urlsplit(config.base_url()).hostname
    budget.data["prompt_version"]=cm.PROMPT_VERSION
    budget.save()
    real=OpenAI(api_key=config.api_key(),base_url=config.base_url(),max_retries=0,
                http_client=httpx.Client(trust_env=False))
    client=BudgetClient(real,budget)
    cases={}
    for split in ["development","evaluation"]:
        for line in (args.cases_dir/"inputs"/(split+".jsonl")).read_text(encoding="utf-8").splitlines():
            data=json.loads(line);cases[data["case_id"]]=data
    store=ProfileStore(args.output.parent/"fictional-model-check-data")
    done={r["label"] for r in budget.data["results"] if not r.get("error")}
    def run_case(case_id,index,baseline=False):
        label=("baseline_" if baseline else "v3_")+case_id+"_B"+str(index+1)
        if label in done:
            return
        batch=cases[case_id]["batches"][index]
        msgs=prepared(batch)
        chat_date=batch["occurred_at"][:10] if batch.get("occurred_at") else None
        budget.label=label
        if case_id not in budget.data["contacts"]:
            budget.data["contacts"][case_id]=store.create(case_id+"（虚构）")["id"]
            budget.save()
        p=store.get(budget.data["contacts"][case_id])
        try:
            if baseline:
                items,dropped=dossier.extract_cloud_dossier(msgs,{"facts":[]},client,config.model_name(),chat_date,"")
                result={"label":label,"items":items,"rejected_count":dropped,"profile_changed":False}
            else:
                items,rejected=cm.extract_ai(msgs,p,client,config.model_name(),chat_date,batch.get("context_hint",""))
                preview=cm.preview(store,p,msgs,items,chat_date,"","ai")
                if preview["token"]:
                    p=cm.commit(store,p["id"],preview["token"])
                result={"label":label,"items":items,"rejected_reasons":rejected,"changes":preview["changes"],
                        "state":[{k:f.get(k) for k in ("id","memory_type","topic","text","context","retention","observed_on","event_identity","event_date","validity","conflict")}
                                 for f in p["facts"]]}
            budget.data["results"].append(result)
            done.add(label)
            budget.save()
            print(label,"completed; valid items",len(items),flush=True)
        except Exception as exc:
            budget.data["results"].append({"label":label,"error":ai_error_detail(exc)["message"]})
            budget.save()
            print(label,"failed:",ai_error_detail(exc)["message"],flush=True)
            raise CheckStopped("实测遇到错误，已停止，未追加自动重试；请求已计入总预算") from None
    if args.stage=="initial":
        run_case("C01",0,True)
        run_case("C01",0)
    elif args.stage=="continuous":
        for cid in ["C01","C02","C05"]:
            for i in range(3):
                run_case(cid,i)
    else:
        run_case("C06",0)
        if len(budget.data["calls"])<budget.maximum:
            run_case("C07",0)
    real.close()
    print("Requests used:",len(budget.data["calls"]),"/",budget.maximum)


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,CheckStopped) else ai_error_detail(exc)["message"])
        sys.exit(1)
