"""Repeat placement capacity selection without the superseded short batching pilot."""
import json
import subprocess
import sys
import time
from pathlib import Path

root = Path('/work/pilots-placement')
root.mkdir(exist_ok=False)
attempts = []
for rate in [20000, 8000, 2000]:
    target = root / f'placement-{rate}'
    with (root / f'placement-{rate}.log').open('w') as log:
        result = subprocess.run(
            [sys.executable, '/work/source/study.py', 'placement', '--rate', str(rate),
             '--pilot', '--output', str(target)], stdout=log, stderr=subprocess.STDOUT)
    attempts.append({'rate_traces_s': rate, 'returncode': result.returncode,
                     'directory': str(target)})
    if result.returncode == 0:
        break
assert attempts[-1]['returncode'] == 0, attempts
selection = {'placement': {'selected_rate_traces_s': attempts[-1]['rate_traces_s'],
                           'attempts': attempts}}
(root / 'selection.json').write_text(json.dumps(selection, indent=2) + '\n')
(root / 'complete.json').write_text(json.dumps(
    {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'selected': selection},
    indent=2) + '\n')
