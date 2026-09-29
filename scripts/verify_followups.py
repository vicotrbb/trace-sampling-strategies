#!/usr/bin/env python3
"""Independent reconstruction of calibration, matched probes, and offline interventions."""
from collections import Counter, defaultdict
import gzip
import hashlib
import itertools
from fractions import Fraction
import json
from pathlib import Path
import sys
from verify_artifact import has_evidence, raw_counters
from verify_revision import read_json, parse_exports, fnv, protected, independent_classification, attrs

ROOT=Path(__file__).resolve().parents[1]

def sources(base):
    recorded=base/'confirm-v1/executed-source'
    pairs=[(base/'calibration/source.py',recorded/'calibration.py'),
           (base/'matched-probes/executed-source.py',recorded/'matched_probes.py'),
           (base/'matched-probes/executed-runner.py',ROOT/'experiments/runner.py'),
           (base/'counterfactual/executed-source.py',recorded/'counterfactual.py'),
           (base/'counterfactual/executed-diagnose.py',recorded/'diagnose.py')]
    for observed,expected in pairs:
        assert observed.read_bytes()==expected.read_bytes(), ('executed source mismatch',observed)
    frozen_checks=0
    if base.name=='revision-20260924':
        frozen=read_json(ROOT/'docs/revision-20260924/confirmatory-freeze.json')['sha256']
        for path,digest in frozen.items():
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
            if path.startswith('experiments/revision/') and path.endswith('.py'):
                assert hashlib.sha256((recorded/Path(path).name).read_bytes()).hexdigest()==digest
            frozen_checks+=1
    return {'followup_source_matches':len(pairs),'frozen_file_matches':frozen_checks}

def parse_payload(path):
    payload=gzip.decompress(path.read_bytes())
    rec=defaultdict(dict)
    for resource in json.loads(payload).get('resourceSpans',[]):
        for scope in resource['scopeSpans']:
            for span in scope['spans']:
                assert span['spanId'] not in rec[span['traceId']]
                rec[span['traceId']][span['spanId']]=span
    return payload,rec

def calibration(base):
    data=read_json(base/'calibration/blocks.json')
    wanted=set(itertools.product(range(31001,31031),['python','sha256'],
                                 ['trace-study-v1','revision-salt-2','revision-salt-3','revision-salt-4'],
                                 ['fnv1a','blake2b']))
    assert len(data)==len(wanted)==480
    assert {tuple(r[k] for k in ['seed','stream','salt','hash']) for r in data}==wanted
    cached={};all_ids=set()
    for row in data:
        assert (row['m'],row['incidents'],row['traces'])==(5,2000,10000)
        key=(row['seed'],row['stream'])
        if key not in cached:
            ids=read_json(base/'calibration'/f'ids-{key[0]}-{key[1]}.json.gz')
            assert len(ids)==len(set(ids))==10000
            assert all(len(tid)==32 and 0<int(tid,16)<2**128 for tid in ids)
            assert not all_ids.intersection(ids);all_ids.update(ids);cached[key]=ids
        ids=cached[key]
        assert row['id_sha256']==hashlib.sha256('\n'.join(ids).encode()).hexdigest()
        h=[]
        for tid in ids:
            b=row['salt'].encode()+bytes.fromhex(tid)
            if row['hash']=='blake2b':value=int.from_bytes(hashlib.blake2b(b,digest_size=8).digest(),'big')
            else:
                value=0xcbf29ce484222325
                for byte in b:value=((value^byte)*0x100000001b3)%(1<<64)
            h.append(value)
        threshold=int((.08/.98)*((1<<64)-1))
        assert min(abs(v-threshold) for v in h)>4096
        kept=[value<=threshold for value in h]
        hist=Counter(sum(kept[i:i+5]) for i in range(0,len(ids),5))
        assert row['histogram']==[hist[i] for i in range(6)]
        assert row['retained_traces']==sum(kept)
        head=[v<int(.1*(1<<64)) for v in h]
        assert row['shared_head_incidents']==sum(any(head[i:i+5]) for i in range(0,len(ids),5))
        assert row['shared_tail_incidents']==2000-hist[0]
        assert row['shared_head_incidents']>=row['shared_tail_incidents']
    return {'cells':len(data),'unique_ids':len(all_ids),'reconstructed_hash_decisions':len(data)*10000}

