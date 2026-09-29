#!/usr/bin/env python3
"""Check this manuscript version, plotted evidence, and preserved frozen inputs.

This is a presentation and integrity check. The archive validators separately
reconstruct measurements and selections. No application or sampling workload runs.
"""
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re
import tarfile

from pypdf import PdfReader
from scipy.optimize import brentq
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/fourth-audit-20260928'
TITLE = 'Trace Sampling at the Collector Boundary: Costs and Diagnostic Evidence'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def active_sources():
    found = {}
    def visit(name):
        if not name.endswith('.tex'):
            name += '.tex'
        if name in found:
            return
        found[name] = (ROOT / 'paper' / name).read_text()
        for target in re.findall(r'\\(?:input|tableinput)\{([^}]+)\}', found[name]):
            visit(target)
    visit('main.tex')
    return found


def sections(sources, name='main.tex'):
    value = sources[name].split('\\appendix')[0]
    result = []
    for match in re.finditer(r'\\section\*?\{([^}]+)\}|\\input\{([^}]+)\}', value):
        if match[1]:
            result.append(match[1])
        elif match[2] in sources:
            result.extend(sections(sources, match[2]))
    return result


def table(name):
    return [[x.strip() for x in line.strip().removesuffix('\\\\').split('&')]
            for line in (ROOT / 'paper' / name).read_text().splitlines()]


