#!/usr/bin/env python3
"""Adversarial checks that independent archive validation rejects damaged evidence."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import verify_artifact as validator

def rejected(root, label):
    try:
        with contextlib.redirect_stdout(io.StringIO()): validator.validate(root)
    except AssertionError:
        return label
    raise AssertionError('validator accepted '+label)

def main():
    original=Path(__file__).resolve().parents[1]/'data/raw/homelab'
    results=[]
    with tempfile.TemporaryDirectory(prefix='trace-validator-') as folder:
        target=Path(folder)/'evidence'
        shutil.copytree(original/'main',target/'main')
        cell=target/'main/seed-1101/full-1.0000'
        incidents=cell/'incidents.json'
        data=incidents.read_bytes();rows=json.loads(data)
        incidents.write_text(json.dumps(rows[:-1]))
        results.append(rejected(target,'missing incident'))
        incidents.write_text(json.dumps(rows+[rows[0]]))
        results.append(rejected(target,'duplicate incident'))
        incidents.write_bytes(data)
        metrics=cell/'metrics-after.txt';data=metrics.read_bytes()
        lines=data.decode().splitlines()
        for i,line in enumerate(lines):
            if line.startswith('otelcol_receiver_accepted_spans_total{'):
                parts=line.rsplit(' ',1);lines[i]=parts[0]+' '+str(float(parts[1])+1);break
        else: raise AssertionError('counter fixture not found')
        metrics.write_text('\n'.join(lines)+'\n')
        results.append(rejected(target,'raw counter tampering'))
        metrics.write_bytes(data)
        with contextlib.redirect_stdout(io.StringIO()):validator.validate(target)
    print(json.dumps({'status':'PASS','rejected_mutations':results,'restored_archive':'PASS'},indent=2))
if __name__=='__main__':main()
