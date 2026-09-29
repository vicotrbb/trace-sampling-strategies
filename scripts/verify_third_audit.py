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

def native_hash(tid):
    value=0x811c9dc5
    for octet in bytes([193,6,0,0])+bytes.fromhex(tid):value=((value^octet)*0x1000193)%(2**32)
    return value

def check_tracestate(tid,state):
    assert state.startswith('ot=') and ',' not in state
    parts=dict(pair.split(':') for pair in state[3:].split(';'))
    assert set(parts)=={'rv','th'}
    h=native_hash(tid);bucket=h%16384;unused=h//2**18
    rnd=(16383-bucket)*2**42+((unused^(unused*1024))*2**14)+bucket
    assert int(parts['rv'],16)==rnd
    assert int(parts['th'].ljust(14,'0'),16)==(16384-1638)*2**42

def decision(tid,index,policy):
    if policy in ['full','tail100']:return True
    if policy in ['gate10','collector10']:return native_hash(tid)%16384<1638
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
        if policy=='collector10':
            assert cfg['processors']['probabilistic_sampler']=={'mode':'hash_seed','hash_seed':1729,'sampling_percentage':10,'sampling_precision':4,'fail_closed':True}
            assert cfg['service']['pipelines']['traces']['processors']==['probabilistic_sampler','batch']
        else:assert 'probabilistic_sampler' not in cfg['processors']
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
                            if policy=='collector10':check_tracestate(tid,span['traceState'])
                            else:assert not span.get('traceState')
                            span_total+=1
                assert len(phases)==1
                if phases=={'measured'}:measured_bytes+=len(line.encode())
        assert all(mask==31 for mask in masks.values())
        for phase in limits:assert sum(k[0]==phase for k in masks)==wanted[phase]
        assert r['exported_spans']==wanted['measured']*5==r['batch_spans'] and r['json_bytes']==measured_bytes
        receipts=read(p/'measured-receipts.json');assert [v['begin'] for v in receipts]==list(range(0,limits['measured'],100))
        for v in receipts:assert v['status']==200 and not json.loads(v['body']).get('partialSuccess',{}).get('rejectedSpans',0)
        assert r['accepted_spans']==(wanted['measured'] if policy=='gate10' else limits['measured'])*5
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

BUDGETS=[.05,.10,.20,.35,.50,.65,.80,.95]
WINDOWS=[20,50,200]

