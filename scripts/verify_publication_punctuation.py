#!/usr/bin/env python3
"""Scan unpacked artifact text and PDF text, preserving original archives."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from pypdf import PdfReader
from publication_receipts import write_receipt
from verify_fourth_revision import active_sources

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/final-publication-20260928/punctuation-checks.json'
TOP = {'data', 'docs', 'experiments', 'paper', 'proofs', 'scripts', 'tests', 'output'}
ARCHIVES = {'.gz', '.zip', '.tgz', '.xz', '.zst', '.bz2', '.tar'}
TEX_TEMP = {'.aux', '.log', '.out', '.bbl', '.blg', '.fls', '.fdb_latexmk'}


def main():
    text_count = 0
    pdfs = []
    archives = 0
    findings = []
    for path in sorted(ROOT.rglob('*')):
        rel = path.relative_to(ROOT)
        if not path.is_file() or path.is_symlink() or path == OUT:
            continue
        if len(rel.parts) > 1 and rel.parts[0] not in TOP:
            continue
        if '__pycache__' in rel.parts or rel.name.startswith('.'):
            continue
        if rel.parts[0] in {'paper', 'proofs'} and path.suffix in TEX_TEMP:
            continue
        if path.suffix in ARCHIVES:
            archives += 1
            continue
        if path.suffix == '.pdf':
            reader = PdfReader(path)
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
            count = text.count(chr(0x2014))
            pdfs.append({'file': rel.as_posix(), 'pages': len(reader.pages),
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'em_dashes': count})
            if count:
                findings.append({'file': rel.as_posix(), 'count': count})
            continue
        count = 0
        try:
            with path.open(encoding='utf-8') as stream:
                while chunk := stream.read(1024 * 1024):
                    if '\0' in chunk:
                        raise UnicodeError('Binary content')
                    count += chunk.count(chr(0x2014))
        except UnicodeError:
            continue
        text_count += 1
        if count:
            findings.append({'file': rel.as_posix(), 'count': count})
    for name, source in active_sources().items():
        assert not re.search(r'---|\\textemdash\b', source), name
    assert not findings, findings
    result = {'status': 'PASS', 'utc': datetime.now(timezone.utc).isoformat(),
              'unpacked_utf8_text_files': text_count, 'pdf_files': len(pdfs),
              'pdf_pages': sum(p['pages'] for p in pdfs), 'em_dashes': 0,
              'active_latex_em_dash_commands': 0, 'findings': findings, 'pdfs': pdfs,
              'compressed_files_not_rewritten': archives,
              'archive_scope': 'Historical original archives and compressed raw observations retain exact original bytes. Submission ZIP contents are checked separately.'}
    result = write_receipt(OUT, result)
    print(json.dumps({key: value for key, value in result.items() if key != 'pdfs'}, indent=2))


if __name__ == '__main__':
    main()
