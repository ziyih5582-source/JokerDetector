# ruff: noqa: E402
# Standalone script resolves the backend import path before importing app modules.
"""Offline replay of a fixed extraction + verification trace under current guards."""
import argparse
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.services import communication as cm
from app.services.profiles import ProfileStore, public_profile
from check_archive_live import check_gold, prepare


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('ledger',type=Path)
    parser.add_argument('--case',default='L20')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    data=json.loads(args.ledger.read_text(encoding='utf-8'))
    case=next(c for c in json.loads((ROOT/'backend/tests/fixtures/archive_suite.json').read_text(encoding='utf-8')) if c['id']==args.case)
    store=ProfileStore(args.output.parent/'archive-v5-offline-replay-data')
    p=store.create(case['name']);results=[]
    for i,step in enumerate(case['steps']):
        extraction=next(c for c in data['calls'] if c['label']==f'new:{args.case}:{i+1}' and c['stage']=='extract')
        verified=next(c for c in data['calls'] if c['label']==f'cached:{args.case}:{i+1}' and c['stage']=='verify')
        def create(_extraction=extraction,_verified=verified,_profile=p,**kwargs):
            payload=json.loads(kwargs['messages'][1]['content'])
            if payload['stage']=='extract':
                content=_extraction['response']
            elif payload['stage']=='verify':
                output=json.loads(_verified['response'].strip().removesuffix('```'))
                old={f['id']:f for f in _verified['payload'].get('existing',[])}
                for check in output['checks']:
                    prior=old.get(check.get('target_id'))
                    if prior:
                        matches=[f for f in _profile['facts'] if all(f.get(k)==prior.get(k) for k in ('subject','memory_type','topic'))]
                        check['target_id']=matches[0]['id'] if len(matches)==1 else check['target_id']
                content=json.dumps(output,ensure_ascii=False)
            else:
                raise ValueError('No recorded response for this additional read')
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=content))])
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        client.with_options=lambda _client=client,**kw:_client
        msgs=prepare(step)
        items,rejected=cm.extract_ai(msgs,p,client,'recorded',step['day'],case['scene'])
        preview=cm.preview(store,p,msgs,items,step['day'],case['scene'])
        if preview['token']:
            p=cm.commit(store,p['id'],preview['token'])
        results.append({'label':f'offline:{args.case}:{i+1}','source':case['source'],'items':items,'rejected':rejected,
                        'checks':check_gold(step,items,p),'profile':public_profile(p),
                        'source_verification_label':verified['label'],'fictional_payload':{'messages':msgs,
                         'existing':copy.deepcopy(verified['payload'].get('existing',[])), 'chat_date':step['day'],'scene_hint':case['scene']}})
        print(results[-1]['label'],'facts',len(p['facts']),'checks',results[-1]['checks'])
    args.output.write_text(json.dumps({'offline_only':True,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
