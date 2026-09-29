#!/usr/bin/env python3
"""Test archive rejection without running an application or modifying raw evidence."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_revision import verify_live

def decode(path):
    data=path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix=='.gz' else data)

def encode(path,data):
    value=json.dumps(data).encode()
    path.write_bytes(gzip.compress(value,mtime=0) if path.suffix=='.gz' else value)

def main():
    source=ROOT/'data/raw/revision-20260924/pilot-v2'
    checks=[]
    with tempfile.TemporaryDirectory(prefix='trace-revision-validation-') as tmp:
        base=Path(tmp)/source.name
        shutil.copytree(source,base)
        cell=base/'checkout-bursty/seed-40002/full'
        assert verify_live(base)['status']=='PASS'

        def rejected(name,files,mutate):
            originals={p:p.read_bytes() for p in files}
            try:
                mutate()
                try:verify_live(base)
                except (AssertionError,KeyError):checks.append({'case':name,'status':'REJECTED'})
                else:raise RuntimeError('Validator accepted '+name)
            finally:
                for p,content in originals.items():p.write_bytes(content)

        p=cell/'outcomes.json'
        rejected('missing request outcome',[p],lambda:encode(p,decode(p)[:-1]))

        p=cell/'predictions.json'
        def wrong_prediction():
            data=decode(p);data[next(iter(data))]=['invented','invented'];encode(p,data)
        rejected('false recorded classification',[p],wrong_prediction)

        p=cell/'resource-endpoints.json'
        def wrong_cpu():
            data=decode(p);data['after']['processes']['collector']['cpu_s']+=1;encode(p,data)
        rejected('CPU summary inconsistent with raw ticks',[p],wrong_cpu)

        p=cell/'metrics-after.txt'
        def wrong_counter():
            value,n=re.subn(r'(?m)^(otelcol_receiver_accepted_spans_total\{[^\n]+?\} )([0-9.]+)$',
                           lambda m:m[1]+str(float(m[2])+1),p.read_text())
            assert n==1;p.write_text(value)
        rejected('modified raw accepted-span counter',[p],wrong_counter)

        p=cell/'query-after-restart.json.gz'
        def duplicate_backend():
            data=decode(p);data['data'][0]['spans'].append(data['data'][0]['spans'][0]);encode(p,data)
        rejected('duplicate stored span',[p],duplicate_backend)
        def wrong_backend():
            data=decode(p);data['data'][0]['spans'][0]['operationName']='altered';encode(p,data)
        rejected('changed stored span content',[p],wrong_backend)

        p=base/'executed-source/diagnose.py'
        rejected('changed executed source',[p],lambda:p.write_bytes(p.read_bytes()+b'\n# changed\n'))

        p=cell/'traces.jsonl.gz';result_path=cell/'result.json'
        def leaked_control():
            lines=gzip.decompress(p.read_bytes()).splitlines()
            first=json.loads(lines[0]);span=first['resourceSpans'][0]['scopeSpans'][0]['spans'][0]
            span.setdefault('attributes',[]).append({'key':'X-Study-Control','value':{'intValue':'1'}})
            lines[0]=json.dumps(first).encode();payload=b'\n'.join(lines)+b'\n'
            p.write_bytes(gzip.compress(payload,mtime=0))
            result=decode(result_path)
            result['export_json_sha256']=hashlib.sha256(payload).hexdigest()
            result['export_json_bytes_all']=len(payload)
            encode(result_path,result)
        rejected('leaked control despite internally consistent export digest',[p,result_path],leaked_control)
        assert verify_live(base)['status']=='PASS'
    print(json.dumps({'status':'PASS','source':str(source.relative_to(ROOT)),
                      'restored_archive':'PASS','rejection_checks':checks},indent=2))

if __name__=='__main__':main()