def matched(base):
    paths=list((base/'matched-probes').glob('*/*/result.json'))
    assert len(paths)==48
    wanted=set(itertools.product([32001,32002,32003],[False,True],[False,True],[False,True],[False,True]))
    found=set();content_hashes=defaultdict(set);counts=[]
    for path in paths:
        row=read_json(path);cell=path.parent
        key=tuple(row[k] for k in ['seed','root_error','late','cache','churn'])
        assert key not in found;found.add(key)
        payload,inputs=parse_payload(cell/'input.json.gz')
        truth=read_json(cell/'truth.json')
        assert len(inputs)==len(truth)==200
        assert row['input_content_sha256']==hashlib.sha256(payload).hexdigest()
        content_hashes[(row['seed'],row['root_error'])].add(row['input_content_sha256'])
        for tid,spans in inputs.items():
            assert len(spans)==7 and set(spans)==set(truth[tid]['span_ids'])
            named={s['name']:s for s in spans.values()}
            assert named['gateway']['status']['code']==(2 if row['root_error'] else 1)
            assert named['database']['status']['code']==2
        churn_payload,churn=parse_payload(cell/'churn-input.json.gz')
        assert len(churn)==(300 if row['churn'] else 0)
        assert all(len(spans)==5 for spans in churn.values())
        data,rec,_=parse_exports(cell/'traces.jsonl.gz')
        assert set(rec)<=set(truth)
        assert row['duplicates']==0
        assert hashlib.sha256(data).hexdigest()==row['export_json_sha256']
        for tid,spans in rec.items():
            assert set(spans)<=set(inputs[tid])
            for sid,span in spans.items():
                original=inputs[tid][sid]
                for name in ['traceId','spanId','name','startTimeUnixNano','endTimeUnixNano']:
                    assert str(span[name])==str(original[name])
                assert span.get('parentSpanId')==original.get('parentSpanId')
                assert attrs(span)==attrs(original)
                codes={'STATUS_CODE_UNSET':0,'STATUS_CODE_OK':1,'STATUS_CODE_ERROR':2}
                output_code=span.get('status',{}).get('code',0)
                assert codes.get(output_code,output_code)==original.get('status',{}).get('code',0)
        assert row['retained_error_ids']==len(rec)
        assert row['retained_spans']==sum(map(len,rec.values()))
        assert row['complete']==sum(set(spans)==set(truth[tid]['span_ids']) for tid,spans in rec.items())
        assert row['witnesses']==sum(has_evidence(spans,'error') for spans in rec.values())
        before,after=raw_counters(cell/'metrics-before.txt'),raw_counters(cell/'metrics-after.txt')
        delta={k:after[k]-before[k] for k in set(before)|set(after)}
        assert delta.get('otelcol_receiver_accepted_spans_total',0)==row['input_spans']==1400+1500*row['churn']
        assert delta.get('otelcol_exporter_sent_spans_total',0)==row['retained_spans']
        assert all(v==0 for k,v in delta.items() if 'refused' in k or 'send_failed' in k)
        counts.append({**{k:row[k] for k in ['seed','root_error','late','cache','churn']},
                       'early_drops':sum(v for k,v in delta.items() if 'dropped_too_early' in k)})
    assert found==wanted
    assert all(len(values)==1 for values in content_hashes.values()),'input content changed between timing/cache/churn cells'
    return {'cells':48,'matched_payload_groups':len(content_hashes),'early_drop_receipts':counts}

