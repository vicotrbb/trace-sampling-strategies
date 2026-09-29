#!/usr/bin/env python3
"""Finite open-loop OTLP load sweep, executable only inside the study pod."""
import argparse, gzip, hashlib, http.client, itertools, json, os, random, shutil, threading, time, traceback
from pathlib import Path
import common as c

HERE=Path(__file__).resolve().parent
POLICIES=['full','head10','tail10','tail100']
SALT='load-second-audit-v1'

def allowed():
    assert os.environ.get('STUDY_CONTEXT')=='homelab'
    assert Path('/var/run/secrets/kubernetes.io/serviceaccount/namespace').read_text().strip()=='trace-sampling-load-20260925'

def trace(block, phase, i):
    tid=hashlib.sha256(f'{block}:{phase}:{i}'.encode()).hexdigest()[:32]
    special=i%100
    start=1700000000000000000+i*1000000
    spans=[]
    for j in range(5):
        spans.append({'traceId':tid,'spanId':f'{j+1:016x}',**({'parentSpanId':f'{1:016x}'} if j else {}),
          'name':'request' if not j else f'operation-{j}','kind':2,
          'startTimeUnixNano':str(start), 'endTimeUnixNano':str(start+(400000000 if special==1 and j==0 else 10000000)),
          'attributes':[{'key':'sequence','value':{'intValue':str(i)}},{'key':'phase','value':{'stringValue':phase}}],
          'status':{'code':2 if special==0 and j==4 else 1}})
    return tid,spans

def keep(tid,i,policy):
    if policy in ('full','tail100'): return True
    if policy=='head10': return int.from_bytes(hashlib.blake2b(bytes.fromhex(tid),digest_size=8).digest(),'big') < int(.1*(1<<64))
    if i%100 in (0,1): return True
    h=0xcbf29ce484222325
    for b in SALT.encode()+bytes.fromhex(tid):h=((h^b)*0x100000001b3)&((1<<64)-1)
    return h <= int((.08/.98)*((1<<64)-1))

def payloads(block,phase,n,policy):
    result=[]; selected=0
    for begin in range(0,n,100):
        spans=[]
        for i in range(begin,min(n,begin+100)):
            tid,ss=trace(block,phase,i)
            if policy!='head10' or keep(tid,i,policy): spans.extend(ss);selected+=1
        data=json.dumps({'resourceSpans':[{'resource':{'attributes':[{'key':'service.name','value':{'stringValue':'load-service'}}]},'scopeSpans':[{'scope':{'name':'load-study'},'spans':spans}]}]},separators=(',',':')).encode()
        result.append((begin,data,len(spans)))
    return result,selected

def schedule(batches,rate,duration):
    start=time.monotonic();receipts=[];conn=http.client.HTTPConnection('127.0.0.1',4318,timeout=10)
    for begin,data,nspans in batches:
        offset=begin/rate;pause=start+offset-time.monotonic()
        if pause>0:time.sleep(pause)
        sent=time.monotonic()
        conn.request('POST','/v1/traces',data,{'Content-Type':'application/json'})
        response=conn.getresponse();body=response.read().decode()
        receipts.append({'begin':begin,'offset_s':offset,'start_s':sent-start,'lag_s':sent-start-offset,'elapsed_s':time.monotonic()-sent,'spans':nspans,'status':response.status,'body':body,'payload_sha256':c.sha(data)})
        assert response.status==200 and not json.loads(body).get('partialSuccess',{}).get('rejectedSpans',0),receipts[-1]
    conn.close();pause=start+duration-time.monotonic()
    if pause>0:time.sleep(pause)
    return receipts

def configuration(out,policy,capacity):
    cfg=c.config(out,'file',1000,'bypass' if policy in ('full','head10') else policy)
    cfg['processors']['batch'].update(send_batch_size=1024,send_batch_max_size=2048)
    if policy.startswith('tail'):
        t=cfg['processors']['tail_sampling'];t['num_traces']=capacity;t['expected_new_traces_per_sec']=capacity//8
        t['decision_cache']={'sampled_cache_size':capacity*8,'non_sampled_cache_size':capacity*8}
        t['policies'][2]['probabilistic']['hash_salt']=SALT
    return cfg

