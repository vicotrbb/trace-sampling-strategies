#!/usr/bin/env python3
"""Exercise rejection of distinct corruptions using disposable pilot copies."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cost_validator', ROOT / 'scripts/verify_cost_study.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
PILOT = ROOT / 'data/raw/final-cost-20260925/pilot-v1'


def change(path, function):
    obj = json.loads(path.read_text())
    function(obj)
    path.write_text(json.dumps(obj))


def corrupt(base, case):
    cell = base / 'block-50001/dual-100-tail100'
    if case == 'missing_cell':
        (cell / 'result.json').unlink()
    elif case == 'source_substitution':
        path = base / 'executed-source/cost_study.py'
        path.write_text(path.read_text() + '\n# substituted source\n')
    elif case == 'cpu_summary_without_raw_ticks':
        change(cell / 'resource-endpoints.json', lambda d: d['after']['processes']['collector'].__setitem__('cpu_s', d['after']['processes']['collector']['cpu_s'] + .01))
    elif case == 'changed_policy':
        change(cell / 'config.json', lambda d: d['processors']['tail_sampling']['policies'][2]['probabilistic'].__setitem__('sampling_percentage', 90))
    elif case == 'trace_attribute_with_updated_hash':
        path = cell / 'traces.jsonl.gz'
        lines = gzip.decompress(path.read_bytes()).splitlines()
        first = json.loads(lines[0])
        first['resourceSpans'][0]['scopeSpans'][0]['spans'][0]['name'] = 'corrupted.operation'
        lines[0] = json.dumps(first, separators=(',', ':')).encode()
        raw = b'\n'.join(lines) + b'\n'
        path.write_bytes(gzip.compress(raw, mtime=0))
        change(cell / 'result.json', lambda d: d.update(export_json_sha256=hashlib.sha256(raw).hexdigest(), export_json_bytes_all=len(raw)))
    elif case == 'backend_parent':
        path = cell / 'backend.json.gz'
        obj = json.loads(gzip.decompress(path.read_bytes()))
        span = next(s for t in obj['data'] for s in t['spans'] if s.get('references'))
        span['references'][0]['spanID'] = 'ffffffffffffffff'
        path.write_bytes(gzip.compress(json.dumps(obj).encode(), mtime=0))
    elif case == 'accepted_counter':
        path = cell / 'metrics-after.txt'
        text = path.read_text()
        text, count = re.subn(r'(otelcol_receiver_accepted_spans_total\{[^\n]+\} )([0-9.]+)', lambda m: m[1] + str(float(m[2]) + 5), text)
        assert count == 1
        path.write_text(text)
    elif case == 'input_schedule_hash':
        change(cell / 'measured-receipts.json', lambda d: d[0].__setitem__('payload_sha256', '0' * 64))
    else:
        raise AssertionError(case)


def main():
    assert validator.validate(PILOT)['status'] == 'PASS'
    cases = ['missing_cell', 'source_substitution', 'cpu_summary_without_raw_ticks', 'changed_policy',
             'trace_attribute_with_updated_hash', 'backend_parent', 'accepted_counter', 'input_schedule_hash']
    results = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix='trace-cost-validator-') as temporary:
            copy = Path(temporary) / 'pilot-v1'
            shutil.copytree(PILOT, copy)
            corrupt(copy, case)
            try:
                validator.validate(copy)
            except (AssertionError, KeyError, FileNotFoundError) as error:
                results.append({'case': case, 'rejected': True, 'error_type': type(error).__name__})
            else:
                raise AssertionError('Corruption accepted: ' + case)
    print(json.dumps({'status': 'PASS', 'unaltered_pilot_passed': True, 'rejected_cases': results}, indent=2))


if __name__ == '__main__':
    main()
