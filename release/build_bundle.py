#!/usr/bin/env python3
"""Package a verified full tree reproducibly; never overwrite a release directory."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from verify import ROOT, inventory, sha, verify

VERSION = '1.8.0'
NAME = f'trace-sampling-strategies-v{VERSION}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'releases' / f'v{VERSION}')
    args = parser.parse_args()
    verify()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    archive = output / f'{NAME}.tar.gz'
    with archive.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=1) as gz:
            with tarfile.open(fileobj=gz, mode='w|', format=tarfile.PAX_FORMAT) as tar:
                for name in sorted([*inventory(), 'SHA256SUMS']):
                    path = ROOT / name
                    item = tarfile.TarInfo(f'{NAME}/{name}')
                    item.size = path.stat().st_size
                    item.mtime = 1790553600
                    item.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                    with path.open('rb') as stream:
                        tar.addfile(item, stream)
    combined = {'name': archive.name, 'bytes': archive.stat().st_size, 'sha256': sha(archive)}
    parts = []
    if archive.stat().st_size >= 2 * 1024**3:
        remaining = archive.stat().st_size
        with archive.open('rb') as stream:
            while remaining:
                part = output / f'{archive.name}.part-{len(parts) + 1:03d}'
                length = min(1024**3, remaining)
                with part.open('wb') as target:
                    pending = length
                    while pending:
                        chunk = stream.read(min(8 * 1024**2, pending))
                        if not chunk:
                            raise EOFError('Unexpected end of archive')
                        target.write(chunk)
                        pending -= len(chunk)
                remaining -= length
                parts.append(part)
    else:
        parts.append(archive)
    shutil.copy2(ROOT / 'output/pdf/trace-sampling-collector-boundary.pdf', output / f'{NAME}.pdf')
    metadata = {'schema_version': 1, 'version': VERSION, 'package_root': NAME,
                'archive': combined, 'archive_parts': [p.name for p in parts],
                'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
                          for p in [*parts, output / f'{NAME}.pdf']},
                'paper_peer_reviewed': False, 'doi': None,
                'raw_evidence_files': 9242,
                'scope': 'Named paper, research sources, derived results, all raw evidence. Private review materials and third-party literature caches are excluded.'}
    (output / 'package-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
