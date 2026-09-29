#!/usr/bin/env python3
"""Fixed-input factorial cost intervention. Workload execution requires homelab."""
import argparse
from collections import defaultdict
from fractions import Fraction
import gzip
import hashlib
import http.client
import itertools
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import signal
import subprocess
import threading
import time
import traceback
import urllib.parse
import urllib.request

WORK = Path('/work')
HERE = Path(__file__).resolve().parent
RATE = 50
DRAIN = 5
ENV = {**os.environ, 'GOMAXPROCS': '2'}
SALT = 'trace-study-v1'
PERCENT = 100 * .08 / .98


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def flattened(raw):
    records = defaultdict(dict)
    for line in raw.splitlines():
        for rs in json.loads(line)['resourceSpans']:
            for ss in rs['scopeSpans']:
                for span in ss['spans']:
                    tid, sid = span['traceId'], span['spanId']
                    assert sid not in records[tid], ('duplicate', tid, sid)
                    records[tid][sid] = {'span': span,
                        'resource': {k: v for k, v in rs.items() if k != 'scopeSpans'},
                        'scope': {k: v for k, v in ss.items() if k != 'spans'}}
    return dict(records)


def keep(tid, records, sampler):
    if sampler != 'tail10':
        return True
    spans = [entry['span'] for entry in records.values()]
    if any(s.get('status', {}).get('code') in (2, 'STATUS_CODE_ERROR') for s in spans):
        return True
    if max(int(s['endTimeUnixNano']) for s in spans) - min(int(s['startTimeUnixNano']) for s in spans) >= 250000000:
        return True
    value = 0xcbf29ce484222325
    for byte in SALT.encode() + bytes.fromhex(tid):
        value = ((value ^ byte) * 0x100000001b3) % (1 << 64)
    threshold = int(Fraction.from_float(PERCENT / 100) * ((1 << 64) - 1))
    assert abs(value - threshold) > 2
    return value <= threshold


def prepare(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    raw = gzip.decompress((source / 'traces.jsonl.gz').read_bytes())
    records = flattened(raw)
    ledger = {phase: json.loads((source / name).read_text())
              for phase, name in [('warmup', 'warmup.json'), ('measured', 'truth.json')]}
    assert [len(ledger[p]) for p in ('warmup', 'measured')] == [500, 3000]
    assert len(records) == 3500 and all(len(r) == 5 for r in records.values())
    minimum = min(int(e['span']['startTimeUnixNano']) for r in records.values() for e in r.values())
    # All cells reuse the same translation, complete trace content and serialized bytes.
    translation = time.time_ns() - 120_000_000_000 - minimum
    for record in records.values():
        for entry in record.values():
            for key in ('startTimeUnixNano', 'endTimeUnixNano'):
                entry['span'][key] = str(int(entry['span'][key]) + translation)
    manifest = {'timestamp_translation_ns': translation, 'source_sha256': {
        p.name: sha(p.read_bytes()) for p in source.iterdir() if p.is_file()}, 'phases': {}}
    for phase, rows in ledger.items():
        tids = [r['trace_id'] for r in rows]
        assert len(set(tids)) == len(tids) and set(tids) <= set(records)
        payloads = []
        for index in range(0, len(tids), 10):
            groups = {}
            for tid in tids[index:index + 10]:
                for entry in records[tid].values():
                    key = json.dumps([entry['resource'], entry['scope']], sort_keys=True)
                    if key not in groups:
                        groups[key] = {**entry['resource'], 'scopeSpans': [
                            {**entry['scope'], 'spans': []}]}
                    groups[key]['scopeSpans'][0]['spans'].append(entry['span'])
            payloads.append(json.dumps({'resourceSpans': list(groups.values())}, separators=(',', ':')).encode())
        data = b'\n'.join(payloads) + b'\n'
        (destination / (phase + '.jsonl.gz')).write_bytes(gzip.compress(data, mtime=0))
        manifest['phases'][phase] = {'trace_ids': tids, 'traces': len(tids), 'spans': 5 * len(tids),
            'serialized_sha256': sha(data), 'bytes': len(data), 'batches': len(payloads),
            'batch_sha256': list(map(sha, payloads))}
    manifest['min_ns'] = minimum + translation
    manifest['max_ns'] = max(int(e['span']['endTimeUnixNano']) for r in records.values() for e in r.values())
    dump(destination / 'manifest.json', manifest)


def start(out, name, command, environment=ENV):
    log = (out / (name + '.log')).open('wb')
    dump(out / (name + '-command.json'), {'command': command,
         'environment': {k: environment[k] for k in ('GOMAXPROCS', 'SPAN_STORAGE_TYPE', 'OTEL_TRACES_SAMPLER') if k in environment}})
    return subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=environment), log


