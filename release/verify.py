#!/usr/bin/env python3
"""Check the released bytes and execution freezes without running workloads."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
FREEZES = [
    ('docs/revision-20260924/confirmatory-freeze.json', 'sha256'),
    ('docs/final-pass-20260925/execution-freeze.json', 'sha256'),
    ('docs/second-audit-20260925/execution-freeze.json', 'files'),
    ('docs/third-audit-20260925/execution-freeze.json', 'files'),
    ('docs/fifth-audit-20260928/execution-freeze.json', 'files'),
    ('docs/fifth-audit-20260928/batching-execution-freeze-v2.json', 'files'),
]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root=ROOT):
    entries = {}
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or str(p) != name or name in entries:
            raise ValueError(f'Invalid inventory path: {name}')
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError(f'Invalid digest for {name}')
        entries[name] = digest
    return entries


def verify(root=ROOT, source_only=False):
    entries = inventory(root)
    checked = skipped = raw = 0
    for name, expected in entries.items():
        is_raw = name.startswith('data/raw/')
        raw += is_raw
        if source_only and is_raw:
            skipped += 1
            continue
        path = root / name
        if path.is_symlink() or not path.is_file() or sha(path) != expected:
            raise ValueError(f'Missing or changed file: {name}')
        checked += 1
    provenance = json.loads((root / 'release/export-provenance.json').read_text())
    assert raw == provenance['preserved_raw_files'] == 9242
    for name, digest in provenance['preserved_original_sha256'].items():
        assert entries[name] == digest, name
    counts = []
    for filename, key in FREEZES:
        frozen = json.loads((root / filename).read_text())[key]
        for name, digest in frozen.items():
            assert entries[name] == digest, (filename, name)
        counts.append(len(frozen))
    assert counts == [12, 7, 10, 9, 21, 17], counts
    assert entries['output/pdf/trace-sampling-collector-boundary.pdf'] == '390ed5be9b794c28a76f223dc9af1071e82e5f7821b77b162b532478290d72bc'
    assert not any('abstract-icpe' in n or 'icpe-anonymous' in n or
                   n.startswith('docs/submission-preparation-') for n in entries)
    return {'status': 'PASS', 'files_checked': checked, 'raw_files_in_inventory': raw,
            'raw_files_skipped': skipped, 'frozen_source_file_counts': counts,
            'mode': 'source checkout only' if source_only else 'complete research archive'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-only', action='store_true', help='Explicitly skip release-only raw evidence.')
    args = parser.parse_args()
    print(json.dumps(verify(source_only=args.source_only), indent=2))
