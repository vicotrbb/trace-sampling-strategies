#!/usr/bin/env python3
"""Rebuild every reported numerical table/figure from retained raw receipts."""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import binom, t

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'derived'
PAPER = ROOT / 'paper'
FIG = PAPER / 'figures'
for folder in [OUT, FIG]: folder.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'serif','mathtext.fontset':'cm','font.size':10,'axes.spines.top':False,
 'axes.spines.right':False,'axes.labelsize':10,'legend.fontsize':8,'figure.dpi':150,'savefig.bbox':'tight', 'pdf.fonttype':42})
COLORS = ['#164c74','#ad4f19','#49806c','#6c4b8d']


def threshold(m,k,delta=.05):
    if k > m: return None
    lo, hi = 0., 1.
    for _ in range(80):
        mid = (lo+hi)/2
        if binom.sf(k-1,m,mid) < 1-delta: lo=mid
        else: hi=mid
    return hi


def dump(path, obj): path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')


def csvwrite(path, rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def theory():
    rows=[]
    tex=[]
    for m in [1,5,20,100]:
        p=threshold(m,1); q=threshold(m,3)
        rows.append({'m':m,'p95_k1':p,'discard95_k1':1-p,'p95_k3':q,
                     'p90_k1':threshold(m,1,.10),'p99_k1':threshold(m,1,.01),
                     'tail_budget95_hidden_k1':.02+.98*p})
        qtex='--' if q is None else f'{100*q:.2f}\\%'
        tex.append(f'{m} & {100*p:.2f}\\% & {100*(1-p):.2f}\\% & {qtex} & {100*(.02+.98*p):.2f}\\% \\\\')
    csvwrite(OUT/'thresholds.csv',rows)
    (PAPER/'threshold-rows.tex').write_text('\n'.join(tex)+'\n')
    ps=np.geomspace(.001,1,400)
    fig,axs=plt.subplots(1,2,figsize=(6.8,2.8),sharey=True)
    for i,m in enumerate([1,5,20,100]):
        axs[0].plot(ps*100,binom.sf(0,m,ps),color=COLORS[i],label=f'm = {m}')
    for i,m in enumerate([5,20,100]):
        axs[1].plot(ps*100,binom.sf(2,m,ps),color=COLORS[i+1],label=f'm = {m}')
    for ax,title in zip(axs,['(a) One complete witness, k = 1','(b) Three witnesses, k = 3']):
        ax.axhline(.95,ls=':',color='0.45',lw=1)
        ax.set_xscale('log');ax.set_xlim(.1,100);ax.set_ylim(0,1.04)
        ax.set_xlabel('Head retention rate (%)');ax.set_title(title,fontsize=10)
        ax.grid(alpha=.15);ax.legend(loc='upper left')
    axs[0].set_ylabel('Incident recovery probability')
    fig.tight_layout();fig.savefig(FIG/'theoretical-visibility.pdf');plt.close(fig)
    bs=np.linspace(.02,1,400); r=(bs-.02)/.98
    fig,axs=plt.subplots(1,2,figsize=(6.8,2.7),sharey=True)
    for ax,m in zip(axs,[1,5]):
        ax.plot(bs*100,binom.sf(0,m,bs),color=COLORS[0],label='Uniform head')
        ax.plot(bs*100,binom.sf(0,m,r),color=COLORS[1],ls='--',label='Tail, unflagged witnesses')
        ax.axhline(1,color=COLORS[2],ls=':',label='Tail, protected witnesses')
        ax.set_xlim(2,25);ax.set_ylim(0,1.04);ax.set_xlabel('Expected retained traces (%)')
        ax.set_title(f'm = {m}, k = 1; protected traffic = 2%',fontsize=9);ax.grid(alpha=.15)
    axs[0].set_ylabel('Incident recovery probability');axs[1].legend(loc='center right',fontsize=7)
    fig.tight_layout();fig.savefig(FIG/'tail-tradeoff.pdf');plt.close(fig)


def wilson(x,n):
    z=1.959963984540054; p=x/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return max(0,center-half),min(1,center+half)


def mean_ci(xs):
    mean=statistics.mean(xs)
    half=t.ppf(.975,len(xs)-1)*statistics.stdev(xs)/math.sqrt(len(xs)) if len(xs)>1 else 0
    return float(mean),float(mean-half),float(mean+half)


def empirical(raw):
    cells=sorted(raw.glob('main/seed-*/*/result.json'))
    if len(cells)!=70: raise RuntimeError(f'Expected 70 cells, found {len(cells)}')
    data=[json.loads(path.read_text()) for path in cells]
    expected={(seed,strategy,p) for seed in range(1101,1106) for strategy,p in [('full',1.0)]+[('head',p) for p in [.001,.01,.025,.05,.1,.25,.5]]+[('tail',p) for p in [.02,.025,.05,.1,.25,.5]]}
    actual=[(x['seed'],x['strategy'],x['p']) for x in data]
    assert set(actual)==expected and len(actual)==len(set(actual))
    assert all(x['valid'] for x in data)
    flat=[]
    for x in data:
        flat.append({k:v for k,v in x.items() if not isinstance(v,(dict,list))})
    csvwrite(OUT/'cells.csv',flat)
    full={x['seed']:x for x in data if x['strategy']=='full'}
    groups=defaultdict(list)
    for x in data: groups[(x['strategy'],x['p'])].append(x)
    resource=[]
    for (strategy,p),group in sorted(groups.items()):
        assert len(group)==5 and len({x['seed'] for x in group})==5
        result={'strategy':strategy,'target_trace_rate':p,'n_blocks':len(group)}
        for key in ['retained_traces','retained_spans','ingress_payload_bytes','export_json_bytes','archive_gzip_bytes','collector_cpu_s','peak_rss_bytes']:
            rawvalues=[x[key] for x in group]
            denom='offered_traces' if key=='retained_traces' else key
            savings=[1-x[key]/full[x['seed']][denom] for x in group]
            mean,lo,hi=mean_ci(savings)
            result.update({f'{key}_mean':statistics.mean(rawvalues),f'{key}_saving':mean,f'{key}_saving_lo':lo,f'{key}_saving_hi':hi})
        resource.append(result)
    csvwrite(OUT/'resource-summary.csv',resource)
    resource_map={(r['strategy'],r['target_trace_rate']):r for r in resource}
    lines=[]
    for strategy,p in [('head',.001),('head',.01),('tail',.02),('head',.025),('tail',.025),('head',.05),('tail',.05),('head',.1),('tail',.1),('head',.25),('tail',.25),('head',.5),('tail',.5)]:
        r=resource_map[(strategy,p)]
        cpu=r['collector_cpu_s_saving']*100;lo=r['collector_cpu_s_saving_lo']*100;hi=r['collector_cpu_s_saving_hi']*100
        lines.append(f'{strategy.capitalize()} & {100*p:g} & {100*(1-r["retained_traces_saving"]):.2f} & {100*r["ingress_payload_bytes_saving"]:.1f} & {100*r["export_json_bytes_saving"]:.1f} & {cpu:.1f} [{lo:.1f}, {hi:.1f}] & {r["peak_rss_bytes_mean"]/2**20:.1f} \\\\')
    (PAPER/'resource-rows.tex').write_text('\n'.join(lines)+'\n')
    incidents=defaultdict(lambda:[0,0])
    for path,x in zip(cells,data):
        for inc in json.loads((path.parent/'incidents.json').read_text()):
            for k in [1,3]:
                if inc['m']<k: continue
                key=(x['strategy'],x['p'],inc['kind'],inc['m'],k)
                incidents[key][0]+=inc['witnesses']>=k
                incidents[key][1]+=1
    rows=[]
    for (strategy,p,kind,m,k),(successes,n) in sorted(incidents.items()):
        pi=p if strategy!='tail' else 1 if kind in ('error','latency') else (p-.02)/.98
        lo,hi=wilson(successes,n)
        rows.append({'strategy':strategy,'p':p,'kind':kind,'m':m,'k':k,'successes':successes,'n':n,
                     'estimate':successes/n,'wilson_lo':lo,'wilson_hi':hi,'theory':float(binom.sf(k-1,m,pi))})
    csvwrite(OUT/'incident-summary.csv',rows)
    diag=[]
    for strategy,p,kind,m,k in [('head',.1,'error',1,1),('tail',.1,'error',1,1),('head',.1,'latency',1,1),('tail',.1,'latency',1,1),('head',.1,'semantic',1,1),('tail',.1,'semantic',1,1),('head',.1,'semantic',5,1),('tail',.1,'semantic',5,1),('head',.1,'semantic',5,3),('tail',.1,'semantic',5,3),('head',.1,'semantic',20,1),('tail',.1,'semantic',20,1),('head',.1,'semantic',20,3),('tail',.1,'semantic',20,3)]:
        row=next(x for x in rows if (x['strategy'],x['p'],x['kind'],x['m'],x['k'])==(strategy,p,kind,m,k))
        diag.append(f'{strategy.capitalize()} & {kind.capitalize()} & {m} & {k} & {row["successes"]}/{row["n"]} & {100*row["estimate"]:.1f} [{100*row["wilson_lo"]:.1f}, {100*row["wilson_hi"]:.1f}] & {100*row["theory"]:.1f} \\\\')
    (PAPER/'diagnosis-rows.tex').write_text('\n'.join(diag)+'\n')
    fig,axs=plt.subplots(1,3,figsize=(7,2.75))
    for strategy,color in [('head',COLORS[0]),('tail',COLORS[1])]:
        subset=sorted([r for r in resource if r['strategy']==strategy],key=lambda x:x['target_trace_rate'])
        xs=[r['target_trace_rate']*100 for r in subset]
        for ax,key,label in zip(axs,['export_json_bytes','collector_cpu_s','peak_rss_bytes'],['Exported JSON','Collector CPU','Peak sampled RSS']):
            ys=[1-r[f'{key}_saving'] for r in subset]
            errlo=[r[f'{key}_saving_hi']-r[f'{key}_saving'] for r in subset]
            errhi=[r[f'{key}_saving']-r[f'{key}_saving_lo'] for r in subset]
            ax.errorbar(xs,ys,yerr=[errlo,errhi],fmt='o-',ms=3,lw=1,capsize=2,color=color,label=strategy.capitalize())
            ax.set_xscale('log');ax.set_xlim(.085,60);ax.set_xlabel('Trace budget (%)');ax.set_title(label,fontsize=10);ax.grid(alpha=.15)
            ax.axhline(1,color='0.6',ls=':',lw=1)
    axs[0].set_ylabel('Fraction of full-retention baseline');axs[2].legend(fontsize=8)
    fig.tight_layout();fig.savefig(FIG/'resource-tradeoff.pdf');plt.close(fig)
    summary={'cells':len(data),'offered_traces':sum(x['offered_traces'] for x in data),
             'offered_spans':sum(x['offered_spans'] for x in data),'full_cpu_mean':statistics.mean(x['collector_cpu_s'] for x in full.values()),
             'full_rss_mib_mean':statistics.mean(x['peak_rss_bytes']/2**20 for x in full.values()),
             'full_json_bytes_mean':statistics.mean(x['export_json_bytes'] for x in full.values()),
             'max_schedule_lag_s':max(x['max_schedule_lag_s'] for x in data),
             'min_ingress_s':min(x['ingress_s'] for x in data),'max_ingress_s':max(x['ingress_s'] for x in data),
             'all_complete':all(x['retained_traces']==x['complete_traces'] for x in data),'resources':resource}
    dump(OUT/'summary.json',summary)
    h=resource_map[('head',.1)]; tail=resource_map[('tail',.1)]
    macros={'MainCells':str(len(data)), 'MainTraces':f"{summary['offered_traces']:,}", 'MainSpans':f"{summary['offered_spans']:,}",
            'FullCPU':f"{summary['full_cpu_mean']:.2f}", 'FullRSS':f"{summary['full_rss_mib_mean']:.1f}",
            'IngressMin':f"{summary['min_ingress_s']:.3f}",'IngressMax':f"{summary['max_ingress_s']:.3f}",'MaxLagMS':f"{summary['max_schedule_lag_s']*1000:.2f}",
            'TailTenCPUIncrease':f"{-tail['collector_cpu_s_saving']*100:.1f}"}
    for label,record in [('HeadTen',h),('TailTen',tail)]:
        for suffix,key in [('Ingress','ingress_payload_bytes_saving'),('JSON','export_json_bytes_saving'),
                           ('CPU','collector_cpu_s_saving'),('CPULo','collector_cpu_s_saving_lo'),
                           ('CPUHi','collector_cpu_s_saving_hi'),('Gzip','archive_gzip_bytes_saving')]:
            macros[label+suffix]=f"{record[key]*100:.1f}"
        macros[label+'RSS']=f"{record['peak_rss_bytes_mean']/2**20:.1f}"
    (PAPER/'measurements.tex').write_text(''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in macros.items()))
    print(json.dumps({k:v for k,v in summary.items() if k!='resources'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path)
    args=p.parse_args();theory()
    if args.raw: empirical(args.raw)
