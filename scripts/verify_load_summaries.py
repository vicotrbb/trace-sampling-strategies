#!/usr/bin/env python3
"""Independently check derived load means, units, pairing, and t intervals."""
from pathlib import Path
import argparse,json,math
from scipy.stats import t
ROOT=Path(__file__).resolve().parents[1]

def read(path):return json.loads(path.read_text())
def check_summary(item,values):
    assert item['n']==5 and item['values']==values
    mean=sum(values)/5
    assert math.isclose(item['mean'],mean,rel_tol=1e-12,abs_tol=1e-12)
    sem=math.sqrt(sum((x-mean)**2 for x in values)/(4*5))
    if min(values)==max(values):
        assert item['lower']==item['mean']==item['upper']
    else:
        for bound,sign in [('lower',-1),('upper',1)]:
            z=(item[bound]-mean)/(sign*sem)
            assert abs(float(t.cdf(z,4))-.975)<1e-8,(bound,z,item)

def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=ROOT/'data/raw/second-audit-20260925/load-confirm-v1');p.add_argument('--summary',type=Path,default=ROOT/'data/derived/second-audit-20260925/load-summary.json');p.add_argument('--receipt',type=Path);a=p.parse_args()
    s=read(a.summary);assert s['cells']==80 and len(s['groups'])==16 and len(s['contrasts'])==12
    checks=0;index={}
    for rate in [50,2000,8000,20000]:
        for policy in ['full','head10','tail10','tail100']:
            rows=[read(a.raw/f'block-{b}'/f'rate-{rate}-{policy}/result.json') for b in range(62001,62006)]
            index[rate,policy]=rows;g=s['groups'][f'{rate}-{policy}']
            for key in ['cpu_s','json_bytes','max_rss_bytes','batches','max_lag_s']:
                check_summary(g[key],[r[key] for r in rows]);checks+=1
            check_summary(g['core_equivalents'],[r['cpu_s']/35 for r in rows]);checks+=1
            check_summary(g['cpu_us_per_offered_span'],[r['cpu_s']*1e6/(30*rate*5) for r in rows]);checks+=1
            if policy!='full':
                full=index[rate,'full'];c=s['contrasts'][f'{rate}-{policy}']
                check_summary(c['cpu_difference_s'],[r['cpu_s']-f['cpu_s'] for r,f in zip(rows,full)]);checks+=1
                check_summary(c['cpu_saving_percent'],[100*(1-r['cpu_s']/f['cpu_s']) for r,f in zip(rows,full)]);checks+=1
    result={'status':'PASS','groups':16,'paired_contrasts':12,'summary_intervals_recomputed':checks,'coverage_scope':'Pointwise t model, df=4; does not verify distributional assumptions'}
    if a.receipt:a.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
