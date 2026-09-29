"""Run placement alone with the reproduced pilot's frozen selected rate."""
import json
import subprocess
import sys
from pathlib import Path

rate = json.loads(Path('/work/source/execution-freeze.json').read_text())['selected_rates_traces_s']['placement']
subprocess.run([sys.executable, '/work/source/study.py', 'placement', '--rate', str(rate),
                '--output', '/work/outputs/placement-confirm-v1'], check=True)
