#!/usr/bin/env python3
"""Analysis of archived load and diagnosis observations, no workload execution."""
import argparse,csv,gzip,json,math,statistics
from collections import defaultdict
from pathlib import Path
from scipy.stats import beta,t

ROOT=Path(__file__).resolve().parents[1]

def summary(values):
    n=len(values);mean=statistics.mean(values);radius=t.ppf(.975,n-1)*statistics.stdev(values)/math.sqrt(n) if n>1 else None
    return {'n':n,'values':values,'mean':mean,'lower':mean-radius if radius is not None else None,'upper':mean+radius if radius is not None else None}

def analyze(raw,out):
    out.mkdir(parents=True,exist_ok=True);cost=[json.loads(p.read_text()) for p in sorted((raw/'load-confirm-v1').glob('block-*/*/result.json'))]
    groups=defaultdict(list)
    for r in cost:groups[r['rate'],r['policy']].append(r)
    means={};contrasts={}
    for (rate,policy),rows in sorted(groups.items()):
        means[f'{rate}-{policy}']={k:summary([r[k] for r in rows]) for k in ['cpu_s','json_bytes','max_rss_bytes','batches','max_lag_s']}
        means[f'{rate}-{policy}']['core_equivalents']=summary([r['cpu_s']/(r['duration_s']+r['drain_s']) for r in rows])
        means[f'{rate}-{policy}']['cpu_us_per_offered_span']=summary([1e6*r['cpu_s']/(r['rate']*r['duration_s']*5) for r in rows])
        if policy!='full':
            baseline={r['block']:r for r in groups[rate,'full']}
            contrasts[f'{rate}-{policy}']={'cpu_difference_s':summary([r['cpu_s']-baseline[r['block']]['cpu_s'] for r in rows]),'cpu_saving_percent':summary([100*(1-r['cpu_s']/baseline[r['block']]['cpu_s']) for r in rows])}
    (out/'load-summary.json').write_text(json.dumps({'cells':len(cost),'groups':means,'contrasts':contrasts},indent=2)+'\n')
    episodes=[json.loads(gzip.decompress(p.read_bytes())) for p in sorted((raw/'diagnosis-confirm-v1/episodes').glob('*.json.gz'))]
    strata=defaultdict(list)
    for e in episodes:
        d=e['design'];strata[f"{d['target']}-{d['added_ms']}-{d['fraction']}"].append(e['full_prediction']==d['target'])
    baseline={'episodes':len(episodes),'full_correct':sum(sum(v) for v in strata.values()),'strata':{k:{'n':len(v),'correct':sum(v)} for k,v in strata.items()}}
    trials=defaultdict(list)
    with gzip.open(raw/'diagnosis-replay-v1/trials.jsonl.gz','rt') as f:
        for line in f:
            row=json.loads(line);trials[row['policy'],row['budget']].append(row)
    episode_strata={e['design']['episode']:f"{e['design']['target']}-{e['design']['added_ms']}-{e['design']['fraction']}" for e in episodes}
    results=[]
    for (policy,budget),rows in sorted(trials.items()):
        if not rows[0]['feasible']:results.append({'policy':policy,'budget':budget,'feasible':False});continue
        n=len(rows);loss=sum(r['loss'] for r in rows);gain=sum(r['gain'] for r in rows)
        upper=1.0 if loss==n else float(beta.ppf(1-.05/16,loss+1,n-loss))
        by_stratum=defaultdict(list)
        for row in rows:by_stratum[episode_strata[row['episode']]].append(row)
        descriptive={key:{'n':len(values),'full_correct':sum(v['full_correct'] for v in values),'correct':sum(v['correct'] for v in values),'losses':sum(v['loss'] for v in values),'gains':sum(v['gain'] for v in values)} for key,values in by_stratum.items()}
        results.append({'policy':policy,'budget':budget,'feasible':True,'n':n,'full_correct':sum(r['full_correct'] for r in rows),'correct':sum(r['correct'] for r in rows),'abstentions':sum(r['prediction'] is None for r in rows),'losses':loss,'gains':gain,'net_loss':(loss-gain)/n,'upper_loss_bound':upper,'meets_five_point_margin':upper<=.05,'retained_fraction':sum(r['retained'] for r in rows)/(n*40),'descriptive_strata':descriptive})
    info=json.loads((raw/'diagnosis-replay-v1/design.json').read_text())
    (out/'diagnosis-summary.json').write_text(json.dumps({'baseline':baseline,'protected_fraction':info['alpha'],'family_size':16,'confidence':.95,'scope':'Conditional on fixed corpus and iid randomized replay','results':results},indent=2)+'\n')
    print(json.dumps({'load_cells':len(cost),'baseline':baseline,'diagnosis_results':results},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=ROOT/'data/raw/second-audit-20260925');p.add_argument('--out',type=Path,default=ROOT/'data/derived/second-audit-20260925');a=p.parse_args();analyze(a.raw,a.out)
