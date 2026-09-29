#!/usr/bin/env python3
"""Format verified sensitivity and boundary summaries without changing inference."""
import json,re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/derived/third-audit-20260925';PAPER=ROOT/'paper'
def read(name):return json.loads((OUT/name).read_text())
def tex(name,rows):(PAPER/name).write_text('\n'.join(rows)+'\n')
def results():
    d=read('diagnosis-summary.json');l=read('load-summary.json');macros={}
    macros['SensitivityThreshold']=f"{d['threshold_ms']:.2f}"
    cohort=[];selected=[];best={}
    for w in [20,50,200]:
        base=d['baselines'][str(w)];cnt=d['protected_counts'][str(w)]
        cohort.append(f"{w} & {base['correct']}/600 & {100*base['correct']/600:.2f} & {100*cnt['reference']/(600*w):.2f} & {100*cnt['incident']/(600*w):.2f} " + r'\\')
        tag={20:'Twenty',50:'Fifty',200:'TwoHundred'}[w]
        macros[f'Window{tag}Full']=f"{100*base['correct']/600:.2f}"
        for policy in ['head','tail']:
            passing=[r for r in d['results'] if r['window']==w and r['policy']==policy and r.get('meets_five_point_margin')]
            label=policy.capitalize()
            if not passing:
                selected.append(f"{w} & {label} & None & -- & -- & -- & -- " + r'\\');best[w,policy]=None;continue
            r=min(passing,key=lambda r:r['budget']);best[w,policy]=r
            macros[f'Window{tag}{label}Discard']=f"{100*(1-r['budget']):.0f}"
            macros[f'Window{tag}{label}Accuracy']=f"{100*r['correct']/r['n']:.2f}"
            macros[f'Window{tag}{label}Bound']=f"{100*r['upper_loss_bound']:.2f}"
            selected.append(f"{w} & {label} & {100*(1-r['budget']):.0f} & {100*r['correct']/r['n']:.2f} & {100*r['upper_loss_bound']:.2f} & {r['mean_reference_retained']:.1f} & {r['mean_incident_retained']:.1f} " + r'\\')
    tex('window-cohort-rows.tex',cohort);tex('window-supported-rows.tex',selected)
    rows=[]
    names={'full':'Full','gate10':'Uniform gate 10\\%','collector10':'Collector uniform 10\\%','tail10':'Tail 10\\%'}
    for policy in ['full','gate10','collector10','tail10']:
        g=l['groups'][policy];cpu=g['cpu_s']['mean'];jsonfraction=g['json_bytes']['mean']/l['groups']['full']['json_bytes']['mean']*100
        if policy=='full':saving='Reference'
        else:
            s=l['contrasts'][policy+'-minus-full']['cpu_saving_percent'];saving=f"{s['mean']:.1f} [{s['lower']:.1f}, {s['upper']:.1f}]"
            macros['Boundary'+{'gate10':'Gate','collector10':'Collector','tail10':'Tail'}[policy]+'Saving']=f"{s['mean']:.1f}"
        rows.append(f"{names[policy]} & {g['accepted_spans']['mean']/3000000*100:.1f} & {cpu:.3f} & {saving} & {jsonfraction:.1f} & {g['max_rss_bytes']['mean']/1024**2:.1f} " + r'\\')
    tex('boundary-rows.tex',rows)
    assert all(re.fullmatch('[A-Za-z]+',name) for name in macros)
    tex('third-audit-measurements.tex',['\\newcommand{\\'+k+'}{'+v+'}' for k,v in macros.items()])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    fig,axes=plt.subplots(2,3,figsize=(7.1,4.4),sharex=True,sharey='row',layout='constrained')
    for j,w in enumerate([20,50,200]):
        ax,loss=axes[:,j]
        ax.axhline(100*d['baselines'][str(w)]['correct']/600,color='#666666',ls=':',lw=1,label='Full corpus')
        for policy,color,marker in [('head','#2166ac','o'),('tail','#b35806','s')]:
            rr=sorted([r for r in d['results'] if r['window']==w and r['policy']==policy and r['feasible']],key=lambda r:r['budget'])
            xs=[100*r['budget'] for r in rr]
            ax.plot(xs,[100*r['correct']/5000 for r in rr],color=color,marker=marker,ms=3,label=policy.capitalize(),lw=1.4)
            loss.plot(xs,[100*r['upper_loss_bound'] for r in rr],color=color,marker=marker,ms=3,lw=1.4)
        ax.set(title=f'{w} requests per window',ylim=(0,102));loss.axhline(5,color='#777777',ls='--',lw=1)
        loss.set(yscale='log',ylim=(.1,100),xlim=(0,100),xlabel='Expected retention (%)',xticks=[5,20,50,80,95],yticks=[.1,1,5,20,100],yticklabels=['0.1','1','5','20','100'])
        for a in [ax,loss]:a.grid(axis='y',alpha=.2)
    axes[0,0].set_ylabel('Correct localization (%)');axes[1,0].set_ylabel('Loss upper bound (pp, log scale)')
    axes[0,0].legend(frameon=False,fontsize=8,loc='lower right')
    fig.savefig(PAPER/'figures/window-sensitivity.pdf');plt.close(fig)
    (OUT/'paper-selection-summary.json').write_text(json.dumps({'best_supported':{f'{w}-{p}':r for (w,p),r in best.items()}},indent=2)+'\n')
    display = {
        'threshold_ms': d['threshold_ms'],
        'baselines': d['baselines'],
        'alphas': d['protected_fraction'],
        'best_supported': {
            f'{w}-{p}': None if row is None else {
                key: row[key] for key in ['budget', 'correct', 'losses', 'gains',
                    'upper_loss_bound', 'mean_reference_retained', 'mean_incident_retained']
            } for (w,p), row in best.items()
        },
    }
    print(json.dumps(display, indent=2))
if __name__=='__main__':results()
