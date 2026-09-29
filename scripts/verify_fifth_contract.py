#!/usr/bin/env python3
"""Additional provenance, input-hash, and summary checks on archived observations."""
import argparse,gzip,hashlib,itertools,json,math,statistics
from datetime import datetime
from pathlib import Path
import verify_fifth_audit as v

ROOT=Path(__file__).resolve().parents[1]

def same(a,b):assert math.isclose(a,b,abs_tol=1e-9,rel_tol=1e-10),(a,b)
def interval(values,record):
    assert len(values)==record['n']==5
    for a,b in zip(values,record['values']):same(a,b)
    mean=sum(values)/5
    sd=math.sqrt(sum((x-mean)**2 for x in values)/4)
    radius=2.7764451051977987*sd/math.sqrt(5)
    for name,value in [('mean',mean),('lower',mean-radius),('upper',mean+radius)]:same(value,record[name])

def payload_hashes(base):
    """Reconstruct the complete input once per byte-identical treatment group."""
    templates=v.templates(base);visited=set();payload_count=0
    for result_path in sorted(base.glob('block-*/*/result.json')):
        cell=result_path.parent;d=v.read(cell/'design.json')
        for phase in ['warmup','measured']:
            key=(d['block'],phase,d['policy']=='gate10')
            if key in visited:continue
            visited.add(key)
            receipts=v.read(cell/f'{phase}-receipts.json');step=100 if d['kind']=='placement' else 10
            count=d['rate_traces_s']*d['warmup_s' if phase=='warmup' else 'duration_s']
            for receipt in receipts:
                groups={};spans=0
                for i in range(receipt['begin'],min(receipt['begin']+step,count)):
                    identity=v.ident(d['block'],phase,i)
                    if d['policy']=='gate10' and not v.selected(identity,i,'gate10'):continue
                    ids=([f'{j:016x}' for j in range(1,6)] if d['kind']=='placement' else list(templates[phase][i%len(templates[phase])]))
                    for sid in ids:
                        span,resource,scope=v.expected(d,templates,phase,i,sid)
                        if d['kind']=='placement':
                            order=['traceId','spanId','parentSpanId','name','kind','startTimeUnixNano','endTimeUnixNano','attributes','status']
                            span={k:span[k] for k in order if k in span}
                        group=json.dumps([resource,scope],sort_keys=True)
                        if group not in groups:groups[group]={**resource,'scopeSpans':[{**scope,'spans':[]}]}
                        groups[group]['scopeSpans'][0]['spans'].append(span);spans+=1
                payload=json.dumps({'resourceSpans':list(groups.values())},separators=(',',':')).encode()
                assert hashlib.sha256(payload).hexdigest()==receipt['payload_sha256'],(cell,phase,receipt['begin'])
                assert spans==receipt['spans'];payload_count+=1
            print('input hashes verified',base.name,key,flush=True)
    return {'byte_identical_input_groups':len(visited),'reconstructed_input_payloads':payload_count}

def metrics(row,key):
    if key=='collector_cpu_s':return row['cpu_s']['collector']
    if key=='jaeger_cpu_s':return row['cpu_s']['jaeger']
    if key=='collector_rss_bytes':return row['max_rss_bytes']['collector']
    if key=='jaeger_rss_bytes':return row['max_rss_bytes']['jaeger']
    return row[key]

def summaries(base,summary):
    rows=[v.read(p) for p in sorted(base.glob('block-*/*/result.json'))]
    count=0
    def select(export,timeout,policy):return sorted([r for r in rows if (r['export'],r['timeout_ms'],r['policy'])==(export,timeout,policy)],key=lambda r:r['block'])
    for name,group in summary['groups'].items():
        export,timeout,policy=name.split('-');selected=select(export,int(timeout),policy)
        for key,record in group.items():interval([metrics(r,key) for r in selected],record);count+=1
    for name,contrast in summary['contrasts'].items():
        for key,record in contrast.items():
            if name=='timeout-interaction':
                pairs=[(select('dual',t,'tail100'),select('dual',t,'full')) for t in [1000,100]]
                values=[(metrics(a,key)-metrics(b,key))-(metrics(c,key)-metrics(d,key)) for (a,b),(c,d) in zip(zip(*pairs[0]),zip(*pairs[1]))]
            elif name.startswith('export-interaction:'):
                left,right=name.split(':')[1].split('-minus-');pairs=[(select(e,1000,left),select(e,1000,right)) for e in ['dual','file']]
                values=[(metrics(a,key)-metrics(b,key))-(metrics(c,key)-metrics(d,key)) for (a,b),(c,d) in zip(zip(*pairs[0]),zip(*pairs[1]))]
            else:
                factor,pair=name.split(':');left,right=pair.split('-minus-')
                export,timeout=(factor,1000) if summary['kind']=='placement' else ('dual',int(factor))
                l,r=select(export,timeout,left),select(export,timeout,right)
                values=([100*(1-a['cpu_s']['collector']/b['cpu_s']['collector']) for a,b in zip(l,r)] if key=='collector_cpu_saving_percent' else [metrics(a,key)-metrics(b,key) for a,b in zip(l,r)])
            interval(values,record);count+=1
    return count