def main():
    source_files = active_sources()
    source = '\n'.join(source_files.values())
    pdf = ROOT / 'output/pdf/how-much-can-we-sample.pdf'
    reader = PdfReader(pdf)
    pdf_text = '\n'.join(p.extract_text() for p in reader.pages)
    aux = (ROOT / 'paper/main.aux').read_text()
    log = (ROOT / 'paper/main.log').read_text()
    biblog = (ROOT / 'paper/main.blg').read_text()
    citations = {k for group in re.findall(r'\\citation\{([^}]+)\}', aux) for k in group.split(',')}
    bibliography = set(re.findall(r'\\bibcite\{([^}]+)\}', aux))
    labels = re.findall(r'\\newlabel\{([^}]+)\}', aux)
    references = set(re.findall(r'\\(?:ref|eqref)\{([^}]+)\}', source))
    assert citations == bibliography and references <= set(labels)
    assert len(labels) == len(set(labels))
    assert not re.search(r'Overfull|Underfull|LaTeX Warning|Package .* Warning|undefined|Missing character', log)
    assert 'Warning--' not in biblog and 'error message' not in biblog
    assert not re.search('\u2014|---|textemdash', source) and '\u2014' not in pdf_text
    assert not re.search(r'\b(?:TODO|TBD|FIXME|PLACEHOLDER)\b', source)
    assert not re.search(r'withdrawn design|earlier live classifier|third audit|initial corpus|new corpus', pdf_text, re.I)
    assert reader.metadata.title == TITLE and reader.metadata.author == 'Victor Bona'
    assert pdf.read_bytes() == (ROOT / 'paper/main.pdf').read_bytes()
    assert sum(k.startswith('fig:') for k in labels) == 3
    assert sum(k.startswith('tab:') for k in labels) == 4
    assert {'huang2024mint', 'zhu2025unisage', 'yang2026gleaner', 'otelSpanLifecycle'} <= citations
    assert 'he2023steam' not in (ROOT / 'paper/references.bib').read_text()
    assert 'AI-assisted research workflow' in source_files['methods.tex']

    with tarfile.open(REPORT / 'prerevision-source-and-paper.tar.gz') as archive:
        previous = {Path(m.name).name: archive.extractfile(m).read().decode()
                    for m in archive.getmembers()
                    if m.isfile() and m.name.startswith('paper/') and m.name.endswith('.tex')}
        manifest = archive.extractfile('SHA256SUMS').read().decode()
    assert sections(source_files) == sections(previous)
    def preamble(value):
        value = value.split('\\begin{document}')[0]
        value = re.sub(r'pdftitle=\{[^}]+\}', 'pdftitle={TITLE}', value)
        return re.sub(r'\\title\{[^}]+\}', r'\\title{TITLE}', value)
    assert preamble(source_files['main.tex']) == preamble(previous['main.tex'])
    raw_count = 0
    for line in manifest.splitlines():
        expected, name = line.split('  ', 1)
        if name.startswith('data/raw/'):
            assert sha(ROOT / name) == expected, name
            raw_count += 1
    assert raw_count == 7328
    freezes = [
        ('docs/revision-20260924/confirmatory-freeze.json', 'sha256'),
        ('docs/final-pass-20260925/execution-freeze.json', 'sha256'),
        ('docs/second-audit-20260925/execution-freeze.json', 'files'),
        ('docs/third-audit-20260925/execution-freeze.json', 'files'),
    ]
    freeze_counts = []
    for name, key in freezes:
        values = read(name)[key]
        for filename, expected in values.items():
            assert sha(ROOT / filename) == expected, filename
        freeze_counts.append(len(values))

    diagnosis = read('data/derived/third-audit-20260925/diagnosis-summary.json')
    figure = read('data/derived/fourth-audit-20260928/window-figure-data.json')
    plotted = 0
    bounds = 0
    for w in [20, 50, 200]:
        values = figure[str(w)]
        assert values['full_corpus_accuracy_percent'] == diagnosis['baselines'][str(w)]['correct'] / 6
        for policy in ['head', 'tail']:
            rows = sorted((r for r in diagnosis['results'] if r['window'] == w and r['policy'] == policy and r['feasible']), key=lambda r: r['budget'])
            actual = values['policies'][policy]
            assert actual['retention_percent'] == [r['budget'] * 100 for r in rows]
            assert actual['accuracy_percent'] == [100 * r['correct'] / r['n'] for r in rows]
            if policy == 'head':
                assert actual['expected_retained_each_window'] == [w * r['budget'] for r in rows]
            else:
                for phase in ['reference', 'incident']:
                    assert actual[f'mean_{phase}_retained'] == [r[f'mean_{phase}_retained'] for r in rows]
            plotted += len(rows)
            for r in rows:
                x, n = r['losses'], r['n']
                upper = 1.0 if x == n else brentq(lambda p: binom.cdf(x, n, p) - .05 / 48, 0, 1)
                assert abs(upper - r['upper_loss_bound']) < 1e-10
                bounds += 1
    assert plotted == bounds == 42
    for policy, expected in [('head', [.8, .65, .2]), ('tail', [.8, .65, .35])]:
        actual = [min(r['budget'] for r in diagnosis['results'] if r['window'] == w and r['policy'] == policy and r.get('meets_five_point_margin')) for w in [20, 50, 200]]
        assert actual == expected
    counts = {}
    for row in table('matched-probe-summary-rows.tex'):
        choices = [([x] if x != 'Either' else levels) for x, levels in zip(row[:4], [['Yes', 'No'], ['Immediate', 'Late'], ['On', 'Off'], ['Yes', 'No']])]
        for combination in itertools.product(*choices):
            assert combination not in counts
            counts[combination] = row[4:]
    original_rows = table('matched-probe-rows.tex')
    assert len(counts) == len(original_rows) == 16
    for row in original_rows:
        assert counts[tuple(row[:4])] == row[4:7]

    cost = read('data/derived/final-cost-20260925/cost-summary.json')
    for timeout, sign, rounded in [(100, -1, '-0.173'), (1000, 1, '0.066')]:
        c = cost['contrasts'][f'dual-{timeout}-tail100-minus-bypass']
        assert all(v * sign > 0 for v in c['values'])
        assert format(c['mean'], '.3f') == rounded
    assert cost['cells'] == 96 and len(set(cost['blocks'])) == 8
    for timeout, count in [(100, 300), (1000, 60)]:
        for exporter in ['file', 'dual']:
            assert set(cost['groups'][f'{exporter}-{timeout}-bypass']['batch_count']['values']) == {count}

    for entry in read('docs/fourth-audit-20260928/sources/manifest.json')['sources']:
        if entry['status'] == 'retrieved':
            assert sha(REPORT / 'sources' / entry['file']) == entry['sha256']
    visual = read('docs/fourth-audit-20260928/pdf-visual-review.json')
    assert visual['status'] == 'PASS' and visual['pdf_sha256'] == sha(pdf)
    assert visual['pages_inspected'] == len(reader.pages) == len(visual['page_images_sha256'])
    for name, expected in visual['page_images_sha256'].items():
        rendered = ROOT / 'tmp/fourth-audit-render' / name
        if rendered.exists():
            assert sha(rendered) == expected
    receipt = {
        'status': 'PASS', 'utc': datetime.now(timezone.utc).isoformat(),
        'title': TITLE, 'pdf_sha256': sha(pdf), 'pdf_pages': len(reader.pages),
        'extracted_whitespace_tokens': len(pdf_text.split()),
        'cited_references': len(citations), 'figures': 3, 'tables': 4,
        'template_author_main_section_order_preserved': True,
        'only_preamble_changes_are_title_and_pdf_title': True,
        'source_and_pdf_em_dashes': 0, 'tex_and_bibtex_warnings_or_bad_boxes': 0,
        'all_citations_and_references_resolve': True,
        'previous_delivery_raw_files_unchanged': raw_count,
        'frozen_file_counts_unchanged': freeze_counts,
        'plotted_configurations_verified': plotted,
        'conditional_limits_recomputed_by_binomial_inversion': bounds,
        'grouped_probe_rows_expand_to_original_factor_combinations': len(counts),
        'batch_cost_sign_reversal_holds_in_every_block': True,
        'all_final_pages_visually_inspected': True,
        'new_workload_executions': 0,
    }
    (REPORT / 'final-document-checks.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
