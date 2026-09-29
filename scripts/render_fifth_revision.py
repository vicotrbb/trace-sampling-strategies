#!/usr/bin/env python3
"""Format frozen analyses; these plots and tables do not run workloads."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/derived/fifth-audit-20260928';PAPER=ROOT/'paper'
def read(p):return json.loads(p.read_text())
def mean(d):return d['mean']
def ci(d,places=1):return f"{d['mean']:.{places}f} [{d['lower']:.{places}f}, {d['upper']:.{places}f}]"

def main():
    placement=read(OUT/'placement-summary.json');rows=[]
    assert placement['rate_traces_s']==8000 and placement['cells']==40
    for export,label in [('file','JSON only'),('dual','JSON plus Jaeger')]:
        rows.append(r'\multicolumn{6}{l}{\textit{'+label+r'}} \\')
        full=placement['groups'][f'{export}-1000-full']
        for policy,name in [('full','Full'),('gate10',r'Pre-ingress 10\%'),('collector10',r'Collector 10\%'),('tail10',r'Tail 10\%')]:
            g=placement['groups'][f'{export}-1000-{policy}']
            saving='0.0 [baseline]' if policy=='full' else ci(placement['contrasts'][f'{export}:{policy}-minus-full']['collector_cpu_saving_percent'])
            row=[name,f"{mean(g['collector_cpu_s']):.2f}",saving,f"{mean(g['jaeger_cpu_s']):.2f}",f"{100*mean(g['json_bytes'])/mean(full['json_bytes']):.1f}",f"{mean(g['collector_rss_bytes'])/2**20:.1f}"]
            rows.append(' & '.join(row)+r' \\')
        if export=='file':rows.append(r'\addlinespace')
    (PAPER/'fifth-placement-rows.tex').write_text('\n'.join(rows)+'\n')
    macros={}
    for export,prefix in [('file','File'),('dual','Dual')]:
        for policy,short in [('gate10','Gate'),('collector10','Uniform'),('tail10','Tail')]:
            c=placement['contrasts'][f'{export}:{policy}-minus-full']['collector_cpu_saving_percent']
            macros['Placement'+prefix+short+'Saving']=f"{c['mean']:.1f}"
    macros['PlacementFileUniformIncrease']=f"{-placement['contrasts']['file:collector10-minus-full']['collector_cpu_saving_percent']['mean']:.1f}"
    old=read(ROOT/'data/derived/final-cost-20260925/cost-summary.json')
    high=read(OUT/'batching-summary.json')
    assert high['rate_traces_s'] in [1000,2000] and high['cells']==20
    high_rate=high['rate_traces_s']*5;macros['HighBatchRate']=f'{high_rate:,}'
    for timeout in [100,1000]:
        c=high['contrasts'][f'{timeout}:tail100-minus-full']['collector_cpu_s']
        name='Short' if timeout==100 else 'Long'
        macros['HighBatch'+name+'Difference']=f"{c['mean']:+.2f}"
        macros['HighBatch'+name+'Interval']=f"[{c['lower']:+.2f}, {c['upper']:+.2f}]"
    (PAPER/'fifth-measurements.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+v+'}' for k,v in macros.items())+'\n')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    fig,axes=plt.subplots(1,2,figsize=(7.1,3.6),gridspec_kw={'width_ratios':[1.28,1]},layout='constrained')
    plotted={};labels=[]
    for i,(export,timeout,policy) in enumerate((e,t,p) for e in ['file','dual'] for t in [100,1000] for p in ['tail10','tail100']):
        d=old['contrasts'][f'{export}-{timeout}-{policy}-minus-bypass']
        color='#2166ac' if policy=='tail10' else '#b35806';y=7-i
        axes[0].scatter(d['values'],[y]*len(d['values']),s=11,color=color,alpha=.5)
        axes[0].errorbar(d['mean'],y,xerr=[[d['mean']-d['lower']],[d['upper']-d['mean']]],fmt='D',color=color,ms=4,capsize=3)
        labels.append(('JSON' if export=='file' else 'Dual')+f', {timeout:,} ms, '+('10%' if policy=='tail10' else 'all'))
        plotted[f'250:{export}:{timeout}:{policy}']=d
    axes[0].set(yticks=list(range(7,-1,-1)),yticklabels=labels,title='250 spans/s; eight blocks')
    for j,timeout in enumerate([100,1000]):
        d=high['contrasts'][f'{timeout}:tail100-minus-full']['collector_cpu_s'];y=1-j
        axes[1].scatter(d['values'],[y]*len(d['values']),s=15,color='#b35806',alpha=.5)
        axes[1].errorbar(d['mean'],y,xerr=[[d['mean']-d['lower']],[d['upper']-d['mean']]],fmt='D',color='#b35806',ms=4,capsize=3)
        plotted[f'{high_rate}:dual:{timeout}:tail100']=d
    axes[1].set(yticks=[1,0],yticklabels=['Dual, 100 ms, all','Dual, 1,000 ms, all'],ylim=(-.55,1.55),title=f'{high_rate:,} spans/s; five blocks')
    for a in axes:
        a.axvline(0,color='#555555',ls=':',lw=1);a.grid(axis='x',alpha=.2);a.set_xlabel('Tail minus bypass CPU (s)')
        a.tick_params(axis='y',labelsize=8)
    fig.savefig(PAPER/'figures/controlled-cost-contrasts.pdf');plt.close(fig)
    (OUT/'cost-figure-data.json').write_text(json.dumps({'scope':'Separate x-axis scales; both experiments measure sixty seconds of offered load plus five seconds of drain.','contrasts':plotted},indent=2)+'\n')
    # Reproduce the restored SDK row directly from its retained paired summaries.
    live=read(ROOT/'data/derived/revision/live-resources.json');rows=[]
    for app in ['checkout','documents']:
        for regime in ['steady','bursty']:
            row=next(x for x in live if (x['app'],x['regime'],x['policy'])==(app,regime,'head'))
            values=[app.capitalize()+' '+('S' if regime=='steady' else 'B')]
            for key in ['apps_cpu_s','collector_cpu_s']:
                d=row[key];values.append(f"{100*d['mean']:.1f} [{100*d['lo']:.1f}, {100*d['hi']:.1f}]")
            rows.append(' & '.join(values)+r' \\')
    (PAPER/'sdk-resource-rows.tex').write_text('\n'.join(rows)+'\n')
    print('Rendered eight placement rows, ten paired cost contrasts, and four SDK rows.')

if __name__=='__main__':main()
