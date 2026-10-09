# ruff: noqa: E402
# Standalone script resolves the backend import path before importing app modules.
"""Export attributed fictional recorded results for free local UI replay."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from check_archive_live import prepare


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('ledger',type=Path)
    parser.add_argument('--offline',type=Path)
    args=parser.parse_args()
    data=json.loads(args.ledger.read_text(encoding='utf-8'))
    corpus=json.loads((ROOT/'backend/tests/fixtures/archive_suite.json').read_text(encoding='utf-8'))
    selected={}
    priority={'new':0,'recheck':1,'final':2,'acceptance':3,'cached':4}
    for r in data['results']:
        mode,cid,number=r['label'].split(':')
        if mode=='baseline' or r.get('error'):
            continue
        key=(cid,int(number))
        if key not in selected or priority.get(mode,0)>=priority.get(selected[key]['label'].split(':')[0],0):
            selected[key]=r
    if args.offline:
        for r in json.loads(args.offline.read_text(encoding='utf-8'))['results']:
            _,cid,number=r['label'].split(':')
            selected[cid,int(number)]=r
    records=[];cases=[]
    nice={'S01':'小夏 · 两段短聊','L20':'小禾 · 丰富聊天持续完善','O02':'小舟 · 表达与观点',
          'I01':'小岚 · 兴趣与边界','E01':'陈叔 · 沟通习惯','W01':'周老师 · 任务变更'}
    for c in corpus:
        # Public CC-NC research excerpts remain evaluation-only, not product demos.
        if c['source']=='DialogSum public research corpus' or not all((c['id'],i+1) in selected for i in range(len(c['steps']))):
            continue
        cid='V5-'+c['id']
        cases.append({**c,'id':cid,'name':nice.get(c['id'],c['name'])})
        for i,s in enumerate(c['steps']):
            result=selected[c['id'],i+1]
            calls=[r for r in data['calls'] if r['label']==result['label']]
            prior=[f for r in calls if r['stage']=='verify' for f in r['payload'].get('existing',[])]
            items=[{k:v for k,v in row.items() if k!='last_message_id'} for row in result['items']]
            records.append({'label':cid+':'+str(i+1),'verified':True,'offline_revalidation':result['label'].startswith('offline:'),
                            'source_label':result['label'],'fictional_payload':{'messages':prepare(s),'existing':prior,
                             'chat_date':s['day'],'scene_hint':c['scene']},
                            'fictional_response':json.dumps({'items':items},ensure_ascii=False)})
            if result.get('fictional_payload'):
                records[-1]['fictional_payload']=result['fictional_payload']
    out=ROOT/'backend/tests/fixtures/archive_preview_recordings.json'
    out.write_text(json.dumps({'cases':cases,'calls':records,'note':'Fictional recorded outputs, no live calls; public research data excluded'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Fictional replay groups',len(cases))


if __name__=='__main__':
    main()
