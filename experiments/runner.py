#!/usr/bin/env python3
"""Stdlib-only controlled OTLP replay. Execute experiments on homelab only."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import http.client
import io
import json
import math
import os
from pathlib import Path
import platform
import random
import signal
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request

VERSION = '0.136.0'
ROOT = Path(os.environ.get('STUDY_WORK', '/work'))
SEEDS = [1101, 1102, 1103, 1104, 1105]
N = 20000
RATE = 2000
WAIT = 2
BASE_NS = 1790200000000000000
KINDS = ['normal', 'error', 'latency', 'semantic']

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def boot():
    assert os.environ.get('STUDY_CONTEXT') == 'homelab', 'requires explicit homelab environment'
    ROOT.mkdir(parents=True, exist_ok=True)
    base = f'https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v{VERSION}/'
    archive = f'otelcol-contrib_{VERSION}_linux_amd64.tar.gz'
    sums = (ROOT / 'release-checksums.txt').read_bytes() if (ROOT / 'release-checksums.txt').exists() else urllib.request.urlopen(base + 'opentelemetry-collector-releases_otelcol-contrib_checksums.txt', timeout=90).read()
    (ROOT / 'published-checksums.txt').write_bytes(sums)
    expected = next(line.split()[0] for line in sums.decode().splitlines() if line.split()[-1] == archive)
    if not (ROOT / archive).exists():
        with urllib.request.urlopen(base + archive, timeout=180) as response:
            (ROOT / archive).write_bytes(response.read())
    data = (ROOT / archive).read_bytes()
    assert digest(data) == expected, 'release checksum mismatch'
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        member = next(m for m in tar.getmembers() if m.name.split('/')[-1] == 'otelcol-contrib')
        binary = tar.extractfile(member).read()
        (ROOT / 'otelcol-contrib').write_bytes(binary)
        (ROOT / 'otelcol-contrib').chmod(0o755)
    dump(ROOT / 'environment.json', {
        'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'python': sys.version, 'platform': platform.platform(),
        'collector_version': subprocess.check_output([str(ROOT / 'otelcol-contrib'), '--version'], text=True).strip(),
        'archive_url': base + archive, 'archive_sha256': digest(data), 'binary_sha256': digest(binary),
        'cpuinfo': Path('/proc/cpuinfo').read_text().split('\n\n')[0],
        'cgroup_cpu_max': read_optional('/sys/fs/cgroup/cpu.max'),
        'cgroup_memory_max': read_optional('/sys/fs/cgroup/memory.max'),
        'clock_ticks': os.sysconf('SC_CLK_TCK'),
        'runner_sha256': digest(Path(__file__).read_bytes()),
    })
    print('BOOTSTRAPPED', VERSION, expected, flush=True)

def read_optional(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None

def attr(key, value):
    kind = 'boolValue' if isinstance(value, bool) else 'intValue' if isinstance(value, int) else 'stringValue'
    return {'key': key, 'value': {kind: str(value) if kind == 'intValue' else value}}

def make_corpus(seed, n=N):
    rng = random.Random(seed)
    assignments = []
    for kind in KINDS[1:]:
        j = 0
        for m, count in [(1, 20), (5, 20), (20, 4)]:
            for _ in range(count):
                assignments.extend((kind, f'{kind}-{j}', m) for _ in range(m))
                j += 1
    assignments += [('normal', None, 0)] * (n - len(assignments))
    rng.shuffle(assignments)
    corpus, truth = [], {}
    for index, (kind, incident, m) in enumerate(assignments):
        trace_id = f'{rng.getrandbits(128):032x}'
        assert trace_id not in truth and int(trace_id, 16) != 0
        count = 7 if kind == 'error' else 6 if kind == 'latency' else 5
        span_ids = [f'{rng.getrandbits(64):016x}' for _ in range(count)]
        start = BASE_NS + index * 500000
        durations = [500, 490, 420, 400, 3, 20] if kind == 'latency' else [50, 45, 20, 12, 3, 5, 5]
        services = ['gateway', 'api', 'db-client', 'database', 'validator', 'cache', 'retry']
        parents = [None, 0, 1, 2, 1, 1, 1]
        resources = []
        for s in range(count):
            attrs = [attr('http.route', '/checkout'), attr('service.operation', services[s])]
            if s == 3:
                attrs += [attr('db.system', 'postgresql')]
                if kind == 'error':
                    attrs += [attr('db.sqlstate', '08006'), attr('exception.type', 'ConnectionFailure'), attr('exception.stacktrace', 'database connection failed; ' * 20)]
                if kind == 'latency':
                    attrs += [attr('db.wait_reason', 'lock')]
            if s == 4:
                attrs += [attr('validation.expected', 100), attr('validation.actual', 99 if kind == 'semantic' else 100)]
            span = {'traceId': trace_id, 'spanId': span_ids[s], 'name': services[s], 'kind': 2,
                    'startTimeUnixNano': str(start + (0 if s == 0 else 1000000)),
                    'endTimeUnixNano': str(start + (0 if s == 0 else 1000000) + durations[s] * 1000000),
                    'attributes': attrs, 'status': {'code': 2 if kind == 'error' and s in (0, 3) else 1}}
            if parents[s] is not None:
                span['parentSpanId'] = span_ids[parents[s]]
            resources.append({'resource': {'attributes': [attr('service.name', services[s])]},
                              'scopeSpans': [{'scope': {'name': 'controlled-trace-replay', 'version': '1.0'}, 'spans': [span]}]})
        corpus.append((trace_id, resources))
        truth[trace_id] = {'kind': kind, 'incident': incident, 'm': m, 'span_ids': span_ids}
    return corpus, truth

def policy_list():
    treatments = [('full', 1.0)]
    treatments += [('head', p) for p in [.001, .01, .025, .05, .10, .25, .50]]
    treatments += [('tail', p) for p in [.02, .025, .05, .10, .25, .50]]
    return treatments

def head_keep(tid, p):
    return int.from_bytes(hashlib.blake2b(('head:' + tid).encode(), digest_size=8).digest(), 'big') < math.floor(p * 2**64)

def config(out, strategy, p, capacity=50000, wait=WAIT, cache=False):
    background = max(0, (p - .02) / .98)
    policies = [
        {'name': 'error', 'type': 'status_code', 'status_code': {'status_codes': ['ERROR']}},
        {'name': 'latency', 'type': 'latency', 'latency': {'threshold_ms': 250}},
    ]
    if background > 0:
        policies.append({'name': 'background', 'type': 'probabilistic', 'probabilistic': {'sampling_percentage': background * 100, 'hash_salt': 'trace-study-v1'}})
    cfg = {
        'receivers': {'otlp': {'protocols': {'http': {'endpoint': '127.0.0.1:4318'}}}},
        'processors': {'batch': {'timeout': '100ms', 'send_batch_size': 512, 'send_batch_max_size': 1024}},
        'exporters': {'file': {'path': str(out / 'traces.jsonl'), 'format': 'json', 'flush_interval': '100ms'}},
        'service': {'telemetry': {'logs': {'level': 'warn'}, 'metrics': {'level': 'detailed', 'readers': [
            {'pull': {'exporter': {'prometheus': {'host': '127.0.0.1', 'port': 8888}}}}
        ]}}, 'pipelines': {'traces': {'receivers': ['otlp'], 'processors': ['batch'], 'exporters': ['file']}}}
    }
    if strategy == 'tail':
        cfg['processors']['tail_sampling'] = {'decision_wait': f'{wait}s', 'num_traces': capacity,
                                             'expected_new_traces_per_sec': RATE, 'policies': policies}
        if cache:
            cfg['processors']['tail_sampling']['decision_cache'] = {'sampled_cache_size': 100000, 'non_sampled_cache_size': 100000}
        cfg['service']['pipelines']['traces']['processors'].insert(0, 'tail_sampling')
    return cfg

def get_metrics():
    return urllib.request.urlopen('http://127.0.0.1:8888/metrics', timeout=2).read().decode()

def proc_sample(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().split()
    return {'time': time.monotonic(), 'cpu_s': (int(fields[13]) + int(fields[14])) / os.sysconf('SC_CLK_TCK'),
            'rss_bytes': int(fields[23]) * os.sysconf('SC_PAGE_SIZE')}

def launch(out, cfg):
    dump(out / 'config.json', cfg)
    logfile = (out / 'collector.log').open('wb')
    proc = subprocess.Popen([str(ROOT / 'otelcol-contrib'), '--config', str(out / 'config.json')], stdout=logfile, stderr=subprocess.STDOUT, env={**os.environ, 'GOMAXPROCS': '2'})
    for _ in range(200):
        if proc.poll() is not None:
            raise RuntimeError((out / 'collector.log').read_text())
        try:
            get_metrics()
            return proc, logfile
        except Exception:
            time.sleep(.05)
    proc.terminate()
    raise RuntimeError('collector readiness timeout')

def pack(resources):
    return json.dumps({'resourceSpans': resources}, separators=(',', ':')).encode()

def post(connection, payload):
    connection.request('POST', '/v1/traces', body=payload, headers={'Content-Type': 'application/json'})
    response = connection.getresponse()
    body = response.read()
    if response.status != 200:
        raise RuntimeError(f'OTLP {response.status}: {body[:500]!r}')
    if body:
        result = json.loads(body)
        partial = result.get('partialSuccess', {})
        if int(partial.get('rejectedSpans', 0)) or partial.get('errorMessage'):
            raise RuntimeError(f'OTLP partial response: {result}')

def exported(path):
    records = defaultdict(dict)
    duplicates = 0
    if not path.exists():
        return records, duplicates
    for line in path.read_text().splitlines():
        for rs in json.loads(line).get('resourceSpans', []):
            for ss in rs.get('scopeSpans', []):
                for span in ss.get('spans', []):
                    tid, sid = span['traceId'].lower(), span['spanId'].lower()
                    duplicates += sid in records[tid]
                    records[tid][sid] = span
    return records, duplicates

def diagnostic(spans, kind):
    byname = {s['name']: s for s in spans.values()}
    if not all(name in byname for name in ['gateway', 'api', 'db-client', 'database', 'validator']):
        return False
    for child, parent in [('api', 'gateway'), ('db-client', 'api'), ('database', 'db-client'), ('validator', 'api')]:
        if byname[child].get('parentSpanId') != byname[parent]['spanId']:
            return False
    attrs = {a['key']: next(iter(a['value'].values())) for a in byname['database'].get('attributes', [])}
    if kind == 'error':
        return attrs.get('db.sqlstate') == '08006' and byname['database']['status'].get('code') in (2, 'STATUS_CODE_ERROR')
    if kind == 'latency':
        s = byname['database']
        return attrs.get('db.wait_reason') == 'lock' and int(s['endTimeUnixNano']) - int(s['startTimeUnixNano']) >= 250000000
    attrs = {a['key']: next(iter(a['value'].values())) for a in byname['validator'].get('attributes', [])}
    return kind == 'semantic' and attrs.get('validation.actual') != attrs.get('validation.expected')

def evaluate(out, truth, strategy, p, admitted):
    rec, duplicates = exported(out / 'traces.jsonl')
    unknown = set(rec) - set(truth)
    complete = {t for t, spans in rec.items() if set(spans) == set(truth[t]['span_ids'])} if not unknown else set()
    witnesses = {t for t in complete if truth[t]['kind'] != 'normal' and diagnostic(rec[t], truth[t]['kind'])}
    by_kind = Counter(truth[t]['kind'] for t in rec if t in truth)
    incidents = defaultdict(list)
    for tid, item in truth.items():
        if item['incident']:
            incidents[item['incident']].append(tid)
    outcomes = []
    for incident, tids in incidents.items():
        item = truth[tids[0]]
        kept = sum(t in witnesses for t in tids)
        outcomes.append({'incident': incident, 'kind': item['kind'], 'm': len(tids), 'witnesses': kept})
    dump(out / 'incidents.json', outcomes)
    dump(out / 'retained.json', {tid: sorted(spans) for tid, spans in rec.items()})
    errors = []
    if unknown: errors.append('unknown trace IDs')
    if duplicates: errors.append('duplicate span IDs')
    if len(complete) != len(rec): errors.append('incomplete traces')
    if strategy in ('full', 'head') and set(rec) != set(admitted): errors.append('head/full ingress/export mismatch')
    if strategy == 'tail' and any(t not in complete for t, item in truth.items() if item['kind'] in ('error', 'latency')):
        errors.append('protected tail trace loss')
    if len(witnesses) != sum(by_kind[k] for k in KINDS[1:]): errors.append('retained faulty trace failed diagnostic predicate')
    raw = (out / 'traces.jsonl').read_bytes() if (out / 'traces.jsonl').exists() else b''
    compressed = gzip.compress(raw, compresslevel=6, mtime=0)
    (out / 'traces.jsonl.gz').write_bytes(compressed)
    (out / 'traces.jsonl').unlink(missing_ok=True)
    return {'retained_traces': len(rec), 'retained_spans': sum(len(s) for s in rec.values()),
            'complete_traces': len(complete), 'diagnostic_witnesses': len(witnesses),
            'retained_by_kind': dict(by_kind), 'duplicates': duplicates, 'export_json_bytes': len(raw),
            'archive_gzip_bytes': len(compressed), 'export_json_sha256': digest(raw),
            'export_gzip_sha256': digest(compressed), 'validation_errors': errors, 'valid': not errors}

def run_cell(base, seed, strategy, p, corpus, truth, position):
    label = f'{strategy}-{p:.4f}'
    out = base / f'seed-{seed}' / label
    if out.exists():
        raise RuntimeError(f'refusing to overwrite {out}')
    out.mkdir(parents=True)
    batches, admitted = [], []
    for i in range(0, len(corpus), 100):
        chunk = [(t, rs) for t, rs in corpus[i:i+100] if strategy != 'head' or head_keep(t, p)]
        admitted += [t for t, rs in chunk]
        batches.append(pack([r for t, rs in chunk for r in rs]) if chunk else None)
    cfg = config(out, strategy, p)
    proc, logfile = launch(out, cfg)
    time.sleep(.5)
    (out / 'metrics-before.txt').write_text(get_metrics())
    samples = []
    stop = threading.Event()
    def monitor():
        while not stop.is_set():
            try: samples.append(proc_sample(proc.pid))
            except (OSError, ValueError): break
            stop.wait(.05)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    conn = http.client.HTTPConnection('127.0.0.1', 4318, timeout=30)
    start = proc_sample(proc.pid)
    started = time.monotonic()
    max_lag = 0.0
    sent_bytes = requests = 0
    try:
        for i, payload in enumerate(batches):
            due = started + i * 100 / RATE
            pause = due - time.monotonic()
            if pause > 0: time.sleep(pause)
            max_lag = max(max_lag, time.monotonic() - due)
            if payload:
                post(conn, payload)
                sent_bytes += len(payload)
                requests += 1
        ingress_s = time.monotonic() - started
        time.sleep(WAIT + 2)
        finish = proc_sample(proc.pid)
        (out / 'metrics-after.txt').write_text(get_metrics())
    finally:
        conn.close()
        stop.set()
        thread.join()
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=30)
        logfile.close()
    assert proc.returncode == 0, f'collector exit {proc.returncode}'
    dump(out / 'process-samples.json', samples)
    result = {'seed': seed, 'strategy': strategy, 'p': p, 'order': position,
              'background_p': (p-.02)/.98 if strategy == 'tail' else None,
              'offered_traces': len(corpus), 'offered_spans': sum(len(rs) for t, rs in corpus),
              'admitted_traces': len(admitted), 'admitted_spans': sum(len(truth[t]['span_ids']) for t in admitted),
              'ingress_payload_bytes': sent_bytes, 'http_requests': requests, 'ingress_s': ingress_s,
              'max_schedule_lag_s': max_lag, 'collector_cpu_s': finish['cpu_s'] - start['cpu_s'],
              'measurement_s': finish['time'] - start['time'],
              'peak_rss_bytes': max(s['rss_bytes'] for s in samples),
              'start_rss_bytes': start['rss_bytes'], 'end_rss_bytes': finish['rss_bytes'],
              'measurement_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    result.update(evaluate(out, truth, strategy, p, admitted))
    counters = {}
    for line in (out / 'metrics-after.txt').read_text().splitlines():
        if line.startswith('#') or not line.strip(): continue
        key = line.split('{',1)[0].split()[0]
        if any(word in key for word in ('accepted_spans', 'refused_spans', 'sent_spans', 'send_failed_spans', 'dropped_too_early')):
            counters[key] = counters.get(key, 0) + float(line.split()[-1])
    result['collector_counters'] = counters
    checks = [('otelcol_receiver_accepted_spans_total', result['admitted_spans']),
              ('otelcol_exporter_sent_spans_total', result['retained_spans']),
              ('otelcol_receiver_refused_spans_total', 0), ('otelcol_exporter_send_failed_spans_total', 0)]
    for key, expected in checks:
        if counters.get(key) != expected:
            result['validation_errors'].append(f'{key}: {counters.get(key)} != {expected}')
    if any(value != 0 for key, value in counters.items() if 'dropped_too_early' in key):
        result['validation_errors'].append('tail buffer early drops')
    result['valid'] = not result['validation_errors']
    dump(out / 'result.json', result)
    print(json.dumps({'cell': str(out), **result}), flush=True)
    if not result['valid']:
        raise RuntimeError(f'invalid confirmatory cell: {result["validation_errors"]}')
    return result

def main(pilot=False):
    assert os.environ.get('STUDY_CONTEXT') == 'homelab'
    base = ROOT / ('pilot' if pilot else 'main')
    base.mkdir(exist_ok=True)
    results = []
    for seed in ([999] if pilot else SEEDS):
        corpus, truth = make_corpus(seed)
        dump(base / f'truth-{seed}.json', truth)
        schedule = [('full', 1.0), ('head', .10), ('tail', .10)] if pilot else policy_list()
        random.Random(seed + 90000).shuffle(schedule)
        dump(base / f'order-{seed}.json', schedule)
        for position, (strategy, p) in enumerate(schedule):
            results.append(run_cell(base, seed, strategy, p, corpus, truth, position))
    dump(base / 'summary.json', results)
    print('PILOT_COMPLETE' if pilot else 'MAIN_COMPLETE', len(results), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['bootstrap', 'pilot', 'main'])
    args = parser.parse_args()
    {'bootstrap': boot, 'pilot': lambda: main(True), 'main': main}[args.mode]()
