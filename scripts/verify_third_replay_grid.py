#!/usr/bin/env python3
"""Fast structural validation, independent of outcome reconstruction."""
import argparse,gzip,itertools,json
from pathlib import Path
WINDOWS=[20,50,200];POLICIES=['head','tail'];BUDGETS=[.05,.10,.20,.35,.50,.65,.80,.95]
def check(path):
    expected=itertools.product(range(5000),WINDOWS,POLICIES,BUDGETS);n=0
    with gzip.open(path,'rt') as f:
        for line,key in itertools.zip_longest(f,expected):
            assert line is not None and key is not None,'row count'
            r=json.loads(line);assert (r['trial'],r['window'],r['policy'],r['budget'])==key,'comparison order, repetition or omission'
            n+=1
    assert n==240000;return n
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path',type=Path);a=p.parse_args();print(json.dumps({'status':'PASS','rows':check(a.path)}))
