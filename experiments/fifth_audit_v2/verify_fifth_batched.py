#!/usr/bin/env python3
"""Separate archive reconstruction; never imports the experiment implementation."""
import argparse,gzip,hashlib,json,math
from collections import defaultdict
from pathlib import Path

def read(p):return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ident(block,phase,i):return hashlib.sha256(('fifth:%d:%s:%d'%(block,phase,i)).encode()).hexdigest()[:32]
def native(tid):
    h=0x811c9dc5
    for x in bytes([193,6,0,0])+bytes.fromhex(tid):h=((h^x)*0x1000193)%(2**32)
    return h

def selected(tid,i,policy):
    if policy in ['full','tail100']:return True
    if policy in ['gate10','collector10']:return native(tid)%16384<1638
    if i%100<2:return True
    h=0xcbf29ce484222325
    for x in b'load-second-audit-v1'+bytes.fromhex(tid):h=((h^x)*0x100000001b3)%(2**64)
    return h<=int((.08/.98)*(2**64-1))
def state(tid,text):
    assert text.startswith('ot=') and ',' not in text
    p=dict(x.split(':') for x in text[3:].split(';'));assert set(p)=={'rv','th'}
    h=native(tid);low=h%16384;high=h//2**18
    assert int(p['rv'],16)==(16383-low)*2**42+((high^(high*1024))*2**14)+low
    assert int(p['th'].ljust(14,'0'),16)==(16384-1638)*2**42

def metric(text,name,exporter=None):
    total=0
    for line in text.splitlines():
        if not line or line.startswith('#'):continue
        key,v=line.rsplit(' ',1)
        if key.split('{')[0]==name and (exporter is None or f'exporter="{exporter}"' in key):total+=float(v)
    return total

def templates(base):
    traces=defaultdict(dict)
    with gzip.open(base/'input/traces.jsonl.gz','rt') as f:
        for line in f:
            for r in json.loads(line)['resourceSpans']:
                for scope in r['scopeSpans']:
                    for s in scope['spans']:
                        traces[s['traceId']][s['spanId']]=(s,{k:v for k,v in r.items() if k!='scopeSpans'},{k:v for k,v in scope.items() if k!='spans'})
    return {phase:[traces[x['trace_id']] for x in read(base/'input'/file)] for phase,file in [('warmup','warmup.json'),('measured','truth.json')]}

def expected(d,ts,phase,i,sid):
    identity=ident(d['block'],phase,i);start=d['origin_ns']+i*1000000+(10**12 if phase=='measured' else 0)
    if d['kind']=='placement':
        j=int(sid,16)-1;assert 0<=j<5
        s={'traceId':identity,'spanId':sid,'name':'request' if j==0 else f'operation-{j}','kind':2,
           'startTimeUnixNano':str(start),'endTimeUnixNano':str(start+(400000000 if i%100==1 and j==0 else 10000000)),
           'attributes':[{'key':'sequence','value':{'intValue':str(i)}},{'key':'phase','value':{'stringValue':phase}}],
           'status':{'code':2 if i%100==0 and j==4 else 1}}
        if j:s['parentSpanId']='0000000000000001'
        return s,{'resource':{'attributes':[{'key':'service.name','value':{'stringValue':'load-service'}}]}},{'scope':{'name':'load-study'}}
    group=ts[phase][i%len(ts[phase])];source,resource,scope=group[sid]
    minimum=min(int(x[0]['startTimeUnixNano']) for x in group.values());s=dict(source);s['traceId']=identity
    for key in ['startTimeUnixNano','endTimeUnixNano']:s[key]=str(int(source[key])-minimum+start)
    s['attributes']=source.get('attributes',[])+[{'key':'study.phase','value':{'stringValue':phase}},
       {'key':'study.sequence','value':{'intValue':str(i)}},{'key':'study.template','value':{'intValue':str(i%len(ts[phase]))}}]
    return s,resource,scope

