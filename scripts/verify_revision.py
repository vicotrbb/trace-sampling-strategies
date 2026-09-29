#!/usr/bin/env python3
"""Independent validation of live-study receipts. Never imports experiment code."""
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import itertools
import sys

ROOT=Path(__file__).resolve().parents[1]
NAMES={'gateway.request','worker.call','worker.request','db.query','domain.validate'}

def read_json(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())

def attrs(span):
    return {x['key']:next(iter(x['value'].values())) for x in span.get('attributes',[])}

def independent_classification(spans):
    db=[s for s in spans if s['name']=='db.query']
    if any(attrs(s).get('db.response.status_code')=='42P01' for s in db): return ['sql_schema','postgresql']
    if any(int(s['endTimeUnixNano'])-int(s['startTimeUnixNano'])>=250000000 for s in db):
        return ['database_latency','postgresql']
    for span in spans:
        values=attrs(span)
        if span['name']=='domain.validate' and {'domain.expected','domain.actual'}<=set(values):
            if int(values['domain.expected'])!=int(values['domain.actual']):
                return ['domain_invariant',values.get('domain.owner','unknown')]
    return ['abstain','unknown']

def parse_exports(path):
    data=gzip.decompress(path.read_bytes())
    traces=defaultdict(dict)
    services={}
    for line in data.splitlines():
        for rs in json.loads(line)['resourceSpans']:
            service=next(x['value']['stringValue'] for x in rs['resource']['attributes'] if x['key']=='service.name')
            for ss in rs['scopeSpans']:
                for span in ss['spans']:
                    tid,sid=span['traceId'],span['spanId']
                    assert sid not in traces[tid], 'duplicate span'
                    traces[tid][sid]=span
                    services[(tid,sid)]=service
    return data,traces,services

def counters(path):
    result=Counter()
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):continue
        name=line.split('{')[0].split()[0]
        if not any(x in name for x in ['accepted_spans','refused_spans','sent_spans','send_failed','dropped_too_early']):continue
        exporter=re.search(r'exporter="([^"]+)"',line)
        result[(name,exporter.group(1) if exporter else '')]+=float(line.split()[-1])
    return result

def fnv(tid):
    value=0xcbf29ce484222325
    for byte in b'trace-study-v1'+bytes.fromhex(tid): value=((value^byte)*0x100000001b3)%(1<<64)
    return value

def protected(spans):
    return any(s.get('status',{}).get('code') in (2,'STATUS_CODE_ERROR') for s in spans) or max(int(s['endTimeUnixNano']) for s in spans)-min(int(s['startTimeUnixNano']) for s in spans)>=250000000

