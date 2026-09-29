#!/usr/bin/env bash
# Reproduce the accepted design in fresh archives, strictly on homelab.
set -euo pipefail
STUDY_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STUDY_NS=trace-sampling-boundaries-20260928
STUDY_RESULTS="$STUDY_ROOT/data/raw/fifth-audit-reproduction-$(date -u +%Y%m%dT%H%M%SZ)"
STUDY_PYTHON="$STUDY_ROOT/.venv/bin/python"
STUDY_STAGE="$(mktemp -d /tmp/trace-boundary-source.XXXXXX)"
STUDY_ASSETS="$(mktemp -d /tmp/trace-boundary-assets.XXXXXX)"
k() { kubectl --context homelab -n "$STUDY_NS" "$@"; }
trap 'rm -rf "$STUDY_STAGE" "$STUDY_ASSETS"' EXIT
if [[ -n "$(kubectl --context homelab get namespace "$STUDY_NS" --ignore-not-found -o name)" ]]; then
  printf 'Refusing to reuse namespace %s\n' "$STUDY_NS" >&2
  exit 1
fi
mkdir -p "$STUDY_RESULTS"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/download_revision_assets.py" "$STUDY_ASSETS"
"$STUDY_PYTHON" - "$STUDY_ROOT" "$STUDY_STAGE" <<'PY'
import hashlib,json,shutil,sys
from pathlib import Path
root,stage=map(Path,sys.argv[1:])
for folder,version,record in [('source','fifth_audit','execution-freeze.json'),
                              ('source-v2','fifth_audit_v2','batching-execution-freeze-v2.json')]:
    target=stage/folder;target.mkdir()
    freeze=root/'docs/fifth-audit-20260928'/record
    for name,digest in json.loads(freeze.read_text())['files'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
        if name.startswith(f'experiments/{version}/'):shutil.copy2(root/name,target/Path(name).name)
    shutil.copy2(freeze,target/'execution-freeze.json')
PY
kubectl --context homelab apply -f "$STUDY_ROOT/experiments/fifth_audit/pod.yaml"
k wait --for=condition=Ready pod/study-runner --timeout=180s
k get pod study-runner -o json > "$STUDY_RESULTS/pod-start.json"
kubectl --context homelab get node homelab-01 -o json > "$STUDY_RESULTS/node-start.json"
k exec study-runner -- mkdir -p /work/source /work/source-v2 /work/downloads /work/input /work/outputs
k cp "$STUDY_STAGE/source/." study-runner:/work/source
k cp "$STUDY_STAGE/source-v2/." study-runner:/work/source-v2
k cp "$STUDY_ROOT/experiments/fifth_audit/reproduce_placement_pilots.py" study-runner:/work/reproduce_placement_pilots.py
k cp "$STUDY_ROOT/experiments/fifth_audit/reproduce_placement_measured.py" study-runner:/work/reproduce_placement_measured.py
for item in traces.jsonl.gz truth.json warmup.json; do
  k cp "$STUDY_ROOT/data/raw/revision-20260924/confirm-v1/checkout-steady/seed-41001/full/$item" "study-runner:/work/input/$item"
done
k cp "$STUDY_ASSETS/otelcol-contrib_0.136.0_linux_amd64.tar.gz" study-runner:/work/downloads/collector.tar.gz
k cp "$STUDY_ASSETS/jaeger-1.76.0-linux-amd64.tar.gz" study-runner:/work/downloads/jaeger.tar.gz
k exec study-runner -- sh -c 'tar xzf /work/downloads/collector.tar.gz -C /work otelcol-contrib && tar xzf /work/downloads/jaeger.tar.gz -C /work'
k exec study-runner -- sh -c 'python /work/reproduce_placement_pilots.py > /work/placement-pilot-campaign.log 2>&1'
k exec study-runner -- sh -c 'python /work/source-v2/run_pilots.py > /work/batching-pilot-campaign.log 2>&1'
k cp study-runner:/work/pilots-placement "$STUDY_RESULTS/pilots-placement"
k cp study-runner:/work/pilots-v3 "$STUDY_RESULTS/pilots-v3"
"$STUDY_PYTHON" - "$STUDY_ROOT" "$STUDY_RESULTS" <<'PY'
import datetime,hashlib,json,subprocess,sys
from pathlib import Path
root,out=map(Path,sys.argv[1:]);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
selections={kind:json.loads((out/folder/'selection.json').read_text())[kind]
            for kind,folder in [('placement','pilots-placement'),('batching','pilots-v3')]}
for kind,folder,validator,record in [
    ('placement','pilots-placement','verify_fifth_audit.py','execution-freeze.json'),
    ('batching','pilots-v3','verify_fifth_batched.py','batching-execution-freeze-v2.json')]:
    base=out/folder/f'{kind}-{selections[kind]["selected_rate_traces_s"]}'
    receipt=out/f'{kind}-pilot-validation.json'
    subprocess.run([sys.executable,str(root/'scripts'/validator),str(base),'--receipt',str(receipt)],check=True)
    subprocess.run([sys.executable,str(root/'scripts/verify_fifth_contract.py'),'--pilot-inputs',str(base),
                    '--receipt',str(out/f'{kind}-pilot-input-validation.json')],check=True)
    original=root/'docs/fifth-audit-20260928'/record;freeze=json.loads(original.read_text())
    freeze['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    freeze['reproduction_of_freeze_sha256']=sha(original)
    freeze['selected_rates_traces_s']={k:v['selected_rate_traces_s'] for k,v in selections.items()}
    inputs={p.name:sha(p) for p in (base/'input').iterdir() if p.is_file()}
    for name in ['traces.jsonl.gz','truth.json','warmup.json']:
        assert inputs[name]==freeze['input_sha256'][name],name
    freeze['input_sha256']=inputs
    freeze['pilot_selection_sha256']=sha(out/folder/'selection.json')
    freeze['reproduction_pilot_validation_sha256']=sha(receipt)
    freeze['stage']='before reproduction measured execution'
    freeze.pop('retained_failed_measured_attempt',None)
    (out/record).write_text(json.dumps(freeze,indent=2)+'\n')
PY
k cp "$STUDY_RESULTS/execution-freeze.json" study-runner:/work/source/execution-freeze.json
k cp "$STUDY_RESULTS/batching-execution-freeze-v2.json" study-runner:/work/source-v2/execution-freeze.json
k exec study-runner -- sh -c 'python /work/reproduce_placement_measured.py > /work/placement-measured-campaign.log 2>&1'
k exec study-runner -- sh -c 'python /work/source-v2/run_measured.py > /work/batching-measured-campaign.log 2>&1'
k exec study-runner -- python -c 'from pathlib import Path; import hashlib,json; root=Path("/work/outputs"); hashes={str(p.relative_to(root)):hashlib.file_digest(p.open("rb"),"sha256").hexdigest() for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}; Path("/work/copy-sha256.json").write_text(json.dumps(hashes,indent=2))'
for campaign in placement-confirm-v1 batching-confirm-v2; do
  k cp "study-runner:/work/outputs/$campaign" "$STUDY_RESULTS/$campaign"
done
k cp study-runner:/work/copy-sha256.json "$STUDY_RESULTS/copy-sha256.json"
for log in placement-pilot batching-pilot placement-measured batching-measured; do
  k cp "study-runner:/work/$log-campaign.log" "$STUDY_RESULTS/$log-campaign.log"
done
"$STUDY_PYTHON" - "$STUDY_RESULTS" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for name,digest in json.loads((root/'copy-sha256.json').read_text()).items():
    with (root/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest,name
PY
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_fifth_audit.py" "$STUDY_RESULTS/placement-confirm-v1" --receipt "$STUDY_RESULTS/placement-validation.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_fifth_batched.py" "$STUDY_RESULTS/batching-confirm-v2" --receipt "$STUDY_RESULTS/batching-validation.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/analyze_fifth_current.py" --raw "$STUDY_RESULTS" --out "$STUDY_RESULTS/analysis"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_fifth_contract.py" --raw "$STUDY_RESULTS" --analysis "$STUDY_RESULTS/analysis" --freeze "$STUDY_RESULTS/execution-freeze.json" --batching-freeze "$STUDY_RESULTS/batching-execution-freeze-v2.json" --receipt "$STUDY_RESULTS/contract-validation.json"
# Failure preserves the namespace for inspection. Only validated runs reach cleanup.
k get pod study-runner -o json > "$STUDY_RESULTS/pod-end.json"
kubectl --context homelab delete namespace "$STUDY_NS" --wait=true --timeout=120s
printf 'Validated reproduction saved at %s\n' "$STUDY_RESULTS"
