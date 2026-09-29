#!/usr/bin/env python3
"""Matched export-path and batching experiments; workloads run only on homelab."""
import argparse, copy, gzip, hashlib, http.client, itertools, json, os, random, shutil
import threading, time, traceback
from pathlib import Path
import runtime as c

HERE=Path(__file__).resolve().parent
NS='trace-sampling-boundaries-20260928'
SALT='load-second-audit-v1'
TEMPLATES={}
ORIGIN=0

def allowed():
    assert os.environ.get('STUDY_CONTEXT')=='homelab'
    assert Path('/var/run/secrets/kubernetes.io/serviceaccount/namespace').read_text().strip()==NS

def setup():
    global TEMPLATES,ORIGIN
    records=c.flattened(gzip.decompress(Path('/work/input/traces.jsonl.gz').read_bytes()))
    for phase,file in [('warmup','warmup.json'),('measured','truth.json')]:
        ledger=json.loads(Path('/work/input',file).read_text())
        TEMPLATES[phase]=[list(records[x['trace_id']].values()) for x in ledger]
    assert [len(TEMPLATES[x]) for x in ['warmup','measured']]==[500,3000]
    origin=Path('/work/input/timestamp-origin.json')
    if not origin.exists():c.dump(origin,{'origin_ns':time.time_ns()-3_600_000_000_000})
    ORIGIN=json.loads(origin.read_text())['origin_ns']

def tid(block,phase,i):
    return hashlib.sha256(f'fifth:{block}:{phase}:{i}'.encode()).hexdigest()[:32]

def keep(block,phase,i,policy):
    if policy in ['full','tail100']:return True
    data=bytes.fromhex(tid(block,phase,i))
    if policy in ['gate10','collector10']:
        h=2166136261
        for byte in (1729).to_bytes(4,'little')+data:h=((h^byte)*16777619)&0xffffffff
        return h%16384<1638
    if i%100 in (0,1):return True
    h=14695981039346656037
    for byte in SALT.encode()+data:h=((h^byte)*1099511628211)&((1<<64)-1)
    return h<=int((.08/.98)*((1<<64)-1))

def entries(kind,block,phase,i):
    identity=tid(block,phase,i);first=ORIGIN+i*1000000+(0 if phase=='warmup' else 10**12)
    if kind=='placement':
        resource={'resource':{'attributes':[{'key':'service.name','value':{'stringValue':'load-service'}}]}}
        scope={'scope':{'name':'load-study'}}
        return [{'resource':resource,'scope':scope,'span':{'traceId':identity,'spanId':f'{j+1:016x}',
            **({'parentSpanId':'0000000000000001'} if j else {}),'name':'request' if not j else f'operation-{j}',
            'kind':2,'startTimeUnixNano':str(first),'endTimeUnixNano':str(first+(400000000 if i%100==1 and not j else 10000000)),
            'attributes':[{'key':'sequence','value':{'intValue':str(i)}},{'key':'phase','value':{'stringValue':phase}}],
            'status':{'code':2 if i%100==0 and j==4 else 1}}} for j in range(5)]
    template=TEMPLATES[phase][i%len(TEMPLATES[phase])]
    minimum=min(int(e['span']['startTimeUnixNano']) for e in template)
    result=copy.deepcopy(template)
    for e in result:
        s=e['span'];s['traceId']=identity
        for field in ['startTimeUnixNano','endTimeUnixNano']:s[field]=str(int(s[field])-minimum+first)
        s.setdefault('attributes',[]).extend([
            {'key':'study.phase','value':{'stringValue':phase}},
            {'key':'study.sequence','value':{'intValue':str(i)}},
            {'key':'study.template','value':{'intValue':str(i%len(TEMPLATES[phase]))}}])
    return result

def payloads(kind,block,phase,n,policy):
    size=100 if kind=='placement' else 10
    result=[];selected=[]
    for begin in range(0,n,size):
        groups={};count=0
        for i in range(begin,min(begin+size,n)):
            if keep(block,phase,i,policy):selected.append(i)
            if policy=='gate10' and not keep(block,phase,i,policy):continue
            for entry in entries(kind,block,phase,i):
                key=json.dumps([entry['resource'],entry['scope']],sort_keys=True)
                if key not in groups:groups[key]={**entry['resource'],'scopeSpans':[{**entry['scope'],'spans':[]}]}
                groups[key]['scopeSpans'][0]['spans'].append(entry['span']);count+=1
        data=json.dumps({'resourceSpans':list(groups.values())},separators=(',',':')).encode()
        result.append((begin,data,count))
    return result,selected

