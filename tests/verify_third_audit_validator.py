#!/usr/bin/env python3
"""Meaningful negative checks on disposable copies of new pilot evidence."""
import gzip,importlib.util,json,shutil,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit',ROOT/'scripts/verify_third_audit.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
RAW=ROOT/'data/raw/third-audit-20260925';checks=[]
def reject(name,kind,mutate):
    with tempfile.TemporaryDirectory(prefix='trace-validator-',dir=ROOT/'tmp') as path:
        p=Path(path)/'evidence';shutil.copytree(RAW/('load-pilot-v1' if kind=='load' else 'calibration-v1' if kind=='calibration' else 'diagnosis-pilot-v1'),p)
        mutate(p)
        try:v.load(p) if kind=='load' else v.corpus(p,kind)
        except (AssertionError,KeyError,ValueError):checks.append(name);return
        raise AssertionError('Corruption was accepted: '+name)
def episode(p,mutate):
    f=next((p/'episodes').glob('*.json.gz'));obj=json.loads(gzip.decompress(f.read_bytes()));mutate(obj);f.write_bytes(gzip.compress(json.dumps(obj).encode(),mtime=0))
def alter_json(p,mutate):
    obj=json.loads(p.read_text());mutate(obj);p.write_text(json.dumps(obj))
reject('observed-duration mismatch','pilot',lambda p:episode(p,lambda e:e['records'][0]['durations_ms'].__setitem__('service-a',123)))
reject('injected-truth ledger mismatch','pilot',lambda p:episode(p,lambda e:e['injected_trace_ids'].append('0'*32)))
reject('wrong full-data answer','pilot',lambda p:episode(p,lambda e:e['full_predictions'].__setitem__('20','invalid')))
reject('threshold not calibration quantile','calibration',lambda p:alter_json(p/'threshold.json',lambda x:x.__setitem__('threshold_ms',0)))
reject('missing incident file','pilot',lambda p:next((p/'episodes').glob('*.json.gz')).unlink())
reject('wrong CPU endpoint','load',lambda p:alter_json(next(p.glob('block-*/*/result.json')),lambda x:x.__setitem__('cpu_s',999)))
reject('wrong native hash seed','load',lambda p:alter_json(p/'block-72000/rate-2000-collector10/config.json',lambda x:x['processors']['probabilistic_sampler'].__setitem__('hash_seed',0)))
reject('wrong exported digest','load',lambda p:alter_json(next(p.glob('block-*/*/result.json')),lambda x:x.__setitem__('export_gzip_sha256','0'*64)))
for x in [0,1,203,204,4999,5000]:
    from scipy.stats import beta
    expected=1. if x==5000 else float(beta.ppf(1-.05/48,x+1,5000-x))
    assert abs(v.upper_bound(x,5000,.05/48)-expected)<1e-12
try:v.check_tracestate('12345678901234567890123456789012','ot=rv:0;th:0')
except AssertionError:checks.append('invalid native sampling metadata')
else:raise AssertionError('bad tracestate accepted')
result={'status':'PASS','rejected_corruptions':checks,'cp_endpoint_and_decision_boundary_checks':6}
(ROOT/'docs/third-audit-20260925/corruption-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
