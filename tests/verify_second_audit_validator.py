#!/usr/bin/env python3
"""Corrupt disposable pilot copies; preserved observations are never modified."""
import gzip,json,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/'.venv/bin/python'
VALIDATOR=ROOT/'scripts/verify_second_audit.py'
RAW=ROOT/'data/raw/second-audit-20260925'

def run(mode,path,corpus=None,analysis=None):
    cmd=[str(PYTHON),str(VALIDATOR),mode,str(path)]
    if corpus:cmd+=['--corpus',str(corpus)]
    if analysis:cmd+=['--analysis',str(analysis)]
    return subprocess.run(cmd,capture_output=True,text=True)

def change_json(path,fn):
    x=json.loads(path.read_text());fn(x);path.write_text(json.dumps(x))

def change_gzip(path,fn,jsonl=False):
    text=gzip.decompress(path.read_bytes()).decode();x=[json.loads(s) for s in text.splitlines()] if jsonl else json.loads(text);fn(x)
    text='\n'.join(json.dumps(s) for s in x)+'\n' if jsonl else json.dumps(x)
    path.write_bytes(gzip.compress(text.encode(),mtime=0))

cases=[]
with tempfile.TemporaryDirectory(prefix='trace-validator-',dir=ROOT/'tmp') as temp:
    temp=Path(temp)
    # A one-cell archive cut from a valid pilot keeps the same observed cell.
    load=temp/'load';load.mkdir();origin=RAW/'load-pilot-v1'
    shutil.copytree(origin/'executed-source',load/'executed-source');shutil.copy(origin/'environment.json',load/'environment.json')
    shutil.copytree(origin/'block-62000/rate-50-full',load/'block-62000/rate-50-full')
    (load/'plan.json').write_text(json.dumps([[62000,50,'full']]))
    (load/'complete.json').write_text(json.dumps({'cells':1}))
    assert run('load',load).returncode==0
    actions=[('cpu_summary',lambda p:change_json(p/'block-62000/rate-50-full/result.json',lambda x:x.update(cpu_s=x['cpu_s']+1))),('accepted_counter',lambda p:change_json(p/'block-62000/rate-50-full/result.json',lambda x:x.update(accepted_spans=x['accepted_spans']-5))),('json_bytes',lambda p:change_json(p/'block-62000/rate-50-full/result.json',lambda x:x.update(json_bytes=x['json_bytes']+1))),('missing_cell',lambda p:shutil.rmtree(p/'block-62000/rate-50-full'))]
    for name,fn in actions:
        p=temp/name;shutil.copytree(load,p);fn(p);result=run('load',p);assert result.returncode!=0,(name,result.stdout);cases.append(name)
    corpus=RAW/'diagnosis-pilot-v1';assert run('corpus',corpus).returncode==0
    for name,fn in [('timing_record',lambda x:x['records'][0]['durations_ms'].update({'service-a':999})),('parent_link',lambda x:x['resourceSpans'][0]['scopeSpans'][0]['spans'][0].update(parentSpanId='ffffffffffffffff')),('baseline_prediction',lambda x:x.update(full_prediction='invalid-service'))]:
        p=temp/name;shutil.copytree(corpus,p);first=sorted((p/'episodes').glob('*.json.gz'))[0];change_gzip(first,fn);assert run('corpus',p).returncode!=0;cases.append(name)
    replay=RAW/'diagnosis-replay-pilot-v1';assert run('replay',replay,corpus).returncode==0
    p=temp/'replay_label';shutil.copytree(replay,p);change_gzip(p/'trials.jsonl.gz',lambda x:x[0].update(prediction='invalid-service'),True);assert run('replay',p,corpus).returncode!=0;cases.append('replay_label')
    p=temp/'replay_coverage';shutil.copytree(replay,p)
    change_gzip(p/'trials.jsonl.gz',lambda x:x[0].update(budget=x[1]['budget']),True)
    assert run('replay',p,corpus).returncode!=0;cases.append('replay_coverage')
    # Rebuild pilot summaries through the prospective analysis, then check them
    # through the validator's separate binomial-CDF inversion.
    raw=temp/'pilot-analysis-input';raw.mkdir()
    (raw/'diagnosis-confirm-v1').symlink_to(corpus)
    (raw/'diagnosis-replay-v1').symlink_to(replay)
    analysis=temp/'analysis'
    result=subprocess.run([str(PYTHON),str(ROOT/'scripts/analyze_second_audit.py'),'--raw',str(raw),'--out',str(analysis)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert run('replay',replay,corpus,analysis).returncode==0
    change_json(analysis/'diagnosis-summary.json',lambda x:x['results'][0].update(upper_loss_bound=0))
    assert run('replay',replay,corpus,analysis).returncode!=0;cases.append('interval_summary')
print(json.dumps({'status':'PASS','uncorrupted_pilots_passed':True,'rejected_cases':cases},indent=2))
