#!/usr/bin/env python3
"""Frozen descriptive and simultaneous conditional analysis of new archives."""
import argparse, gzip, json, math, statistics
from collections import defaultdict
from pathlib import Path
from scipy.stats import beta,t
ROOT=Path(__file__).resolve().parents[1]
BUDGETS=[.05,.10,.20,.35,.50,.65,.80,.95]
WINDOWS=[20,50,200]

def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def summary(xs):
    mean=statistics.mean(xs);radius=float(t.ppf(.975,len(xs)-1))*statistics.stdev(xs)/math.sqrt(len(xs))
    return {'values':xs,'mean':mean,'lower':mean-radius,'upper':mean+radius}

def diagnosis(raw,out):
    episodes=[json.loads(gzip.decompress(p.read_bytes())) for p in sorted((raw/'diagnosis-confirm-v1/episodes').glob('*.json.gz'))]
    assert len(episodes)==600
    design=json.loads((raw/'diagnosis-replay-v1/design.json').read_text())
    baselines={n:{'episodes':600,'correct':sum(e['full_predictions'][str(n)]==e['design']['target'] for e in episodes)} for n in WINDOWS}
    strata={e['design']['episode']:f"{e['design']['target']}-{e['design']['added_ms']}-{e['design']['fraction']}" for e in episodes}
    grouped=defaultdict(list)
    with gzip.open(raw/'diagnosis-replay-v1/trials.jsonl.gz','rt') as f:
        for line in f:
            v=json.loads(line);grouped[v['window'],v['policy'],v['budget']].append(v)
    expected={(n,p,b) for n in WINDOWS for p in ['head','tail'] for b in BUDGETS}
    assert set(grouped)==expected
    result=[]
    for key,rows in sorted(grouped.items()):
        n,policy,budget=key;assert len(rows)==5000 and {r['trial'] for r in rows}==set(range(5000))
        feasible=policy!='tail' or budget>=design['alphas'][str(n)]
        assert all(r['feasible']==feasible for r in rows)
        row={'window':n,'policy':policy,'budget':budget,'feasible':feasible}
        if feasible:
            losses=sum(r['loss'] for r in rows);gains=sum(r['gain'] for r in rows)
            upper=1. if losses==5000 else float(beta.ppf(1-.05/48,losses+1,5000-losses))
            sub=defaultdict(lambda:defaultdict(int))
            for r in rows:
                s=sub[strata[r['episode']]];s['n']+=1
                for k in ['full_correct','correct','loss','gain']:s[k]+=int(r[k])
            row.update(n=5000,full_correct=sum(r['full_correct'] for r in rows),correct=sum(r['correct'] for r in rows),losses=losses,gains=gains,net_loss=(losses-gains)/5000,upper_loss_bound=upper,meets_five_point_margin=upper<=.05,abstentions=sum(r['prediction'] is None for r in rows),retained_fraction=sum(r['retained'] for r in rows)/(5000*2*n),mean_reference_retained=statistics.mean(r['retained_reference'] for r in rows),mean_incident_retained=statistics.mean(r['retained_incident'] for r in rows),descriptive_strata=sub)
        result.append(row)
    protection={}
    for n in WINDOWS:
        protection[n]={phase:sum(r['root_ms']>=design['threshold_ms'] for e in episodes for r in e['records'] if r['index']<n and r['phase']==phase) for phase in ['reference','incident']}
    write(out/'diagnosis-summary.json',{'episodes':600,'requests':240000,'family_size':48,'trials_per_comparison':5000,'baselines':baselines,'threshold_ms':design['threshold_ms'],'protected_fraction':design['alphas'],'protected_counts':protection,'scope':'Conditional on fixed new corpus and ideal iid replay; nested windows are paired','results':result})

def load(raw,out):
    cells=[json.loads(p.read_text()) for p in sorted((raw/'load-confirm-v1').glob('block-*/*/result.json'))]
    assert len(cells)==20
    group={p:sorted([r for r in cells if r['policy']==p],key=lambda r:r['block']) for p in ['full','gate10','collector10','tail10']}
    for rows in group.values():assert [r['block'] for r in rows]==list(range(72001,72006))
    results={p:{k:summary([r[k] for r in rows]) for k in ['cpu_s','json_bytes','max_rss_bytes','batches','accepted_spans','exported_spans']} for p,rows in group.items()}
    contrasts={}
    for a,b in [('gate10','full'),('collector10','full'),('tail10','full'),('collector10','gate10'),('tail10','collector10')]:
        contrasts[a+'-minus-'+b]={'cpu_difference_s':summary([x['cpu_s']-y['cpu_s'] for x,y in zip(group[a],group[b])]),'cpu_saving_percent':summary([100*(1-x['cpu_s']/y['cpu_s']) for x,y in zip(group[a],group[b])])}
    write(out/'load-summary.json',{'cells':20,'groups':results,'contrasts':contrasts,'max_lag_s':max(r['max_lag_s'] for r in cells)})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['diagnosis','load','all']);p.add_argument('--raw',type=Path,default=ROOT/'data/raw/third-audit-20260925');p.add_argument('--out',type=Path,default=ROOT/'data/derived/third-audit-20260925');a=p.parse_args()
    if a.mode in ['diagnosis','all']:diagnosis(a.raw,a.out)
    if a.mode in ['load','all']:load(a.raw,a.out)
