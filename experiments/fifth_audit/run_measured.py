"""Execute the two fixed, sequential homelab campaigns; stop on any failure."""
import json,subprocess,sys
from pathlib import Path
import study

study.allowed()
source=Path(__file__).resolve().parent
freeze=json.loads((source/'execution-freeze.json').read_text())
for kind in ['placement','batching']:
    rate=freeze['selected_rates_traces_s'][kind]
    subprocess.run([sys.executable,str(source/'study.py'),kind,'--rate',str(rate),
                    '--output',f'/work/outputs/{kind}-confirm-v1'],check=True)
