#!/usr/bin/env python3
"""Post-freeze contract audit: coverage, source provenance, paired input, summaries."""
import argparse,datetime,gzip,hashlib,itertools,json,math,random,statistics
from collections import defaultdict
from pathlib import Path
from scipy.optimize import brentq
from scipy.stats import t
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/third-audit-20260925'
DOC=ROOT/'docs/third-audit-20260925'
OUT=ROOT/'data/derived/third-audit-20260925'
def read(p):return json.loads(p.read_text())
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def stamp(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
def audit():
    freeze=read(DOC/'execution-freeze.json');pilot=read(DOC/'pilot-source-freeze.json')
    for name,sha in freeze['files'].items():assert digest(ROOT/name)==sha,name
    assert freeze['files']==pilot['files']
    assert digest(RAW/'calibration-v1/threshold.json')==freeze['calibration_threshold_sha256']
    assert stamp(pilot['utc'])<stamp(read(RAW/'calibration-v1/complete.json')['utc'])<stamp(freeze['utc'])<stamp(read(DOC/'launch.json')['utc'])
    for group in ['diagnosis-confirm-v1','diagnosis-replay-v1','load-confirm-v1']:
        source=RAW/group/'executed-source'
        assert read(source/'execution-freeze.json')==freeze
        for name,sha in freeze['files'].items():assert digest(source/Path(name).name)==sha
        assert stamp(read(RAW/group/'complete.json')['utc'])>stamp(freeze['utc'])
    corpus=read(RAW/'diagnosis-confirm-v1/plan.json');ordered=sorted(corpus,key=lambda r:r['episode']);random.Random('sensitivity-order-v1').shuffle(ordered);assert ordered==corpus
    diagnosis=read(OUT/'diagnosis-summary.json')
    protected={str(w):{'reference':0,'incident':0} for w in [20,50,200]}
    for path in sorted((RAW/'diagnosis-confirm-v1/episodes').glob('*.json.gz')):
        episode=json.loads(gzip.decompress(path.read_bytes()))
        for record in episode['records']:
            for w in [20,50,200]:
                if record['index']<w and record['root_ms']>=diagnosis['threshold_ms']:
                    protected[str(w)][record['phase']]+=1
    assert diagnosis['protected_counts']==protected
    strata={d['episode']:f"{d['target']}-{d['added_ms']}-{d['fraction']}" for d in corpus}
    subgroup=defaultdict(lambda:defaultdict(lambda:defaultdict(int)))
    with gzip.open(RAW/'diagnosis-replay-v1/trials.jsonl.gz','rt') as stream:
        for line in stream:
            row=json.loads(line)
            if not row['feasible']:continue
            group=subgroup[row['window'],row['policy'],row['budget']][strata[row['episode']]]
            group['n']+=1
            for key in ['full_correct','correct','loss','gain']:group[key]+=int(row[key])
    for row in diagnosis['results']:
        if row['feasible']:assert row['descriptive_strata']==subgroup[row['window'],row['policy'],row['budget']]
    plan=[]
    for block in range(72001,72006):
        rows=list(itertools.product([20000],['full','gate10','collector10','tail10']));random.Random(f'load-plan:{block}').shuffle(rows);plan.extend([[block,*row] for row in rows])
    load=RAW/'load-confirm-v1';assert read(load/'plan.json')==plan
    assert read(load/'complete.json')['cells']==20
    all_cells={};input_pairs=0
    for block,rate,policy in plan:
        p=load/f'block-{block}'/f'rate-{rate}-{policy}';d=read(p/'design.json');assert d['capacity']==161000 and d['duration_s']==30 and d['warmup_s']==5 and d['drain_s']==5
        cfg=read(p/'config.json');assert list(cfg['exporters'])==['file'] and cfg['exporters']['file']['format']=='json'
        assert read(p/'collector-command.json')['environment']['GOMAXPROCS']=='2'
        if policy=='tail10':
            assert cfg['processors']['tail_sampling']['decision_cache']=={'sampled_cache_size':1288000,'non_sampled_cache_size':1288000}
            assert cfg['service']['pipelines']['traces']['processors']==['tail_sampling','batch']
            assert cfg['processors']['tail_sampling']['policies']==[
                {'name':'error','type':'status_code','status_code':{'status_codes':['ERROR']}},
                {'name':'latency','type':'latency','latency':{'threshold_ms':250}},
                {'name':'background','type':'probabilistic','probabilistic':{'sampling_percentage':100*.08/.98,'hash_salt':'load-second-audit-v1'}},
            ]
        endpoint=read(p/'endpoints.json')
        before=endpoint['before']['processes']['collector'];after=endpoint['after']['processes']['collector']
        assert before['pid']==after['pid'] and before['start_ticks']==after['start_ticks']
        assert endpoint['after']['begin_monotonic']>endpoint['before']['end_monotonic']
        for sample in read(p/'samples.json'):
            process=sample['processes']['collector']
            assert process['pid']==before['pid'] and process['start_ticks']==before['start_ticks']
        all_cells[block,policy]=read(p/'result.json')
        for phase,duration in [('warmup',5),('measured',30)]:
            receipts=read(p/f'{phase}-receipts.json');assert len(receipts)==rate*duration//100
            assert [v['begin'] for v in receipts]==list(range(0,rate*duration,100))
            assert all(v['offset_s']==v['begin']/rate and abs(v['start_s']-v['offset_s']-v['lag_s'])<1e-10 for v in receipts)
            if policy in ['collector10','tail10']:
                reference=read(load/f'block-{block}'/f'rate-{rate}-full'/f'{phase}-receipts.json')
                assert [(v['payload_sha256'],v['spans']) for v in receipts]==[(v['payload_sha256'],v['spans']) for v in reference];input_pairs+=1
    for b in range(72001,72006):assert all_cells[b,'gate10']['exported_spans']==all_cells[b,'collector10']['exported_spans']
    environment=read(load/'environment.json');assert environment['ticks']==100 and environment['cpu_max'].split()==['400000','100000'] and int(environment['memory_max'])==6*1024**3
    previous=read(ROOT/'data/raw/second-audit-20260925/load-confirm-v1/environment.json');assert environment['collector_sha256']==previous['collector_sha256']
    summary=read(OUT/'load-summary.json');assert summary['cells']==20 and len(summary['groups'])==4 and len(summary['contrasts'])==5
    crit=brentq(lambda z:float(t.cdf(z,4))-.975,0,10)
    def check(record,xs):
        assert record['values']==xs
        mean=math.fsum(xs)/5;radius=crit*math.sqrt(math.fsum((x-mean)**2 for x in xs)/4)/math.sqrt(5)
        for key,val in [('mean',mean),('lower',mean-radius),('upper',mean+radius)]:assert math.isclose(record[key],val,rel_tol=1e-10,abs_tol=1e-9),(key,val,record)
    for p,g in summary['groups'].items():
        for key,v in g.items():check(v,[all_cells[b,p][key] for b in range(72001,72006)])
    for name,g in summary['contrasts'].items():
        a,b=name.split('-minus-');xs=[all_cells[i,a]['cpu_s'] for i in range(72001,72006)];ys=[all_cells[i,b]['cpu_s'] for i in range(72001,72006)]
        check(g['cpu_difference_s'],[x-y for x,y in zip(xs,ys)]);check(g['cpu_saving_percent'],[100*(1-x/y) for x,y in zip(xs,ys)])
    assert summary['max_lag_s']==max(v['max_lag_s'] for v in all_cells.values())
    copies=read(RAW/'copy-sha256.json')
    for name,sha in copies.items():assert digest(RAW/name)==sha,name
    return {'status':'PASS','frozen_files':len(freeze['files']),'threshold_frozen_before_incidents':True,'new_load_cells':20,'matched_full_ingress_phase_pairs':input_pairs,'uniform_selected_counts_match':True,'load_summaries_independently_recomputed':34,'protected_window_counts_and_all_descriptive_strata_verified':True,'source_side_copy_hashes':len(copies),'pinned_binary_and_runtime_limits_verified':True,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
if __name__=='__main__':
    v=audit();(DOC/'contract-validation.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v,indent=2))
