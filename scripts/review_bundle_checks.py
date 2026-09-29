#!/usr/bin/env python3
"""Check the compact review package using only its packaged observations.

This reconstructs resource summaries and conditional replay precision. It does
not substitute for complete span-export, payload-hash, or runtime validation.
"""
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile

from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def near(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), (actual, expected)


def same(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            same(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            same(a, b)
    elif isinstance(expected, (float, int)):
        near(actual, expected)
    else:
        assert actual == expected, (actual, expected)


def interval(values, published):
    near(statistics.mean(values), published['mean'])
    radius = float(t.ppf(.975, len(values) - 1)) * statistics.stdev(values) / math.sqrt(len(values))
    near(published.get('lower', published.get('lo')), statistics.mean(values) - radius)
    near(published.get('upper', published.get('hi')), statistics.mean(values) + radius)
    same(values, published['values'])


def process_cpu(path, ticks):
    endpoints = read(path)
    values = {}
    for endpoint in ['before', 'after']:
        for name, record in endpoints[endpoint]['processes'].items():
            fields = record['raw_stat'].rsplit(') ', 1)[1].split()
            seconds = (int(fields[11]) + int(fields[12])) / ticks
            near(seconds, record['cpu_s'])
            values.setdefault(name, {})[endpoint] = seconds
    return {name: row['after'] - row['before'] for name, row in values.items()}


def main():
    manifest = (ROOT / 'SHA256SUMS').read_text().splitlines()
    for line in manifest:
        digest, name = line.split('  ', 1)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    ticks = read('data/cpu-clock-ticks.json')
    latest = ROOT / 'data/raw/fifth-audit-20260928'
    cpu_cells = 0
    for path in sorted(latest.glob('*-confirm-v*/block-*/*/result.json')):
        row = json.loads(path.read_text())
        cpu = process_cpu(path.parent / 'endpoints.json', ticks[row['kind']])
        for name, value in row['cpu_s'].items():
            near(cpu[name], value)
        near(cpu['collector'] + cpu.get('jaeger', 0), row['collector_jaeger_cpu_s'])
        cpu_cells += 1
    assert cpu_cells == 60
    with tempfile.TemporaryDirectory(prefix='sampling-review-') as temporary:
        subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_fifth_current.py'),
                        '--raw', str(latest), '--out', temporary], check=True)
        for kind in ['placement', 'batching']:
            same(json.loads((Path(temporary) / f'{kind}-summary.json').read_text()),
                 read(f'data/derived/fifth-audit-20260928/{kind}-summary.json'))

    low_rows = {}
    for path in sorted((ROOT / 'data/raw/final-cost-20260925/confirm-v1').glob('block-*/*/result.json')):
        row = json.loads(path.read_text())
        cpu = process_cpu(path.parent / 'resource-endpoints.json', ticks['low_load'])
        for name, value in row['cpu_s'].items():
            near(cpu[name], value)
        low_rows[row['block'], row['export'], row['timeout_ms'], row['sampler']] = row
    assert len(low_rows) == 96
    low = read('data/derived/final-cost-20260925/cost-summary.json')
    for export in ['file', 'dual']:
        for timeout in [100, 1000]:
            for policy in ['tail10', 'tail100']:
                values = [low_rows[b, export, timeout, policy]['cpu_s']['collector'] -
                          low_rows[b, export, timeout, 'bypass']['cpu_s']['collector']
                          for b in range(51001, 51009)]
                interval(values, low['contrasts'][f'{export}-{timeout}-{policy}-minus-bypass'])

    load_rows = defaultdict(list)
    for path in sorted((ROOT / 'data/raw/second-audit-20260925/load-confirm-v1').glob('block-*/*/result.json')):
        row = json.loads(path.read_text())
        near(process_cpu(path.parent / 'endpoints.json', ticks['load_sweep'])['collector'], row['cpu_s'])
        load_rows[row['rate'], row['policy']].append(row)
    assert sum(map(len, load_rows.values())) == 80
    load = read('data/derived/second-audit-20260925/load-summary.json')
    for (rate, policy), rows in load_rows.items():
        rows.sort(key=lambda r: r['block'])
        group = load['groups'][f'{rate}-{policy}']
        for key in ['cpu_s', 'json_bytes', 'max_rss_bytes', 'batches', 'max_lag_s']:
            interval([r[key] for r in rows], group[key])
        interval([r['cpu_s'] / (r['duration_s'] + r['drain_s']) for r in rows], group['core_equivalents'])
        interval([1e6 * r['cpu_s'] / (r['rate'] * r['duration_s'] * 5) for r in rows], group['cpu_us_per_offered_span'])
        if policy != 'full':
            baseline = {r['block']: r for r in load_rows[rate, 'full']}
            interval([r['cpu_s'] - baseline[r['block']]['cpu_s'] for r in rows], load['contrasts'][f'{rate}-{policy}']['cpu_difference_s'])
            interval([100 * (1 - r['cpu_s'] / baseline[r['block']]['cpu_s']) for r in rows], load['contrasts'][f'{rate}-{policy}']['cpu_saving_percent'])

    sdk = read('data/derived/revision/live-resources.json')
    sdk_cells = 0
    for app in ['checkout', 'documents']:
        for regime in ['steady', 'bursty']:
            observed = {}
            for policy in ['full', 'head']:
                observed[policy] = []
                for seed in range(41001, 41006):
                    path = f'data/raw/revision-20260924/confirm-v1/{app}-{regime}/seed-{seed}/{policy}/resource-endpoints.json'
                    cpu = process_cpu(path, ticks['sdk'])
                    observed[policy].append({'apps_cpu_s': cpu['gateway'] + cpu['worker'], 'collector_cpu_s': cpu['collector']})
                    sdk_cells += 1
            published = next(r for r in sdk if (r['app'], r['regime'], r['policy']) == (app, regime, 'head'))
            for key in ['apps_cpu_s', 'collector_cpu_s']:
                interval([1 - h[key] / f[key] for h, f in zip(observed['head'], observed['full'])], published[key])

    groups = defaultdict(list)
    replay_rows = 0
    with gzip.open(ROOT / 'data/raw/third-audit-20260925/diagnosis-replay-v1/trials.jsonl.gz', 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            replay_rows += 1
            if row['feasible']:
                groups[row['window'], row['policy'], row['budget']].append(row)
    assert replay_rows == 240000 and len(groups) == 42
    localization = read('data/derived/fifth-audit-20260928/localization-descriptive.json')
    for row in localization['results']:
        if not row['feasible']:
            continue
        observations = groups[row['window'], row['policy'], row['budget']]
        assert len(observations) == row['n'] == 5000
        correct = [int(r['correct']) for r in observations]
        losses = [int(r['full_correct']) - int(r['correct']) for r in observations]
        assert sum(correct) == row['correct'] and losses.count(1) == row['losses'] and losses.count(-1) == row['gains']
        for values, key in [(correct, 'accuracy'), (losses, 'paired_net_loss')]:
            near(statistics.mean(values), row[key])
            near(statistics.stdev(values) / math.sqrt(len(values)), row[key + '_mcse'])
        for phase in ['reference', 'incident']:
            near(statistics.mean(r['retained_' + phase] for r in observations), row['mean_' + phase + '_retained'])

    probes = defaultdict(list)
    for path in sorted((ROOT / 'data/raw/revision-20260924/matched-probes').glob('seed-*/*/result.json')):
        row = json.loads(path.read_text())
        probes[row['root_error'], row['late'], row['cache'], row['churn']].append(row)
    assert len(probes) == 16 and all(len(rows) == 3 for rows in probes.values())
    with (ROOT / 'data/derived/revision/matched-probes.csv').open() as stream:
        for row in csv.DictReader(stream):
            key = tuple(row[k] == 'True' for k in ['root_error', 'late', 'cache', 'churn'])
            for field in ['retained_error_ids', 'retained_spans', 'complete', 'witnesses']:
                assert min(r[field] for r in probes[key]) == int(row[field + '_min'])
                assert max(r[field] for r in probes[key]) == int(row[field + '_max'])
    result = {'status': 'PASS', 'checksummed_files': len(manifest), 'latest_cpu_cells': cpu_cells,
              'latest_group_and_contrast_summaries_reproduced': 2, 'low_load_cpu_cells': len(low_rows),
              'low_load_plotted_contrasts': 8, 'load_sweep_cpu_cells': 80, 'sdk_cpu_cells': sdk_cells,
              'replay_rows': replay_rows, 'conditional_mcse_recomputed': 84,
              'matched_probe_result_cells': 48,
              'scope': 'Packaged raw CPU endpoints, recorded results and replay outcomes. Full span-export and input-payload reconstruction are not included.'}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