def schedule(batches,rate,duration):
    start=time.monotonic();receipts=[];conn=http.client.HTTPConnection('127.0.0.1',4318,timeout=20)
    try:
        for begin,data,n in batches:
            offset=begin/rate;delay=start+offset-time.monotonic()
            if delay>0:time.sleep(delay)
            sent=time.monotonic();conn.request('POST','/v1/traces',data,{'Content-Type':'application/json'})
            response=conn.getresponse();body=response.read().decode()
            receipts.append({'begin':begin,'offset_s':offset,'start_s':sent-start,'lag_s':sent-start-offset,
                'elapsed_s':time.monotonic()-sent,'spans':n,'status':response.status,'body':body,'payload_sha256':c.sha(data)})
            assert response.status==200 and not int(json.loads(body).get('partialSuccess',{}).get('rejectedSpans',0)),receipts[-1]
        remaining=start+duration-time.monotonic()
        if remaining>0:time.sleep(remaining)
    finally:conn.close()
    return receipts

def configuration(out,kind,export,timeout,policy):
    cfg=c.config(out,export,timeout,'bypass' if policy in ['full','gate10','collector10'] else policy)
    if kind=='placement':cfg['processors']['batch'].update(send_batch_size=1024,send_batch_max_size=2048)
    if policy=='collector10':
        cfg['processors']['probabilistic_sampler']={'mode':'hash_seed','hash_seed':1729,'sampling_percentage':10,'sampling_precision':4,'fail_closed':True}
        cfg['service']['pipelines']['traces']['processors'].insert(0,'probabilistic_sampler')
    if policy.startswith('tail'):
        cfg['processors']['tail_sampling'].update(num_traces=161000,expected_new_traces_per_sec=20000,
            decision_cache={'sampled_cache_size':1288000,'non_sampled_cache_size':1288000})
        cfg['processors']['tail_sampling']['policies'][2]['probabilistic']['hash_salt']=SALT
    return cfg

def backend_saved(text,expected):
    values=c.metrics(text)
    ok=sum(v for k,v in values.items() if k.split('{')[0]=='jaeger_collector_spans_saved_by_svc_total' and 'result="ok"' in k)
    errors=sum(v for k,v in values.items() if k.split('{')[0]=='jaeger_collector_spans_saved_by_svc_total' and 'result="err"' in k)
    assert ok==expected and errors==0, ('backend endpoint',ok,expected,errors)

def compress(path):
    if not path.exists():return
    with path.open('rb') as src,path.with_suffix(path.suffix+'.gz').open('wb') as dest:
        with gzip.GzipFile(fileobj=dest,mode='wb',mtime=0,compresslevel=1) as gz:shutil.copyfileobj(src,gz)
    path.unlink()

