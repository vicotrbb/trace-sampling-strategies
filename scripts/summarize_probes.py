#!/usr/bin/env python3
import csv
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
from verify_artifact import has_evidence, raw_counters
parser=argparse.ArgumentParser()
parser.add_argument('raw',nargs='?',type=Path,default=ROOT/'data/raw/homelab')
parser.add_argument('--write',action='store_true',help='Regenerate manuscript table and derived CSV')
args=parser.parse_args()
raw=args.raw
labels={'complete-control':'Complete control','late-cached':'Late, cached','late-uncached':'Late, uncached',
        'buffer-16':'Burst, buffer 16','late-evicted-cached':'Late + churn, cached','late-evicted-uncached':'Late + churn, uncached'}
rows=[];tex=[]
for name,label in labels.items():
    folder=raw/'sensitivity'/name
    x=json.loads((folder/'result.json').read_text())
    truth=json.loads((folder/'truth.json').read_text())
    data=gzip.decompress((folder/'traces.jsonl.gz').read_bytes())
    assert hashlib.sha256(data).hexdigest()==x['export_json_sha256']
    records=defaultdict(dict)
    for line in data.splitlines():
        for rs in json.loads(line).get('resourceSpans',[]):
            for ss in rs.get('scopeSpans',[]):
                for s in ss.get('spans',[]):
                    tid,sid=s['traceId'].lower(),s['spanId'].lower()
                    assert tid in truth and sid not in records[tid]
                    records[tid][sid]=s
    complete=sum(set(spans)==set(truth[tid]['span_ids']) for tid,spans in records.items())
    useful=sum(has_evidence(spans,'error') for spans in records.values())
    assert len(records)==x['retained_trace_ids'] and sum(len(s) for s in records.values())==x['retained_spans']
    assert complete==x['complete_traces'] and useful==x['diagnostic_witnesses']
    # Each original probe starts a fresh Collector; its archived final counters
    # therefore account for the complete probe, without reusing result summaries.
    counters=raw_counters(folder/'metrics.txt')
    assert dict(counters)==x['collector_counters']
    assert counters['otelcol_receiver_accepted_spans_total']==x['input_spans']
    assert counters.get('otelcol_exporter_sent_spans_total',0)==x['retained_spans']
    assert all(value==0 for key,value in counters.items() if 'refused' in key or 'send_failed' in key)
    row={k:v for k,v in x.items() if not isinstance(v,(dict,list))}
    row['early_buffer_drops']=sum(v for k,v in counters.items() if 'dropped_too_early' in k)
    rows.append(row)
    tex.append(f'{label} & {x["capacity"]:,} & {x["retained_trace_ids"]} & {x["retained_spans"]} & {complete} & {useful} \\\\')
if args.write:
    with (ROOT/'data/derived/probe-summary.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (ROOT/'paper/probe-rows.tex').write_text('\n'.join(tex)+'\n')
print(json.dumps({'status':'PASS','validated_probes':len(rows),'early_drops_buffer16':next(x['early_buffer_drops'] for x in rows if x['name']=='buffer-16')},indent=2))
