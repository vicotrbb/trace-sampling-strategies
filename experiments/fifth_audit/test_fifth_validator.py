#!/usr/bin/env python3
"""Corrupt disposable archive copies to exercise scientific acceptance checks."""
import contextlib,gzip,io,json,tempfile
from pathlib import Path
import verify_fifth_audit as v

ROOT=Path(__file__).resolve().parents[1]
PILOT=ROOT/'data/raw/fifth-audit-20260928/pilots-v2/placement-8000'

def fixture(path):
    plan=v.read(PILOT/'plan.json')[:1]
    for name in ['environment.json','input','executed-source']:(path/name).symlink_to(PILOT/name)
    (path/'plan.json').write_text(json.dumps(plan));(path/'complete.json').write_text('{"cells":1}')
    block,kind,export,timeout,policy,_=plan[0]
    rel=Path(f'block-{block}')/f'{kind}-{export}-{timeout}-{policy}'
    target=path/rel;target.mkdir(parents=True)
    for source in (PILOT/rel).iterdir():
        if source.is_file():(target/source.name).symlink_to(source)
    return target

def replace(path,data):
    path.unlink();path.write_bytes(data)

def main():
    checks=[]
    for mutation in ['none','missing_span','wrong_cpu','wrong_selection_count','wrong_backend_count']:
        with tempfile.TemporaryDirectory(prefix='trace-validator-') as tmp:
            base=Path(tmp);cell=fixture(base)
            if mutation=='missing_span':
                p=cell/'traces.jsonl.gz';lines=gzip.decompress(p.read_bytes()).splitlines()
                row=json.loads(lines[0]);row['resourceSpans'][0]['scopeSpans'][0]['spans'].pop()
                lines[0]=json.dumps(row).encode();payload=gzip.compress(b'\n'.join(lines)+b'\n',mtime=0)
                replace(p,payload);result=v.read(cell/'result.json');result['export_gzip_sha256']=v.sha(p)
                replace(cell/'result.json',json.dumps(result).encode())
            elif mutation in ['wrong_cpu','wrong_selection_count']:
                p=cell/'result.json';result=v.read(p)
                if mutation=='wrong_cpu':result['cpu_s']['collector']+=1
                else:result['accepted_spans']+=5
                replace(p,json.dumps(result).encode())
            elif mutation=='wrong_backend_count':
                p=cell/'jaeger-metrics-after.txt';text=p.read_text()+'\njaeger_collector_spans_saved_by_svc_total{result="ok"} 1\n'
                replace(p,text.encode())
            rejected=False
            try:
                with contextlib.redirect_stdout(io.StringIO()):v.verify(base)
            except AssertionError:rejected=True
            assert rejected==(mutation!='none'),mutation
            checks.append({'mutation':mutation,'result':'rejected' if rejected else 'accepted'})
    out=ROOT/'docs/fifth-audit-20260928/validator-negative-controls.json'
    out.write_text(json.dumps({'status':'PASS','checks':checks},indent=2)+'\n');print(out.read_text())

if __name__=='__main__':main()
