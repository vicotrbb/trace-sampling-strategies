#!/usr/bin/env python3
"""Run measured stages sequentially so workload classes do not overlap."""
import subprocess,sys,time,json
from pathlib import Path
from load_study import allowed
allowed();source=Path(__file__).resolve().parent
for index,command in enumerate([
 ['diagnosis_study.py','collect','--output','/work/outputs/diagnosis-confirm-v1'],
 ['diagnosis_study.py','replay','--corpus','/work/outputs/diagnosis-confirm-v1','--calibration','/work/outputs/calibration-v1','--output','/work/outputs/diagnosis-replay-v1'],
 ['load_study.py','--rates','20000','--output','/work/outputs/load-confirm-v1'],
]):
    print(json.dumps({'stage':index,'command':command,'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}),flush=True)
    with open(f'/work/measured-stage-{index}.log','w') as log:subprocess.run([sys.executable,str(source/command[0]),*command[1:]],stdout=log,stderr=subprocess.STDOUT,check=True)
print(json.dumps({'complete':True,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}),flush=True)
