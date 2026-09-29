#!/usr/bin/env python3
"""Download pinned public release archives for preparation, without running them."""
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
root=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
for item in json.loads((root/'docs/revision-20260924/release-assets.json').read_text()):
    name=item['url'].rsplit('/',1)[-1]
    target=out/name
    if not target.exists():
        with urllib.request.urlopen(item['url'],timeout=180) as response,target.open('wb') as f:
            while chunk:=response.read(1024*1024):f.write(chunk)
    data=target.read_bytes()
    assert len(data)==item['bytes']
    assert hashlib.sha256(data).hexdigest()==item['sha256']
    print('VERIFIED',name,item['sha256'])
