#!/usr/bin/env python3
"""Render a task-focused view of retained evidence without changing analysis."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'paper'
OUT = ROOT / 'data/derived/fourth-audit-20260928'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = json.loads((ROOT / 'data/derived/third-audit-20260925/diagnosis-summary.json').read_text())
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'pdf.fonttype': 42})
    fig, axes = plt.subplots(2, 3, figsize=(7.1, 4.5), sharex=True, layout='constrained')
    plotted = {}
    for j, w in enumerate([20, 50, 200]):
        accuracy, evidence = axes[:, j]
        baseline = 100 * d['baselines'][str(w)]['correct'] / 600
        accuracy.axhline(baseline, color='#666666', ls=':', lw=1, label='Full corpus')
        recorded = {'full_corpus_accuracy_percent': baseline, 'policies': {}}
        for policy, color, marker in [('head', '#2166ac', 'o'), ('tail', '#b35806', 's')]:
            rows = sorted((r for r in d['results'] if r['window'] == w and r['policy'] == policy and r['feasible']), key=lambda r: r['budget'])
            xs = [100 * r['budget'] for r in rows]
            ys = [100 * r['correct'] / r['n'] for r in rows]
            accuracy.plot(xs, ys, color=color, marker=marker, ms=3, lw=1.4, label=policy.capitalize())
            record = {'retention_percent': xs, 'accuracy_percent': ys}
            if policy == 'head':
                expected = [w * r['budget'] for r in rows]
                evidence.plot(xs, expected, color='#555555', ls=':', lw=1.5, label='Uniform expectation')
                record['expected_retained_each_window'] = expected
            else:
                for phase, color, marker in [('reference', '#b35806', 's'), ('incident', '#238b45', '^')]:
                    counts = [r[f'mean_{phase}_retained'] for r in rows]
                    evidence.plot(xs, counts, color=color, marker=marker, ms=3, lw=1.4, label=f'Tail {phase}')
                    record[f'mean_{phase}_retained'] = counts
            recorded['policies'][policy] = record
        accuracy.set(title=f'{w} requests per window', ylim=(0, 102), yticks=[0, 25, 50, 75, 100])
        evidence.set(ylim=(0, w * 1.04), xlabel='Expected retention (%)', xlim=(0, 100), xticks=[5, 20, 50, 80, 95])
        if j:
            accuracy.tick_params(labelleft=False)
        for ax in [accuracy, evidence]:
            ax.grid(axis='y', alpha=.2)
        plotted[str(w)] = recorded
    axes[0, 0].set_ylabel('Correct localization (%)')
    axes[1, 0].set_ylabel('Mean retained requests')
    axes[0, 0].legend(frameon=False, fontsize=7, loc='lower right')
    axes[1, 0].legend(frameon=False, fontsize=6.5, loc='upper left')
    fig.savefig(PAPER / 'figures/window-evidence.pdf')
    plt.close(fig)
    (OUT / 'window-figure-data.json').write_text(json.dumps(plotted, indent=2) + '\n')

    # Group the unchanged sixteen factor rows only after checking every outcome.
    rows = [[v.strip() for v in line.removesuffix('\\\\').split('&')]
            for line in (PAPER / 'matched-probe-rows.tex').read_text().splitlines()]
    assert len(rows) == 16 and len({tuple(r[:4]) for r in rows}) == 16
    for row in rows:
        marker, leaf, cache, churn = row[:4]
        expected = ['200', '1400', '200', '200'] if marker == 'Yes' or leaf == 'Immediate' else (
            ['200', '200', '0', '0'] if cache == 'Off' and churn == 'Yes' else ['0'] * 4)
        assert row[4:] == expected
    compact = [
        'Yes & Either & Either & Either & 200 & 1400 & 200',
        'No & Immediate & Either & Either & 200 & 1400 & 200',
        'No & Late & Off & No & 0 & 0 & 0',
        'No & Late & On & Either & 0 & 0 & 0',
        'No & Late & Off & Yes & 200 & 200 & 0',
    ]
    (PAPER / 'matched-probe-summary-rows.tex').write_text('\n'.join(s + ' \\\\' for s in compact) + '\n')
    print(json.dumps({'status': 'PASS', 'window_sizes': 3, 'plotted_feasible_configurations': 42,
                      'delivery_factor_combinations': len(rows), 'grouped_delivery_rows': len(compact)}))


if __name__ == '__main__':
    main()
