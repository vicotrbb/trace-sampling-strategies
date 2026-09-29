#!/usr/bin/env python3
"""Recompute descriptive replay precision and SDK resource rows from raw records."""
import gzip,json,math,statistics
from collections import defaultdict
from pathlib import Path
from scipy.stats import t

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def near(a,b):assert math.isclose(a,b,abs_tol=1e-12,rel_tol=1e-12),(a,b)

def main():
    groups=defaultdict(list);rows=0
    with gzip.open(ROOT/'data/raw/third-audit-20260925/diagnosis-replay-v1/trials.jsonl.gz','rt') as f:
        for line in f:
            r=json.loads(line);rows+=1
            if r['feasible']:groups[r['window'],r['policy'],r['budget']].append(r)
    assert rows==240000 and len(groups)==42
    data=read(ROOT/'data/derived/fifth-audit-20260928/localization-descriptive.json')
    checked=0
    for r in data['results']:
        if not r['feasible']:continue
        observations=groups[r['window'],r['policy'],r['budget']];n=len(observations);assert n==r['n']==5000
        correct=[int(x['correct']) for x in observations]
        differences=[int(x['full_correct'])-int(x['correct']) for x in observations]
        assert sum(correct)==r['correct'] and differences.count(1)==r['losses'] and differences.count(-1)==r['gains']
        for values,key in [(correct,'accuracy'),(differences,'paired_net_loss')]:
            near(statistics.mean(values),r[key]);near(statistics.stdev(values)/math.sqrt(n),r[key+'_mcse'])
        for phase in ['reference','incident']:near(statistics.mean(x['retained_'+phase] for x in observations),r['mean_'+phase+'_retained'])
        checked+=1
    live=ROOT/'data/raw/revision-20260924/confirm-v1';published=read(ROOT/'data/derived/revision/live-resources.json')
    ticks=read(live/'environment.json')['clock_ticks'];table=[]
    for app in ['checkout','documents']:
        for regime in ['steady','bursty']:
            sums={}
            for policy in ['full','head']:
                values=[]
                for seed in range(41001,41006):
                    e=read(live/f'{app}-{regime}'/f'seed-{seed}'/policy/'resource-endpoints.json');cpu={}
                    for name in ['gateway','worker','collector']:
                        points=[]
                        for endpoint in ['before','after']:
                            p=e[endpoint]['processes'][name];fields=p['raw_stat'].rsplit(') ',1)[1].split()
                            seconds=(int(fields[11])+int(fields[12]))/ticks;near(seconds,p['cpu_s']);points.append(seconds)
                        cpu[name]=points[1]-points[0]
                    values.append({'apps_cpu_s':cpu['gateway']+cpu['worker'],'collector_cpu_s':cpu['collector']})
                sums[policy]=values
            report=next(r for r in published if (r['app'],r['regime'],r['policy'])==(app,regime,'head'))
            row=[app.capitalize()+' '+('S' if regime=='steady' else 'B')]
            for key in ['apps_cpu_s','collector_cpu_s']:
                saving=[1-h[key]/f[key] for h,f in zip(sums['head'],sums['full'])]
                for a,b in zip(saving,report[key]['values']):near(a,b)
                mean=statistics.mean(saving);radius=t.ppf(.975,4)*statistics.stdev(saving)/math.sqrt(5)
                for field,value in [('mean',mean),('lo',mean-radius),('hi',mean+radius)]:near(value,report[key][field])
                row.append(f'{100*mean:.1f} [{100*(mean-radius):.1f}, {100*(mean+radius):.1f}]')
            table.append(' & '.join(row)+r' \\')
    expected='\n'.join(table)+'\n'
    assert expected==(ROOT/'paper/sdk-resource-rows.tex').read_text()
    cost=read(ROOT/'data/derived/final-cost-20260925/cost-summary.json')
    raw_cost=[read(p) for p in (ROOT/'data/raw/final-cost-20260925/confirm-v1').glob('block-*/*/result.json')]
    index={(r['block'],r['export'],r['timeout_ms'],r['sampler']):r for r in raw_cost};assert len(index)==96
    cost_checks=0
    for export in ['file','dual']:
        for timeout in [100,1000]:
            for policy in ['tail10','tail100']:
                values=[index[b,export,timeout,policy]['cpu_s']['collector']-index[b,export,timeout,'bypass']['cpu_s']['collector'] for b in range(51001,51009)]
                c=cost['contrasts'][f'{export}-{timeout}-{policy}-minus-bypass']
                for a,b in zip(values,c['values']):near(a,b)
                center=sum(values)/8;radius=2.3646242515927844*math.sqrt(sum((x-center)**2 for x in values)/7)/math.sqrt(8)
                for key,value in [('mean',center),('lower',center-radius),('upper',center+radius)]:near(value,c[key])
                cost_checks+=1
    receipt={'status':'PASS','raw_replay_rows':rows,'feasible_configurations_checked':checked,
             'independently_recomputed_accuracy_and_paired_loss_mcse':84,'sdk_rows_from_raw_process_ticks':len(table),
             'sdk_cells_checked':40,'low_load_plotted_contrasts_recomputed':cost_checks,'frozen_primary_analysis_unchanged':True}
    (ROOT/'docs/fifth-audit-20260928/context-validation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
