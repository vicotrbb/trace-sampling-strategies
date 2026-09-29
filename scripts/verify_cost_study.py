#!/usr/bin/env python3
"""Reconstruct cost-study evidence without importing the experiment harness."""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'data/raw/revision-20260924/confirm-v1/checkout-steady/seed-41001/full'


def read(path):
    content = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return json.loads(content)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def unpack(data):
    records = {}
    for line in data.splitlines():
        for resource in json.loads(line).get('resourceSpans', []):
            for scope in resource.get('scopeSpans', []):
                for span in scope.get('spans', []):
                    key = (span['traceId'], span['spanId'])
                    assert key not in records, ('duplicate', key)
                    records[key] = (span, {k: v for k, v in resource.items() if k != 'scopeSpans'},
                                    {k: v for k, v in scope.items() if k != 'spans'})
    return records


def policy_ids(records, sampler):
    groups = {}
    for (tid, _), (span, _, _) in records.items():
        groups.setdefault(tid, []).append(span)
    threshold = int(Fraction.from_float((100 * .08 / .98) / 100) * (2**64 - 1))
    retained = set()
    for tid, spans in groups.items():
        code_error = any(s.get('status', {}).get('code') in (2, 'STATUS_CODE_ERROR') for s in spans)
        duration = max(int(s['endTimeUnixNano']) for s in spans) - min(int(s['startTimeUnixNano']) for s in spans)
        hashed = 14695981039346656037
        for octet in b'trace-study-v1' + bytes.fromhex(tid):
            hashed = (1099511628211 * (hashed ^ octet)) & 0xffffffffffffffff
        assert abs(hashed - threshold) > 2
        if sampler in ('bypass', 'tail100') or code_error or duration >= 250000000 or hashed <= threshold:
            retained.add(tid)
    return retained


def metric_values(path):
    values = Counter()
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})?\s+([^ ]+)', line)
        assert match, line
        name, raw_labels, number = match.groups()
        labels = tuple(sorted(re.findall(r'(\w+)="((?:[^"\\]|\\.)*)"', raw_labels or '')))
        key = (name, labels)
        assert key not in values
        values[key] = float(number)
    return values


def total(values, name, exporter=None):
    return sum(value for (metric, labels), value in values.items() if metric == name
               and (exporter is None or dict(labels).get('exporter') == exporter))


def process_value(item, ticks, page_size):
    fields = item['raw_stat'].rsplit(') ', 1)[1].split()
    cpu = (int(fields[11]) + int(fields[12])) / ticks
    assert item['cpu_s'] == cpu
    assert item['rss_bytes'] == int(fields[21]) * page_size
    assert item['start_ticks'] == int(fields[19])
    assert item['pid'] == int(item['raw_stat'].split(' ', 1)[0])
    return cpu


