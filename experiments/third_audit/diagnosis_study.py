#!/usr/bin/env python3
"""Observed HTTP leaf timings and fixed-corpus randomized diagnosis replay."""
import argparse, concurrent.futures, gzip, hashlib, http.client, itertools, json, math, os, random, shutil, statistics, threading, time, traceback
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import common as c
from load_study import allowed

HERE=Path(__file__).resolve().parent
SERVICES=['service-a','service-b','service-c']
BUDGETS=[.05,.10,.20,.35,.50,.65,.80,.95]
WINDOWS=[20,50,200]

class Leaf(BaseHTTPRequestHandler):
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        started=time.time_ns();time.sleep(body['delay_s']);ended=time.time_ns()
        response=json.dumps({'start_ns':started,'end_ns':ended}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(response)));self.end_headers();self.wfile.write(response)
    def log_message(self,*args):pass

def prediction(records,selected=None):
    values={phase:{service:[] for service in SERVICES} for phase in ['reference','incident']}
    for record in records:
        if selected is not None and record['trace_id'] not in selected:continue
        for service,duration in record['durations_ms'].items():values[record['phase']][service].append(duration)
    if any(not values[phase][SERVICES[0]] for phase in values):return None
    scores={s:statistics.median(values['incident'][s])-statistics.median(values['reference'][s]) for s in SERVICES}
    return max(SERVICES,key=lambda s:scores[s])

def episode(row,ports):
    rng=random.Random(row['seed']);records=[];resource=[];injected=[]
    clients=[http.client.HTTPConnection('127.0.0.1',p,timeout=10) for p in ports]
    try:
        for phase in ['reference','incident']:
            for index in range(row['window']):
                tid=hashlib.sha256(f"sensitivity-v1:{row['seed']}:{phase}:{index}".encode()).hexdigest()[:32]
                root_id=hashlib.sha256((tid+':gateway').encode()).hexdigest()[:16];start=time.time_ns();durations={}
                hit=phase=='incident' and rng.random()<row['fraction']
                if hit:injected.append(tid)
                for j,service in enumerate(SERVICES):
                    delay=rng.lognormvariate(math.log(.008),.5)+(row['added_ms']/1000 if hit and service==row['target'] else 0)
                    body=json.dumps({'delay_s':delay}).encode();clients[j].request('POST','/operation',body,{'Content-Type':'application/json'})
                    response=clients[j].getresponse();observed=json.loads(response.read());assert response.status==200
                    first,last=observed['start_ns'],observed['end_ns'];durations[service]=(last-first)/1e6
                    resource.append({'resource':{'attributes':[{'key':'service.name','value':{'stringValue':service}}]},'scopeSpans':[{'scope':{'name':'diagnosis-timing'},'spans':[{'traceId':tid,'spanId':hashlib.sha256((tid+':'+service).encode()).hexdigest()[:16],'parentSpanId':root_id,'name':'operation','kind':2,'startTimeUnixNano':str(first),'endTimeUnixNano':str(last),'status':{'code':1}}]}]})
                end=time.time_ns();resource.append({'resource':{'attributes':[{'key':'service.name','value':{'stringValue':'gateway'}}]},'scopeSpans':[{'scope':{'name':'diagnosis-timing'},'spans':[{'traceId':tid,'spanId':root_id,'name':'request','kind':2,'startTimeUnixNano':str(start),'endTimeUnixNano':str(end),'status':{'code':1}}]}]})
                records.append({'trace_id':tid,'phase':phase,'index':index,'durations_ms':durations,'root_ms':(end-start)/1e6})
    finally:
        for client in clients:client.close()
    return {'design':row,'records':records,'injected_trace_ids':injected,'full_predictions':{str(n):prediction([v for v in records if v['index']<n]) for n in WINDOWS if n<=row['window']},'resourceSpans':resource}

