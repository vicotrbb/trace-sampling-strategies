#!/usr/bin/env python3
"""Descriptive fixed-corpus Monte Carlo presentation; no new replay trials."""
import json,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]

def main():
    data=json.loads((ROOT/'data/derived/third-audit-20260925/diagnosis-summary.json').read_text())
    results=[]
    for r in data['results']:
        if not r['feasible']:
            results.append({k:r[k] for k in ['window','policy','budget','feasible']});continue
        n=r['n'];q=r['correct']/n;loss=(r['losses']-r['gains'])/n
        results.append({**{k:r[k] for k in ['window','policy','budget','feasible','n','correct','losses','gains','mean_reference_retained','mean_incident_retained']},
            'accuracy':q,'accuracy_mcse':math.sqrt(q*(1-q)/(n-1)),
            'paired_net_loss':loss,'paired_net_loss_mcse':math.sqrt(((r['losses']+r['gains'])-n*loss**2)/((n-1)*n))})
    out=ROOT/'data/derived/fifth-audit-20260928';out.mkdir(exist_ok=True,parents=True)
    (out/'localization-descriptive.json').write_text(json.dumps({'scope':'Post-collection descriptive view of the unchanged fixed-corpus replay. MCSE is conditional on the corpus, scorer and iid replay model, not population uncertainty. No qualifying-discard rule.','baselines':data['baselines'],'results':results},indent=2)+'\n')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    fig,axes=plt.subplots(2,3,figsize=(7.1,4.45),sharex=True,layout='constrained')
    for j,w in enumerate([20,50,200]):
        a,e=axes[:,j];a.axhline(100*data['baselines'][str(w)]['correct']/600,color='#666666',ls=':',lw=1,label='Full corpus')
        for policy,color,marker in [('head','#2166ac','o'),('tail','#b35806','s')]:
            rows=sorted([r for r in results if r['window']==w and r['policy']==policy and r['feasible']],key=lambda r:r['budget'])
            x=[r['budget']*100 for r in rows]
            a.errorbar(x,[r['accuracy']*100 for r in rows],yerr=[r['accuracy_mcse']*100 for r in rows],color=color,marker=marker,ms=3,lw=1.4,capsize=2,label=policy.capitalize())
            if policy=='head':e.plot(x,[w*r['budget'] for r in rows],color='#555555',ls=':',lw=1.5,label='Uniform expectation')
            else:
                for phase,col,m in [('reference','#b35806','s'),('incident','#238b45','^')]:e.plot(x,[r[f'mean_{phase}_retained'] for r in rows],color=col,marker=m,ms=3,lw=1.4,label=f'Tail {phase}')
        a.set(title=f'{w} requests per window',ylim=(0,102),yticks=[0,25,50,75,100]);e.set(ylim=(0,w*1.04),xlabel='Expected retention (%)',xlim=(0,100),xticks=[5,20,50,80,95])
        if j:a.tick_params(labelleft=False)
        for axis in [a,e]:axis.grid(axis='y',alpha=.2)
    axes[0,0].set_ylabel('Correct localization (%)');axes[1,0].set_ylabel('Mean retained requests')
    axes[0,0].legend(frameon=False,fontsize=7,loc='lower right');axes[1,0].legend(frameon=False,fontsize=6.5,loc='upper left')
    fig.savefig(ROOT/'paper/figures/window-evidence.pdf');plt.close(fig)
    macro=[]
    for p in ['head','tail']:
        r=next(r for r in results if r['window']==200 and r['policy']==p and r['budget']==.2)
        macro.append('\\newcommand{\\Window'+p.capitalize()+'MCSE}{'+f"{r['accuracy_mcse']*100:.2f}"+'}')
    r=next(r for r in results if r['window']==20 and r['policy']=='head' and r['budget']==.65)
    macro.append('\\newcommand{\\WindowNetLossMCSE}{'+f"{r['paired_net_loss_mcse']*100:.2f}"+'}')
    (ROOT/'paper/fifth-localization-measurements.tex').write_text('\n'.join(macro)+'\n')
    print('Descriptive localization: 42 feasible configurations, unchanged 5,000-trial inputs.')
if __name__=='__main__':main()
