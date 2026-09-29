"""Full-duration capacity pilots after the preserved first measured failure."""
import json,subprocess,sys,time
from pathlib import Path
import study

study.allowed();root=Path('/work/pilots-v3');root.mkdir(exist_ok=False);attempts=[]
for rate in [2000,1000]:
    target=root/f'batching-{rate}'
    with (root/f'batching-{rate}.log').open('w') as log:
        result=subprocess.run([sys.executable,str(Path(__file__).parent/'study.py'),'batching','--rate',str(rate),'--pilot','--output',str(target)],stdout=log,stderr=subprocess.STDOUT)
    attempts.append({'rate_traces_s':rate,'returncode':result.returncode,'directory':str(target)})
    print('batching',rate,'returncode',result.returncode,flush=True)
    if result.returncode==0:break
assert attempts[-1]['returncode']==0,attempts
selection={'batching':{'selected_rate_traces_s':attempts[-1]['rate_traces_s'],'attempts':attempts}}
(root/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
(root/'complete.json').write_text(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selected':selection},indent=2)+'\n')