def collect(args):
    allowed();out=args.output;out.mkdir(parents=True,exist_ok=False);shutil.copytree(HERE,out/'executed-source',ignore=shutil.ignore_patterns('__pycache__'))
    rows=[]
    if args.mode=='calibrate':
        rows=[{'episode':i,'seed':710000+i,'target':'service-a','added_ms':0,'fraction':0,'window':20,'kind':'calibration'} for i in range(50)]
    else:
        copies=1 if args.pilot else 50
        start_seed=740000 if args.pilot else 730000
        for target,added,fraction in itertools.product(SERVICES,[5,15],[.5,1]):
            for _ in range(copies):
                rows.append({'episode':len(rows),'seed':start_seed+len(rows),'target':target,'added_ms':added,'fraction':fraction,'window':20 if args.pilot else 200,'kind':'pilot' if args.pilot else 'measured'})
    random.Random('sensitivity-order-v1').shuffle(rows);c.dump(out/'plan.json',rows)
    servers=[ThreadingHTTPServer(('127.0.0.1',0),Leaf) for _ in SERVICES]
    for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
    ports=[s.server_port for s in servers]
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures={pool.submit(episode,row,ports):row for row in rows}
            for future in concurrent.futures.as_completed(futures):
                row=futures[future];value=future.result();destination=out/'episodes'/f"episode-{row['episode']:04}.json.gz";destination.parent.mkdir(exist_ok=True)
                destination.write_bytes(gzip.compress(json.dumps(value,separators=(',',':')).encode(),mtime=0))
                print(json.dumps({'episode':row['episode'],'complete':True}),flush=True)
    finally:
        for server in servers:server.shutdown();server.server_close()
    if args.mode=='calibrate':
        values=sorted(r['root_ms'] for p in sorted((out/'episodes').glob('*.json.gz')) for r in json.loads(gzip.decompress(p.read_bytes()))['records'])
        assert len(values)==2000
        c.dump(out/'threshold.json',{'requests':2000,'quantile':.95,'method':'nearest rank ceil(.95*n), one based','rank':1900,'threshold_ms':values[1899], 'source_sha256':{p.name:c.sha(p.read_bytes()) for p in sorted((out/'episodes').glob('*.json.gz'))}})
    c.dump(out/'complete.json',{'episodes':len(rows),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})

def replay(args):
    allowed();out=args.output;out.mkdir(parents=True,exist_ok=False);shutil.copytree(HERE,out/'executed-source',ignore=shutil.ignore_patterns('__pycache__'))
    episodes=[json.loads(gzip.decompress(p.read_bytes())) for p in sorted((args.corpus/'episodes').glob('*.json.gz'))]
    threshold=json.loads((args.calibration/'threshold.json').read_text())['threshold_ms']
    windows=[n for n in WINDOWS if n<=episodes[0]['design']['window']]
    alphas={str(n):sum(r['root_ms']>=threshold for e in episodes for r in e['records'] if r['index']<n)/(2*n*len(episodes)) for n in windows}
    c.dump(out/'design.json',{'episodes':len(episodes),'windows':windows,'budgets':BUDGETS,'trials':5000,'alphas':alphas,'threshold_ms':threshold,'family_size':48,'trial_seed_base':1990000,'calibration_sha256':c.sha((args.calibration/'threshold.json').read_bytes()),'source_episode_sha256':{p.name:c.sha(p.read_bytes()) for p in sorted((args.corpus/'episodes').glob('*.json.gz'))}})
    with (out/'trials.jsonl.gz').open('wb') as file:
        with gzip.GzipFile(fileobj=file,mode='wb',mtime=0) as stream:
            for trial in range(5000):
                rng=random.Random(1990000+trial);e=episodes[rng.randrange(len(episodes))];all_records=e['records'];priorities=[rng.random() for _ in all_records]
                for window in windows:
                    records=[r for r in all_records if r['index']<window]
                    u=[v for r,v in zip(all_records,priorities) if r['index']<window]
                    alpha=alphas[str(window)]
                    for policy,budget in itertools.product(['head','tail'],BUDGETS):
                        value={'trial':trial,'window':window,'policy':policy,'budget':budget,'feasible':policy!='tail' or budget>=alpha}
                        if value['feasible']:
                            background=(budget-alpha)/(1-alpha) if policy=='tail' else budget
                            selected={r['trace_id'] for r,x in zip(records,u) if x<background or (policy=='tail' and r['root_ms']>=threshold)}
                            pred=prediction(records,selected);truth=e['design']['target'];full=e['full_predictions'][str(window)];before=full==truth;after=pred==truth
                            counts={phase:sum(r['trace_id'] in selected for r in records if r['phase']==phase) for phase in ['reference','incident']}
                            value.update(episode=e['design']['episode'],full_prediction=full,prediction=pred,truth=truth,retained=len(selected),retained_reference=counts['reference'],retained_incident=counts['incident'],full_correct=before,correct=after,loss=before and not after,gain=after and not before)
                        stream.write((json.dumps(value,separators=(',',':'))+'\n').encode())
                if trial%100==0:print(json.dumps({'trial':trial}),flush=True)
    c.dump(out/'complete.json',{'trials':5000,'comparisons':len(windows)*16,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['collect','calibrate','replay']);p.add_argument('--output',required=True,type=Path);p.add_argument('--corpus',type=Path);p.add_argument('--calibration',type=Path);p.add_argument('--pilot',action='store_true');a=p.parse_args();replay(a) if a.mode=='replay' else collect(a)