def native_metadata(base):
    lengths=set();spans=0
    for p in base.glob('block-*/placement-*-collector10/traces.jsonl.gz'):
        with gzip.open(p,'rt') as f:
            for line in f:
                for resource in json.loads(line)['resourceSpans']:
                    for scope in resource['scopeSpans']:
                        for span in scope['spans']:
                            a=len(json.dumps(span,separators=(',',':')).encode());span.pop('traceState')
                            b=len(json.dumps(span,separators=(',',':')).encode());lengths.add(a-b);spans+=1
    assert lengths=={44} and spans>0
    return {'native_spans_checked':spans,'added_json_bytes_per_span':44}

def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=ROOT/'data/raw/fifth-audit-20260928')
    p.add_argument('--analysis',type=Path,default=ROOT/'data/derived/fifth-audit-20260928')
    p.add_argument('--freeze',type=Path,default=ROOT/'docs/fifth-audit-20260928/execution-freeze.json')
    p.add_argument('--batching-freeze',type=Path,default=ROOT/'docs/fifth-audit-20260928/batching-execution-freeze-v2.json')
    p.add_argument('--kind',choices=['placement','batching','both'],default='both')
    p.add_argument('--pilot-inputs',type=Path);p.add_argument('--receipt',type=Path,required=True);args=p.parse_args()
    if args.pilot_inputs:
        receipt={'status':'PASS',**payload_hashes(args.pilot_inputs)}
    else:
        kinds=['placement','batching'] if args.kind=='both' else [args.kind]
        freezes={kind:v.read(path) for kind,path in [('placement',args.freeze),('batching',args.batching_freeze)] if kind in kinds}
        for freeze in freezes.values():
            for name,digest in freeze['files'].items():assert v.sha(ROOT/name)==digest,name
        intervals=0;inputs=[];metadata=None
        for kind,seeds in [('placement',range(82001,82006)),('batching',range(83001,83006))]:
            if kind not in kinds:continue
            freeze=freezes[kind];freeze_path=args.freeze if kind=='placement' else args.batching_freeze
            base=args.raw/('placement-confirm-v1' if kind=='placement' else 'batching-confirm-v2');plan=v.read(base/'plan.json');env=v.read(base/'environment.json')
            assert (base/'executed-source/execution-freeze.json').read_bytes()==freeze_path.read_bytes()
            source_prefix='experiments/fifth_audit/' if kind=='placement' else 'experiments/fifth_audit_v2/'
            for name,digest in freeze['files'].items():
                if name.startswith(source_prefix):assert v.sha(base/'executed-source'/Path(name).name)==digest,(kind,name)
            assert env['binary_sha256']==freeze['binary_sha256']
            for name,digest in freeze['input_sha256'].items():assert v.sha(base/'input'/name)==digest
            rate=freeze['selected_rates_traces_s'][kind]
            factors=list(itertools.product(['file','dual'],[1000],['full','gate10','collector10','tail10'])) if kind=='placement' else list(itertools.product(['dual'],[100,1000],['full','tail100']))
            assert set(map(tuple,plan))=={(s,kind,*f,rate) for s in seeds for f in factors}
            for path in base.glob('block-*/*/design.json'):
                d=v.read(path);assert not d['pilot'] and datetime.fromisoformat(d['utc'])>datetime.fromisoformat(freeze['utc'])
                cell=path.parent;config=v.read(cell/'config.json');ep=v.read(cell/'endpoints.json')
                assert config['exporters']['file']['flush_interval']=='100ms'
                if d['policy'].startswith('tail'):
                    policies=config['processors']['tail_sampling']['policies']
                    assert policies[:2]==[{'name':'error','type':'status_code','status_code':{'status_codes':['ERROR']}},{'name':'latency','type':'latency','latency':{'threshold_ms':250}}]
                for name in ['collector','jaeger']:
                    a,b=[ep[t]['processes'][name] for t in ['before','after']]
                    assert (a['pid'],a['start_ticks'])==(b['pid'],b['start_ticks'])
                    assert a['read_monotonic']<b['read_monotonic']
                    assert v.read(cell/f'{name}-command.json')['environment']['GOMAXPROCS']=='2'
            inputs.append(payload_hashes(base))
            if kind=='placement':metadata=native_metadata(base)
            summary=v.read(args.analysis/f'{kind}-summary.json');intervals+=summaries(base,summary)
        receipt={'status':'PASS','frozen_file_counts_checked':{k:len(f['files']) for k,f in freezes.items()},'cells':sum(40 if k=='placement' else 20 for k in kinds),'summary_intervals_recomputed':intervals,'input_checks':inputs,'native_metadata':metadata}
    args.receipt.parent.mkdir(parents=True,exist_ok=True);args.receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
