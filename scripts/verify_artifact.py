#!/usr/bin/env python3
"""Read-only validation of raw exports, ground truth, counters and head decisions."""
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import sys
import math

ROOT=Path(__file__).resolve().parents[1]
SEEDS = [1101, 1102, 1103, 1104, 1105]
POLICIES = [('full',1.0)] + [('head',p) for p in [.001,.01,.025,.05,.1,.25,.5]] + [('tail',p) for p in [.02,.025,.05,.1,.25,.5]]

def head_selection(tid, probability):
    priority = int.from_bytes(hashlib.blake2b(b'head:' + tid.encode('ascii'), digest_size=8).digest(), 'big')
    return priority < math.floor(probability * (1 << 64))

def has_evidence(spans, kind):
    # Implemented independently of the workload generator and its evaluator.
    named = {span['name']: span for span in spans.values()}
    required = {'gateway', 'api', 'db-client', 'database', 'validator'}
    if not required.issubset(named): return False
    for child, parent in [('api','gateway'),('db-client','api'),('database','db-client'),('validator','api')]:
        if named[child].get('parentSpanId') != named[parent]['spanId']: return False
    def attrs(name):
        return {a['key']: next(iter(a['value'].values())) for a in named[name].get('attributes', [])}
    if kind == 'error':
        return attrs('database').get('db.sqlstate') == '08006' and named['database'].get('status',{}).get('code') in (2,'STATUS_CODE_ERROR')
    if kind == 'latency':
        leaf = named['database']
        return attrs('database').get('db.wait_reason') == 'lock' and int(leaf['endTimeUnixNano']) - int(leaf['startTimeUnixNano']) >= 250000000
    leaf_attrs = attrs('validator')
    return kind == 'semantic' and 'validation.actual' in leaf_attrs and 'validation.expected' in leaf_attrs and leaf_attrs['validation.actual'] != leaf_attrs['validation.expected']

def raw_counters(path):
    counters = Counter()
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        name = line.split('{',1)[0].split()[0]
        if any(part in name for part in ('accepted_spans','sent_spans','refused_spans','send_failed','dropped_too_early')):
            counters[name] += float(line.split()[-1])
    return counters

def verify_incident_universe(reported, expected):
    names = [row['incident'] for row in reported]
    assert len(names) == len(set(names)), 'duplicate incident entries'
    assert set(names) == set(expected), 'missing or unknown incidents'
    for row in reported:
        actual = expected[row['incident']]
        assert all(row[key] == actual[key] for key in ('kind','m','witnesses'))


def fnv1a(tid, salt='trace-study-v1'):
    h=14695981039346656037
    for byte in salt.encode()+bytes.fromhex(tid):
        h=((h^byte)*1099511628211)&((1<<64)-1)
    return h