def offline(base):
    curves=read_json(base/'counterfactual/curves.json')
    ablations=read_json(base/'counterfactual/ablations.json.gz')
    assert len(curves)==800 and len(ablations)==100
    groups=defaultdict(list);masks=defaultdict(list)
    for row in curves:groups[tuple(row[k] for k in ['app','regime','seed'])].append(row)
    for row in ablations:masks[tuple(row[k] for k in ['app','regime','seed'])].append(row)
    assert len(groups)==len(masks)==20
    for key,rows in groups.items():
        app,regime,seed=key
        cell=base/'confirm-v1'/f'{app}-{regime}'/f'seed-{seed}'/'full'
        truth=read_json(cell/'truth.json')
        _,all_traces,_=parse_exports(cell/'traces.jsonl.gz')
        traces={r['trace_id']:list(all_traces[r['trace_id']].values()) for r in truth}
        flags={tid:protected(spans) for tid,spans in traces.items()}
        alpha=sum(flags.values())/len(flags)
        expected=defaultdict(list)
        original={tid:independent_classification(spans) for tid,spans in traces.items()}
        for r in truth:
            if r['kind']!='normal':expected[r['kind']].append(r)
        def succeeds(row,pred):
            return pred.get(row['trace_id'],['abstain','unknown'])==[row['kind'],row['service']]
        h_native={tid:int(tid,16)&((1<<64)-1) for tid in traces}
        t_native={tid:fnv(tid) for tid in traces}
        common={tid:int.from_bytes(hashlib.sha256(b'common:'+bytes.fromhex(tid)).digest()[:8],'big') for tid in traces}
        assert len(rows)==40
        wanted=set(itertools.product(['native','shared'],['head','tail'],[.01,.05,.10,.25,.50,.75,.90,.95,.99,1.0]))
        assert {tuple(r[k] for k in ['priorities','policy','rate']) for r in rows}==wanted
        for row in rows:
            assert row['alpha']==alpha
            assert row['feasible']==(row['policy']=='head' or row['rate']>=alpha)
            if not row['feasible']:continue
            hp=h_native if row['priorities']=='native' else common
            tp=t_native if row['priorities']=='native' else common
            r=(row['rate']-alpha)/(1-alpha)
            selected={tid for tid in traces if (hp[tid]<round(row['rate']*2**64) if row['policy']=='head' else flags[tid] or tp[tid]<=int(r*((1<<64)-1)))}
            if row['priorities']=='native' and row['policy']=='tail':
                # Go receives a percentage, divides by 100, then rounds a 64-bit
                # big.Float product before truncation. Check every observed ID is
                # safely away from that boundary and both selections agree.
                go_ratio=(r*100)/100
                go_floor=int(Fraction.from_float(go_ratio)*((1<<64)-1))
                assert min(abs(value-go_floor) for value in t_native.values())>4096
                go_selected={tid for tid in traces if flags[tid] or t_native[tid]<=go_floor}
                assert selected==go_selected
            predictions={tid:original[tid] for tid in selected}
            assert row['retained']==len(selected) and row['offered']==len(traces)
            for kind,cases in expected.items():
                grouped=[cases[i:i+5] for i in range(0,len(cases),5)]
                actual={'n':len(cases),'baseline':sum(succeeds(r,original) for r in cases),
                        'correct':sum(succeeds(r,predictions) for r in cases),'groups':len(grouped),
                        'baseline_groups':sum(any(succeeds(r,original) for r in g) for g in grouped),
                        'correct_groups':sum(any(succeeds(r,predictions) for r in g) for g in grouped)}
                assert row['by_kind'][kind]==actual
        expected_masks={'none','remove_gateway','remove_database','remove_validator','evidence_leaf_only'}
        assert len(masks[key])==5 and {r['mask'] for r in masks[key]}==expected_masks
        ledger={r['trace_id']:r for r in truth}
        for item in masks[key]:
            output=item['outcomes']
            assert len(output)==len(ledger) and {r['trace_id'] for r in output}==set(ledger)
            for result in output:
                row=ledger[result['trace_id']];spans=traces[result['trace_id']]
                mask=item['mask']
                if mask in ('remove_gateway','remove_database','remove_validator'):
                    remove={'remove_gateway':'gateway.request','remove_database':'db.query','remove_validator':'domain.validate'}[mask]
                    spans=[s for s in spans if s['name']!=remove]
                elif mask=='evidence_leaf_only':
                    keep='domain.validate' if row['kind']=='domain_invariant' else 'db.query'
                    spans=[s for s in spans if s['name']==keep]
                prediction=independent_classification(spans)
                assert result['prediction']==prediction and result['kind']==row['kind']
                assert result['complete']==(len(spans)==5)
                assert result['correct']==(row['kind']!='normal' and prediction==[row['kind'],row['service']])
    return {'curve_cells':800,'ablation_cells':100,'ablation_predictions':300000}

if __name__=='__main__':
    base=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'data/raw/revision-20260924'
    print(json.dumps({'status':'PASS','sources':sources(base),'calibration':calibration(base),'matched':matched(base),'offline':offline(base)},indent=2))
