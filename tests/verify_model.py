#!/usr/bin/env python3
"""Independent exact enumeration of finite sampling models; not a proof over all m."""
from fractions import Fraction
from itertools import product
import json
import math
import os
from pathlib import Path
import random
import sys
import time


def survival(m, k, p):
    return sum(math.comb(m, i) * p**i * (1-p)**(m-i) for i in range(k, m+1))


def run():
    assert os.environ.get('STUDY_CONTEXT') == 'homelab', 'run computational experiments on homelab'
    counts = {'weighted_outcomes': 0, 'binomial_cases': 0, 'monotonicity_pairs': 0, 'tail_budget_cases': 0, 'hybrid_pairs': 0}
    for m in range(1, 13):
        for p in [Fraction(1,10), Fraction(1,4), Fraction(1,2), Fraction(9,10)]:
            hist = [Fraction(0)] * (m+1)
            for word in product([0, 1], repeat=m):
                count = sum(word)
                probability = Fraction(1)
                for bit in word:
                    probability *= p if bit else 1-p
                hist[count] += probability
                counts['weighted_outcomes'] += 1
            assert sum(hist) == 1
            for k in range(1, m+1):
                assert sum(hist[k:]) == survival(m,k,p)
                counts['binomial_cases'] += 1
            assert sum(hist[1:]) == 1-(1-p)**m
    for m in range(1, 9):
        masks = list(product([0,1], repeat=m))
        for up in masks:
            for down in masks:
                if all(a <= b for a,b in zip(down,up)):
                    assert sum(down) <= sum(up)
                    counts['hybrid_pairs'] += 1
        for k in range(1, m+1):
            prev = Fraction(0)
            for i in range(101):
                now = survival(m,k,Fraction(i,100))
                assert now >= prev
                prev = now
                counts['monotonicity_pairs'] += 1
    for alpha in [Fraction(1,100), Fraction(1,50), Fraction(1,10), Fraction(1,2)]:
        for i in range(101):
            b = Fraction(i,100)
            if b < alpha:
                continue
            r = (b-alpha)/(1-alpha)
            assert alpha+(1-alpha)*r == b
            assert 0 <= r <= b <= 1
            if b < 1: assert r < b
            counts['tail_budget_cases'] += 1
    rng = random.Random(20260923)
    monte_carlo = []
    for m in [1,5,20,100]:
        for p in [.001,.01,.025,.05,.1,.25,.5,1.0]:
            hist = [0]*(m+1)
            for _ in range(10000):
                hist[sum(rng.random() < p for _ in range(m))] += 1
            for k in ([1] if m == 1 else [1,3]):
                count = sum(hist[k:])
                monte_carlo.append({'m':m,'k':k,'p':p,'successes':count,'trials':10000,'theory':survival(m,k,p)})
    result = {'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'python':sys.version,'context':os.environ['STUDY_CONTEXT'],
              'exact_checks':counts,'status':'PASS','monte_carlo_seed':20260923,'monte_carlo':monte_carlo}
    print(json.dumps(result, indent=2))

if __name__ == '__main__': run()