def validate(raw):
    cells=list(raw.glob('main/seed-*/*/result.json'))
    assert len(cells)==70, len(cells)
    cases=[json.loads(path.read_text()) for path in cells]
    expected={(seed,strategy,p) for seed in SEEDS for strategy,p in POLICIES}
    actual=[(x['seed'],x['strategy'],x['p']) for x in cases]
    assert set(actual)==expected and len(actual)==len(set(actual))
    for seed in SEEDS:
        ledger=json.loads((raw/'main'/f'truth-{seed}.json').read_text())
        assert len(ledger)==20000
        assert Counter(v['kind'] for v in ledger.values())=={'normal':19400,'error':200,'latency':200,'semantic':200}
        for tid,item in ledger.items():
            assert len(tid)==32 and int(tid,16)>0
            ids=item['span_ids']
            assert len(ids)==len(set(ids)) and all(len(s)==16 and int(s,16)>0 for s in ids)
    hashes={}
    for seed in SEEDS:
        ledger=json.loads((raw/'main'/f'truth-{seed}.json').read_text())
        hashes[seed]={tid:fnv1a(tid) for tid in ledger}
    traces=spans=tail_checks=0
    for path in sorted(cells):
        result=json.loads(path.read_text()); seed=result['seed']
        truth=json.loads((raw/'main'/f'truth-{seed}.json').read_text())
        archive=(path.parent/'traces.jsonl.gz').read_bytes()
        assert len(archive)==result['archive_gzip_bytes']
        assert hashlib.sha256(archive).hexdigest()==result['export_gzip_sha256']
        data=gzip.decompress(archive)
        assert hashlib.sha256(data).hexdigest()==result['export_json_sha256']
        assert len(data)==result['export_json_bytes']
        rec=defaultdict(dict)
        for line in data.splitlines():
            for resource in json.loads(line).get('resourceSpans',[]):
                for scope in resource.get('scopeSpans',[]):
                    for span in scope.get('spans',[]):
                        tid,sid=span['traceId'].lower(),span['spanId'].lower()
                        assert tid in truth and sid not in rec[tid]
                        rec[tid][sid]=span
        recorded_ids=json.loads((path.parent/'retained.json').read_text())
        assert {tid:set(spans) for tid,spans in rec.items()}=={tid:set(ids) for tid,ids in recorded_ids.items()}
        assert len(rec)==result['retained_traces']
        assert sum(len(x) for x in rec.values())==result['retained_spans']
        assert all(set(v)==set(truth[t]['span_ids']) for t,v in rec.items())
        if result['strategy']=='full': assert set(rec)==set(truth)
        elif result['strategy']=='head':
            expected={t for t in truth if head_selection(t,result['p'])}
            assert set(rec)==expected
        else:
            protected={t for t,v in truth.items() if v['kind'] in ('error','latency')}
            cfg=json.loads((path.parent/'config.json').read_text())
            policies=cfg['processors']['tail_sampling']['policies']
            bg=next((p for p in policies if p['type']=='probabilistic'),None)
            if bg:
                ratio=bg['probabilistic']['sampling_percentage']/100
                # The Go implementation rounds an exact float64 ratio product to
                # 64 significant bits before truncation. Its integer threshold
                # differs from this exact rational floor by at most one. Every
                # observed hash is farther away, so predictions are unambiguous.
                threshold=int(Fraction.from_float(ratio)*((1<<64)-1))
                assert all(abs(h-threshold)>2 for h in hashes[seed].values())
                expected=protected|{tid for tid,h in hashes[seed].items() if h<=threshold}
            else: expected=protected
            assert set(rec)==expected, (result['seed'],result['p'],len(set(rec)^expected))
            tail_checks+=1
        inc=defaultdict(lambda:{'m':0,'witnesses':0})
        for tid,item in truth.items():
            if item['incident']:
                inc[item['incident']]['kind']=item['kind']
                inc[item['incident']]['m']+=1
                inc[item['incident']]['witnesses']+=tid in rec and has_evidence(rec[tid],item['kind'])
        assert len(inc)==132
        assert Counter((v['kind'],v['m']) for v in inc.values())==Counter({(kind,m):count for kind in ('error','latency','semantic') for m,count in [(1,20),(5,20),(20,4)]})
        verify_incident_universe(json.loads((path.parent/'incidents.json').read_text()),inc)
        before=raw_counters(path.parent/'metrics-before.txt')
        after=raw_counters(path.parent/'metrics-after.txt')
        assert all(value==0 for value in before.values())
        counters={name:after[name]-before[name] for name in set(before)|set(after)}
        assert counters==result['collector_counters'], 'raw metric versus recorded counter mismatch'
        assert counters.get('otelcol_processor_tail_sampling_sampling_trace_dropped_too_early_total',0)==0
        assert result['admitted_traces']==(len(rec) if result['strategy'] in ('head','full') else 20000)
        assert result['admitted_spans']==(sum(len(x) for x in rec.values()) if result['strategy'] in ('head','full') else 100600)
        samples=json.loads((path.parent/'process-samples.json').read_text())
        assert all(b['time']>=a['time'] and b['cpu_s']>=a['cpu_s'] for a,b in zip(samples,samples[1:]))
        assert samples[-1]['cpu_s']-samples[0]['cpu_s'] <= result['collector_cpu_s']+.021
        assert max(x['rss_bytes'] for x in samples)<=result['peak_rss_bytes']
        assert counters['otelcol_receiver_accepted_spans_total']==result['admitted_spans']
        assert counters['otelcol_exporter_sent_spans_total']==result['retained_spans']
        assert counters['otelcol_receiver_refused_spans_total']==0
        assert counters['otelcol_exporter_send_failed_spans_total']==0
        assert result['valid'] and not result['validation_errors']
        traces+=len(rec);spans+=sum(len(x) for x in rec.values())
    output={'status':'PASS','validated_cells':len(cells),'reconstructed_trace_occurrences':traces,'reconstructed_span_occurrences':spans,'tail_cells_matching_independent_hash':tail_checks,'independent_raw_metric_checks':len(cells),'unique_incidents_checked':len(cells)*132,'historical_cpu_limitation':'Exact CPU start/end snapshots were not archived; monotone intermediate samples and reported endpoint differences are checked, not independently reconstructed.'}
    print(json.dumps(output,indent=2))
    return output

if __name__=='__main__':
    validate(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'data/raw/homelab')
