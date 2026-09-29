#!/usr/bin/env python3
"""Separate mechanistic probes. Run after the main experiment, never pool."""
from collections import Counter
import copy
import gzip
import hashlib
import http.client
import json
import os
from pathlib import Path
import signal
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
import runner as r


def run_probe(name, late, cache, capacity, churn=False):
    out=r.ROOT/'sensitivity'/name
    out.mkdir(parents=True,exist_ok=False)
    corpus,truth=r.make_corpus(2201)
    error_corpus=[(tid,rs) for tid,rs in corpus if truth[tid]['kind']=='error']
    churn_resources=[rs for tid,rs in corpus if truth[tid]['kind']=='normal'][:300] if churn else []
    truth={tid:truth[tid] for tid,rs in error_corpus}
    r.dump(out/'truth.json',truth)
    cfg=r.config(out,'tail',.02,capacity=capacity,wait=2,cache=cache)
    proc,log=r.launch(out,cfg)
    conn=http.client.HTTPConnection('127.0.0.1',4318,timeout=30)
    delayed=[];first=[]
    for tid,resources in error_corpus:
        if not late:
            first.extend(resources)
            continue
        resources=copy.deepcopy(resources)
        for rs in resources:
            span=rs['scopeSpans'][0]['spans'][0]
            if span['name']=='database':
                delayed.append(rs)
            else:
                span['status']['code']=1
                first.append(rs)
    started=time.monotonic()
    r.post(conn,r.pack(first))
    first_elapsed=time.monotonic()-started
    if delayed:
        time.sleep(5)
        if churn:
            r.post(conn,r.pack([rs for resources in churn_resources for rs in resources]))
        r.post(conn,r.pack(delayed))
    time.sleep(5)
    metrics=r.get_metrics();(out/'metrics.txt').write_text(metrics)
    conn.close();proc.send_signal(signal.SIGTERM);proc.wait(timeout=30);log.close()
    records,duplicates=r.exported(out/'traces.jsonl')
    complete=[tid for tid,spans in records.items() if set(spans)==set(truth[tid]['span_ids'])]
    useful=[tid for tid,spans in records.items() if r.diagnostic(spans,'error')]
    counters={}
    for line in metrics.splitlines():
        if line.startswith('#') or not line.strip():continue
        key=line.split('{',1)[0].split()[0]
        if any(part in key for part in ('accepted_spans','sent_spans','refused_spans','send_failed','dropped_too_early')):
            counters[key]=counters.get(key,0)+float(line.split()[-1])
    raw=(out/'traces.jsonl').read_bytes() if (out/'traces.jsonl').exists() else b''
    (out/'traces.jsonl.gz').write_bytes(gzip.compress(raw,compresslevel=6,mtime=0))
    (out/'traces.jsonl').unlink(missing_ok=True)
    result={'name':name,'seed':2201,'input_traces':len(error_corpus),'input_spans':1400+1500*churn,'background_traces':300*churn,'churn':churn,'late':late,'late_delay_s':5 if late else 0,
            'cache':cache,'capacity':capacity,'decision_wait_s':2,'first_request_s':first_elapsed,
            'retained_trace_ids':len(records),'retained_spans':sum(len(s) for s in records.values()),'complete_traces':len(complete),
            'diagnostic_witnesses':len(useful),'duplicates':duplicates,'collector_counters':counters,
            'export_json_sha256':hashlib.sha256(raw).hexdigest(),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    r.dump(out/'result.json',result);print(json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    assert os.environ.get('STUDY_CONTEXT')=='homelab'
    results=[]
    for name,late,cache,capacity,churn in [('complete-control',False,False,50000,False),('late-cached',True,True,50000,False),
                                     ('late-uncached',True,False,50000,False),('buffer-16',False,False,16,False),
                                     ('late-evicted-cached',True,True,256,True),('late-evicted-uncached',True,False,256,True)]:
        results.append(run_probe(name,late,cache,capacity,churn))
    r.dump(r.ROOT/'sensitivity'/'summary.json',results)
    print('SENSITIVITY_COMPLETE',flush=True)
