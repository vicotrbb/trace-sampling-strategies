#!/usr/bin/env python3
"""Fresh, fully enumerated hash calibration; run on homelab only."""
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import random

def priority(tid, salt, method):
    data = salt.encode() + bytes.fromhex(tid)
    if method == 'blake2b':
        return int.from_bytes(hashlib.blake2b(data, digest_size=8).digest(), 'big')
    value = 14695981039346656037
    for byte in data: value = ((value ^ byte) * 1099511628211) & ((1 << 64)-1)
    return value

def main():
    assert os.environ.get('STUDY_CONTEXT') == 'homelab'
    out=Path('/work/revision/calibration')
    out.mkdir(parents=True,exist_ok=False)
    results=[]
    for seed in range(31001,31031):
        rng=random.Random(f'ids-only:{seed}')
        for stream in ('python','sha256'):
            ids=[format(rng.getrandbits(128),'032x') if stream=='python' else
                 hashlib.sha256(f'ids-only:{seed}:{i}'.encode()).digest()[:16].hex() for i in range(10000)]
            assert len(set(ids))==10000 and all(int(t,16)>0 for t in ids)
            # Independent assignment order prevents shared RNG state between labels and IDs.
            order=list(range(10000)); random.Random(f'groups-only:{seed}').shuffle(order)
            ids=[ids[i] for i in order]
            (out/f'ids-{seed}-{stream}.json.gz').write_bytes(gzip.compress(json.dumps(ids).encode(),mtime=0))
            for salt in ['trace-study-v1','revision-salt-2','revision-salt-3','revision-salt-4']:
                for method in ('fnv1a','blake2b'):
                    h=[priority(t,salt,method) for t in ids]
                    threshold=int((.08/.98)*((1<<64)-1))
                    assert min(abs(v-threshold) for v in h)>2
                    retained=[v<=threshold for v in h]
                    histogram=Counter(sum(retained[i:i+5]) for i in range(0,10000,5))
                    head=[v < int(.1*(1<<64)) for v in h]
                    results.append({'seed':seed,'stream':stream,'salt':salt,'hash':method,
                                    'm':5,'incidents':2000,'traces':10000,
                                    'histogram':[histogram[i] for i in range(6)],
                                    'retained_traces':sum(retained),
                                    'shared_head_incidents':sum(any(head[i:i+5]) for i in range(0,10000,5)),
                                    'shared_tail_incidents':2000-histogram[0],
                                    'id_sha256':hashlib.sha256('\n'.join(ids).encode()).hexdigest()})
    (out/'blocks.json').write_text(json.dumps(results,indent=2)+'\n')
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    print('CALIBRATION_COMPLETE',len(results),flush=True)
if __name__=='__main__':main()
