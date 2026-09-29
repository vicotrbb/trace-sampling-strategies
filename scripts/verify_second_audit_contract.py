#!/usr/bin/env python3
"""Check the fixed design, source provenance, and injected-delay ledger.

This additional audit was written after the premeasurement freeze. It does not
change the frozen experiment, analysis, or primary validator.
"""
import argparse,datetime,gzip,hashlib,itertools,json,math,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/second-audit-20260925'
DOCS=ROOT/'docs/second-audit-20260925'
SERVICES=['service-a','service-b','service-c']
BUDGETS=[.05,.10,.20,.35,.50,.65,.80,.95]

def read(path):return json.loads(path.read_text())
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def check(diagnosis_only=False):
    freeze=read(DOCS/'execution-freeze.json')
    assert freeze['measured_load_rates']==[50,2000,8000,20000]
    assert freeze['measured_load_cells']==80 and freeze['diagnosis_incidents']==600
    assert freeze['replay_trials_per_comparison']==5000 and freeze['comparisons']==16
    assert freeze['context']=='homelab' and freeze['namespace']=='trace-sampling-load-20260925'
    groups=['diagnosis-confirm-v1','diagnosis-replay-v1']+([] if diagnosis_only else ['load-confirm-v1'])
    for filename,expected in freeze['files'].items():
        assert sha(ROOT/filename)==expected,filename
        for group in groups:assert sha(RAW/group/'executed-source'/Path(filename).name)==expected,(group,filename)
    for group in groups:assert (RAW/group/'executed-source/execution-freeze.json').read_bytes()==(DOCS/'execution-freeze.json').read_bytes()
    launch=read(DOCS/'launch.json');assert freeze['frozen_utc']<launch['utc'] and launch['sources_verified']
    plan=[]
    for service,delay,fraction in itertools.product(SERVICES,[5,15],[.5,1]):
        for _ in range(50):
            index=len(plan);plan.append({'episode':index,'seed':63000+index,'target':service,'added_ms':delay,'fraction':fraction})
    random.Random('diagnosis-order-v1').shuffle(plan)
    assert read(RAW/'diagnosis-confirm-v1/plan.json')==plan
    assert read(RAW/'diagnosis-confirm-v1/complete.json')['episodes']==600
    d=read(RAW/'diagnosis-replay-v1/design.json')
    assert d['episodes']==600 and d['trials']==5000 and d['trial_seed_base']==990000 and d['budgets']==BUDGETS
    assert read(RAW/'diagnosis-replay-v1/complete.json')['comparisons']==16
    seen=set();calls=0;min_excess=math.inf;protected_by_phase={'reference':0,'incident':0}
    for path in sorted((RAW/'diagnosis-confirm-v1/episodes').glob('*.json.gz')):
        e=json.loads(gzip.decompress(path.read_bytes()));design=e['design'];rng=random.Random(design['seed']);injected=[]
        for record in e['records']:
            tid=record['trace_id'];assert tid not in seen;seen.add(tid)
            active=record['phase']=='incident' and rng.random()<design['fraction']
            if active:injected.append(tid)
            for service in SERVICES:
                programmed_ms=1000*rng.lognormvariate(math.log(.008),.5)
                if active and service==design['target']:programmed_ms+=design['added_ms']
                excess=record['durations_ms'][service]-programmed_ms
                assert excess>=-.001,(path,record['index'],service,excess)
                min_excess=min(min_excess,excess);calls+=1
            protected_by_phase[record['phase']]+=record['root_ms']>=80
        assert injected==e['injected_trace_ids']
    assert len(seen)==24000 and calls==72000
    checked_files=0
    for name in ['diagnosis-copy-sha256.json']+([] if diagnosis_only else ['load-copy-sha256.json']):
        manifest=read(DOCS/name)
        for filename,expected in manifest.items():assert sha(RAW/filename)==expected,filename
        checked_files+=len(manifest)
    if not diagnosis_only:
        expected=[]
        for block in range(62001,62006):
            entries=list(itertools.product([50,2000,8000,20000],['full','head10','tail10','tail100']))
            random.Random(f'load-plan:{block}').shuffle(entries)
            expected.extend([[block,*e] for e in entries])
        base=RAW/'load-confirm-v1';assert read(base/'plan.json')==expected and read(base/'complete.json')['cells']==80
        assert len(list(base.glob('block-*/*/result.json')))==80
        environment=read(base/'environment.json')
        earlier=read(ROOT/'data/raw/revision-20260924/confirm-v1/environment.json')
        assert environment['collector_sha256']==earlier['binary_sha256']['otelcol-contrib']
        assert environment['cpu_max'].strip()=='400000 100000' and int(environment['memory_max'])==6*2**30
        for block,rate,policy in expected:
            cell=base/f'block-{block}'/f'rate-{rate}-{policy}';r=read(cell/'result.json')
            assert r['duration_s']==30 and r['warmup_s']==5 and r['drain_s']==5 and r['capacity']==161000
            assert r['utc']>launch['utc'][:19]+'Z'
            endpoints=read(cell/'endpoints.json')
            assert r['wall_s']==endpoints['after']['end_monotonic']-endpoints['before']['begin_monotonic']
            assert r['wall_s']>=35
            for phase,seconds in [('warmup',5),('measured',30)]:
                count=rate*seconds;receipts=read(cell/f'{phase}-receipts.json')
                assert [v['begin'] for v in receipts]==list(range(0,count,100))
                expected_ingress=0
                for v in receipts:
                    assert v['offset_s']==v['begin']/rate and v['lag_s']==v['start_s']-v['offset_s']
                    assert v['elapsed_s']>=0 and v['status']==200
                    assert not json.loads(v['body']).get('partialSuccess',{}).get('rejectedSpans',0)
                    stop=min(v['begin']+100,count)
                    if policy=='head10':
                        selected=0
                        for sequence in range(v['begin'],stop):
                            trace_id=hashlib.sha256(f'{block}:{phase}:{sequence}'.encode()).hexdigest()[:32]
                            priority=int.from_bytes(hashlib.blake2b(bytes.fromhex(trace_id),digest_size=8).digest(),'big')
                            selected+=priority<int(.1*2**64)
                    else:selected=stop-v['begin']
                    assert v['spans']==5*selected
                    expected_ingress+=5*selected
                if phase=='measured':
                    assert r['accepted_spans']==expected_ingress
                    assert r['wall_s']>=receipts[-1]['start_s']+receipts[-1]['elapsed_s']+5
            command=read(cell/'collector-command.json');assert command['environment']=={'GOMAXPROCS':'2'}
            assert command['command']==['/work/otelcol-contrib','--config',f'/work/outputs/load-confirm-v1/block-{block}/rate-{rate}-{policy}/config.json']
            cfg=read(cell/'config.json');assert set(cfg['exporters'])=={'file'}
            assert cfg['exporters']['file']=={'flush_interval':'100ms','format':'json','path':f'/work/outputs/load-confirm-v1/block-{block}/rate-{rate}-{policy}/traces.jsonl'}
            assert cfg['receivers']=={'otlp':{'protocols':{'http':{'endpoint':'127.0.0.1:4318'}}}}
            chain=['tail_sampling','batch'] if policy.startswith('tail') else ['batch']
            assert cfg['service']['pipelines']=={'traces':{'exporters':['file'],'processors':chain,'receivers':['otlp']}}
            if policy.startswith('tail'):
                tail=cfg['processors']['tail_sampling']
                assert tail['expected_new_traces_per_sec']==20125
                assert tail['decision_cache']=={'non_sampled_cache_size':1288000,'sampled_cache_size':1288000}
                assert tail['policies'][:2]==[{'name':'error','type':'status_code','status_code':{'status_codes':['ERROR']}},{'name':'latency','type':'latency','latency':{'threshold_ms':250}}]
    return {'status':'PASS','scope':'diagnosis' if diagnosis_only else 'all measured extensions','frozen_files_unchanged':len(freeze['files']),'source_side_copy_checksums':checked_files,'unique_diagnosis_traces':len(seen),'programmed_leaf_delays_reconciled':calls,'minimum_observed_minus_programmed_ms':min_excess,'protected_traces_by_phase':protected_by_phase,'fixed_trial_comparison_grid_verified':True,'pinned_binary_limits_and_full_load_configuration_verified':not diagnosis_only,'planned_ingress_and_schedule_receipts_verified':not diagnosis_only}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--diagnosis-only',action='store_true');p.add_argument('--receipt',type=Path);a=p.parse_args();result=check(a.diagnosis_only)
    if a.receipt:a.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
