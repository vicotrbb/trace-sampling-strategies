import json,subprocess,sys,time
from pathlib import Path
import study
study.allowed()
root=Path('/work/pilots-v2');root.mkdir(exist_ok=False)
results={}
for kind,candidates in [('placement',[20000,8000,2000]),('batching',[4000,2000,1000])]:
    attempts=[]
    for rate in candidates:
        target=root/f'{kind}-{rate}'
        with (root/f'{kind}-{rate}.log').open('w') as log:
            result=subprocess.run([sys.executable,'/work/source/study.py',kind,'--rate',str(rate),'--pilot','--output',str(target)],stdout=log,stderr=subprocess.STDOUT)
        attempts.append({'rate_traces_s':rate,'returncode':result.returncode,'directory':str(target)})
        print(kind,rate,'returncode',result.returncode,flush=True)
        if result.returncode==0:break
    assert attempts[-1]['returncode']==0,(kind,attempts)
    results[kind]={'selected_rate_traces_s':attempts[-1]['rate_traces_s'],'attempts':attempts}
    (root/'selection.json').write_text(json.dumps(results,indent=2)+'\n')
(root/'complete.json').write_text(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selected':results},indent=2)+'\n')
