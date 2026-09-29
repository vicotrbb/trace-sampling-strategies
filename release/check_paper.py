#!/usr/bin/env python3
"""Check the unchanged named paper, its source ZIP, and measurement inputs."""
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys
import zipfile
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_fourth_revision import active_sources, table
from prepare_mathematical_appendix import expected_appendix
from verify_fifth_contract import summaries


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text())


def main():
    sources = active_sources()
    source = '\n'.join(sources.values())
    reader = PdfReader(ROOT / 'output/pdf/trace-sampling-collector-boundary.pdf')
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    assert len(reader.pages) == 22
    assert reader.metadata.author == 'Victor Bona'
    assert reader.metadata.title == 'Trace Sampling at the Collector Boundary: Costs and Diagnostic Evidence'
    assert 'Mathematical supplement' in reader.pages[-2].extract_text()
    assert not re.search('\u2014|---|textemdash', source)
    assert chr(0x2014) not in text
    assert sources['mathematical-supplement.tex'] == expected_appendix()
    citations = {key for group in re.findall(r'\\cite\w*\{([^}]+)\}', source) for key in group.split(',')}
    bibliography = set(re.findall(r'(?m)^@\w+\{([^,]+),', (ROOT / 'paper/references.bib').read_text()))
    assert citations == bibliography and len(citations) == 32
    labels = re.findall(r'\\label\{([^}]+)\}', source)
    refs = set(re.findall(r'\\(?:ref|eqref)\{([^}]+)\}', source))
    assert len(labels) == len(set(labels)) and refs <= set(labels)
    assert sum(x.startswith('fig:') for x in labels) == 3
    assert sum(x.startswith('tab:') for x in labels) == 6
    receipt = read('release/preprint-source-checks.json')
    assert sha(ROOT / receipt['source_zip']) == receipt['source_zip_sha256']
    with zipfile.ZipFile(ROOT / receipt['source_zip']) as archive:
        assert set(archive.namelist()) == set(receipt['source_files_sha256'])
        for name, digest in receipt['source_files_sha256'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest, name
            assert sha(ROOT / receipt['source_paths'][name]) == digest, name
    placement = read('data/derived/fifth-audit-20260928/placement-summary.json')
    batching = read('data/derived/fifth-audit-20260928/batching-summary.json')
    assert placement['cells'] == 40 and batching['cells'] == 20
    count = 0
    for name, data in [('placement-confirm-v1', placement), ('batching-confirm-v2', batching)]:
        count += summaries(ROOT / 'data/raw/fifth-audit-20260928' / name, data)
    macros = dict(re.findall(r'\\newcommand\{\\([^}]+)\}\{([^}]+)\}', sources['fifth-measurements.tex']))
    for export, prefix in [('file', 'File'), ('dual', 'Dual')]:
        for policy, short in [('gate10', 'Gate'), ('collector10', 'Uniform'), ('tail10', 'Tail')]:
            value = placement['contrasts'][f'{export}:{policy}-minus-full']['collector_cpu_saving_percent']['mean']
            assert macros[f'Placement{prefix}{short}Saving'] == f'{value:.1f}'
    value = placement['contrasts']['file:collector10-minus-full']['collector_cpu_saving_percent']['mean']
    assert macros['PlacementFileUniformIncrease'] == f'{-value:.1f}'
    assert macros['HighBatchRate'] == f"{batching['rate_traces_s'] * 5:,}"
    for timeout, label in [(100, 'Short'), (1000, 'Long')]:
        c = batching['contrasts'][f'{timeout}:tail100-minus-full']['collector_cpu_s']
        assert macros[f'HighBatch{label}Difference'] == f"{c['mean']:+.2f}"
        assert macros[f'HighBatch{label}Interval'] == f"[{c['lower']:+.2f}, {c['upper']:+.2f}]"
    grouped = {}
    for row in table('matched-probe-summary-rows.tex'):
        choices = [([x] if x != 'Either' else levels) for x, levels in
                   zip(row[:4], [['Yes', 'No'], ['Immediate', 'Late'], ['On', 'Off'], ['Yes', 'No']])]
        for key in itertools.product(*choices):
            assert key not in grouped
            grouped[key] = row[4:]
    assert len(grouped) == 16
    for row in table('matched-probe-rows.tex'):
        assert grouped[tuple(row[:4])] == row[4:7]
    print(json.dumps({'status': 'PASS', 'pages': 22, 'citations': 32, 'figures': 3, 'tables': 6,
                      'preprint_source_zip_files': 33, 'paired_summary_intervals_recomputed': count,
                      'active_source_and_pdf_em_dashes': 0, 'measurements_modified': False}, indent=2))


if __name__ == '__main__':
    main()