def check_backend(base,d,ts,indices):
    with gzip.open(base/'backend-sample.json.gz','rt') as f:rows=json.load(f)
    if d['export']=='file':assert rows==[];return 0
    wanted={(phase,values[int(j*(len(values)-1)/15)]) for phase,values in indices.items() for j in range(16)}
    assert {(r['phase'],r['sequence']) for r in rows}==wanted and len(rows)==len(wanted)
    for row in rows:
        phase,i=row['phase'],row['sequence'];identity=ident(d['block'],phase,i);data=row['response'];assert not data.get('errors')
        assert len(data['data'])==1;trace=data['data'][0];assert trace['traceID']==identity and len(trace['spans'])==5
        seen=set()
        for span in trace['spans']:
            sid=span['spanID'];assert sid not in seen;seen.add(sid);s,resource,_=expected(d,ts,phase,i,sid)
            assert span['operationName']==s['name'];parent=s.get('parentSpanId')
            assert span.get('references',[])==([{'refType':'CHILD_OF','traceID':identity,'spanID':parent}] if parent else [])
            assert abs(span['startTime']-int(s['startTimeUnixNano'])//1000)<=1
            assert abs(span['duration']-(int(s['endTimeUnixNano'])-int(s['startTimeUnixNano']))/1000)<=2
            tags={x['key']:x['value'] for x in span['tags']}
            for attr in s.get('attributes',[]):assert str(tags[attr['key']])==str(next(iter(attr['value'].values())))
            if s.get('status',{}).get('code')==2:assert tags.get('error') is True
            service=next(x['value']['stringValue'] for x in resource['resource']['attributes'] if x['key']=='service.name')
            assert trace['processes'][span['processID']]['serviceName']==service
    return len(rows)

def verify(base):
    plan=read(base/'plan.json');environment=read(base/'environment.json');assert read(base/'complete.json')['cells']==len(plan)
    assert len(list(base.glob('block-*/*/result.json')))==len(plan)
    assert environment['cpu_max']=='600000 100000\n' and environment['memory_max']=='10737418240\n'
    ts=templates(base);total=0;queries=0;maxlag=0;throttle=0;payload_groups={}
    for block,kind,export,timeout,policy,rate in plan:
        p=base/f'block-{block}'/f'{kind}-{export}-{timeout}-{policy}';d=read(p/'design.json');result=read(p/'result.json')
        assert result['valid'] and all(result[k]==v for k,v in d.items())
        assert (d['block'],d['kind'],d['export'],d['timeout_ms'],d['policy'],d['rate_traces_s'])==(block,kind,export,timeout,policy,rate)
        assert d['origin_ns']==read(base/'input/timestamp-origin.json')['origin_ns']
        for name,digest in d['source_sha256'].items():assert sha(base/'executed-source'/name)==digest
        cfg=read(p/'config.json');size,maximum=(1024,2048) if kind=='placement' else (256,512)
        assert d['drain_s']==5 and d['warmup_s']==(5 if kind=='placement' else 10)
        assert d['duration_s']==(60 if kind=='batching' else (5 if d['pilot'] else 30))
        assert cfg['service']['pipelines']['traces']['processors']==(['probabilistic_sampler'] if policy=='collector10' else ['tail_sampling'] if policy.startswith('tail') else [])+['batch']
        assert cfg['processors']['batch']=={'timeout':f'{timeout}ms','send_batch_size':size,'send_batch_max_size':maximum}
        assert set(cfg['exporters'])==({'file','otlphttp'} if export=='dual' else {'file'})
        if export=='dual':assert cfg['exporters']['otlphttp']=={'endpoint':'http://127.0.0.1:14318','encoding':'proto','compression':'gzip','timeout':'5s','retry_on_failure':{'enabled':False},'sending_queue':{'enabled':False}}
        if policy.startswith('tail'):
            t=cfg['processors']['tail_sampling'];assert t['num_traces']==161000 and t['decision_wait']=='2s' and t['sample_on_first_match'] is False
            assert t['decision_cache']=={'sampled_cache_size':1288000,'non_sampled_cache_size':1288000}
            assert t['policies'][2]['probabilistic']=={'sampling_percentage':100 if policy=='tail100' else 100*.08/.98,'hash_salt':'load-second-audit-v1'}
        else:assert 'tail_sampling' not in cfg['processors']
        if policy=='collector10':assert cfg['processors']['probabilistic_sampler']=={'mode':'hash_seed','hash_seed':1729,'sampling_percentage':10,'sampling_precision':4,'fail_closed':True}
        else:assert 'probabilistic_sampler' not in cfg['processors']
        limits={'warmup':rate*d['warmup_s'],'measured':rate*d['duration_s']}
        indices={phase:[i for i in range(n) if selected(ident(block,phase,i),i,policy)] for phase,n in limits.items()}
        expected_count={k:len(v) for k,v in indices.items()};masks=defaultdict(set);measured_bytes=0
        assert sha(p/'traces.jsonl.gz')==result['export_gzip_sha256']
        with gzip.open(p/'traces.jsonl.gz','rt') as stream:
            for line in stream:
                phases=set()
                for resource in json.loads(line)['resourceSpans']:
                    for scope in resource['scopeSpans']:
                        for span in scope['spans']:
                            attrs={a['key']:next(iter(a['value'].values())) for a in span.get('attributes',[])}
                            phase=attrs['phase' if kind=='placement' else 'study.phase'];i=int(attrs['sequence' if kind=='placement' else 'study.sequence']);phases.add(phase)
                            assert phase in limits and 0<=i<limits[phase];identity=ident(block,phase,i);assert span['traceId']==identity and selected(identity,i,policy)
                            sid=span['spanId'];assert sid not in masks[phase,i];masks[phase,i].add(sid)
                            wanted,r,s=expected(d,ts,phase,i,sid);actual=dict(span)
                            if policy=='collector10':state(identity,actual.pop('traceState'))
                            assert actual==wanted,(p,phase,i,sid,actual,wanted)
                            assert {k:v for k,v in resource.items() if k!='scopeSpans'}==r
                            assert {k:v for k,v in scope.items() if k!='spans'}==s
                            total+=1
                assert len(phases)==1
                if phases=={'measured'}:measured_bytes+=len(line.encode())
        assert all(len(v)==5 for v in masks.values())
        for phase,n in expected_count.items():assert sum(k[0]==phase for k in masks)==n
        assert result['json_bytes']==measured_bytes
        assert result['exported_spans']==result['batch_spans']==expected_count['measured']*5
        assert result['accepted_spans']==(expected_count['measured'] if policy=='gate10' else limits['measured'])*5
        for phase in ['warmup','measured']:
            receipts=read(p/f'{phase}-receipts.json');step=100 if kind=='placement' else 10
            assert [x['begin'] for x in receipts]==list(range(0,limits[phase],step))
            assert sum(x['spans'] for x in receipts)==5*(expected_count[phase] if policy=='gate10' else limits[phase])
            assert all(x['status']==200 and not int(json.loads(x['body']).get('partialSuccess',{}).get('rejectedSpans',0)) for x in receipts)
            for x in receipts:assert abs(x['offset_s']-x['begin']/rate)<1e-10 and abs(x['start_s']-x['offset_s']-x['lag_s'])<1e-10
            assert all(x['elapsed_s']>=0 and len(x['payload_sha256'])==64 for x in receipts)
            key=(block,phase,policy=='gate10')
            hashes=[x['payload_sha256'] for x in receipts]
            if key in payload_groups:assert hashes==payload_groups[key],('input bytes differ',p,phase)
            else:payload_groups[key]=hashes
        assert result['max_lag_s']==max(x['lag_s'] for x in read(p/'measured-receipts.json'))
        e=read(p/'endpoints.json');samples=read(p/'samples.json')
        assert abs(result['wall_s']-(e['after']['end_monotonic']-e['before']['begin_monotonic']))<1e-9
        assert result['wall_s']>=d['duration_s']+d['drain_s']
        assert samples and all(e['before']['begin_monotonic']<=x['begin_monotonic']<=e['after']['end_monotonic'] for x in samples)
        generator=[]
        for moment in ['before','after']:
            proc=e['generator_'+moment];fields=proc['raw_stat'].rsplit(') ',1)[1].split()
            value=(int(fields[11])+int(fields[12]))/environment['ticks'];assert value==proc['cpu_s'];generator.append(value)
        assert abs(generator[1]-generator[0]-result['generator_cpu_s'])<1e-10
        for name in ['collector','jaeger']:
            values=[]
            for moment in ['before','after']:
                proc=e[moment]['processes'][name];f=proc['raw_stat'].rsplit(') ',1)[1].split();cpu=(int(f[11])+int(f[12]))/environment['ticks'];assert cpu==proc['cpu_s'];values.append(cpu)
            assert abs(values[1]-values[0]-result['cpu_s'][name])<1e-10
            rss=[]
            for sample in samples:
                proc=sample['processes'][name];f=proc['raw_stat'].rsplit(') ',1)[1].split();value=int(f[21])*environment['page_size'];assert value==proc['rss_bytes'];rss.append(value)
            assert max(rss)==result['max_rss_bytes'][name]
        assert abs(sum(result['cpu_s'].values())-result['collector_jaeger_cpu_s'])<1e-10
        cg=[dict(x.split() for x in e[m]['runner_cgroup_cpu'].splitlines()) for m in ['before','after']]
        assert int(cg[1]['throttled_usec'])-int(cg[0]['throttled_usec'])==result['throttled_usec']==0
        before=(p/'collector-metrics-before.txt').read_text();after=(p/'collector-metrics-after.txt').read_text()
        assert metric(after,'otelcol_receiver_accepted_spans_total')-metric(before,'otelcol_receiver_accepted_spans_total')==result['accepted_spans']
        for target in (['file','otlphttp'] if export=='dual' else ['file']):assert metric(after,'otelcol_exporter_sent_spans_total',target)-metric(before,'otelcol_exporter_sent_spans_total',target)==result['exported_spans']
        for suffix,key in [('batch_send_size_count','batch_count'),('batch_send_size_sum','batch_spans'),('timeout_trigger_send_total','batch_timeout_triggers'),('batch_size_trigger_send_total','batch_size_triggers')]:assert metric(after,'otelcol_processor_batch_'+suffix)-metric(before,'otelcol_processor_batch_'+suffix)==result[key]
        for line in after.splitlines():
            if line and not line.startswith('#') and any(x in line.split(' ')[0] for x in ['refused_spans','send_failed_spans','dropped_too_early']):assert float(line.rsplit(' ',1)[1])==0
        for moment,count in [('before',expected_count['warmup']),('after',sum(expected_count.values()))]:
            text=(p/f'jaeger-metrics-{moment}.txt').read_text();ok=error=0
            for line in text.splitlines():
                if line.startswith('jaeger_collector_spans_saved_by_svc_total{'):
                    key,v=line.rsplit(' ',1)
                    if 'result="ok"' in key:ok+=float(v)
                    if 'result="err"' in key:error+=float(v)
            assert ok==(count*5 if export=='dual' else 0) and error==0
        queries+=check_backend(p,d,ts,indices);maxlag=max(maxlag,result['max_lag_s']);throttle+=result['throttled_usec']
        print('verified',p.name,'block',block,flush=True)
    assert maxlag<.5
    return {'status':'PASS','cells':len(plan),'exported_spans_including_warmup':total,'backend_sample_traces':queries,'max_schedule_lag_s':maxlag,'throttled_usec':throttle,'matched_input_payload_groups':len(payload_groups)}

def main():
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    result=verify(a.archive);a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