def cell(base,block,rate,policy,duration,capacity):
    out=base/f'block-{block}'/f'rate-{rate}-{policy}';out.mkdir(parents=True,exist_ok=False)
    warm=5;drain=5
    data={p:payloads(block,p,rate*s,policy) for p,s in [('warmup',warm),('measured',duration)]}
    design={'block':block,'rate':rate,'policy':policy,'duration_s':duration,'warmup_s':warm,'drain_s':drain,'capacity':capacity,'spans_per_trace':5,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'sources':{f.name:c.sha(f.read_bytes()) for f in HERE.iterdir() if f.is_file()}}
    c.dump(out/'design.json',design);c.dump(out/'config.json',configuration(out,policy,capacity))
    pair=c.start(out,'collector',['/work/otelcol-contrib','--config',str(out/'config.json')]);event=threading.Event();samples=[];thread=None
    try:
        c.ready(pair,'http://127.0.0.1:8888/metrics')
        c.dump(out/'warmup-receipts.json',schedule(data['warmup'][0],rate,warm));time.sleep(drain)
        warmbytes=(out/'traces.jsonl').stat().st_size
        metrics0=c.get('http://127.0.0.1:8888/metrics').decode();(out/'metrics-before.txt').write_text(metrics0)
        processes={'collector':pair};before=c.snapshot(processes)
        def monitor():
            while not event.is_set():
                samples.append(c.snapshot(processes));event.wait(.5)
        thread=threading.Thread(target=monitor);thread.start()
        receipts=schedule(data['measured'][0],rate,duration);time.sleep(drain)
        after=c.snapshot(processes);event.set();thread.join()
        endpointbytes=(out/'traces.jsonl').stat().st_size
        metrics1=c.get('http://127.0.0.1:8888/metrics').decode();(out/'metrics-after.txt').write_text(metrics1)
        c.dump(out/'endpoints.json',{'before':before,'after':after});c.dump(out/'samples.json',samples);c.dump(out/'measured-receipts.json',receipts)
        c.stop(pair)
        assert (out/'traces.jsonl').stat().st_size==endpointbytes,'output after CPU endpoint'
        a,b=c.metrics(metrics0),c.metrics(metrics1);delta={k:b.get(k,0)-a.get(k,0) for k in set(a)|set(b)}
        accepted=c.summed(delta,'otelcol_receiver_accepted_spans_total');exported=c.summed(delta,'otelcol_exporter_sent_spans_total','file')
        wanted=sum(keep(trace(block,'measured',i)[0],i,policy) for i in range(rate*duration))*5
        lost={k:v for k,v in b.items() if any(t in k.split('{')[0] for t in ['refused_spans','send_failed_spans','dropped_too_early']) and v}
        assert not lost and accepted==data['measured'][1]*5 and exported==wanted,(lost,accepted,exported,wanted)
        result={**design,'valid':True,'cpu_s':after['processes']['collector']['cpu_s']-before['processes']['collector']['cpu_s'],'wall_s':after['end_monotonic']-before['begin_monotonic'],'accepted_spans':accepted,'exported_spans':exported,'max_lag_s':max(r['lag_s'] for r in receipts),'json_bytes':endpointbytes-warmbytes,'max_rss_bytes':max(s['processes']['collector']['rss_bytes'] for s in samples),'batches':c.summed(delta,'otelcol_processor_batch_batch_send_size_count'),'batch_spans':c.summed(delta,'otelcol_processor_batch_batch_send_size_sum')}
        with (out/'traces.jsonl').open('rb') as src,(out/'traces.jsonl.gz').open('wb') as target:
            with gzip.GzipFile(fileobj=target,mode='wb',mtime=0,compresslevel=1) as compressed:shutil.copyfileobj(src,compressed)
        result['export_gzip_sha256']=c.sha((out/'traces.jsonl.gz').read_bytes());(out/'traces.jsonl').unlink()
        c.dump(out/'result.json',result);print(json.dumps({k:result[k] for k in ['block','rate','policy','cpu_s','max_lag_s','exported_spans']}),flush=True)
    except BaseException:
        (out/'failure.txt').write_text(traceback.format_exc());raise
    finally:
        event.set()
        if thread:thread.join()
        if pair[0].poll() is None:c.stop(pair)

def run(args):
    allowed();base=args.output;base.mkdir(parents=True,exist_ok=False);shutil.copytree(HERE,base/'executed-source',ignore=shutil.ignore_patterns('__pycache__'))
    rates=list(map(int,args.rates.split(',')));blocks=[62000] if args.pilot else list(range(62001,62006));policies=args.policies.split(',') if args.policies else (['full'] if args.pilot else POLICIES)
    assert set(policies)<=set(POLICIES)
    capacity=max(rates)*8+1000;plan=[]
    for block in blocks:
        rows=list(itertools.product(rates,policies));random.Random(f'load-plan:{block}').shuffle(rows);plan.extend([[block,*row] for row in rows])
    c.dump(base/'plan.json',plan);c.dump(base/'environment.json',{'ticks':os.sysconf('SC_CLK_TCK'),'page_size':os.sysconf('SC_PAGE_SIZE'),'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text(),'memory_max':Path('/sys/fs/cgroup/memory.max').read_text(),'collector_sha256':c.sha(Path('/work/otelcol-contrib').read_bytes())})
    for block,rate,policy in plan:cell(base,block,rate,policy,10 if args.pilot else 30,capacity)
    c.dump(base/'complete.json',{'cells':len(plan),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--rates',default='50,2000,8000');p.add_argument('--policies');p.add_argument('--pilot',action='store_true');run(p.parse_args())
