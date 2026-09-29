#!/usr/bin/env python3
"""Render tables and figures from the frozen analysis; no workload execution."""
from collections import Counter,defaultdict
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/derived/second-audit-20260925'
PAPER=ROOT/'paper'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
COLORS={'full':'#303b45','head10':'#1676a3','tail10':'#c76b21','tail100':'#795aa4'}
NAMES={'full':'Full retention','head10':'Head 10%','tail10':'Tail 10%','tail100':'Tail 100%'}
STYLES={'full':('o','-'),'head10':('s','--'),'tail10':('^','-.'),'tail100':('D',':')}

def macro(name,value):return '\\newcommand{\\'+name+'}{'+str(value)+'}\n'

def render():
    d=json.loads((OUT/'diagnosis-summary.json').read_text())
    rows={(r['policy'],r['budget']):r for r in d['results']}
    budgets=sorted({r['budget'] for r in d['results']})
    text=[]
    for b in budgets:
        h,t=rows['head',b],rows['tail',b]
        fields=[f'{100*b:g}']
        for key in ['correct','upper_loss_bound']:
            for r in [h,t]:fields.append(f"{100*r[key]/r['n']:.2f}" if key=='correct' else f"{100*r[key]:.2f}")
        passed=[p.capitalize() for p in ['head','tail'] if rows[p,b].get('meets_five_point_margin')]
        fields.append('Both' if len(passed)==2 else (passed[0] if passed else 'Neither'))
        text.append(' & '.join(fields)+r' \\')
    (PAPER/'task-diagnosis-rows.tex').write_text('\n'.join(text)+'\n')
    baseline=defaultdict(Counter)
    for key,value in d['baseline']['strata'].items():baseline['-'.join(key.split('-')[-2:])].update(value)
    strata={}
    for p in ['head','tail']:
        groups=defaultdict(Counter)
        for key,value in rows[p,.8]['descriptive_strata'].items():groups['-'.join(key.split('-')[-2:])].update(value)
        strata[p]=groups
    lines=[]
    for delay in [5,15]:
        for fraction in ['0.5','1']:
            key=f'{delay}-{fraction}';v=baseline[key];h,t=strata['head'][key],strata['tail'][key]
            lines.append(f"{delay} & {100*float(fraction):g} & {v['correct']}/{v['n']} & {h['n']} & {100*h['correct']/h['n']:.2f} & {100*t['correct']/t['n']:.2f}"+r' \\')
    (PAPER/'task-strata-rows.tex').write_text('\n'.join(lines)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(7.1,2.8),layout='constrained')
    for p,color,marker in [('head',COLORS['head10'],'o'),('tail',COLORS['tail10'],'s')]:
        values=[rows[p,b] for b in budgets if rows[p,b]['feasible']]
        x=[100*r['budget'] for r in values]
        axes[0].plot(x,[100*r['correct']/r['n'] for r in values],color=color,marker=marker,label=p.capitalize(),linewidth=1.4,markersize=4)
        axes[1].plot(x,[100*r['upper_loss_bound'] for r in values],color=color,marker=marker,label=p.capitalize(),linewidth=1.4,markersize=4)
    axes[0].axhline(100*d['baseline']['full_correct']/d['baseline']['episodes'],color=COLORS['full'],linestyle=':',linewidth=1.3,label='Full corpus')
    axes[0].set(ylabel='Correct localizations (%)',ylim=(0,100),title='(a) Absolute accuracy')
    axes[0].legend(frameon=False,loc='lower right',fontsize=8)
    axes[1].axhline(5,color=COLORS['full'],linestyle=':',linewidth=1.3)
    axes[1].set(ylabel='Simultaneous loss upper bound (pp)',ylim=(0,25),title='(b) Conservative loss bound')
    axes[1].annotate('5-point margin',xy=(36,5),xytext=(36,6.4),fontsize=8)
    # Low-budget limits exceed the plotted inset; disclose exact values in table.
    for ax in axes:
        ax.set(xlabel='Expected trace retention (%)',xlim=(0,100));ax.grid(axis='y',alpha=.2)
    fig.savefig(PAPER/'figures/task-diagnosis.pdf');plt.close(fig)
    macros=macro('TaskFullCorrect',d['baseline']['full_correct'])+macro('TaskFullAccuracy',f"{100*d['baseline']['full_correct']/d['baseline']['episodes']:.2f}")+macro('TaskAlpha',f"{100*d['protected_fraction']:.3f}")
    for p,label in [('head','Head'),('tail','Tail')]:
        r=rows[p,.8]
        macros+=macro('Task'+label+'Accuracy',f"{100*r['correct']/r['n']:.2f}")+macro('Task'+label+'Bound',f"{100*r['upper_loss_bound']:.2f}")
        passing=[r['budget'] for r in d['results'] if r['policy']==p and r.get('meets_five_point_margin')]
        macros+=macro('Task'+label+'Discard',f'{100*(1-min(passing)):g}' if passing else 'none')
    cost=json.loads((OUT/'load-summary.json').read_text())
    if cost['cells']==80:
        groups=cost['groups'];contrasts=cost['contrasts'];rates=[50,2000,8000,20000]
        fig,axes=plt.subplots(1,2,figsize=(7.1,2.8),layout='constrained')
        for p in NAMES:
            for axis,metric,scale in [(axes[0],'core_equivalents',100),(axes[1],'max_rss_bytes',1/2**20)]:
                ys=[groups[f'{rate}-{p}'][metric]['mean']*scale for rate in rates]
                lo=[(groups[f'{rate}-{p}'][metric]['mean']-groups[f'{rate}-{p}'][metric]['lower'])*scale for rate in rates]
                marker,linestyle=STYLES[p]
                axis.errorbar([r*5 for r in rates],ys,yerr=lo,label=NAMES[p],color=COLORS[p],marker=marker,linestyle=linestyle,markersize=3,linewidth=1.2,capsize=2)
        axes[0].set(ylabel='Collector CPU (% of one core)',title='(a) CPU over 35-second window')
        axes[1].set(ylabel='Mean sampled peak RSS (MiB)',title='(b) Memory during measurement')
        for ax in axes:
            ax.set(xscale='log',xlabel='Offered spans per second');ax.grid(axis='y',alpha=.2)
            ax.set_xticks([250,10000,40000,100000],['250','10k','40k','100k'])
            ax.minorticks_off()
        axes[0].legend(frameon=False,fontsize=7.5)
        fig.savefig(PAPER/'figures/load-sweep.pdf');plt.close(fig)
        highest=[];fulljson=groups['20000-full']['json_bytes']['mean']
        for p in NAMES:
            g=groups[f'20000-{p}'];ci=contrasts.get(f'20000-{p}',{}).get('cpu_saving_percent')
            saving='Reference' if ci is None else f"{ci['mean']:+.1f} [{ci['lower']:+.1f}, {ci['upper']:+.1f}]"
            highest.append(f"{NAMES[p].replace('%',r'\%')} & {g['cpu_s']['mean']:.2f} & {saving} & {100*g['json_bytes']['mean']/fulljson:.1f} & {g['max_rss_bytes']['mean']/2**20:.1f}"+r' \\')
        (PAPER/'load-high-rows.tex').write_text('\n'.join(highest)+'\n')
        macros+=macro('LoadCells',cost['cells'])
        for p,label in [('full','Full'),('head10','Head'),('tail10','Tail'),('tail100','AllTail')]:
            g=groups[f'20000-{p}'];macros+=macro('Load'+label+'Core',f"{100*g['core_equivalents']['mean']:.1f}")+macro('Load'+label+'CPU',f"{g['cpu_s']['mean']:.2f}")
            if p!='full':
                c=contrasts[f'20000-{p}']['cpu_saving_percent']
                macros+=macro('Load'+label+'Saving',f"{c['mean']:.1f}")
        # Absolute row summaries and all points remain independently inspectable.
    (PAPER/'second-audit-measurements.tex').write_text(macros)
    print(json.dumps({'diagnosis_comparisons':len(rows),'load_cells':cost['cells'],'rendered_load':cost['cells']==80},indent=2))

if __name__=='__main__':render()