def verify_live(base):
    environment=read_json(base/'environment.json')
    # The earlier pilots predate explicit sysconf fields and ran on the same
    # archived x86-64 Linux node. Confirmatory receipts must contain them.
    if base.name.startswith('confirm'):
        assert environment['clock_ticks']>0 and environment['page_size']>0
    ticks=environment.get('clock_ticks',100)
    page_size=environment.get('page_size',4096)
    plan=read_json(base/'plan.json')
    expected={tuple(row) for row in plan}
    assert len(plan)==len(expected)
    if base.name.startswith('confirm'):
        assert expected==set(itertools.product(['checkout','documents'],['steady','bursty'],range(41001,41006),['full','head','tail']))
    paired_inputs={};unique_ids=set();unique_measured_ids=set()
    paths=list(base.glob('*/*/*/result.json'))
    actual=set()
    count=Counter()
    max_snapshot_duration=0
    for path in sorted(paths):
        cell=path.parent
        result=read_json(path)
        key=tuple(result[k] for k in ('app','regime','seed','policy'))
        assert key not in actual;actual.add(key)
        assert result['valid'] and not result['errors']
        for name,digest in result['source_sha256'].items():
            assert hashlib.sha256((base/'executed-source'/name).read_bytes()).hexdigest()==digest
        truth=read_json(cell/'truth.json')
        warm=read_json(cell/'warmup.json')
        assert len(truth)==result['duration_s']*result['offered_rate']
        assert len(warm)==result['warmup_s']*result['offered_rate']
        assert Counter(r['kind'] for r in truth)=={'normal':len(truth)*97//100,'sql_schema':len(truth)//100,'database_latency':len(truth)//100,'domain_invariant':len(truth)//100}
        pair_key=key[:3]
        inputs=[{k:r[k] for k in ['index','request_id','trace_id','kind','service','offset_s','payload','phase']} for r in truth+warm]
        if pair_key in paired_inputs: assert inputs==paired_inputs[pair_key], 'unpaired workload'
        else:
            paired_inputs[pair_key]=inputs
            ids={r['trace_id'] for r in truth+warm}
            assert not unique_ids.intersection(ids), 'trace ID reused across different block corpora'
            unique_ids.update(ids)
            unique_measured_ids.update(r['trace_id'] for r in truth)
        assert [r['index'] for r in truth]==list(range(len(truth)))
        ledger={r['trace_id']:r for r in truth+warm}
        assert len(ledger)==len(truth)+len(warm)
        predicted=read_json(cell/'predictions.json')
        outcomes=read_json(cell/'outcomes.json')
        assert {r['trace_id'] for r in outcomes}=={r['trace_id'] for r in truth}
        assert len(outcomes)==len(truth)
        for r in truth+warm:
            assert r['transport_ok']
            wanted_offset=r['index']/result['offered_rate'] if result['regime']=='steady' else r['index']//result['offered_rate']+(r['index']%result['offered_rate'])/(5*result['offered_rate'])
            assert r['offset_s']==wanted_offset
            assert math.isclose(r['schedule_lag_s'],r['started_s']-r['offset_s'],abs_tol=1e-9)
            assert r['latency_s']>=0 and r['schedule_lag_s']>=0
            assert r['trace_id']==hashlib.sha256(r['request_id'].encode()).digest()[:16].hex()
            assert r['response']['trace_id']==r['trace_id']
            assert set(r['response']['span_ids'])==NAMES
            assert len(set(r['response']['span_ids'].values()))==5
            sdk_keep=result['policy']!='head' or (int(r['trace_id'],16)&((1<<64)-1))<round(.1*(1<<64))
            assert r['response']['sampled']==sdk_keep
            assert r['http_status']==(500 if r['kind']=='sql_schema' else 200)
        data,traces,services=parse_exports(cell/'traces.jsonl.gz')
        assert hashlib.sha256(data).hexdigest()==result['export_json_sha256']
        assert len(data)==result['export_json_bytes_all']
        assert len(traces)==result['retained_all']
        assert sum(map(len,traces.values()))==result['export_spans_all']
        assert set(traces)<=set(ledger)
        assert set(predicted)==set(traces)
        for tid,spans in traces.items():
            row=ledger[tid]
            expected_ids=row['response']['span_ids']
            assert set(spans)==set(expected_ids.values()), 'incomplete exported trace'
            named={s['name']:s for s in spans.values()}
            assert set(named)==NAMES
            for child,parent in [('worker.call','gateway.request'),('worker.request','worker.call'),
                                  ('db.query','worker.request'),('domain.validate','worker.request')]:
                assert named[child].get('parentSpanId')==named[parent]['spanId']
            assert not named['gateway.request'].get('parentSpanId')
            for name,span in named.items():
                assert int(span['endTimeUnixNano'])>=int(span['startTimeUnixNano'])
                values=attrs(span)
                allowed={'db.system.name','server.address','db.operation.name','db.response.status_code','exception.type',
                         'domain.expected','domain.actual','domain.owner'}
                assert set(values)<=allowed, 'unplanned or leaking span attribute'
                assert not span.get('events') and not span.get('links'), 'unplanned evidence channel'
                assert services[(tid,span['spanId'])]==result['app']+('-gateway' if name in ('gateway.request','worker.call') else '-worker')
            assert predicted[tid]==independent_classification(list(spans.values()))
        if result['policy'] in ('full','head'):
            expected_ids={tid for tid,row in ledger.items() if row['response']['sampled']}
            assert set(traces)==expected_ids
        else:
            # All actual protected cases are checked using the full-input receiver count,
            # known injected error/delay classes, and hashes for unprotected observed traces.
            cfg=read_json(cell/'config.json')
            percentage=next(p['probabilistic']['sampling_percentage'] for p in cfg['processors']['tail_sampling']['policies'] if p['type']=='probabilistic')
            threshold=int(Fraction.from_float(percentage/100)*((1<<64)-1))
            assert min(abs(fnv(tid)-threshold) for tid in ledger)>2
            mandatory={tid for tid,row in ledger.items() if row['kind'] in ('sql_schema','database_latency')}
            background={tid for tid in ledger if fnv(tid)<=threshold}
            assert mandatory|background<=set(traces)
            assert all(protected(list(traces[t].values())) for t in set(traces)-(mandatory|background))
        for outcome in outcomes:
            tid=outcome['trace_id'];row=ledger[tid]
            pred=predicted.get(tid,['abstain','unknown'])
            assert outcome['kind']==row['kind'] and outcome['service']==row['service']
            assert outcome['retained']==(tid in traces)
            assert outcome['complete']==(tid in traces)
            assert outcome['prediction']==pred
            assert outcome['correct']==(row['kind']!='normal' and pred==[row['kind'],row['service']])
        assert result['retained_measured']==sum(o['retained'] for o in outcomes)
        assert result['false_accusations']==sum(o['kind']=='normal' and o['prediction'][0]!='abstain' for o in outcomes)
        for kind in ('normal','sql_schema','database_latency','domain_invariant'):
            assert result['diagnosis_by_kind'][kind]=={'n':sum(o['kind']==kind for o in outcomes),'correct':sum(o['correct'] for o in outcomes if o['kind']==kind)}
        before,after=counters(cell/'metrics-before.txt'),counters(cell/'metrics-after.txt')
        delta={key:after[key]-before[key] for key in set(before)|set(after)}
        admitted=sum(r['response']['sampled'] for r in truth)*5
        exported=sum(o['retained'] for o in outcomes)*5
        assert delta.get(('otelcol_receiver_accepted_spans_total',''),0)==admitted
        assert delta.get(('otelcol_exporter_sent_spans_total','file'),0)==exported
        assert delta.get(('otelcol_exporter_sent_spans_total','otlphttp'),0)==exported
        assert all(value==0 for (name,exporter),value in delta.items() if any(x in name for x in ['refused','failed','dropped_too_early']))
        for phase in ('before','after'):
            snap=read_json(cell/'resource-endpoints.json')[phase]
            max_snapshot_duration=max(max_snapshot_duration,snap['end_monotonic']-snap['begin_monotonic'])
            for sample in snap['processes'].values():
                fields=sample['raw_stat'].split(') ',1)[1].split()
                assert sample['cpu_s']==(int(fields[11])+int(fields[12]))/ticks
                assert sample['rss_bytes']==int(fields[21])*page_size
                assert sample['start_ticks']==int(fields[19])
            raw_pg=snap['postgres']['raw'].splitlines()
            cpu=dict(line.split() for line in raw_pg[raw_pg.index('CPU')+1:raw_pg.index('MEMORY')])
            assert snap['postgres']['cpu_s']==int(cpu['usage_usec'])/1e6
            assert snap['postgres']['memory_current']==int(raw_pg[raw_pg.index('MEMORY')+1])
        endpoints=read_json(cell/'resource-endpoints.json')
        samples=read_json(cell/'resource-samples.json')
        assert samples and not any('error' in sample for sample in samples)
        assert endpoints['after']['begin_monotonic']>endpoints['before']['end_monotonic']
        for name in endpoints['before']['processes']:
            a=endpoints['before']['processes'][name];b=endpoints['after']['processes'][name]
            assert a['pid']==b['pid'] and a['start_ticks']==b['start_ticks'] and b['cpu_s']>=a['cpu_s']
        for query_name in ('query-before-restart','query-after-restart'):
            query=read_json(cell/(query_name+'.json.gz'))
            assert not query.get('errors')
            queried={t['traceID']:t for t in query['data']}
            assert len(queried)==len(query['data']) and set(queried)==set(traces)
            for tid,trace in queried.items():
                assert len(trace['spans'])==len(traces[tid]), 'duplicate or missing backend span'
                assert {s['spanID'] for s in trace['spans']}==set(traces[tid])
                for backend_span in trace['spans']:
                    span=traces[tid][backend_span['spanID']]
                    assert backend_span['operationName']==span['name']
                    refs=backend_span.get('references',[])
                    expected_parent=span.get('parentSpanId')
                    assert refs==([{'refType':'CHILD_OF','traceID':tid,'spanID':expected_parent}] if expected_parent else [])
                    assert trace['processes'][backend_span['processID']]['serviceName']==services[(tid,backend_span['spanID'])]
                    tags={x['key']:x['value'] for x in backend_span['tags']}
                    for name,value in attrs(span).items():
                        assert str(tags[name])==str(value), ('backend attribute mismatch',name,tags,value)
                    assert abs(backend_span['duration']-(int(span['endTimeUnixNano'])-int(span['startTimeUnixNano']))/1000)<=2
                    assert abs(backend_span['startTime']-int(span['startTimeUnixNano'])//1000)<=1
        count['cells']+=1;count['measured_requests']+=len(truth);count['measured_faults']+=sum(r['kind']!='normal' for r in truth)
        count['export_trace_occurrences']+=len(traces);count['export_span_occurrences']+=sum(map(len,traces.values()))
    assert actual==expected, (len(actual),len(expected))
    return {'status':'PASS',**dict(count),'unique_trace_ids_including_warmup':len(unique_ids),
            'unique_measured_trace_ids':len(unique_measured_ids),'max_snapshot_span_s':max_snapshot_duration}

if __name__=='__main__':
    print(json.dumps(verify_live(Path(sys.argv[1])),indent=2))