def cell(base,block,kind,export,timeout,policy,rate,pilot):
    out=base/f'block-{block}'/f'{kind}-{export}-{timeout}-{policy}';out.mkdir(parents=True,exist_ok=False)
    warm=5 if kind=='placement' else 10;duration=60 if pilot else (30 if kind=='placement' else 60);drain=5
    prepared={phase:payloads(kind,block,phase,rate*seconds,policy) for phase,seconds in [('warmup',warm),('measured',duration)]}
    d={'block':block,'kind':kind,'export':export,'timeout_ms':timeout,'policy':policy,'rate_traces_s':rate,'warmup_s':warm,
       'duration_s':duration,'drain_s':drain,'origin_ns':ORIGIN,'pilot':pilot,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
       'source_sha256':{p.name:c.sha(p.read_bytes()) for p in (base/'executed-source').iterdir() if p.is_file()}}
    c.dump(out/'design.json',d);c.dump(out/'config.json',configuration(out,kind,export,timeout,policy))
    processes={};event=threading.Event();thread=None;samples=[]
    try:
        processes['jaeger']=c.start(out,'jaeger',['/work/jaeger-1.76.0-linux-amd64/jaeger-all-in-one',
          '--collector.otlp.enabled=true','--collector.otlp.http.host-port=127.0.0.1:14318','--collector.otlp.grpc.host-port=127.0.0.1:14317',
          '--badger.ephemeral=false','--badger.directory-key='+str(out/'badger/keys'),'--badger.directory-value='+str(out/'badger/values'),
          '--badger.span-store-ttl=24h','--log-level=warn'],{**c.ENV,'SPAN_STORAGE_TYPE':'badger','OTEL_TRACES_SAMPLER':'always_off'})
        c.ready(processes['jaeger'],'http://127.0.0.1:16686/api/services')
        processes['collector']=c.start(out,'collector',['/work/otelcol-contrib','--config',str(out/'config.json')])
        c.ready(processes['collector'],'http://127.0.0.1:8888/metrics')
        c.dump(out/'warmup-receipts.json',schedule(prepared['warmup'][0],rate,warm));time.sleep(drain)
        warmbytes=(out/'traces.jsonl').stat().st_size
        for name,url in [('collector','http://127.0.0.1:8888/metrics'),('jaeger','http://127.0.0.1:14269/metrics')]:
            (out/f'{name}-metrics-before.txt').write_bytes(c.get(url))
        backend_saved((out/'jaeger-metrics-before.txt').read_text(),len(prepared['warmup'][1])*5 if export=='dual' else 0)
        before=c.snapshot(processes);generator_before=c.proc(os.getpid())
        def monitor():
            while not event.is_set():
                samples.append(c.snapshot(processes));event.wait(.5)
        thread=threading.Thread(target=monitor);thread.start()
        receipts=schedule(prepared['measured'][0],rate,duration);time.sleep(drain)
        endbytes=(out/'traces.jsonl').stat().st_size
        for name,url in [('collector','http://127.0.0.1:8888/metrics'),('jaeger','http://127.0.0.1:14269/metrics')]:
            (out/f'{name}-metrics-after.txt').write_bytes(c.get(url))
        after=c.snapshot(processes);generator_after=c.proc(os.getpid());event.set();thread.join()
        c.dump(out/'endpoints.json',{'before':before,'after':after,'generator_before':generator_before,'generator_after':generator_after})
        c.dump(out/'samples.json',samples);c.dump(out/'measured-receipts.json',receipts)
        backend_saved((out/'jaeger-metrics-after.txt').read_text(),sum(len(v[1]) for v in prepared.values())*5 if export=='dual' else 0)
        a,b=[c.metrics((out/f'collector-metrics-{x}.txt').read_text()) for x in ['before','after']]
        delta={k:b.get(k,0)-a.get(k,0) for k in set(a)|set(b)}
        expected=len(prepared['measured'][1])*5;accepted=sum(v[2] for v in prepared['measured'][0])
        assert c.summed(delta,'otelcol_receiver_accepted_spans_total')==accepted
        for target in (['file','otlphttp'] if export=='dual' else ['file']):assert c.summed(delta,'otelcol_exporter_sent_spans_total',target)==expected
        lost={k:v for k,v in b.items() if any(t in k.split('{')[0] for t in ['refused_spans','send_failed_spans','dropped_too_early']) and v}
        assert not lost,lost
        c.stop(processes.pop('collector'));assert (out/'traces.jsonl').stat().st_size==endbytes,'JSON after endpoint'
        backend=[]
        if export=='dual':
            for phase in ['warmup','measured']:
                chosen=prepared[phase][1]
                indices=sorted({chosen[int(j*(len(chosen)-1)/15)] for j in range(16)}) if chosen else []
                for i in indices:
                    identity=tid(block,phase,i);query=c.get('http://127.0.0.1:16686/api/traces/'+identity,timeout=60)
                    data=json.loads(query);record={e['span']['spanId']:e for e in entries(kind,block,phase,i)}
                    c.verify_backend(data,{identity:record});backend.append({'phase':phase,'sequence':i,'response':data})
        else:
            services=json.loads(c.get('http://127.0.0.1:16686/api/services'));assert not services.get('data'),services
        c.dump(out/'backend-sample.json',backend)
        c.stop(processes.pop('jaeger'))
        size=sum(p.stat().st_size for p in (out/'badger').rglob('*') if p.is_file())
        cpu={name:after['processes'][name]['cpu_s']-before['processes'][name]['cpu_s'] for name in before['processes']}
        cg=[dict(row.split() for row in snap['runner_cgroup_cpu'].splitlines()) for snap in [before,after]]
        result={**d,'valid':True,'cpu_s':cpu,'collector_jaeger_cpu_s':sum(cpu.values()),'generator_cpu_s':generator_after['cpu_s']-generator_before['cpu_s'],
            'wall_s':after['end_monotonic']-before['begin_monotonic'],'accepted_spans':accepted,'exported_spans':expected,
            'json_bytes':endbytes-warmbytes,'max_lag_s':max(v['lag_s'] for v in receipts),
            'max_rss_bytes':{name:max(s['processes'][name]['rss_bytes'] for s in samples) for name in before['processes']},
            'throttled_usec':int(cg[1]['throttled_usec'])-int(cg[0]['throttled_usec']),
            'batch_count':c.summed(delta,'otelcol_processor_batch_batch_send_size_count'),
            'batch_spans':c.summed(delta,'otelcol_processor_batch_batch_send_size_sum'),
            'batch_timeout_triggers':c.summed(delta,'otelcol_processor_batch_timeout_trigger_send_total'),
            'batch_size_triggers':c.summed(delta,'otelcol_processor_batch_batch_size_trigger_send_total'),
            'backend_sample_traces':len(backend),'backend_files_bytes':size}
        assert result['batch_spans']==expected
        compress(out/'traces.jsonl');compress(out/'backend-sample.json')
        result['export_gzip_sha256']=c.sha((out/'traces.jsonl.gz').read_bytes())
        c.dump(out/'result.json',result);shutil.rmtree(out/'badger')
        print(json.dumps({k:result[k] for k in ['block','kind','export','timeout_ms','policy','rate_traces_s','cpu_s','max_lag_s','throttled_usec','batch_count']}),flush=True)
        return result
    except BaseException:
        (out/'failure.txt').write_text(traceback.format_exc());raise
    finally:
        event.set()
        if thread:thread.join()
        for pair in processes.values():
            try:c.stop(pair)
            except Exception:pass
        compress(out/'traces.jsonl')

