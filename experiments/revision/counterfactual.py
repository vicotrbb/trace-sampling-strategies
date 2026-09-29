#!/usr/bin/env python3
"""Whole-trace selection and partial-span interventions on full live exports."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path
from diagnose import diagnose

RATES = [.01,.05,.10,.25,.50,.75,.90,.95,.99,1.0]

def fnv(tid):
    h=14695981039346656037
    for b in b'trace-study-v1'+bytes.fromhex(tid): h=((h^b)*1099511628211)&((1<<64)-1)
    return h

def parse(path):
    records=defaultdict(list)
    for line in gzip.decompress(path.read_bytes()).splitlines():
        for resource in json.loads(line)['resourceSpans']:
            for scope in resource['scopeSpans']:
                for span in scope['spans']: records[span['traceId']].append(span)
    return records

def protected(spans):
    return any(s.get('status',{}).get('code') in (2,'STATUS_CODE_ERROR') for s in spans) or (
        max(int(s['endTimeUnixNano']) for s in spans)-min(int(s['startTimeUnixNano']) for s in spans)>=250000000)

def main():
    assert os.environ.get('STUDY_CONTEXT')=='homelab'
    base=Path('/work/revision/confirm-v1')
    out=Path('/work/revision/counterfactual');out.mkdir(exist_ok=False)
    (out/'executed-source.py').write_bytes(Path(__file__).read_bytes())
    (out/'executed-diagnose.py').write_bytes((Path(__file__).parent/'diagnose.py').read_bytes())
    curves=[]; ablations=[]
    for result_path in sorted(base.glob('*/*/full/result.json')):
        cell=result_path.parent
        result=json.loads(result_path.read_text())
        truth=json.loads((cell/'truth.json').read_text())
        rec=parse(cell/'traces.jsonl.gz')
        chosen={r['trace_id']:rec[r['trace_id']] for r in truth}
        flags={tid:protected(spans) for tid,spans in chosen.items()}
        alpha=sum(flags.values())/len(flags)
        original={tid:diagnose(spans) for tid,spans in chosen.items()}
        fault_rows=[r for r in truth if r['kind']!='normal']
        def success(row,predictions):
            return tuple(predictions.get(row['trace_id'],('abstain','unknown')))==(row['kind'],row['service'])
        for priorities in ('native','shared'):
            h={tid:(int(tid,16)&((1<<64)-1)) if priorities=='native' else
                      int.from_bytes(hashlib.sha256(b'common:'+bytes.fromhex(tid)).digest()[:8],'big') for tid in chosen}
            t={tid:fnv(tid) if priorities=='native' else h[tid] for tid in chosen}
            for policy in ('head','tail'):
                for rate in RATES:
                    info={k:result[k] for k in ('app','regime','seed')}
                    info.update(priorities=priorities,policy=policy,rate=rate,alpha=alpha,feasible=policy=='head' or rate>=alpha)
                    if not info['feasible']: curves.append(info);continue
                    bg=(rate-alpha)/(1-alpha) if policy=='tail' else None
                    keep={tid for tid in chosen if ((h[tid]<round(rate*2**64)) if policy=='head' else
                         (flags[tid] or t[tid]<=int(bg*((1<<64)-1))))}
                    predictions={tid:original[tid] for tid in keep}
                    by_kind={}
                    for kind in ('sql_schema','database_latency','domain_invariant'):
                        rows=[r for r in fault_rows if r['kind']==kind]
                        groups=[rows[i:i+5] for i in range(0,len(rows),5)]
                        assert all(len(group)==5 for group in groups)
                        by_kind[kind]={'n':len(rows),'baseline':sum(success(r,original) for r in rows),
                                       'correct':sum(success(r,predictions) for r in rows),
                                       'groups':len(groups),
                                       'baseline_groups':sum(any(success(r,original) for r in group) for group in groups),
                                       'correct_groups':sum(any(success(r,predictions) for r in group) for group in groups)}
                    info.update(retained=len(keep),offered=len(chosen),by_kind=by_kind)
                    curves.append(info)
        for mask in ('none','remove_gateway','remove_database','remove_validator','evidence_leaf_only'):
            outcomes=[]
            for row in truth:
                spans=chosen[row['trace_id']]
                if mask=='remove_gateway': spans=[s for s in spans if s['name']!='gateway.request']
                elif mask=='remove_database': spans=[s for s in spans if s['name']!='db.query']
                elif mask=='remove_validator': spans=[s for s in spans if s['name']!='domain.validate']
                elif mask=='evidence_leaf_only':
                    name='domain.validate' if row['kind']=='domain_invariant' else 'db.query'
                    spans=[s for s in spans if s['name']==name]
                prediction=diagnose(spans)
                outcomes.append({'trace_id':row['trace_id'],'kind':row['kind'],'complete':len(spans)==5,
                                 'prediction':prediction,'correct':row['kind']!='normal' and tuple(prediction)==(row['kind'],row['service'])})
            info={k:result[k] for k in ('app','regime','seed')}
            info.update(mask=mask,outcomes=outcomes)
            ablations.append(info)
    (out/'curves.json').write_text(json.dumps(curves,indent=2)+'\n')
    (out/'ablations.json.gz').write_bytes(gzip.compress(json.dumps(ablations).encode(),mtime=0))
    print('COUNTERFACTUAL_COMPLETE',len(curves),len(ablations),flush=True)
if __name__=='__main__': main()
