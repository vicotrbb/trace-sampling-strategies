"""Run only the amended batching campaign; preserve the completed placement data."""
import json,subprocess,sys
from pathlib import Path
import study

study.allowed();source=Path(__file__).resolve().parent
freeze=json.loads((source/'execution-freeze.json').read_text())
subprocess.run([sys.executable,str(source/'study.py'),'batching','--rate',str(freeze['selected_rates_traces_s']['batching']),
                '--output','/work/outputs/batching-confirm-v2'],check=True)
