#!/usr/bin/env python3
"""Matched 2x2x2x2 marker/timing/cache/churn controls; homelab only."""
from collections import Counter
import copy
import gzip
import hashlib
import http.client
import itertools
import json
import os
from pathlib import Path
import random
import signal
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import runner as r

def run(seed, corpus, truth, root_error, late, cache, churn):
    name=f'root-{int(root_error)}-late-{int(late)}-cache-{int(cache)}-churn-{int(churn)}'
    out=Path('/work/revision/matched-probes')/f'seed-{seed}'/name
    out.mkdir(parents=True,exist_ok=False)
    errors=copy.deepcopy([(tid,resources) for tid,resources in corpus if truth[tid]['kind']=='error'])
    normal=[resources for tid,resources in corpus if truth[tid]['kind']=='normal'][:300] if churn else []
    for tid,resources in errors:
        for resource in resources:
            span=resource['scopeSpans'][0]['spans'][0]
            if span['name']=='gateway':span['status']['code']=2 if root_error else 1
    ledger={tid:truth[tid] for tid,resources in errors}
    payload=r.pack([resource for tid,resources in errors for resource in resources])
    r.dump(out/'truth.json',ledger)
    (out/'input.json.gz').write_bytes(gzip.compress(payload,mtime=0))
    (out/'churn-input.json.gz').write_bytes(gzip.compress(r.pack([resource for resources in normal for resource in resources]),mtime=0))
    cfg=r.config(out,'tail',.02,capacity=256 if churn else 50000,wait=2,cache=cache)
    p,log=r.launch(out,cfg)
    connection=http.client.HTTPConnection('127.0.0.1',4318,timeout=30)
    first=[]; delayed=[]
    for tid,resources in errors:
        for resource in resources:
            span=resource['scopeSpans'][0]['spans'][0]
            (delayed if late and span['name']=='database' else first).append(resource)
    (out/'metrics-before.txt').write_text(r.get_metrics())
    r.post(connection,r.pack(first))
    time.sleep(5)
    if churn:r.post(connection,r.pack([resource for resources in normal for resource in resources]))
    if delayed:r.post(connection,r.pack(delayed))
    time.sleep(5)
    (out/'metrics-after.txt').write_text(r.get_metrics())
    connection.close();p.send_signal(signal.SIGTERM);p.wait(timeout=30);log.close()
    rec,duplicates=r.exported(out/'traces.jsonl')
    kept={tid:spans for tid,spans in rec.items() if tid in ledger}
    complete=sum(set(spans)==set(ledger[tid]['span_ids']) for tid,spans in kept.items())
    useful=sum(r.diagnostic(spans,'error') for spans in kept.values())
    raw=(out/'traces.jsonl').read_bytes() if (out/'traces.jsonl').exists() else b''
    (out/'traces.jsonl.gz').write_bytes(gzip.compress(raw,mtime=0))
    (out/'traces.jsonl').unlink(missing_ok=True)
    result={'seed':seed,'name':name,'root_error':root_error,'late':late,'cache':cache,'churn':churn,
            'input_traces':200,'input_spans':1400+1500*churn,
            'input_content_sha256':hashlib.sha256(payload).hexdigest(),
            'retained_error_ids':len(kept),'retained_spans':sum(len(s) for s in rec.values()),
            'complete':complete,'witnesses':useful,'duplicates':duplicates,
            'export_json_sha256':hashlib.sha256(raw).hexdigest()}
    r.dump(out/'result.json',result)
    print('MATCHED',json.dumps(result),flush=True)

def main():
    assert os.environ.get('STUDY_CONTEXT')=='homelab'
    base=Path('/work/revision/matched-probes');base.mkdir(exist_ok=False)
    (base/'executed-source.py').write_bytes(Path(__file__).read_bytes())
    (base/'executed-runner.py').write_bytes(Path(r.__file__).read_bytes())
    for seed in [32001,32002,32003]:
        corpus,truth=r.make_corpus(seed)
        treatments=list(itertools.product([False,True],repeat=4))
        random.Random(seed).shuffle(treatments)
        for treatment in treatments:run(seed,corpus,truth,*treatment)
    print('MATCHED_COMPLETE',flush=True)
if __name__=='__main__':main()
