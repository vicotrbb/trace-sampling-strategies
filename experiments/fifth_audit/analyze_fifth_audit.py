#!/usr/bin/env python3
"""Analyze every frozen export-path and higher-load treatment, without workloads."""
import argparse,json,statistics
from pathlib import Path
from scipy.stats import t

def interval(xs):
    n=len(xs);mean=statistics.mean(xs);radius=t.ppf(.975,n-1)*statistics.stdev(xs)/n**.5 if n>1 else 0
    return {'n':n,'values':xs,'mean':mean,'lower':mean-radius,'upper':mean+radius}

def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    for kind in ['placement','batching']:
        base=a.raw/f'{kind}-confirm-v1';rows=[json.loads(x.read_text()) for x in sorted(base.glob('block-*/*/result.json'))]
        planned=json.loads((base/'plan.json').read_text());assert len(rows)==len(planned)==(40 if kind=='placement' else 20)
        groups={};contrasts={};blocks=sorted({x['block'] for x in rows})
        def select(export,timeout,policy):return sorted([x for x in rows if (x['export'],x['timeout_ms'],x['policy'])==(export,timeout,policy)],key=lambda x:x['block'])
        def value(row,key):
            if key=='collector_cpu_s':return row['cpu_s']['collector']
            if key=='jaeger_cpu_s':return row['cpu_s']['jaeger']
            if key=='collector_rss_bytes':return row['max_rss_bytes']['collector']
            if key=='jaeger_rss_bytes':return row['max_rss_bytes']['jaeger']
            return row[key]
        metrics=['collector_cpu_s','jaeger_cpu_s','collector_jaeger_cpu_s','generator_cpu_s','collector_rss_bytes','jaeger_rss_bytes','accepted_spans','exported_spans','json_bytes','batch_count','batch_timeout_triggers','batch_size_triggers','wall_s']
        for export,timeout,policy in sorted({(x['export'],x['timeout_ms'],x['policy']) for x in rows}):
            cells=select(export,timeout,policy);assert [x['block'] for x in cells]==blocks
            groups[f'{export}-{timeout}-{policy}']={k:interval([value(x,k) for x in cells]) for k in metrics}
        def difference(export,timeout,left,right):
            l,r=select(export,timeout,left),select(export,timeout,right);assert len(l)==len(r)==5
            return {k:interval([value(x,k)-value(y,k) for x,y in zip(l,r)]) for k in ['collector_cpu_s','jaeger_cpu_s','collector_jaeger_cpu_s']}
        if kind=='placement':
            for export in ['file','dual']:
                for left,right in [('gate10','full'),('collector10','full'),('tail10','full'),('collector10','gate10'),('tail10','collector10')]:
                    result=difference(export,1000,left,right)
                    result['collector_cpu_saving_percent']=interval([100*(1-x['cpu_s']['collector']/y['cpu_s']['collector']) for x,y in zip(select(export,1000,left),select(export,1000,right))])
                    contrasts[f'{export}:{left}-minus-{right}']=result
            for left,right in [('gate10','full'),('collector10','full'),('tail10','full'),('collector10','gate10'),('tail10','collector10')]:
                contrasts[f'export-interaction:{left}-minus-{right}']={k:interval([x-y for x,y in zip(contrasts[f'dual:{left}-minus-{right}'][k]['values'],contrasts[f'file:{left}-minus-{right}'][k]['values'])]) for k in ['collector_cpu_s','jaeger_cpu_s','collector_jaeger_cpu_s']}
        else:
            for timeout in [100,1000]:contrasts[f'{timeout}:tail100-minus-full']=difference('dual',timeout,'tail100','full')
            contrasts['timeout-interaction']={k:interval([x-y for x,y in zip(contrasts['1000:tail100-minus-full'][k]['values'],contrasts['100:tail100-minus-full'][k]['values'])]) for k in ['collector_cpu_s','jaeger_cpu_s','collector_jaeger_cpu_s']}
        result={'kind':kind,'cells':len(rows),'blocks':blocks,'rate_traces_s':rows[0]['rate_traces_s'],'groups':groups,'contrasts':contrasts,'max_schedule_lag_s':max(x['max_lag_s'] for x in rows),'total_throttled_usec':sum(x['throttled_usec'] for x in rows),'interval_scope':'Pointwise t summaries of paired runtime blocks, df=4; not a distributional assumption check.'}
        (a.out/f'{kind}-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(kind,len(rows),'cells analyzed')
if __name__=='__main__':main()
