#!/usr/bin/env python3
"""Prespecified summaries of the fixed-input, eight-block cost intervention."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean, stdev
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]


def interval(values):
    n = len(values)
    center = mean(values)
    half = float(t.ppf(.975, n - 1)) * stdev(values) / n**.5
    return {'n': n, 'values': values, 'mean': center, 'lower': center - half, 'upper': center + half}


def cell_summary(rows):
    return {name: interval([getter(row) for row in rows]) for name, getter in {
        'collector_cpu_s': lambda r: r['cpu_s']['collector'],
        'jaeger_cpu_s': lambda r: r['cpu_s']['jaeger'],
        'batch_count': lambda r: r['batch_count'],
        'mean_batch_spans': lambda r: r['batch_spans'] / r['batch_count'],
        'json_measured_bytes': lambda r: r['export_json_bytes_measured'],
        'max_schedule_lag_s': lambda r: r['max_schedule_lag_s'],
    }.items()}


def analyze(raw, output):
    paths = sorted(raw.glob('block-*/*/result.json'))
    rows = [json.loads(path.read_text()) for path in paths]
    assert len(rows) == 96 and all(row['valid'] for row in rows)
    indexed = {(r['block'], r['export'], r['timeout_ms'], r['sampler']): r for r in rows}
    assert len(indexed) == 96
    blocks = list(range(51001, 51009))
    groups, contrasts = {}, {}
    cpu = lambda block, export, timeout, sampler: indexed[block, export, timeout, sampler]['cpu_s']['collector']
    for export in ('file', 'dual'):
        for timeout in (100, 1000):
            for sampler in ('bypass', 'tail100', 'tail10'):
                groups[f'{export}-{timeout}-{sampler}'] = cell_summary([indexed[b, export, timeout, sampler] for b in blocks])
            for sampler in ('tail100', 'tail10'):
                contrasts[f'{export}-{timeout}-{sampler}-minus-bypass'] = interval([
                    cpu(b, export, timeout, sampler) - cpu(b, export, timeout, 'bypass') for b in blocks])
    for timeout in (100, 1000):
        for sampler in ('tail100', 'tail10'):
            contrasts[f'dual-minus-file-{timeout}-{sampler}-contrast'] = interval([
                (cpu(b, 'dual', timeout, sampler) - cpu(b, 'dual', timeout, 'bypass')) -
                (cpu(b, 'file', timeout, sampler) - cpu(b, 'file', timeout, 'bypass')) for b in blocks])
    for export in ('file', 'dual'):
        for sampler in ('tail100', 'tail10'):
            contrasts[f'1000-minus-100-{export}-{sampler}-contrast'] = interval([
                (cpu(b, export, 1000, sampler) - cpu(b, export, 1000, 'bypass')) -
                (cpu(b, export, 100, sampler) - cpu(b, export, 100, 'bypass')) for b in blocks])
    for sampler in ('tail100', 'tail10'):
        contrasts[f'three-factor-{sampler}'] = interval([
            ((cpu(b, 'dual', 1000, sampler) - cpu(b, 'dual', 1000, 'bypass')) -
             (cpu(b, 'file', 1000, sampler) - cpu(b, 'file', 1000, 'bypass'))) -
            ((cpu(b, 'dual', 100, sampler) - cpu(b, 'dual', 100, 'bypass')) -
             (cpu(b, 'file', 100, sampler) - cpu(b, 'file', 100, 'bypass'))) for b in blocks])
    output.mkdir(parents=True, exist_ok=True)
    summary = {'cells': len(rows), 'blocks': blocks, 'groups': groups, 'contrasts': contrasts,
        'conditional_corpus': True, 'confidence_intervals': 'Pointwise model-based Student t, df=7; no multiplicity-adjusted decisions',
        'retained_measured': {sampler: sorted({r['export_traces_measured'] for r in rows if r['sampler'] == sampler}) for sampler in ('bypass', 'tail100', 'tail10')},
        'max_schedule_lag_s': max(r['max_schedule_lag_s'] for r in rows)}
    (output / 'cost-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    with (output / 'cost-cells.csv').open('w', newline='') as stream:
        fields = ['block', 'export', 'timeout_ms', 'sampler', 'collector_cpu_s', 'jaeger_cpu_s', 'batch_count', 'mean_batch_spans', 'export_traces_measured', 'export_json_bytes_measured', 'max_schedule_lag_s']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({**{key: row[key] for key in fields if key in row},
                'collector_cpu_s': row['cpu_s']['collector'], 'jaeger_cpu_s': row['cpu_s']['jaeger'],
                'mean_batch_spans': row['batch_spans'] / row['batch_count']})
    def fmt(item):
        return f"{item['mean']:+.3f} [{item['lower']:+.3f}, {item['upper']:+.3f}]"
    table = []
    batches = []
    for export in ('file', 'dual'):
        name = 'JSON' if export == 'file' else 'JSON + Jaeger'
        for timeout in (100, 1000):
            base = groups[f'{export}-{timeout}-bypass']['collector_cpu_s']['mean']
            table.append(f'{name} & {timeout} & {base:.3f} & ' + ' & '.join(
                fmt(contrasts[f'{export}-{timeout}-{s}-minus-bypass']) for s in ('tail100', 'tail10')) + r' \\')
            for sampler in ('bypass', 'tail100', 'tail10'):
                group = groups[f'{export}-{timeout}-{sampler}']
                batches.append(f'{name} & {timeout} & {sampler} & ' + ' & '.join(f"{group[k]['mean']:.2f}" for k in ('collector_cpu_s', 'jaeger_cpu_s', 'batch_count', 'mean_batch_spans')) + r' \\')
    interactions = []
    for key, value in contrasts.items():
        if not key.endswith('-minus-bypass'):
            interactions.append(f"{key} & {fmt(value)}" + r' \\')
    (ROOT / 'paper/cost-contrast-rows.tex').write_text('\n'.join(table) + '\n')
    (ROOT / 'paper/cost-batch-rows.tex').write_text('\n'.join(batches) + '\n')
    (output / 'cost-interaction-rows.tex').write_text('\n'.join(interactions) + '\n')
    (ROOT / 'paper/cost-measurements.tex').write_text(
        f"\\newcommand{{\\CostCells}}{{{len(rows)}}}\n\\newcommand{{\\CostBlocks}}{{{len(blocks)}}}\n"
        f"\\newcommand{{\\CostTailRetained}}{{{summary['retained_measured']['tail10'][0]}}}\n"
        f"\\newcommand{{\\CostMaxLagMs}}{{{summary['max_schedule_lag_s']*1000:.2f}}}\n")
    print(json.dumps({'cells': len(rows), 'groups': len(groups), 'contrasts': len(contrasts), 'summary': str(output / 'cost-summary.json')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('raw', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/derived/final-cost-20260925')
    args = parser.parse_args()
    analyze(args.raw, args.output)
