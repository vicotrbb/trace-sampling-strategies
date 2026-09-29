#!/usr/bin/env python3
"""Live measurement controller, executable only inside the authorized homelab pod."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import http.client
import json
import os
from pathlib import Path
import random
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import psycopg
from diagnose import diagnose

WORK = Path('/work')
HERE = Path(__file__).resolve().parent
KINDS = ['normal', 'sql_schema', 'database_latency', 'domain_invariant']
RATE = 50
DURATION = 60
WARMUP = 10
DRAIN = 5
SEEDS = [41001, 41002, 41003, 41004, 41005]
GOVARS = {**os.environ, 'GOMAXPROCS': '2'}

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')

def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()

def start(out, name, command, env=GOVARS):
    log = (out / (name + '.log')).open('wb')
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
    return process, log

def ready(process, url):
    for _ in range(400):
        if process.poll() is not None: raise RuntimeError(f'process exited {process.args}')
        try: get(url); return
        except Exception: time.sleep(.05)
    raise RuntimeError(f'readiness timeout: {url}')

def stop(pair):
    process, log = pair
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=35)
    log.close()
    if process.returncode not in (0, -signal.SIGTERM):
        raise RuntimeError(f'exit {process.returncode}: {process.args}')

def proc(pid):
    raw = Path(f'/proc/{pid}/stat').read_text()
    fields = raw[raw.rfind(')')+2:].split()
    return {'pid': pid, 'read_monotonic': time.monotonic(), 'raw_stat': raw,
            'cpu_s': (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK'),
            'rss_bytes': int(fields[21]) * os.sysconf('SC_PAGE_SIZE'), 'start_ticks': int(fields[19])}

def snapshot(processes):
    result = {'begin_monotonic': time.monotonic(),
              'processes': {name: proc(p[0].pid) for name, p in processes.items()}}
    raw = get('http://127.0.0.1:9081').decode()
    lines = raw.splitlines()
    cpu = lines[lines.index('CPU')+1:lines.index('MEMORY')]
    result['postgres'] = {'raw': raw, 'cpu_s': float(dict(x.split() for x in cpu)['usage_usec']) / 1e6,
                          'memory_current': int(lines[lines.index('MEMORY')+1])}
    result['runner_cgroup_cpu'] = Path('/sys/fs/cgroup/cpu.stat').read_text()
    result['end_monotonic'] = time.monotonic()
    return result

def disk(path):
    files = [p.stat() for p in path.rglob('*') if p.is_file()]
    return {'logical_bytes': sum(s.st_size for s in files),
            'allocated_bytes': sum(s.st_blocks * 512 for s in files), 'files': len(files)}

def collector_config(out, policy):
    cfg = {
        'receivers': {'otlp': {'protocols': {'http': {'endpoint': '127.0.0.1:4318'}}}},
        'processors': {'batch': {'timeout': '100ms', 'send_batch_size': 256, 'send_batch_max_size': 512}},
        'exporters': {
            'file': {'path': str(out / 'traces.jsonl'), 'format': 'json', 'flush_interval': '100ms'},
            'otlphttp': {'endpoint': 'http://127.0.0.1:14318', 'retry_on_failure': {'enabled': False},
                         'sending_queue': {'enabled': False}}},
        'service': {
            'telemetry': {'logs': {'level': 'warn'}, 'metrics': {'level': 'detailed', 'readers': [
                {'pull': {'exporter': {'prometheus': {'host': '127.0.0.1', 'port': 8888}}}}]}},
            'pipelines': {'traces': {'receivers': ['otlp'], 'processors': ['batch'],
                                    'exporters': ['file', 'otlphttp']}}}}
    if policy == 'tail':
        cfg['processors']['tail_sampling'] = {
            'decision_wait': '2s', 'num_traces': 512, 'expected_new_traces_per_sec': RATE,
            'decision_cache': {'sampled_cache_size': 10000, 'non_sampled_cache_size': 10000},
            'policies': [
                {'name': 'error', 'type': 'status_code', 'status_code': {'status_codes': ['ERROR']}},
                {'name': 'latency', 'type': 'latency', 'latency': {'threshold_ms': 250}},
                {'name': 'background', 'type': 'probabilistic',
                 'probabilistic': {'sampling_percentage': 100 * .08 / .98, 'hash_salt': 'trace-study-v1'}}]}
        cfg['service']['pipelines']['traces']['processors'].insert(0, 'tail_sampling')
    return cfg

def launch_jaeger(out, name='jaeger'):
    command = [str(WORK / 'jaeger-1.76.0-linux-amd64/jaeger-all-in-one'),
        '--collector.otlp.enabled=true', '--collector.otlp.http.host-port=127.0.0.1:14318',
        '--collector.otlp.grpc.host-port=127.0.0.1:14317',
        '--badger.ephemeral=false', '--badger.directory-key=' + str(out / 'badger/keys'),
        '--badger.directory-value=' + str(out / 'badger/values'), '--badger.span-store-ttl=1h',
        '--log-level=warn']
    dump(out / (name + '-command.json'), {'command':command,'environment':{'SPAN_STORAGE_TYPE':'badger','OTEL_TRACES_SAMPLER':'always_off','GOMAXPROCS':'2'}})
    pair = start(out, name, command, {**GOVARS, 'SPAN_STORAGE_TYPE': 'badger', 'OTEL_TRACES_SAMPLER': 'always_off'})
    ready(pair[0], 'http://127.0.0.1:16686/api/services')
    return pair

def initialize_database():
    with psycopg.connect(os.environ['PG_DSN'], autocommit=True) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS study_products (id integer PRIMARY KEY, unit_price integer)')
        connection.execute('TRUNCATE study_products')
        connection.execute('INSERT INTO study_products VALUES (1,100),(2,250),(3,75)')
        connection.execute('CREATE TABLE IF NOT EXISTS study_documents (id integer PRIMARY KEY, content text)')
        connection.execute('TRUNCATE study_documents')
        for i in range(1, 11):
            connection.execute('INSERT INTO study_documents VALUES (%s,%s)', (i, ' '.join(['Document', 'token', 'value'] * i)))

def schedule(app, regime, seed, phase, duration):
    n = RATE * duration
    controls = [1] * (n // 100) + [2] * (n // 100) + [3] * (n // 100)
    controls += [0] * (n - len(controls))
    random.Random(f'labels:{seed}:{phase}').shuffle(controls)
    requests = []
    for i, control in enumerate(controls):
        rid = hashlib.sha256(f'opaque:{app}:{regime}:{seed}:{phase}:{i}'.encode()).hexdigest()
        tid = hashlib.sha256(rid.encode()).digest()[:16].hex()
        offset = i / RATE if regime == 'steady' else (i // RATE) + (i % RATE) / (RATE * 5)
        payload = {'quantities': [1+i%3, 2, 1]} if app == 'checkout' else {'document_id': 1+i%10, 'expected_tokens': 3*(1+i%10)}
        requests.append({'index': i, 'request_id': rid, 'trace_id': tid, 'control': control, 'kind': KINDS[control],
                         'service': app+'-worker' if control == 3 else 'postgresql',
                         'offset_s': offset, 'payload': payload, 'phase': phase})
    return requests

def send_request(item, origin):
    started = time.monotonic()
    result = dict(item, started_s=started-origin, schedule_lag_s=started-origin-item['offset_s'])
    connection = http.client.HTTPConnection('127.0.0.1', 8081, timeout=20)
    try:
        connection.request('POST', '/process', json.dumps(item['payload']),
                           {'Content-Type': 'application/json', 'X-Request-Id': item['request_id'],
                            'X-Study-Control': str(item['control'])})
        response = connection.getresponse()
        result.update(http_status=response.status, response=json.loads(response.read()))
        result['transport_ok'] = True
    except Exception as error:
        result.update(transport_ok=False, error=repr(error))
    finally:
        connection.close()
        result['latency_s'] = time.monotonic()-started
    return result

def load(items, duration):
    origin = time.monotonic()
    futures = []
    with ThreadPoolExecutor(max_workers=64) as executor:
        for item in items:
            delay = origin + item['offset_s'] - time.monotonic()
            if delay > 0: time.sleep(delay)
            futures.append(executor.submit(send_request, item, origin))
        rest = origin + duration - time.monotonic()
        if rest > 0: time.sleep(rest)
        results = [future.result() for future in futures]
    return results

def flush():
    for port in (8081, 8082):
        assert json.loads(get(f'http://127.0.0.1:{port}/flush'))['flushed']
    time.sleep(DRAIN)

def read_exports(path):
    records = defaultdict(dict)
    duplicates = []
    for line in path.read_bytes().splitlines():
        for rs in json.loads(line).get('resourceSpans', []):
            for ss in rs.get('scopeSpans', []):
                for span in ss['spans']:
                    tid, sid = span['traceId'].lower(), span['spanId'].lower()
                    if sid in records[tid]: duplicates.append([tid, sid])
                    records[tid][sid] = span
    return records, duplicates

def backend_query(out, app, min_ns, max_ns, name):
    query = urllib.parse.urlencode({'service': app+'-gateway', 'start': min_ns//1000,
                                    'end': max_ns//1000 + 1000000, 'limit': 10000})
    started = time.monotonic()
    raw = get('http://127.0.0.1:16686/api/traces?' + query, timeout=60)
    elapsed = time.monotonic()-started
    (out / (name + '.json.gz')).write_bytes(gzip.compress(raw, mtime=0))
    data = json.loads(raw)
    if data.get('errors'): raise RuntimeError(data['errors'])
    traces = data.get('data') or []
    return {'seconds': elapsed, 'json_bytes': len(raw), 'trace_count': len(traces),
            'spans': {t['traceID']: sorted(s['spanID'] for s in t['spans']) for t in traces}}

def cell(base, app, regime, seed, policy, duration=DURATION, warmup=WARMUP):
    out = base / f'{app}-{regime}' / f'seed-{seed}' / policy
    out.mkdir(parents=True, exist_ok=False)
    processes = {}
    finished = False
    config = {'app': app, 'regime': regime, 'seed': seed, 'policy': policy, 'duration_s': duration,
              'warmup_s': warmup, 'drain_s': DRAIN, 'offered_rate': RATE,
              'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in HERE.glob('*.py')}, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    dump(out / 'design.json', config)
    try:
        initialize_database()
        processes['jaeger'] = launch_jaeger(out)
        dump(out / 'config.json', collector_config(out, policy))
        processes['collector'] = start(out, 'collector', [str(WORK / 'otelcol-contrib'), '--config', str(out / 'config.json')])
        ready(processes['collector'][0], 'http://127.0.0.1:8888/metrics')
        for role in ('worker', 'gateway'):
            processes[role] = start(out, role, [sys.executable, str(HERE / 'application.py'), '--app', app,
                                               '--role', role, '--rate', '.1' if policy == 'head' else '1'])
            ready(processes[role][0], f'http://127.0.0.1:{8081 if role=="gateway" else 8082}/health')
        wall_start = time.time_ns()
        warm = load(schedule(app, regime, seed, 'warmup', warmup), warmup)
        flush()
        dump(out / 'warmup.json', warm)
        (out / 'metrics-before.txt').write_bytes(get('http://127.0.0.1:8888/metrics'))
        initial_disk = disk(out / 'badger')
        before = snapshot(processes)
        controller_before = proc(os.getpid())
        samples, event = [], threading.Event()
        def monitor():
            while not event.is_set():
                try: samples.append(snapshot(processes))
                except Exception as error: samples.append({'error': repr(error), 'time': time.monotonic()})
                event.wait(1)
        monitor_thread = threading.Thread(target=monitor)
        monitor_thread.start()
        measured = load(schedule(app, regime, seed, 'measured', duration), duration)
        flush()
        after = snapshot(processes)
        controller_after = proc(os.getpid())
        event.set(); monitor_thread.join()
        (out / 'metrics-after.txt').write_bytes(get('http://127.0.0.1:8888/metrics'))
        dump(out / 'resource-endpoints.json', {'before': before, 'after': after,
                                             'controller_before': controller_before, 'controller_after': controller_after})
        dump(out / 'resource-samples.json', samples)
        dump(out / 'truth.json', measured)
        ingest_disk = disk(out / 'badger')
        for name in ('gateway', 'worker', 'collector'):
            stop(processes.pop(name))
        records, duplicates = read_exports(out / 'traces.jsonl')
        original_query = backend_query(out, app, wall_start, time.time_ns(), 'query-before-restart')
        stop(processes.pop('jaeger'))
        closed_disk = disk(out / 'badger')
        processes['jaeger'] = launch_jaeger(out, 'jaeger-restarted')
        restarted_query = backend_query(out, app, wall_start, time.time_ns(), 'query-after-restart')
        stop(processes.pop('jaeger'))
        # Classify solely from span content, then join predictions to the private truth ledger.
        predictions = {tid: diagnose(list(spans.values())) for tid, spans in records.items()}
        dump(out / 'predictions.json', predictions)
        outcome = []
        errors = []
        for row in warm + measured:
            if not row['transport_ok']: errors.append(['transport', row['phase'], row['index']]); continue
            if row['response']['trace_id'] != row['trace_id']: errors.append(['trace_link', row['index']])
            if row['http_status'] != (500 if row['control']==1 else 200): errors.append(['unexpected_status', row['index']])
        offered = {row['trace_id']: row for row in warm + measured}
        if set(records)-set(offered): errors.append(['unknown_trace_ids'])
        if duplicates: errors.append(['duplicates', duplicates[:5]])
        expected_stored = {tid: sorted(spans) for tid, spans in records.items()}
        if original_query['spans'] != expected_stored: errors.append(['backend_export_mismatch_before'])
        if restarted_query['spans'] != expected_stored: errors.append(['backend_export_mismatch_after'])
        for row in measured:
            tid = row['trace_id']
            spans = records.get(tid, {})
            prediction = predictions.get(tid, ('abstain', 'unknown'))
            expected_ids = set(row.get('response', {}).get('span_ids', {}).values())
            complete = bool(expected_ids) and set(spans) == expected_ids
            correct = row['control'] != 0 and tuple(prediction) == (row['kind'], row['service'])
            outcome.append({'index': row['index'], 'trace_id': tid, 'kind': row['kind'], 'service': row['service'],
                            'retained': bool(spans), 'complete': complete, 'prediction': prediction, 'correct': correct})
        if policy == 'full' and any(not r['complete'] for r in outcome): errors.append(['incomplete_baseline'])
        if any(not r['correct'] for r in outcome if policy == 'full' and r['kind'] != 'normal'):
            errors.append(['baseline_diagnosis_failure'])
        dump(out / 'outcomes.json', outcome)
        raw = (out / 'traces.jsonl').read_bytes()
        (out / 'traces.jsonl.gz').write_bytes(gzip.compress(raw, mtime=0))
        (out / 'traces.jsonl').unlink()
        result = {**config, 'valid': not errors, 'errors': errors, 'offered_measured': len(measured),
                  'retained_measured': sum(r['retained'] for r in outcome), 'retained_all': len(records),
                  'export_spans_all': sum(len(v) for v in records.values()), 'export_json_bytes_all': len(raw),
                  'export_json_sha256': hashlib.sha256(raw).hexdigest(),
                  'diagnosis_by_kind': {kind: {'n': sum(r['kind']==kind for r in outcome),
                                             'correct': sum(r['correct'] for r in outcome if r['kind']==kind)}
                                        for kind in KINDS},
                  'false_accusations': sum(r['kind']=='normal' and r['prediction'][0]!='abstain' for r in outcome),
                  'storage': {'before': initial_disk, 'ingest': ingest_disk, 'after_shutdown': closed_disk},
                  'query_before_restart': {k:v for k,v in original_query.items() if k!='spans'},
                  'query_after_restart': {k:v for k,v in restarted_query.items() if k!='spans'}}
        dump(out / 'result.json', result)
        # Query receipts retain every stored trace; compact fresh Badger databases can now be removed.
        shutil.rmtree(out / 'badger')
        finished = True
        print('CELL', json.dumps({k:result[k] for k in ('app','regime','seed','policy','valid','errors','retained_measured','diagnosis_by_kind')}), flush=True)
        if errors: raise RuntimeError(f'cell validation: {errors}')
        return result
    except Exception:
        (out / 'failure.txt').write_text(traceback.format_exc())
        raise
    finally:
        for name, pair in reversed(list(processes.items())):
            try: stop(pair)
            except Exception:
                with (out / 'cleanup-errors.txt').open('a') as f: f.write(traceback.format_exc())
        if not finished: print('FAILED_CELL', str(out), flush=True)

def main():
    assert os.environ.get('STUDY_CONTEXT') == 'homelab'
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['pilot','pilot-backend','confirm'], required=True)
    p.add_argument('--label', required=True)
    a = p.parse_args()
    base = WORK / 'revision' / a.label
    base.mkdir(parents=True, exist_ok=False)
    shutil.copytree(HERE, base / 'executed-source', ignore=shutil.ignore_patterns('__pycache__'))
    dump(base / 'environment.json', {'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
          'python':sys.version, 'clock_ticks':os.sysconf('SC_CLK_TCK'), 'page_size':os.sysconf('SC_PAGE_SIZE'), 'cpuinfo':Path('/proc/cpuinfo').read_text().split('\n\n')[0],
          'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text(), 'memory_max':Path('/sys/fs/cgroup/memory.max').read_text(),
          'pip_freeze':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True),
          'binary_sha256': {name:hashlib.sha256((WORK/name).read_bytes()).hexdigest()
                            for name in ['otelcol-contrib','jaeger-1.76.0-linux-amd64/jaeger-all-in-one']}})
    plan = []
    seeds = [40002] if a.mode=='pilot-backend' else [40001] if a.mode=='pilot' else SEEDS
    for seed in seeds:
        combos = [(app, regime) for app in ['checkout','documents'] for regime in ['steady','bursty']]
        if a.mode=='pilot-backend': combos=[(app,'bursty') for app in ['checkout','documents']]
        random.Random(f'blocks:{seed}').shuffle(combos)
        for app, regime in combos:
            policies = ['full','tail'] if a.mode=='pilot-backend' else ['full','head','tail']
            random.Random(f'policies:{seed}:{app}:{regime}').shuffle(policies)
            for policy in policies: plan.append([app,regime,seed,policy])
    dump(base / 'plan.json', plan)
    for app, regime, seed, policy in plan:
        cell(base, app, regime, seed, policy, duration=10 if a.mode!='confirm' else DURATION,
             warmup=2 if a.mode!='confirm' else WARMUP)
    print('STUDY_COMPLETE', a.label, flush=True)

if __name__ == '__main__': main()
