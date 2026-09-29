#!/usr/bin/env python3
"""Reconstruct new archives without importing either experiment or scorer."""
import argparse,gzip,hashlib,json,random
from collections import defaultdict
from pathlib import Path

SERVICES=['service-a','service-b','service-c']

def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def median(x):
    y=sorted(x);n=len(y);return y[n//2] if n%2 else (y[n//2-1]+y[n//2])/2
def diagnose(records,selected):
    times=defaultdict(list)
    for r in records:
        if r['trace_id'] in selected:
            for s,t in r['durations_ms'].items():times[r['phase'],s].append(t)
    if not times['reference',SERVICES[0]] or not times['incident',SERVICES[0]]:return None
    values=[median(times['incident',s])-median(times['reference',s]) for s in SERVICES]
    return SERVICES[values.index(max(values))]

def decision(tid,index,policy):
    if policy in ['full','tail100']:return True
    if policy=='head10':return int(hashlib.blake2b(bytes.fromhex(tid),digest_size=8).hexdigest(),16)<int(.1*2**64)
    if index%100 in [0,1]:return True
    number=14695981039346656037
    for byte in b'load-second-audit-v1'+bytes.fromhex(tid):number=((number^byte)*1099511628211)%(2**64)
    return number<=int((.08/.98)*(2**64-1))

def metric(text,name,exporter=None):
    total=0
    for line in text.splitlines():
        if line.startswith('#') or not line:continue
        key,value=line.rsplit(' ',1)
        if key.split('{')[0]==name and (exporter is None or f'exporter="{exporter}"' in key):total+=float(value)
    return total

def load(base):
    plan=read(base/'plan.json');environment=read(base/'environment.json');assert read(base/'complete.json')['cells']==len(plan)
    assert len(list(base.glob('block-*/*/result.json')))==len(plan)
    total_spans=0;max_lag=0;throttle=0
    for block,rate,policy in plan:
        p=base/f'block-{block}'/f'rate-{rate}-{policy}';r=read(p/'result.json');d=read(p/'design.json');assert r['valid'] and (r['block'],r['rate'],r['policy'])==(block,rate,policy)
        assert all(r[k]==v for k,v in d.items())
        for name,sha in d['sources'].items():assert digest(base/'executed-source'/name)==sha
        cfg=read(p/'config.json');assert cfg['processors']['batch']=={'timeout':'1000ms','send_batch_size':1024,'send_batch_max_size':2048}
        if policy.startswith('tail'):
            tail=cfg['processors']['tail_sampling'];assert tail['decision_wait']=='2s' and tail['num_traces']==d['capacity'] and tail['sample_on_first_match'] is False
            assert tail['policies'][2]['probabilistic']=={'sampling_percentage':100 if policy=='tail100' else 100*.08/.98,'hash_salt':'load-second-audit-v1'}
        else:assert 'tail_sampling' not in cfg['processors']
        limits={'warmup':rate*d['warmup_s'],'measured':rate*d['duration_s']};wanted={}
        for phase,n in limits.items():
            wanted[phase]=sum(decision(hashlib.sha256(f'{block}:{phase}:{i}'.encode()).hexdigest()[:32],i,policy) for i in range(n))
        masks={};span_total=0;measured_bytes=0
        assert digest(p/'traces.jsonl.gz')==r['export_gzip_sha256']
        with gzip.open(p/'traces.jsonl.gz','rt') as f:
            for line in f:
                phases=set()
                for resource in json.loads(line)['resourceSpans']:
                    assert resource['resource']['attributes']==[{'key':'service.name','value':{'stringValue':'load-service'}}]
                    for scope in resource['scopeSpans']:
                        for span in scope['spans']:
                            attrs={a['key']:next(iter(a['value'].values())) for a in span['attributes']};i=int(attrs['sequence']);phase=attrs['phase'];assert 0<=i<limits[phase];phases.add(phase)
                            tid=hashlib.sha256(f'{block}:{phase}:{i}'.encode()).hexdigest()[:32];assert span['traceId']==tid and decision(tid,i,policy)
                            j=int(span['spanId'],16)-1;assert 0<=j<5;key=(phase,i);bit=1<<j;assert not masks.get(key,0)&bit;masks[key]=masks.get(key,0)|bit
                            assert span.get('parentSpanId')==(None if j==0 else '0000000000000001')
                            assert span['name']==('request' if j==0 else f'operation-{j}') and span['kind']==2
                            first=1700000000000000000+i*1000000;last=first+(400000000 if i%100==1 and j==0 else 10000000)
                            assert int(span['startTimeUnixNano'])==first and int(span['endTimeUnixNano'])==last
                            assert span['status']['code']==(2 if i%100==0 and j==4 else 1)
                            span_total+=1
                assert len(phases)==1
                if phases=={'measured'}:measured_bytes+=len(line.encode())
        assert all(mask==31 for mask in masks.values())
        for phase in limits:assert sum(k[0]==phase for k in masks)==wanted[phase]
        assert r['exported_spans']==wanted['measured']*5==r['batch_spans'] and r['json_bytes']==measured_bytes
        receipts=read(p/'measured-receipts.json');assert [v['begin'] for v in receipts]==list(range(0,limits['measured'],100))
        for v in receipts:assert v['status']==200 and not json.loads(v['body']).get('partialSuccess',{}).get('rejectedSpans',0)
        assert sum(v['spans'] for v in receipts)==r['accepted_spans'];assert max(v['lag_s'] for v in receipts)==r['max_lag_s']
        endpoints=read(p/'endpoints.json');raw_cpus=[];cg=[]
        for moment in ['before','after']:
            value=endpoints[moment];proc=value['processes']['collector'];fields=proc['raw_stat'].split(') ',1)[1].split();cpu=(int(fields[11])+int(fields[12]))/environment['ticks'];assert cpu==proc['cpu_s'];raw_cpus.append(cpu)
            cg.append(dict(line.split() for line in value['runner_cgroup_cpu'].splitlines()))
        assert abs(raw_cpus[1]-raw_cpus[0]-r['cpu_s'])<1e-10
        samples=read(p/'samples.json');rss=[]
        for sample in samples:
            value=sample['processes']['collector'];fields=value['raw_stat'].split(') ',1)[1].split();actual=int(fields[21])*environment['page_size'];assert value['rss_bytes']==actual;rss.append(actual)
        assert max(rss)==r['max_rss_bytes']
        throttle+=int(cg[1]['throttled_usec'])-int(cg[0]['throttled_usec'])
        first=(p/'metrics-before.txt').read_text();last=(p/'metrics-after.txt').read_text()
        for name,expected,exporter in [('otelcol_receiver_accepted_spans_total',r['accepted_spans'],None),('otelcol_exporter_sent_spans_total',r['exported_spans'],'file'),('otelcol_processor_batch_batch_send_size_count',r['batches'],None)]:assert metric(last,name,exporter)-metric(first,name,exporter)==expected
        for line in last.splitlines():
            if line and not line.startswith('#') and any(x in line.split(' ')[0] for x in ['refused_spans','send_failed_spans','dropped_too_early']):assert float(line.rsplit(' ',1)[1])==0
        total_spans+=span_total;max_lag=max(max_lag,r['max_lag_s'])
    return {'status':'PASS','cells':len(plan),'exported_spans_including_warmup':total_spans,'max_lag_s':max_lag,'throttled_usec':throttle}

def corpus(base):
    plan=read(base/'plan.json');assert read(base/'complete.json')['episodes']==len(plan)
    paths=sorted((base/'episodes').glob('*.json.gz'));assert len(paths)==len(plan)
    rows={r['episode']:r for r in plan};episodes=[]
    for path in paths:
        e=json.loads(gzip.decompress(path.read_bytes()));d=e['design'];assert d==rows[d['episode']]
        assert [(r['phase'],r['index']) for r in e['records']]==[(phase,i) for phase in ['reference','incident'] for i in range(20)]
        spans=defaultdict(dict)
        for rs in e['resourceSpans']:
            service=rs['resource']['attributes'][0]['value']['stringValue'];assert service in SERVICES+['gateway']
            for ss in rs['scopeSpans']:
                for span in ss['spans']:
                    assert service not in spans[span['traceId']];spans[span['traceId']][service]=span
                    assert span['status']['code']==1 and not span.get('attributes')
        assert len(spans)==40
        for r in e['records']:
            tid=hashlib.sha256(f"diagnosis:{d['seed']}:{r['phase']}:{r['index']}".encode()).hexdigest()[:32];assert r['trace_id']==tid
            ss=spans[tid];assert set(ss)==set(SERVICES+['gateway']);root=ss['gateway'];begin=int(root['startTimeUnixNano']);end=int(root['endTimeUnixNano']);assert begin<end
            assert root['spanId']==hashlib.sha256((tid+':gateway').encode()).hexdigest()[:16] and not root.get('parentSpanId')
            assert r['root_ms']==(end-begin)/1e6
            for service in SERVICES:
                s=ss[service];a=int(s['startTimeUnixNano']);b=int(s['endTimeUnixNano']);assert begin<=a<b<=end and s['parentSpanId']==root['spanId']
                assert s['spanId']==hashlib.sha256((tid+':'+service).encode()).hexdigest()[:16]
                assert r['durations_ms'][service]==(b-a)/1e6
        assert e['full_prediction']==diagnose(e['records'],set(spans))
        episodes.append(e)
    return episodes

def replay(base,source,analysis=None):
    episodes=corpus(source);design=read(base/'design.json');assert len(episodes)==design['episodes']
    for name,sha in design['source_episode_sha256'].items():assert digest(source/'episodes'/name)==sha
    alpha=sum(r['root_ms']>=80 for e in episodes for r in e['records'])/(40*len(episodes));assert alpha==design['alpha']
    n=0;trial_last=-1;rng=None;episode=None;u=None;coverage=set();counts=defaultdict(lambda:defaultdict(int))
    with gzip.open(base/'trials.jsonl.gz','rt') as f:
        for line in f:
            row=json.loads(line);trial=row['trial'];key=(trial,row['policy'],row['budget']);assert key not in coverage;coverage.add(key)
            if trial!=trial_last:
                assert trial==trial_last+1;rng=random.Random(design['trial_seed_base']+trial);episode=episodes[rng.randrange(len(episodes))];u=[rng.random() for _ in range(40)];trial_last=trial
            p=row['policy'];b=row['budget'];assert b in design['budgets'] and p in ['head','tail']
            if p=='tail' and b<alpha:assert not row['feasible']
            else:
                rate=b if p=='head' else (b-alpha)/(1-alpha)
                chosen={r['trace_id'] for r,x in zip(episode['records'],u) if x<rate or (p=='tail' and r['root_ms']>=80)}
                answer=diagnose(episode['records'],chosen);truth=episode['design']['target'];baseline=episode['full_prediction'];before=baseline==truth;after=answer==truth
                expected={'episode':episode['design']['episode'],'feasible':True,'full_prediction':baseline,'prediction':answer,'truth':truth,'retained':len(chosen),'full_correct':before,'correct':after,'loss':before and not after,'gain':after and not before}
                assert all(row[k]==v for k,v in expected.items())
                tally=counts[p,b];tally['n']+=1;tally['full_correct']+=before;tally['correct']+=after;tally['abstentions']+=answer is None;tally['losses']+=before and not after;tally['gains']+=after and not before;tally['retained']+=len(chosen)
            n+=1
    assert n==design['trials']*16 and len(coverage)==n
    assert coverage=={(trial,policy,budget) for trial in range(design['trials']) for policy in ['head','tail'] for budget in design['budgets']}
    if analysis is not None:
        from scipy.optimize import brentq
        from scipy.stats import binom
        summary=read(analysis/'diagnosis-summary.json');assert summary['family_size']==16 and summary['confidence']==.95 and summary['protected_fraction']==alpha
        assert summary['baseline']['episodes']==len(episodes) and summary['baseline']['full_correct']==sum(e['full_prediction']==e['design']['target'] for e in episodes)
        assert len(summary['results'])==16 and {(r['policy'],r['budget']) for r in summary['results']}=={(p,b) for p in ['head','tail'] for b in design['budgets']}
        for r in summary['results']:
            key=r['policy'],r['budget']
            if key not in counts:assert not r['feasible'];continue
            tally=counts[key];total=tally['n'];loss=tally['losses']
            for name in ['n','full_correct','correct','abstentions','losses','gains']:assert r[name]==tally[name]
            upper=1.0 if loss==total else brentq(lambda p:binom.cdf(loss,total,p)-.05/16,0,1,xtol=1e-13)
            assert abs(r['upper_loss_bound']-upper)<2e-12 and r['meets_five_point_margin']==(upper<=.05)
            assert r['net_loss']==(loss-tally['gains'])/total and r['retained_fraction']==tally['retained']/(total*40)
    return {'status':'PASS','corpus_episodes':len(episodes),'trials_per_comparison':design['trials'],'comparison_rows':n,'protected_fraction':alpha,'full_correct':sum(e['full_prediction']==e['design']['target'] for e in episodes),'intervals_recomputed_by_binomial_inversion':analysis is not None}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['load','corpus','replay']);p.add_argument('directory',type=Path);p.add_argument('--corpus',type=Path);p.add_argument('--analysis',type=Path);p.add_argument('--receipt',type=Path);a=p.parse_args()
    if a.mode=='load':result=load(a.directory)
    elif a.mode=='replay':result=replay(a.directory,a.corpus,a.analysis)
    else:
        es=corpus(a.directory);result={'status':'PASS','episodes':len(es),'spans':len(es)*160,'full_correct':sum(e['full_prediction']==e['design']['target'] for e in es)}
    if a.receipt:a.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