def corpus(base,kind):
    import math
    plan=read(base/'plan.json');expected_n={'measured':600,'pilot':12,'calibration':50}[kind]
    assert len(plan)==expected_n and {r['episode'] for r in plan}==set(range(expected_n))
    assert read(base/'complete.json')['episodes']==expected_n
    assert len(list((base/'episodes').glob('*.json.gz')))==expected_n
    episodes=[];seen=set()
    for d in sorted(plan,key=lambda r:r['episode']):
        assert d['kind']==kind and d['window']==(200 if kind=='measured' else 20)
        expected_seed={'measured':730000,'pilot':740000,'calibration':710000}[kind]+d['episode']
        assert d['seed']==expected_seed
        if kind=='calibration':assert (d['target'],d['added_ms'],d['fraction'])==('service-a',0,0)
        else:
            copies=50 if kind=='measured' else 1;index=d['episode']//copies
            assert (d['target'],d['added_ms'],d['fraction'])==(SERVICES[index//4],[5,15][index%4//2],[.5,1][index%2])
        path=base/'episodes'/f"episode-{d['episode']:04}.json.gz";e=json.loads(gzip.decompress(path.read_bytes()));assert e['design']==d
        assert [(r['phase'],r['index']) for r in e['records']]==[(phase,i) for phase in ['reference','incident'] for i in range(d['window'])]
        spans=defaultdict(dict)
        for rs in e['resourceSpans']:
            assert len(rs['resource']['attributes'])==1 and rs['resource']['attributes'][0]['key']=='service.name'
            service=rs['resource']['attributes'][0]['value']['stringValue'];assert service in SERVICES+['gateway']
            for ss in rs['scopeSpans']:
                assert ss['scope']=={'name':'diagnosis-timing'}
                for span in ss['spans']:
                    assert service not in spans[span['traceId']];spans[span['traceId']][service]=span
                    assert span['status']=={'code':1} and not span.get('attributes') and span['kind']==2
        assert len(spans)==2*d['window'];rng=random.Random(d['seed']);injected=[]
        for row in e['records']:
            tid=hashlib.sha256(f"sensitivity-v1:{d['seed']}:{row['phase']}:{row['index']}".encode()).hexdigest()[:32]
            assert row['trace_id']==tid and tid not in seen;seen.add(tid)
            hit=row['phase']=='incident' and rng.random()<d['fraction']
            if hit:injected.append(tid)
            group=spans[tid];assert set(group)==set(SERVICES+['gateway']);root=group['gateway'];begin=int(root['startTimeUnixNano']);end=int(root['endTimeUnixNano']);assert begin<end
            assert root['spanId']==hashlib.sha256((tid+':gateway').encode()).hexdigest()[:16] and not root.get('parentSpanId') and root['name']=='request'
            assert row['root_ms']==(end-begin)/1e6 and set(row['durations_ms'])==set(SERVICES)
            previous=begin
            for service in SERVICES:
                requested=rng.lognormvariate(math.log(.008),.5)+(d['added_ms']/1000 if hit and service==d['target'] else 0)
                span=group[service];a=int(span['startTimeUnixNano']);b=int(span['endTimeUnixNano'])
                assert previous<=a<b<=end and span['parentSpanId']==root['spanId'] and span['name']=='operation';previous=b
                assert span['spanId']==hashlib.sha256((tid+':'+service).encode()).hexdigest()[:16]
                assert row['durations_ms'][service]==(b-a)/1e6
                assert (b-a)/1e9+1e-6>=requested
        assert e['injected_trace_ids']==injected
        for window in [v for v in WINDOWS if v<=d['window']]:
            selected={r['trace_id'] for r in e['records'] if r['index']<window}
            assert e['full_predictions'][str(window)]==diagnose(e['records'],selected)
        episodes.append(e)
    if kind=='calibration':
        values=sorted(r['root_ms'] for e in episodes for r in e['records']);info=read(base/'threshold.json')
        assert len(values)==info['requests']==2000 and info['rank']==1900 and info['quantile']==.95
        assert info['threshold_ms']==values[1899]
        assert info['source_sha256']=={p.name:digest(p) for p in sorted((base/'episodes').glob('*.json.gz'))}
    return episodes

def upper_bound(x,n,alpha):
    from scipy.stats import binom
    if x==n:return 1.
    lo=0.;hi=1.
    for _ in range(64):
        mid=(lo+hi)/2
        if binom.cdf(x,n,mid)>alpha:lo=mid
        else:hi=mid
    return (lo+hi)/2

def replay(base,source,calibration,analysis=None):
    episodes=corpus(source,'measured');corpus(calibration,'calibration');threshold=read(calibration/'threshold.json')['threshold_ms'];design=read(base/'design.json')
    assert design['windows']==WINDOWS and design['budgets']==BUDGETS and design['trials']==5000 and design['family_size']==48 and design['episodes']==600 and design['trial_seed_base']==1990000
    assert design['threshold_ms']==threshold and design['calibration_sha256']==digest(calibration/'threshold.json')
    assert design['source_episode_sha256']=={p.name:digest(p) for p in sorted((source/'episodes').glob('*.json.gz'))}
    alphas={n:sum(r['root_ms']>=threshold for e in episodes for r in e['records'] if r['index']<n)/(600*2*n) for n in WINDOWS}
    assert design['alphas']=={str(k):v for k,v in alphas.items()}
    counts=defaultdict(lambda:defaultdict(int));last=-1;keys=set();rows=0
    expected={(w,p,b) for w in WINDOWS for p in ['head','tail'] for b in BUDGETS}
    with gzip.open(base/'trials.jsonl.gz','rt') as f:
        for line in f:
            v=json.loads(line);trial=v['trial'];key=(v['window'],v['policy'],v['budget'])
            if trial!=last:
                if last>=0:assert keys==expected
                assert trial==last+1 and trial<5000;last=trial;keys=set()
                rng=random.Random(1990000+trial);e=episodes[rng.randrange(600)];u=[rng.random() for _ in e['records']]
            assert key in expected and key not in keys;keys.add(key);window,policy,budget=key
            feasible=policy=='head' or budget>=alphas[window];assert v['feasible']==feasible
            if feasible:
                rate=budget if policy=='head' else (budget-alphas[window])/(1-alphas[window])
                chosen={r['trace_id'] for r,x in zip(e['records'],u) if r['index']<window and (x<rate or policy=='tail' and r['root_ms']>=threshold)}
                answer=diagnose(e['records'],chosen);truth=e['design']['target'];full=e['full_predictions'][str(window)];before=full==truth;after=answer==truth
                ref=sum(r['trace_id'] in chosen for r in e['records'] if r['phase']=='reference')
                fields={'episode':e['design']['episode'],'full_prediction':full,'prediction':answer,'truth':truth,'retained':len(chosen),'retained_reference':ref,'retained_incident':len(chosen)-ref,'full_correct':before,'correct':after,'loss':before and not after,'gain':after and not before}
                assert all(v[k]==value for k,value in fields.items()),(trial,key)
                for k in ['full_correct','correct','retained','retained_reference','retained_incident','loss','gain']:counts[key][k]+=v[k]
                counts[key]['abstentions']+=answer is None
            counts[key]['n']+=1;rows+=1
    assert last==4999 and keys==expected and rows==240000
    assert read(base/'complete.json')['comparisons']==48 and read(base/'complete.json')['trials']==5000
    if analysis:
        summary=read(analysis/'diagnosis-summary.json');assert summary['family_size']==48 and summary['trials_per_comparison']==5000 and summary['episodes']==600 and summary['requests']==240000
        assert summary['threshold_ms']==threshold and summary['protected_fraction']=={str(k):v for k,v in alphas.items()}
        assert len(summary['results'])==48
        assert {(v['window'],v['policy'],v['budget']) for v in summary['results']}==expected
        for n in WINDOWS:assert summary['baselines'][str(n)]=={'episodes':600,'correct':sum(e['full_predictions'][str(n)]==e['design']['target'] for e in episodes)}
        for v in summary['results']:
            key=v['window'],v['policy'],v['budget'];c=counts[key];feasible=v['policy']=='head' or v['budget']>=alphas[v['window']];assert v['feasible']==feasible
            if not feasible:continue
            assert c['n']==5000
            for key1,key2 in [('losses','loss'),('gains','gain'),('correct','correct'),('full_correct','full_correct'),('abstentions','abstentions')]:assert v[key1]==c[key2]
            assert v['net_loss']==(c['loss']-c['gain'])/5000
            upper=upper_bound(c['loss'],5000,.05/48);assert abs(v['upper_loss_bound']-upper)<1e-12 and v['meets_five_point_margin']==(upper<=.05)
            assert v['retained_fraction']==c['retained']/(5000*2*v['window'])
            assert v['mean_reference_retained']==c['retained_reference']/5000 and v['mean_incident_retained']==c['retained_incident']/5000
    return {'status':'PASS','episodes':600,'requests':240000,'spans':960000,'comparison_rows':rows,'family_size':48,'bounds_independently_inverted':bool(analysis)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['load','measured','pilot','calibration','replay']);p.add_argument('path',type=Path);p.add_argument('--corpus',type=Path);p.add_argument('--calibration',type=Path);p.add_argument('--analysis',type=Path);p.add_argument('--receipt',type=Path);a=p.parse_args()
    if a.mode=='load':result=load(a.path)
    elif a.mode=='replay':result=replay(a.path,a.corpus,a.calibration,a.analysis)
    else:result={'status':'PASS','kind':a.mode,'episodes':len(corpus(a.path,a.mode))}
    if a.receipt:a.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