def validate_backend(data, records):
    assert not data.get('errors')
    traces = data.get('data') or []
    assert len(traces) == len({tid for tid, _ in records})
    observed = set()
    for trace in traces:
        tid = trace['traceID']
        for exported in trace['spans']:
            key = (tid, exported['spanID'])
            assert key in records and key not in observed
            observed.add(key)
            original, resource, scope = records[key]
            assert exported['traceID'] == tid and exported['operationName'] == original['name']
            expected_parent = original.get('parentSpanId')
            assert exported.get('references', []) == ([{'refType': 'CHILD_OF', 'traceID': tid, 'spanID': expected_parent}] if expected_parent else [])
            attrs = {a['key']: next(iter(a['value'].values())) for a in original.get('attributes', [])}
            tags = {a['key']: a['value'] for a in exported['tags']}
            assert all(str(tags[k]) == str(value) for k, value in attrs.items())
            if original.get('status', {}).get('code') in (2, 'STATUS_CODE_ERROR'):
                assert tags['error'] is True
            service = next(a['value']['stringValue'] for a in resource['resource']['attributes'] if a['key'] == 'service.name')
            assert trace['processes'][exported['processID']]['serviceName'] == service
            assert abs(exported['startTime'] - int(original['startTimeUnixNano']) // 1000) <= 1
            assert abs(exported['duration'] - (int(original['endTimeUnixNano']) - int(original['startTimeUnixNano'])) / 1000) <= 2
    assert observed == set(records)


def validate(base):
    pilot = base.name.startswith('pilot')
    expected_blocks = [50001] if pilot else list(range(51001, 51009))
    original = unpack(gzip.decompress((ORIGINAL / 'traces.jsonl.gz').read_bytes()))
    corpus_manifest = read(base / 'corpus/manifest.json')
    for filename, expected_sha in corpus_manifest['source_sha256'].items():
        assert digest((ORIGINAL / filename).read_bytes()) == expected_sha
    translated = {}
    corpus = {}
    for phase, filename in [('warmup', 'warmup.json'), ('measured', 'truth.json')]:
        data = gzip.decompress((base / 'corpus' / (phase + '.jsonl.gz')).read_bytes())
        meta = corpus_manifest['phases'][phase]
        corpus[phase] = data.splitlines()
        assert digest(data) == meta['serialized_sha256'] and len(data) == meta['bytes']
        assert len(corpus[phase]) == meta['batches']
        assert list(map(digest, corpus[phase])) == meta['batch_sha256']
        ledger = read(ORIGINAL / filename)
        assert meta['trace_ids'] == [r['trace_id'] for r in ledger]
        decoded = unpack(data)
        assert len(decoded) == meta['spans'] == 5 * meta['traces']
        assert {tid for tid, _ in decoded} == set(meta['trace_ids'])
        for i, payload in enumerate(corpus[phase]):
            assert {tid for tid, _ in unpack(payload)} == set(meta['trace_ids'][10*i:10*i+10])
        assert not set(translated).intersection(decoded)
        translated.update(decoded)
    assert set(original) == set(translated)
    for key, (span, resource, scope) in translated.items():
        old_span, old_resource, old_scope = original[key]
        assert resource == old_resource and scope == old_scope
        corrected = dict(span)
        for name in ('startTimeUnixNano', 'endTimeUnixNano'):
            corrected[name] = str(int(corrected[name]) - corpus_manifest['timestamp_translation_ns'])
        assert corrected == old_span
    assert corpus_manifest['min_ns'] == min(int(s['startTimeUnixNano']) for s, _, _ in translated.values())
    assert corpus_manifest['max_ns'] == max(int(s['endTimeUnixNano']) for s, _, _ in translated.values())
    plan = read(base / 'plan.json')
    expected_plan = []
    for block in expected_blocks:
        order = list(itertools.product(['file', 'dual'], [100, 1000], ['bypass', 'tail100', 'tail10']))
        random.Random(f'final-cost-factorial-v1:{block}').shuffle(order)
        expected_plan.extend([[block, *row] for row in order])
    assert plan == expected_plan
    assert read(base / 'complete.json')['complete'] is True
    assert read(base / 'complete.json')['cells'] == len(plan)
    environment = read(base / 'environment.json')
    ticks, page_size = environment['clock_ticks'], environment['page_size']
    assert ticks > 0 and page_size > 0
    assert environment['cpu_max'].strip() == '400000 100000'
    assert int(environment['memory_max']) == 4 * 1024**3
    actual = set()
    counts = Counter()
    throttled = 0
    max_snapshot_span = 0
    max_lag = 0
    for path in sorted(base.glob('block-*/*/result.json')):
        cell = path.parent
        row = read(path)
        key = tuple(row[k] for k in ('block', 'export', 'timeout_ms', 'sampler'))
        assert key not in actual
        actual.add(key)
        assert row['valid'] is True
        design = read(cell / 'design.json')
        assert all(row[k] == value for k, value in design.items())
        assert design['corpus_manifest_sha256'] == digest((base / 'corpus/manifest.json').read_bytes())
        for filename, expected_sha in design['source_sha256'].items():
            assert digest((base / 'executed-source' / filename).read_bytes()) == expected_sha
        assert row['warmup_s'] == (4 if pilot else 10) and row['duration_s'] == (10 if pilot else 60)
        assert row['drain_s'] == 5 and row['offered_rate'] == 50
        cfg = read(cell / 'config.json')
        assert cfg['processors']['batch'] == {'timeout': f"{row['timeout_ms']}ms", 'send_batch_size': 256, 'send_batch_max_size': 512}
        assert cfg['exporters']['file']['format'] == 'json' and cfg['exporters']['file']['flush_interval'] == '100ms'
        wanted_exporters = ['file'] if row['export'] == 'file' else ['file', 'otlphttp']
        pipeline = cfg['service']['pipelines']['traces']
        assert set(cfg['exporters']) == set(wanted_exporters) and pipeline['exporters'] == wanted_exporters
        if row['export'] == 'dual':
            assert cfg['exporters']['otlphttp'] == {'endpoint': 'http://127.0.0.1:14318', 'encoding': 'proto', 'compression': 'gzip', 'timeout': '5s', 'retry_on_failure': {'enabled': False}, 'sending_queue': {'enabled': False}}
        if row['sampler'] == 'bypass':
            assert pipeline['processors'] == ['batch'] and set(cfg['processors']) == {'batch'}
        else:
            assert pipeline['processors'] == ['tail_sampling', 'batch']
            tail = cfg['processors']['tail_sampling']
            assert tail['sample_on_first_match'] is False and tail['decision_wait'] == '2s'
            assert tail['num_traces'] == 512 and tail['expected_new_traces_per_sec'] == 50
            assert tail['decision_cache'] == {'sampled_cache_size': 10000, 'non_sampled_cache_size': 10000}
            assert tail['policies'] == [
                {'name': 'error', 'type': 'status_code', 'status_code': {'status_codes': ['ERROR']}},
                {'name': 'latency', 'type': 'latency', 'latency': {'threshold_ms': 250}},
                {'name': 'background', 'type': 'probabilistic', 'probabilistic': {'sampling_percentage': 100 if row['sampler'] == 'tail100' else 100*.08/.98, 'hash_salt': 'trace-study-v1'}}]
        selected = {}
        phases = {}
        for phase, duration in [('warmup', row['warmup_s']), ('measured', row['duration_s'])]:
            payloads = corpus[phase][:duration * 5]
            input_records = unpack(b'\n'.join(payloads))
            ids = policy_ids(input_records, row['sampler'])
            phases[phase] = {k: v for k, v in input_records.items() if k[0] in ids}
            selected.update(phases[phase])
            receipts = read(cell / (phase + '-receipts.json'))
            assert len(receipts) == len(payloads)
            for i, receipt in enumerate(receipts):
                assert receipt['index'] == i and receipt['payload_sha256'] == digest(payloads[i])
                assert receipt['offset_s'] == i / 5 and receipt['status'] == 200
                assert receipt['lag_s'] >= 0 and receipt['elapsed_s'] >= 0
                assert math.isclose(receipt['lag_s'], receipt['started_s'] - i/5, abs_tol=1e-9)
                assert receipt['started_s'] + receipt['elapsed_s'] <= duration, 'send extended beyond planned schedule'
                partial = json.loads(receipt['body']).get('partialSuccess', {})
                assert not int(partial.get('rejectedSpans', 0)) and not partial.get('errorMessage')
            max_lag = max(max_lag, max(r['lag_s'] for r in receipts))
        raw = gzip.decompress((cell / 'traces.jsonl.gz').read_bytes())
        assert unpack(raw) == selected
        assert digest(raw) == row['export_json_sha256'] and len(raw) == row['export_json_bytes_all']
        assert row['export_traces_all'] == len(selected) // 5
        assert row['export_traces_measured'] == len(phases['measured']) // 5
        assert row['export_spans_measured'] == len(phases['measured'])
        warm_bytes = sum(len(line) + 1 for line in raw.splitlines() if {tid for tid, _ in unpack(line)} <= {tid for tid, _ in phases['warmup']})
        assert row['export_json_bytes_measured'] == len(raw) - warm_bytes
        before, after = metric_values(cell / 'metrics-before.txt'), metric_values(cell / 'metrics-after.txt')
        delta = {k: after[k] - before[k] for k in set(before) | set(after)}
        assert total(before, 'otelcol_receiver_accepted_spans_total') == row['warmup_s'] * 250
        assert total(delta, 'otelcol_receiver_accepted_spans_total') == row['duration_s'] * 250
        for exporter in wanted_exporters:
            assert total(before, 'otelcol_exporter_sent_spans_total', exporter) == len(phases['warmup'])
            assert total(delta, 'otelcol_exporter_sent_spans_total', exporter) == len(phases['measured'])
        assert all(value == 0 for (name, _), value in after.items() if any(s in name for s in ('refused_spans', 'send_failed_spans', 'dropped_too_early')))
        for field, metric in [('batch_count', 'batch_send_size_count'), ('batch_spans', 'batch_send_size_sum'),
                              ('batch_timeout_sends', 'timeout_trigger_send_total'), ('batch_size_sends', 'batch_size_trigger_send_total')]:
            assert row[field] == total(delta, 'otelcol_processor_batch_' + metric)
        assert row['batch_spans'] == len(phases['measured'])
        assert row['batch_count'] == row['batch_timeout_sends'] + row['batch_size_sends']
        endpoints = read(cell / 'resource-endpoints.json')
        samples = read(cell / 'resource-samples.json')
        assert len(samples) >= row['duration_s'] and not any('error' in s for s in samples)
        for snapshot in [endpoints['before'], endpoints['after'], *samples]:
            span = snapshot['end_monotonic'] - snapshot['begin_monotonic']
            assert span >= 0
            max_snapshot_span = max(max_snapshot_span, span)
            for item in snapshot['processes'].values():
                process_value(item, ticks, page_size)
                assert snapshot['begin_monotonic'] <= item['read_monotonic'] <= snapshot['end_monotonic']
        for component in ('collector', 'jaeger'):
            a, b = [endpoints[p]['processes'][component] for p in ('before', 'after')]
            assert a['pid'] == b['pid'] and a['start_ticks'] == b['start_ticks']
            assert b['read_monotonic'] - a['read_monotonic'] >= row['duration_s'] + row['drain_s']
            assert math.isclose(row['cpu_s'][component], b['cpu_s'] - a['cpu_s'], abs_tol=1e-12)
        for phase in ('before', 'after'):
            process_value(endpoints['controller_' + phase], ticks, page_size)
        cg = [dict(line.split() for line in endpoints[p]['runner_cgroup_cpu'].splitlines()) for p in ('before', 'after')]
        throttled += int(cg[1]['nr_throttled']) - int(cg[0]['nr_throttled'])
        measured_receipts = read(cell / 'measured-receipts.json')
        assert row['max_schedule_lag_s'] == max(r['lag_s'] for r in measured_receipts)
        validate_backend(read(cell / 'backend.json.gz'), selected if row['export'] == 'dual' else {})
        counts['cells'] += 1
        counts['measured_trace_occurrences'] += row['duration_s'] * 50
        counts['exported_spans_all'] += len(selected)
        counts['backend_spans_all'] += len(selected) if row['export'] == 'dual' else 0
    assert actual == set(map(tuple, plan))
    assert not list(base.rglob('failure.txt'))
    return {'status': 'PASS', **counts, 'unique_input_traces': 3500, 'clock_ticks': ticks,
            'throttled_periods': throttled, 'max_snapshot_span_s': max_snapshot_span, 'max_schedule_lag_s': max_lag,
            'fixed_content_and_input_order_verified': True, 'native_selection_recomputed': True,
            'exact_cpu_endpoints_recomputed': True, 'backend_content_verified': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('raw', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    result = validate(args.raw)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
