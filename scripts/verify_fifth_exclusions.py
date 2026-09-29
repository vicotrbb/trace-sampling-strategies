#!/usr/bin/env python3
"""Check recorded reasons for excluding the interrupted batching attempts."""
import json
from pathlib import Path
import verify_fifth_audit as v

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/fifth-audit-20260928'
REPORT = ROOT / 'docs/fifth-audit-20260928'


def saves(path):
    totals = {'ok': 0, 'err': 0}
    for line in path.read_text().splitlines():
        if line.startswith('jaeger_collector_spans_saved_by_svc_total{'):
            for result in totals:
                if f'result="{result}"' in line:
                    totals[result] += int(float(line.rsplit(' ', 1)[1]))
    return totals


def main():
    failed = RAW / 'batching-confirm-v1'
    cell = failed / 'block-83001/batching-dual-1000-tail100'
    d = v.read(cell / 'design.json')
    assert not d['pilot'] and d['rate_traces_s'] == 4000
    assert not (failed / 'complete.json').exists() and not (cell / 'result.json').exists()
    assert len(list(failed.glob('block-*/*/design.json'))) == 1
    count = 5 * d['rate_traces_s'] * (d['warmup_s'] + d['duration_s'])
    metrics = (cell / 'collector-metrics-after.txt').read_text()
    accepted = v.metric(metrics, 'otelcol_receiver_accepted_spans_total')
    assert accepted == count == 1400000
    for exporter in ['file', 'otlphttp']:
        assert v.metric(metrics, 'otelcol_exporter_sent_spans_total', exporter) == count
    saved = saves(cell / 'jaeger-metrics-after.txt')
    assert saved == {'ok': 1373900, 'err': 0}
    assert "('backend endpoint', 1373900.0, 1400000, 0.0)" in (cell / 'failure.txt').read_text()
    lag = max(r['lag_s'] for r in v.read(cell / 'measured-receipts.json'))
    assert lag < 0.5
    pilot = RAW / 'pilots-v3/batching-2000'
    capacity = v.read(pilot / 'capacity-failure.json')
    pcell = pilot / 'block-81100/batching-dual-1000-full'
    result = v.read(pcell / 'result.json')
    assert result['pilot'] and result['duration_s'] == 60 and result['rate_traces_s'] == 2000
    assert not (pilot / 'complete.json').exists()
    assert result['max_lag_s'] == capacity['max_lag_s'] > 0.5
    assert result['throttled_usec'] == 0
    assert saves(pcell / 'jaeger-metrics-after.txt') == {'ok': 700000, 'err': 0}
    assert v.read(RAW / 'pilots-v3/selection.json')['batching']['selected_rate_traces_s'] == 1000
    report = {
        'status': 'PASS',
        'failed_measured_attempt': {
            'offered_spans_s': 20000, 'collector_accepted_and_exported_spans': count,
            'jaeger_successful_saves_at_endpoint': saved['ok'], 'jaeger_save_errors': 0,
            'max_schedule_lag_s': lag, 'complete_paired_blocks': 0},
        'excluded_long_pilot': {
            'offered_spans_s': 10000, 'max_schedule_lag_s': result['max_lag_s'],
            'maximum_allowed_lag_s': 0.5, 'backend_completion_passed': True},
        'next_selected_offered_spans_s': 5000,
        'inference': 'Neither interrupted attempt is a complete campaign or enters a paired estimate.'}
    (REPORT / 'exclusion-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
