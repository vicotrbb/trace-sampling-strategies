#!/usr/bin/env python3
"""Plot every primary contrast and every block from the frozen cost analysis."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
summary = json.loads((ROOT / 'data/derived/final-cost-20260925/cost-summary.json').read_text())
plt.rcParams.update({'font.family': 'serif', 'mathtext.fontset': 'cm', 'font.size': 10,
                     'axes.labelsize': 10, 'figure.dpi': 150, 'savefig.bbox': 'tight',
                     'pdf.fonttype': 42, 'axes.spines.top': False, 'axes.spines.right': False})
fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.1), sharey=True, sharex=True)
labels = ['JSON, retain all tail', 'JSON, 10% tail', 'Dual, retain all tail', 'Dual, 10% tail']
offsets = [(i - 3.5) * .035 for i in range(8)]
for ax, timeout in zip(axes, (100, 1000)):
    for index, (export, sampler) in enumerate((('file', 'tail100'), ('file', 'tail10'), ('dual', 'tail100'), ('dual', 'tail10'))):
        result = summary['contrasts'][f'{export}-{timeout}-{sampler}-minus-bypass']
        assert result['n'] == 8
        color = '#164c74' if sampler == 'tail100' else '#ad4f19'
        ax.scatter(result['values'], [index + offset for offset in offsets], s=15,
                   color=color, alpha=.55, linewidths=0, zorder=3)
        ax.errorbar(result['mean'], index, xerr=[[result['mean'] - result['lower']], [result['upper'] - result['mean']]],
                    fmt='D', mfc='white', mec='black', ecolor='black', markersize=4,
                    capsize=3, elinewidth=1, zorder=4)
    ax.axvline(0, color='.4', linestyle=':', linewidth=1)
    ax.set_title(f'Batch timeout {timeout:,} ms')
    ax.set_xlabel('Tail minus bypass CPU (seconds)')
    ax.grid(axis='x', alpha=.15)
    ax.set_yticks(range(4), labels)
axes[0].invert_yaxis()
fig.tight_layout()
fig.savefig(ROOT / 'paper/figures/controlled-cost-contrasts.pdf')

# Format every prespecified interaction from the unchanged numerical analysis.
rows = []
def interaction_row(kind, condition, sampler, key):
    value = summary['contrasts'][key]
    rows.append(f"{kind} & {condition} & {sampler} & "
                f"{value['mean']:+.3f} [{value['lower']:+.3f}, {value['upper']:+.3f}]" + r' \\')
for timeout in (100, 1000):
    for sampler in ('tail100', 'tail10'):
        interaction_row('Added Jaeger', f'{timeout} ms', sampler,
                        f'dual-minus-file-{timeout}-{sampler}-contrast')
for export, label in (('file', 'JSON'), ('dual', 'JSON + Jaeger')):
    for sampler in ('tail100', 'tail10'):
        interaction_row('Longer timeout', label, sampler,
                        f'1000-minus-100-{export}-{sampler}-contrast')
for sampler in ('tail100', 'tail10'):
    interaction_row('Three-factor', 'Both changes', sampler, f'three-factor-{sampler}')
assert len(rows) == 10
(ROOT / 'paper/cost-interaction-rows.tex').write_text('\n'.join(rows) + '\n')
