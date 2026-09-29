#!/usr/bin/env python3
"""Refresh the content inventory when deliberately preparing a new release."""
from pathlib import Path
from verify import ROOT, sha

OMIT = {'.git', '.venv', '__pycache__', 'tmp', 'releases'}
TEX_TEMP = ('.aux', '.blg', '.fdb_latexmk', '.fls', '.log', '.out', '.synctex.gz')


def included(path):
    rel = path.relative_to(ROOT)
    if not path.is_file() or path.is_symlink() or any(x in OMIT for x in rel.parts):
        return False
    if rel.as_posix() == 'SHA256SUMS' or path.name == '.DS_Store' or path.suffix == '.pyc':
        return False
    if rel.parts[0] in {'paper', 'proofs'} and path.name.endswith(TEX_TEMP):
        return False
    return True


if __name__ == '__main__':
    paths = sorted(p for p in ROOT.rglob('*') if included(p))
    (ROOT / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in paths))
    print(f'Inventoried {len(paths)} files. Verify and rebuild release assets before publication.')
