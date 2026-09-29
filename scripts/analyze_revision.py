#!/usr/bin/env python3
"""Generate revision tables, figures, and statistics from archived measurements."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
import math
from pathlib import Path
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from scipy.stats import binom, binomtest, chisquare, t
from verify_revision import parse_exports, protected

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/derived/revision'
PAPER=ROOT/'paper'
COLORS=['#164c74','#ad4f19','#49806c','#6c4b8d']
plt.rcParams.update({'font.family':'serif','mathtext.fontset':'cm','font.size':10,
 'axes.spines.top':False,'axes.spines.right':False,'axes.labelsize':10,
 'legend.fontsize':8,'figure.dpi':150,'savefig.bbox':'tight','pdf.fonttype':42})

def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())

def dump(path,data):path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')

def csvwrite(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def mean_ci(values):
    mean=statistics.mean(values)
    half=float(t.ppf(.975,len(values)-1))*statistics.stdev(values)/math.sqrt(len(values)) if len(values)>1 else float('nan')
    return {'mean':mean,'lo':mean-half,'hi':mean+half,'n_blocks':len(values),'values':values}

def short(app,regime):
    return ('Checkout' if app=='checkout' else 'Documents')+(' S' if regime=='steady' else ' B')

def architecture():
    fig,ax=plt.subplots(figsize=(6.8,2.7))
    ax.set(xlim=(0,1.02),ylim=(0,1));ax.axis('off')
    ax.add_patch(FancyBboxPatch((.265,.16),.735,.72,boxstyle='round,pad=0.008',
                              fc='#f3f6f8',ec='#72828d',lw=.8))
    ax.text(.632,.935,'Measured ingestion-interval CPU',ha='center',va='center',fontsize=10)
    def box(x,y,w,h,text,color):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.012',fc='white',ec=color,lw=1.1))
        ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=8.5)
    def arrow(start,end,telemetry=False):
        ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=10,lw=1,
                                    linestyle='--' if telemetry else '-',
                                    color=COLORS[0] if telemetry else '#444444'))
    box(.02,.645,.18,.18,'Load driver\n50 requests/s','#777777')
    box(.30,.645,.17,.18,'Gateway\nSDK head / full',COLORS[0])
    box(.545,.645,.17,.18,'Worker\nInherited decision',COLORS[0])
    box(.79,.645,.18,.18,'PostgreSQL\nContainer cgroup',COLORS[2])
    box(.435,.215,.275,.21,'Collector\nOptional tail policy\nJSON evidence mirror',COLORS[1])
    box(.795,.215,.175,.21,'Jaeger\nLocal Badger',COLORS[2])
    for a,b in [((.21,.735),(.286,.735)),((.48,.735),(.531,.735)),((.725,.735),(.776,.735))]:arrow(a,b)
    arrow((.385,.63),(.50,.44),True);arrow((.63,.63),(.62,.44),True)
    arrow((.723,.32),(.781,.32),True)
    ax.text(.515,.535,'OTLP',fontsize=8,color=COLORS[0],ha='center')
    ax.text(.52,.065,'Solid: application requests. Dashed: recorded telemetry.',ha='center',fontsize=8)
    fig.tight_layout(pad=.25);fig.savefig(PAPER/'figures/live-pipeline.pdf');plt.close(fig)

def live(base):
    paths=sorted((base/'confirm-v1').glob('*/*/*/result.json'))
    assert len(paths)==60,len(paths)
    cells=[];confusion=Counter()
    for path in paths:
        result=read(path);cell=path.parent;endpoints=read(cell/'resource-endpoints.json')
        before,after=endpoints['before'],endpoints['after']
        rows=read(cell/'truth.json');outcomes=read(cell/'outcomes.json')
        _,exported_traces,_=parse_exports(cell/'traces.jsonl.gz')
        measured_ids={r['trace_id'] for r in rows}
        protected_count=sum(protected(list(spans.values())) for tid,spans in exported_traces.items() if tid in measured_ids)
        for outcome in outcomes:
            confusion[(result['app'],result['regime'],result['policy'],outcome['kind'],*outcome['prediction'],outcome['retained'])]+=1
        cpu={name:after['processes'][name]['cpu_s']-before['processes'][name]['cpu_s']
             for name in before['processes']}
        cpu['apps']=cpu['gateway']+cpu['worker']
        cpu['postgres']=after['postgres']['cpu_s']-before['postgres']['cpu_s']
        cpu['pipeline']=cpu['apps']+cpu['collector']+cpu['jaeger']+cpu['postgres']
        samples=read(cell/'resource-samples.json')
        assert not any('error' in s for s in samples)
        samples=[before]+samples+[after]
        rss={name:max(s['processes'][name]['rss_bytes'] for s in samples) for name in before['processes']}
        rss['postgres_cgroup']=max(s['postgres']['memory_current'] for s in samples)
        flat={k:result[k] for k in ['app','regime','seed','policy','retained_measured','offered_measured','false_accusations']}
        flat.update({key+'_cpu_s':value for key,value in cpu.items()})
        flat.update({key+('_sampled_memory_bytes' if key=='postgres_cgroup' else '_sampled_rss_bytes'):value for key,value in rss.items()})
        for component in before['processes']:
            flat[component+'_rss_start_bytes']=before['processes'][component]['rss_bytes']
            flat[component+'_rss_end_bytes']=after['processes'][component]['rss_bytes']
            flat[component+'_rss_growth_bytes']=after['processes'][component]['rss_bytes']-before['processes'][component]['rss_bytes']
        flat['postgres_memory_start_bytes']=before['postgres']['memory_current']
        flat['postgres_memory_end_bytes']=after['postgres']['memory_current']
        flat.update(export_json_bytes=result['export_json_bytes_all'],
                    disk_logical_bytes=result['storage']['after_shutdown']['logical_bytes'],
                    disk_allocated_bytes=result['storage']['after_shutdown']['allocated_bytes'],
                    preclose_logical_bytes=result['storage']['ingest']['logical_bytes'],
                    preclose_allocated_bytes=result['storage']['ingest']['allocated_bytes'],
                    query_before_s=result['query_before_restart']['seconds'],
                    query_after_s=result['query_after_restart']['seconds'],
                    query_traces=result['query_after_restart']['trace_count'],
                    max_schedule_lag_s=max(r['schedule_lag_s'] for r in rows),
                    request_p99_s=float(np.quantile([r['latency_s'] for r in rows],.99)),
                    measured_interval_s=after['end_monotonic']-before['begin_monotonic'])
        flat.update({kind+'_correct':result['diagnosis_by_kind'][kind]['correct']
                     for kind in ['sql_schema','database_latency','domain_invariant']})
        flat['fault_cases']=90
        completion=max(result['duration_s'],max(r['started_s']+r['latency_s'] for r in rows))
        flat['completion_elapsed_s']=completion
        flat['achieved_completion_rate']=len(rows)/completion
        flat['controller_cpu_s']=endpoints['controller_after']['cpu_s']-endpoints['controller_before']['cpu_s']
        def cg(raw):
            return {parts[0]:int(parts[1]) for line in raw.splitlines() if len(parts:=line.split())==2 and parts[0] in ('usage_usec','nr_throttled','throttled_usec')}
        for component in ('runner','postgres'):
            a=before['runner_cgroup_cpu'] if component=='runner' else before['postgres']['raw']
            b=after['runner_cgroup_cpu'] if component=='runner' else after['postgres']['raw']
            ac,bc=cg(a),cg(b)
            flat[component+'_throttled_periods']=bc['nr_throttled']-ac['nr_throttled']
            flat[component+'_throttled_s']=(bc['throttled_usec']-ac['throttled_usec'])/1e6
        flat['normal_retained']=sum(o['kind']=='normal' and o['retained'] for o in outcomes)
        flat['protected_exported_measured']=protected_count
        flat['protected_fraction_full']=protected_count/len(rows) if result['policy']=='full' else None
        flat['missing_faults']=sum(o['kind']!='normal' and not o['retained'] for o in outcomes)
        flat['retained_incorrect_faults']=sum(o['kind']!='normal' and o['retained'] and not o['correct'] for o in outcomes)
        flat['cause_correct']=sum(o['kind']!='normal' and o['prediction'][0]==o['kind'] for o in outcomes)
        flat['service_correct']=sum(o['kind']!='normal' and o['prediction'][1]==o['service'] for o in outcomes)
        cells.append(flat)
    csvwrite(OUT/'live-cells.csv',cells)
    dump(OUT/'diagnostic-confusion.json',[{**dict(zip(['app','regime','policy','truth','predicted_cause','predicted_service','retained'],key)),'n':value} for key,value in sorted(confusion.items())])
    full={(r['app'],r['regime'],r['seed']):r for r in cells if r['policy']=='full'}
    resources=[];diagnoses=[];resource_tex=[];diagnostic_tex=[];memory_tex=[];storage_tex=[]
    for app in ['checkout','documents']:
        for regime in ['steady','bursty']:
            for policy in ['full','head','tail']:
                group=[r for r in cells if (r['app'],r['regime'],r['policy'])==(app,regime,policy)]
                row={'app':app,'regime':regime,'policy':policy,
                     'retained_rate':sum(r['retained_measured'] for r in group)/sum(r['offered_measured'] for r in group),
                     'correct':sum(sum(r[k+'_correct'] for k in ['sql_schema','database_latency','domain_invariant']) for r in group),
                     'n_faults':sum(r['fault_cases'] for r in group),
                     'false_accusations':sum(r['false_accusations'] for r in group),
                     'n_normal_offered':sum(r['offered_measured']-r['fault_cases'] for r in group),
                     'n_normal_retained':sum(r['normal_retained'] for r in group)}
                for kind in ['sql_schema','database_latency','domain_invariant']:
                    row[kind+'_accuracy']=sum(r[kind+'_correct'] for r in group)/150
                diagnoses.append(row)
                diagnostic_tex.append(short(app,regime)+' & '+policy.capitalize()+' & '+f"{100*row['retained_rate']:.2f}"+
                   ''.join(f" & {100*row[k+'_accuracy']:.1f}" for k in ['sql_schema','database_latency','domain_invariant'])+
                   f" & {100*row['correct']/row['n_faults']:.1f} & {row['false_accusations']}/{row['n_normal_offered']:,}"+r' \\')
                memory_tex.append(short(app,regime)+' & '+policy.capitalize()+
                    ''.join(f" & {statistics.mean(r[k+'_sampled_rss_bytes'] for r in group)/2**20:.1f}" for k in ['gateway','worker','collector','jaeger'])+
                    f" & {statistics.mean(r['postgres_cgroup_sampled_memory_bytes'] for r in group)/2**20:.1f}"+r' \\')
                if policy=='full':continue
                report={'app':app,'regime':regime,'policy':policy}
                for metric in ['apps_cpu_s','collector_cpu_s','jaeger_cpu_s','postgres_cpu_s','pipeline_cpu_s',
                               'export_json_bytes','disk_logical_bytes','disk_allocated_bytes']:
                    values=[1-r[metric]/full[(app,regime,r['seed'])][metric] for r in group]
                    report[metric]=mean_ci(values)
                resources.append(report)
                storage_tex.append(short(app,regime)+' & '+policy.capitalize()+
                    ''.join(f" & {100*report[k]['mean']:.1f}" for k in ['export_json_bytes','disk_logical_bytes','disk_allocated_bytes'])+r' \\')
                total=report['pipeline_cpu_s']
                resource_tex.append(short(app,regime)+' & '+policy.capitalize()+
                    ''.join(f" & {100*report[k+'_cpu_s']['mean']:.1f}" for k in ['apps','collector','jaeger','postgres'])+
                    f" & {100*total['mean']:.1f} [{100*total['lo']:.1f}, {100*total['hi']:.1f}]"+r' \\')
    csvwrite(OUT/'live-diagnosis.csv',diagnoses);dump(OUT/'live-resources.json',resources)
    (PAPER/'live-diagnosis-rows.tex').write_text('\n'.join(diagnostic_tex)+'\n')
    (PAPER/'live-resource-rows.tex').write_text('\n'.join(resource_tex)+'\n')
    (PAPER/'live-memory-rows.tex').write_text('\n'.join(memory_tex)+'\n')
    (PAPER/'live-storage-rows.tex').write_text('\n'.join(storage_tex)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(6.8,2.85))
    combos=[(a,r) for a in ['checkout','documents'] for r in ['steady','bursty']]
    for policy,color,offset in [('head',COLORS[0],-.10),('tail',COLORS[1],.10)]:
        for ax,metric,title in zip(axes,['pipeline_cpu_s','disk_allocated_bytes'],['Ingestion-interval pipeline CPU','Closed Badger allocated size']):
            records=[next(r for r in resources if (r['app'],r['regime'],r['policy'])==(a,l,policy))[metric] for a,l in combos]
            means=[1-r['mean'] for r in records]
            errors=[[r['hi']-r['mean'] for r in records],[r['mean']-r['lo'] for r in records]]
            ax.errorbar(np.arange(4)+offset,means,yerr=errors,fmt='o',capsize=3,color=color,label=policy.capitalize())
            ax.axhline(1,color='0.55',ls=':',lw=1);ax.set_title(title,fontsize=9)
            ax.set_xticks(range(4),['Checkout\nsteady','Checkout\nbursty','Documents\nsteady','Documents\nbursty'],fontsize=7)
            ax.grid(axis='y',alpha=.15)
    axes[0].set_ylabel('Fraction of full-retention control');axes[1].legend()
    fig.tight_layout();fig.savefig(PAPER/'figures/live-resource-tradeoff.pdf');plt.close(fig)
    return {'cells':60,'measured_requests':sum(r['offered_measured'] for r in cells),
            'measured_fault_cases':sum(r['fault_cases'] for r in cells),
            'max_schedule_lag_s':max(r['max_schedule_lag_s'] for r in cells),
            'false_accusations':sum(r['false_accusations'] for r in cells),
            'retained_incorrect_faults':sum(r['retained_incorrect_faults'] for r in cells),
            'protected_fraction_range':[min(r['protected_fraction_full'] for r in cells if r['policy']=='full'),max(r['protected_fraction_full'] for r in cells if r['policy']=='full')],
            'completion_rate_range':[min(r['achieved_completion_rate'] for r in cells),max(r['achieved_completion_rate'] for r in cells)],
            'throttled_periods':{component:sum(r[component+'_throttled_periods'] for r in cells) for component in ['runner','postgres']},
            'max_throttled_s':{component:max(r[component+'_throttled_s'] for r in cells) for component in ['runner','postgres']},
            'rss_growth_range_mib':{component:[min(r[component+'_rss_growth_bytes'] for r in cells)/2**20,max(r[component+'_rss_growth_bytes'] for r in cells)/2**20] for component in ['gateway','worker','collector','jaeger']},
            'full_cpu_mean_by_workload':{short(a,l):statistics.mean(r['pipeline_cpu_s'] for r in cells if (r['app'],r['regime'],r['policy'])==(a,l,'full')) for a,l in combos},
            'resource_savings':resources,'diagnosis':diagnoses,
            'query_before_range_s':[min(r['query_before_s'] for r in cells),max(r['query_before_s'] for r in cells)],
            'query_after_range_s':[min(r['query_after_s'] for r in cells),max(r['query_after_s'] for r in cells)]}

def calibration(base):
    blocks=read(base/'calibration/blocks.json');assert len(blocks)==480
    groups=defaultdict(list)
    for row in blocks:groups[(row['stream'],row['hash'],row['salt'])].append(row)
    assert len(groups)==16
    tests=[]
    for key,rows in sorted(groups.items()):
        assert len(rows)==30
        observed=np.sum([r['histogram'] for r in rows],axis=0)
        expected=60000*binom.pmf(np.arange(6),5,.08/.98)
        # Prespecified merge of rare upper bins; first five categories become 0,1,2,3,4+.
        observed=np.r_[observed[:4],observed[4:].sum()]
        expected=np.r_[expected[:4],expected[4:].sum()]
        assert min(expected)>=5
        stat,p=chisquare(observed,expected)
        tests.append({'stream':key[0],'hash':key[1],'salt':key[2],'chi_square':float(stat),'p':float(p),
                      'observed_bins':observed.tolist(),'expected_bins':expected.tolist(),'df':4,
                      'retention':sum(r['retained_traces'] for r in rows)/300000,
                      'witness_recovery':sum(r['incidents']-r['histogram'][0] for r in rows)/60000,
                      'block_recovery':mean_ci([(r['incidents']-r['histogram'][0])/r['incidents'] for r in rows]),
                      'shared_head_recovery':sum(r['shared_head_incidents'] for r in rows)/60000})
    order=sorted(range(len(tests)),key=lambda i:tests[i]['p']);previous=0
    for rank,index in enumerate(order):
        adjusted=min(1,max(previous,(len(tests)-rank)*tests[index]['p']))
        tests[index]['holm_p']=adjusted;tests[index]['rejected']=adjusted<.05;previous=adjusted
    dump(OUT/'calibration-tests.json',tests)
    tex=[]
    for row in tests:
        salt='Original' if row['salt']=='trace-study-v1' else row['salt'].rsplit('-',1)[-1]
        tex.append(f"{row['stream']} & {row['hash']} & {salt} & {100*row['retention']:.3f} & {100*row['witness_recovery']:.2f} & {row['p']:.3g} & {row['holm_p']:.3g}"+r' \\')
    (PAPER/'calibration-rows.tex').write_text('\n'.join(tex)+'\n')
    original_p=float(binomtest(19,100,1-(1-.08/.98)**5).pvalue)
    return {'tests':tests,'rejections':sum(t['rejected'] for t in tests),'model_recovery':float(binom.sf(0,5,.08/.98)),
            'original_selected_p':original_p,'original_bonferroni_130_p':min(1,130*original_p)}

def matched(base):
    results=[read(p) for p in sorted((base/'matched-probes').glob('*/*/result.json'))]
    assert len(results)==48
    groups=defaultdict(list)
    for r in results:groups[tuple(r[k] for k in ['root_error','late','cache','churn'])].append(r)
    rows=[];tex=[]
    for key,values in sorted(groups.items()):
        assert len(values)==3
        row=dict(zip(['root_error','late','cache','churn'],key))
        for metric in ['retained_error_ids','retained_spans','complete','witnesses']:
            row[metric+'_min']=min(v[metric] for v in values);row[metric+'_max']=max(v[metric] for v in values)
        rows.append(row)
        def range_text(metric):
            lo,hi=row[metric+'_min'],row[metric+'_max']
            return str(lo) if lo==hi else str(lo)+'--'+str(hi)
        tex.append(' & '.join(['Yes' if key[0] else 'No','Late' if key[1] else 'Immediate','On' if key[2] else 'Off','Yes' if key[3] else 'No']+
                             [range_text(m) for m in ['retained_error_ids','retained_spans','complete','witnesses']])+r' \\')
    (PAPER/'matched-probe-rows.tex').write_text('\n'.join(tex)+'\n')
    csvwrite(OUT/'matched-probes.csv',rows)
    return rows

def offline(base):
    curves=read(base/'counterfactual/curves.json')
    assert len(curves)==800,len(curves)
    groups=defaultdict(list)
    for row in curves:
        groups[tuple(row[k] for k in ['app','regime','priorities','policy','rate'])].append(row)
    results=[]
    for key,rows in sorted(groups.items()):
        assert len(rows)==5
        rows=[row for row in rows if row['feasible']]
        if len(rows)!=5:
            results.append({**dict(zip(['app','regime','priorities','policy','rate'],key)),
                            'eligible':False,'reason':'Not all five prespecified blocks are feasible',
                            'n_feasible_blocks':len(rows)})
            continue
        for endpoint in ['requests','groups']:
            values=[];accuracies=[];rates=[]
            for row in rows:
                suffix='' if endpoint=='requests' else '_groups'
                baseline=sum(r['baseline'+suffix] for r in row['by_kind'].values())
                correct=sum(r['correct'+suffix] for r in row['by_kind'].values())
                denominator=sum(r['n' if endpoint=='requests' else 'groups'] for r in row['by_kind'].values())
                values.append((baseline-correct)/denominator);accuracies.append(correct/denominator)
                rates.append(row['retained']/row['offered'])
            radius=math.sqrt(math.log(160/.05)/(2*len(rows)))
            bound=min(1,statistics.mean(values)+radius)
            results.append({**dict(zip(['app','regime','priorities','policy','rate'],key)),
                            'eligible':True,'endpoint':endpoint,'loss':statistics.mean(values),'accuracy':statistics.mean(accuracies),
                            'loss_by_block':values,'accuracy_by_block':accuracies,'retained_trace_rate':statistics.mean(rates),
                            'simultaneous_loss_upper':bound if key[2]=='native' else None,'margin_certified':key[2]=='native' and bound<=.05,
                            'deterministic_identity':key[-1]==1})
    dump(OUT/'offline-curves.json',results)
    class_groups=defaultdict(list)
    for row in curves:
        if not row['feasible']:continue
        for kind,counts in row['by_kind'].items():
            class_groups[tuple(row[k] for k in ['app','regime','priorities','policy','rate'])+(kind,)].append({'seed':row['seed'],**counts})
    class_summary=[]
    for key,rows in sorted(class_groups.items()):
        class_summary.append({**dict(zip(['app','regime','priorities','policy','rate','kind'],key)),
                              'n_feasible_blocks':len(rows),'correct':sum(r['correct'] for r in rows),
                              'n':sum(r['n'] for r in rows),'correct_groups':sum(r['correct_groups'] for r in rows),
                              'n_groups':sum(r['groups'] for r in rows),'block_values':rows,
                              'scope':'Descriptive cause-specific result outside the aggregate certification family'})
    dump(OUT/'offline-class-summary.json',class_summary)
    shared_ten={policy:{'correct':sum(r['correct'] for r in class_summary if (r['priorities'],r['policy'],r['rate'],r['kind'])==('shared',policy,.1,'domain_invariant')),
                        'n':sum(r['n'] for r in class_summary if (r['priorities'],r['policy'],r['rate'],r['kind'])==('shared',policy,.1,'domain_invariant'))}
                for policy in ['head','tail']}
    ablations=read(base/'counterfactual/ablations.json.gz')
    assert len(ablations)==100
    totals=defaultdict(Counter)
    for item in ablations:
        mask=item['mask']
        for row in item['outcomes']:
            if row['kind']=='normal':
                totals[mask]['normal']+=1
                totals[mask]['false_accusations']+=row['prediction'][0]!='abstain'
            else:
                totals[mask]['faults']+=1;totals[mask]['correct']+=row['correct']
                totals[mask][row['kind']+'_n']+=1;totals[mask][row['kind']+'_correct']+=row['correct']
                totals[mask][f"complete_{int(row['complete'])}_correct_{int(row['correct'])}"]+=1
    dump(OUT/'ablation-summary.json',totals)
    names={'none':'Full trace','remove_gateway':'Remove gateway','remove_database':'Remove database',
           'remove_validator':'Remove validator','evidence_leaf_only':'Evidence leaf only'}
    tex=[]
    for mask,row in totals.items():
        tex.append(names[mask]+''.join(f" & {row[k+'_correct']}/{row[k+'_n']}" for k in ['sql_schema','database_latency','domain_invariant'])+
                   f" & {row['false_accusations']}/{row['normal']}"+r' \\')
    (PAPER/'ablation-rows.tex').write_text('\n'.join(tex)+'\n')
    fig,axes=plt.subplots(2,2,figsize=(6.8,5.0),sharex=True,sharey=True)
    for ax,(app,regime) in zip(axes.flat,[(a,r) for a in ['checkout','documents'] for r in ['steady','bursty']]):
        for policy,color in [('head',COLORS[0]),('tail',COLORS[1])]:
            for endpoint,style in [('requests','-'),('groups','--')]:
                rows=sorted([r for r in results if r.get('eligible') and (r['app'],r['regime'],r['priorities'],r['policy'],r['endpoint'])==(app,regime,'native',policy,endpoint)],key=lambda r:r['rate'])
                ax.plot([100*r['rate'] for r in rows],[100*r['accuracy'] for r in rows],ls=style,color=color,marker='o',ms=2,
                        label=policy.capitalize()+(' requests' if endpoint=='requests' else ' groups of 5'))
        ax.axhline(95,color='0.45',ls=':',lw=1);ax.set_title(short(app,regime),fontsize=10)
        ax.set_xlim(0,100);ax.set_ylim(0,103);ax.grid(alpha=.12)
    for ax in axes[-1]:ax.set_xlabel('Nominal retained-trace budget (%)')
    fig.supylabel('Correct classification / group recovery (%)',x=.005,fontsize=10)
    axes[0,0].legend(loc='lower right',fontsize=6)
    fig.tight_layout(rect=(.03,0,1,1));fig.savefig(PAPER/'figures/live-selection-curves.pdf');plt.close(fig)
    return {'curves':results,'ablations':totals,'shared_ten_semantic':shared_ten,'bound_radius':math.sqrt(math.log(160/.05)/10)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=ROOT/'data/raw/revision-20260924')
    args=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    architecture()
    summary={'live':live(args.raw),'calibration':calibration(args.raw),'matched':matched(args.raw),'offline':offline(args.raw)}
    dump(OUT/'summary.json',summary)
    h=[r for r in summary['live']['diagnosis'] if r['policy']=='head']
    tail=[r for r in summary['live']['diagnosis'] if r['policy']=='tail']
    macros={'LiveCells':'60','LiveRequests':f"{summary['live']['measured_requests']:,}",
            'LiveFaults':f"{summary['live']['measured_fault_cases']:,}",
            'LiveHeadAccuracy':f"{100*sum(r['correct'] for r in h)/sum(r['n_faults'] for r in h):.1f}",
            'LiveTailAccuracy':f"{100*sum(r['correct'] for r in tail)/sum(r['n_faults'] for r in tail):.1f}",
            'CalibrationRejects':str(summary['calibration']['rejections']),
            'HoeffdingRadius':f"{100*summary['offline']['bound_radius']:.1f}",
            'CommonHeadSemanticCorrect':str(summary['offline']['shared_ten_semantic']['head']['correct']),
            'CommonTailSemanticCorrect':str(summary['offline']['shared_ten_semantic']['tail']['correct']),
            'CommonSemanticCases':str(summary['offline']['shared_ten_semantic']['head']['n']),
            'LiveMaxLagMS':f"{1000*summary['live']['max_schedule_lag_s']:.2f}"}
    (PAPER/'revision-measurements.tex').write_text(''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in macros.items()))
    print(json.dumps({'live_cells':60,'calibration_tests':16,'matched_probes':48,'offline_cells':800,'macros':macros},indent=2))

if __name__=='__main__':main()