def ready(pair, url):
    for _ in range(400):
        if pair[0].poll() is not None:
            raise RuntimeError('process exited: ' + str(pair[0].args))
        try:
            get(url)
            return
        except Exception:
            time.sleep(.05)
    raise RuntimeError('readiness timeout: ' + url)


def stop(pair):
    process, log = pair
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=35)
    log.close()
    assert process.returncode in (0, -signal.SIGTERM), (process.args, process.returncode)


def proc(pid):
    raw = Path(f'/proc/{pid}/stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    return {'pid': pid, 'read_monotonic': time.monotonic(), 'raw_stat': raw,
        'cpu_s': (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK'),
        'rss_bytes': int(fields[21]) * os.sysconf('SC_PAGE_SIZE'), 'start_ticks': int(fields[19])}


def snapshot(processes):
    result = {'begin_monotonic': time.monotonic(),
        'processes': {name: proc(pair[0].pid) for name, pair in processes.items()},
        'runner_cgroup_cpu': Path('/sys/fs/cgroup/cpu.stat').read_text()}
    result['end_monotonic'] = time.monotonic()
    return result


def metrics(text):
    values = {}
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        key, value = line.rsplit(' ', 1)
        # Prometheus names/labels are retained; no labels are silently collapsed.
        values[key] = float(value)
    return values


def summed(values, name, exporter=None):
    return sum(v for k, v in values.items() if k.split('{')[0] == name
               and (exporter is None or f'exporter="{exporter}"' in k))


def config(out, export, timeout, sampler):
    exporters = {'file': {'path': str(out / 'traces.jsonl'), 'format': 'json', 'flush_interval': '100ms'}}
    if export == 'dual':
        exporters['otlphttp'] = {'endpoint': 'http://127.0.0.1:14318', 'encoding': 'proto',
            'compression': 'gzip', 'timeout': '5s', 'retry_on_failure': {'enabled': False},
            'sending_queue': {'enabled': False}}
    processors = {'batch': {'timeout': f'{timeout}ms', 'send_batch_size': 256, 'send_batch_max_size': 512}}
    pipeline = ['batch']
    if sampler != 'bypass':
        processors['tail_sampling'] = {'decision_wait': '2s', 'num_traces': 512,
            'expected_new_traces_per_sec': RATE, 'sample_on_first_match': False,
            'decision_cache': {'sampled_cache_size': 10000, 'non_sampled_cache_size': 10000},
            'policies': [
                {'name': 'error', 'type': 'status_code', 'status_code': {'status_codes': ['ERROR']}},
                {'name': 'latency', 'type': 'latency', 'latency': {'threshold_ms': 250}},
                {'name': 'background', 'type': 'probabilistic', 'probabilistic': {
                    'sampling_percentage': 100 if sampler == 'tail100' else PERCENT, 'hash_salt': SALT}}]}
        pipeline.insert(0, 'tail_sampling')
    return {'receivers': {'otlp': {'protocols': {'http': {'endpoint': '127.0.0.1:4318'}}}},
        'processors': processors, 'exporters': exporters, 'service': {
            'telemetry': {'logs': {'level': 'warn'}, 'metrics': {'level': 'detailed', 'readers': [
                {'pull': {'exporter': {'prometheus': {'host': '127.0.0.1', 'port': 8888}}}}]}},
            'pipelines': {'traces': {'receivers': ['otlp'], 'processors': pipeline, 'exporters': list(exporters)}}}}


def schedule(payloads, duration):
    receipts = []
    connection = http.client.HTTPConnection('127.0.0.1', 4318, timeout=10)
    origin = time.monotonic()
    try:
        for index, payload in enumerate(payloads):
            offset = index / 5
            delay = origin + offset - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            started = time.monotonic()
            connection.request('POST', '/v1/traces', payload, {'Content-Type': 'application/json'})
            response = connection.getresponse()
            body = response.read()
            receipt = {'index': index, 'offset_s': offset, 'started_s': started - origin,
                'lag_s': started - origin - offset, 'elapsed_s': time.monotonic() - started,
                'status': response.status, 'body': body.decode(), 'payload_sha256': sha(payload)}
            receipts.append(receipt)
            assert response.status == 200, receipt
            partial = json.loads(body).get('partialSuccess', {})
            assert not int(partial.get('rejectedSpans', 0)) and not partial.get('errorMessage'), receipt
        rest = origin + duration - time.monotonic()
        if rest > 0:
            time.sleep(rest)
    finally:
        connection.close()
    return receipts


def verify_export(raw, expected):
    actual = flattened(raw)
    assert actual == expected, ('export differs from expected trace content', len(actual), len(expected))
    return actual


def verify_backend(data, records):
    assert not data.get('errors')
    traces = data.get('data') or []
    assert len(traces) == len(records) and {t['traceID'] for t in traces} == set(records)
    for trace in traces:
        tid = trace['traceID']
        assert len(trace['spans']) == len(records[tid])
        assert {s['spanID'] for s in trace['spans']} == set(records[tid])
        for span in trace['spans']:
            entry = records[tid][span['spanID']]
            original = entry['span']
            assert span['operationName'] == original['name']
            parent = original.get('parentSpanId')
            assert span.get('references', []) == ([{'refType': 'CHILD_OF', 'traceID': tid, 'spanID': parent}] if parent else [])
            service = next(a['value']['stringValue'] for a in entry['resource']['resource']['attributes'] if a['key'] == 'service.name')
            assert trace['processes'][span['processID']]['serviceName'] == service
            tags = {a['key']: a['value'] for a in span['tags']}
            for attr in original.get('attributes', []):
                assert str(tags[attr['key']]) == str(next(iter(attr['value'].values())))
            if original.get('status', {}).get('code') in (2, 'STATUS_CODE_ERROR'):
                assert tags.get('error') is True
            assert abs(span['startTime'] - int(original['startTimeUnixNano']) // 1000) <= 1
            assert abs(span['duration'] - (int(original['endTimeUnixNano']) - int(original['startTimeUnixNano'])) / 1000) <= 2


def cell(base, corpus, manifest, factor, pilot):
    block, export, timeout, sampler = factor
    out = base / f'block-{block}' / f'{export}-{timeout}-{sampler}'
    out.mkdir(parents=True, exist_ok=False)
    warmup, duration = (4, 10) if pilot else (10, 60)
    phase_data = {phase: corpus[phase][:seconds * 5] for phase, seconds in [('warmup', warmup), ('measured', duration)]}
    expected = {phase: {tid: value for tid, value in flattened(b'\n'.join(payloads)).items() if keep(tid, value, sampler)}
                for phase, payloads in phase_data.items()}
    design = {'block': block, 'export': export, 'timeout_ms': timeout, 'sampler': sampler,
        'warmup_s': warmup, 'duration_s': duration, 'drain_s': DRAIN, 'offered_rate': RATE,
        'corpus_manifest_sha256': sha((base / 'corpus/manifest.json').read_bytes()),
        'source_sha256': {p.name: sha(p.read_bytes()) for p in (base / 'executed-source').iterdir() if p.is_file()},
        'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    dump(out / 'design.json', design)
    processes = {}
    monitor = None
    event = threading.Event()
    success = False
    try:
        processes['jaeger'] = start(out, 'jaeger', [str(WORK / 'jaeger-1.76.0-linux-amd64/jaeger-all-in-one'),
            '--collector.otlp.enabled=true', '--collector.otlp.http.host-port=127.0.0.1:14318',
            '--collector.otlp.grpc.host-port=127.0.0.1:14317', '--badger.ephemeral=false',
            '--badger.directory-key=' + str(out / 'badger/keys'), '--badger.directory-value=' + str(out / 'badger/values'),
            '--badger.span-store-ttl=24h', '--log-level=warn'],
            {**ENV, 'SPAN_STORAGE_TYPE': 'badger', 'OTEL_TRACES_SAMPLER': 'always_off'})
        ready(processes['jaeger'], 'http://127.0.0.1:16686/api/services')
        dump(out / 'config.json', config(out, export, timeout, sampler))
        processes['collector'] = start(out, 'collector', [str(WORK / 'otelcol-contrib'), '--config', str(out / 'config.json')])
        ready(processes['collector'], 'http://127.0.0.1:8888/metrics')
        dump(out / 'warmup-receipts.json', schedule(phase_data['warmup'], warmup))
        time.sleep(DRAIN)
        warm_raw = (out / 'traces.jsonl').read_bytes()
        verify_export(warm_raw, expected['warmup'])
        before_metrics = get('http://127.0.0.1:8888/metrics').decode()
        (out / 'metrics-before.txt').write_text(before_metrics)
        samples = []
        def sample():
            while not event.is_set():
                try:
                    samples.append(snapshot(processes))
                except Exception as error:
                    samples.append({'error': repr(error)})
                event.wait(1)
        before = snapshot(processes)
        controller_before = proc(os.getpid())
        monitor = threading.Thread(target=sample)
        monitor.start()
        receipts = schedule(phase_data['measured'], duration)
        time.sleep(DRAIN)
        after = snapshot(processes)
        controller_after = proc(os.getpid())
        event.set()
        monitor.join()
        raw = (out / 'traces.jsonl').read_bytes()
        after_metrics = get('http://127.0.0.1:8888/metrics').decode()
        (out / 'metrics-after.txt').write_text(after_metrics)
        dump(out / 'resource-endpoints.json', {'before': before, 'after': after,
            'controller_before': controller_before, 'controller_after': controller_after})
        dump(out / 'resource-samples.json', samples)
        dump(out / 'measured-receipts.json', receipts)
        actual = verify_export(raw, {**expected['warmup'], **expected['measured']})
        a, b = metrics(before_metrics), metrics(after_metrics)
        delta = {key: b.get(key, 0) - a.get(key, 0) for key in set(a) | set(b)}
        assert summed(delta, 'otelcol_receiver_accepted_spans_total') == duration * RATE * 5
        exported = len(expected['measured']) * 5
        for target in (['file', 'otlphttp'] if export == 'dual' else ['file']):
            assert summed(delta, 'otelcol_exporter_sent_spans_total', target) == exported
        assert all(v == 0 for k, v in b.items() if any(s in k.split('{')[0] for s in ('refused_spans', 'send_failed_spans', 'dropped_too_early')))
        assert not any('error' in s for s in samples)
        stop(processes.pop('collector'))
        assert (out / 'traces.jsonl').read_bytes() == raw, 'late export after fixed endpoint'
        query = urllib.parse.urlencode({'service': 'checkout-gateway', 'start': manifest['min_ns'] // 1000,
            'end': manifest['max_ns'] // 1000 + 1000000, 'limit': 10000})
        query_start = time.monotonic()
        queried = get('http://127.0.0.1:16686/api/traces?' + query, timeout=60)
        query_seconds = time.monotonic() - query_start
        (out / 'backend.json.gz').write_bytes(gzip.compress(queried, mtime=0))
        verify_backend(json.loads(queried), actual if export == 'dual' else {})
        stop(processes.pop('jaeger'))
        result = {**design, 'valid': True, 'export_traces_all': len(actual), 'export_traces_measured': len(expected['measured']),
            'export_spans_measured': exported, 'export_json_bytes_all': len(raw), 'export_json_bytes_measured': len(raw) - len(warm_raw),
            'export_json_sha256': sha(raw), 'query_seconds': query_seconds,
            'cpu_s': {name: after['processes'][name]['cpu_s'] - before['processes'][name]['cpu_s'] for name in before['processes']},
            'max_schedule_lag_s': max(r['lag_s'] for r in receipts),
            'batch_count': summed(delta, 'otelcol_processor_batch_batch_send_size_count'),
            'batch_spans': summed(delta, 'otelcol_processor_batch_batch_send_size_sum'),
            'batch_timeout_sends': summed(delta, 'otelcol_processor_batch_timeout_trigger_send_total'),
            'batch_size_sends': summed(delta, 'otelcol_processor_batch_batch_size_trigger_send_total')}
        assert result['batch_spans'] == exported
        dump(out / 'result.json', result)
        (out / 'traces.jsonl.gz').write_bytes(gzip.compress(raw, mtime=0))
        (out / 'traces.jsonl').unlink()
        shutil.rmtree(out / 'badger')
        success = True
        print(json.dumps({k: result[k] for k in ('block', 'export', 'timeout_ms', 'sampler', 'valid', 'cpu_s', 'batch_count')}), flush=True)
    except BaseException:
        (out / 'failure.txt').write_text(traceback.format_exc())
        raise
    finally:
        event.set()
        if monitor is not None:
            monitor.join()
        for pair in list(processes.values()):
            try:
                stop(pair)
            except Exception:
                if success:
                    raise


def run(output, corpus_dir, pilot):
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(corpus_dir, output / 'corpus')
    (output / 'executed-source').mkdir()
    for path in HERE.iterdir():
        if path.is_file():
            shutil.copy2(path, output / 'executed-source' / path.name)
    manifest = json.loads((output / 'corpus/manifest.json').read_text())
    corpus = {phase: gzip.decompress((output / 'corpus' / (phase + '.jsonl.gz')).read_bytes()).splitlines()
              for phase in ('warmup', 'measured')}
    for phase in corpus:
        assert [sha(p) for p in corpus[phase]] == manifest['phases'][phase]['batch_sha256']
    blocks = [50001] if pilot else list(range(51001, 51009))
    plan = []
    for block in blocks:
        order = list(itertools.product(['file', 'dual'], [100, 1000], ['bypass', 'tail100', 'tail10']))
        random.Random(f'final-cost-factorial-v1:{block}').shuffle(order)
        plan.extend([[block, *row] for row in order])
    dump(output / 'plan.json', plan)
    dump(output / 'environment.json', {'python': platform.python_version(), 'platform': platform.platform(),
        'clock_ticks': os.sysconf('SC_CLK_TCK'), 'page_size': os.sysconf('SC_PAGE_SIZE'),
        'cpu_max': Path('/sys/fs/cgroup/cpu.max').read_text(),
        'memory_max': Path('/sys/fs/cgroup/memory.max').read_text(),
        'binaries_sha256': {p.name: sha(p.read_bytes()) for p in [WORK / 'otelcol-contrib', WORK / 'jaeger-1.76.0-linux-amd64/jaeger-all-in-one']}})
    for factor in plan:
        cell(output, corpus, manifest, factor, pilot)
    dump(output / 'complete.json', {'cells': len(plan), 'complete': True, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'pilot', 'confirm'])
    parser.add_argument('--input', type=Path, default=WORK / 'input')
    parser.add_argument('--corpus', type=Path, default=WORK / 'corpus')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if os.environ.get('STUDY_CONTEXT') != 'homelab' or not Path('/var/run/secrets/kubernetes.io/serviceaccount/namespace').exists():
        raise SystemExit('Execution is restricted to the authorized homelab study pod.')
    namespace = Path('/var/run/secrets/kubernetes.io/serviceaccount/namespace').read_text().strip()
    assert namespace == 'trace-sampling-final-20260925'
    if args.mode == 'prepare':
        prepare(args.input, args.corpus)
    else:
        assert args.output is not None
        run(args.output, args.corpus, args.mode == 'pilot')
