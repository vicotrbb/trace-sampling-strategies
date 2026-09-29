#!/usr/bin/env python3
import subprocess,sys,json,time
from pathlib import Path
from load_study import allowed
allowed();source=Path(__file__).resolve().parent
for index,command in enumerate([
 ['diagnosis_study.py','calibrate','--output','/work/outputs/calibration-v1'],
 ['diagnosis_study.py','collect','--pilot','--output','/work/outputs/diagnosis-pilot-v1'],
 ['load_study.py','--pilot','--policies','full,gate10,collector10,tail10','--rates','2000','--output','/work/outputs/load-pilot-v1'],
]):
    print(json.dumps({'stage':index,'command':command}),flush=True)
    with open(f'/work/pilot-stage-{index}.log','w') as log:subprocess.run([sys.executable,str(source/command[0]),*command[1:]],stdout=log,stderr=subprocess.STDOUT,check=True)
print(json.dumps({'complete':True,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}),flush=True)