def run(args):
    assert args.kind=='batching', 'This amendment applies only to the batching extension'
    allowed();setup();base=args.output;base.mkdir(parents=True,exist_ok=False)
    shutil.copytree(HERE,base/'executed-source',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree('/work/input',base/'input')
    blocks=([81000 if args.kind=='placement' else 81100] if args.pilot else list(range(82001,82006) if args.kind=='placement' else range(83001,83006)))
    factors=(list(itertools.product(['file','dual'],[1000],['full','gate10','collector10','tail10'])) if args.kind=='placement' else list(itertools.product(['dual'],[100,1000],['full','tail100'])))
    plan=[]
    for block in blocks:
        order=list(factors);random.Random(f'fifth:{args.kind}:{block}').shuffle(order);plan.extend([[block,args.kind,*x,args.rate] for x in order])
    c.dump(base/'plan.json',plan);c.dump(base/'environment.json',{'ticks':os.sysconf('SC_CLK_TCK'),'page_size':os.sysconf('SC_PAGE_SIZE'),
        'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text(),'memory_max':Path('/sys/fs/cgroup/memory.max').read_text(),
        'binary_sha256':{p.name:c.sha(p.read_bytes()) for p in [Path('/work/otelcol-contrib'),Path('/work/jaeger-1.76.0-linux-amd64/jaeger-all-in-one')]}})
    results=[]
    for row in plan:
        r=cell(base,*row,args.pilot);results.append(r)
        if r['max_lag_s']>=.5 or r['throttled_usec']:
            c.dump(base/'capacity-failure.json',{'cell':row,'max_lag_s':r['max_lag_s'],'throttled_usec':r['throttled_usec']})
            raise RuntimeError('Declared lag/throttling criterion failed')
    c.dump(base/'complete.json',{'cells':len(plan),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['placement','batching']);p.add_argument('--rate',type=int,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--pilot',action='store_true');run(p.parse_args())
