#!/usr/bin/env bash
# Reproduce the declared sensitivity study, keeping new observations separate.
set -euo pipefail
STUDY_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STUDY_NS=trace-sampling-sensitivity-20260925
STUDY_RESULTS="$STUDY_ROOT/data/raw/third-audit-reproduction-$(date -u +%Y%m%dT%H%M%SZ)"
STUDY_PYTHON="$STUDY_ROOT/.venv/bin/python"
STUDY_STAGE="$(mktemp -d /tmp/trace-sensitivity-source.XXXXXX)"
STUDY_ASSETS="$(mktemp -d /tmp/trace-sensitivity-assets.XXXXXX)"
k() { kubectl --context homelab -n "$STUDY_NS" "$@"; }
trap 'rm -rf "$STUDY_STAGE" "$STUDY_ASSETS"' EXIT
if [[ -n "$(kubectl --context homelab get namespace "$STUDY_NS" --ignore-not-found -o name)" ]]; then
  printf 'Refusing to reuse namespace %s\n' "$STUDY_NS" >&2
  exit 1
fi
mkdir -p "$STUDY_RESULTS"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/download_revision_assets.py" "$STUDY_ASSETS"
"$STUDY_PYTHON" - "$STUDY_ROOT" "$STUDY_STAGE" <<'PY'
from pathlib import Path
import hashlib,json,shutil,sys
root,stage=map(Path,sys.argv[1:]);freeze=json.loads((root/'docs/third-audit-20260925/execution-freeze.json').read_text())
for name,sha in freeze['files'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
    shutil.copy2(root/name,stage/Path(name).name)
shutil.copy2(root/'docs/third-audit-20260925/pilot-source-freeze.json',stage/'pilot-source-freeze.json')
PY
kubectl --context homelab apply -f "$STUDY_ROOT/experiments/third_audit/pod.yaml"
k wait --for=condition=Ready pod/study-runner --timeout=180s
k get pod study-runner -o json > "$STUDY_RESULTS/pod-start.json"
kubectl --context homelab get node homelab-01 -o json > "$STUDY_RESULTS/node-start.json"
k exec study-runner -- mkdir -p /work/source /work/downloads /work/outputs
k cp "$STUDY_STAGE/." study-runner:/work/source
k cp "$STUDY_ASSETS/otelcol-contrib_0.136.0_linux_amd64.tar.gz" study-runner:/work/downloads/otelcol-contrib.tar.gz
k exec study-runner -- sh -c 'tar xzf /work/downloads/otelcol-contrib.tar.gz -C /work otelcol-contrib'
k exec study-runner -- sh -c 'python /work/source/run_pilots.py > /work/pilots.log 2>&1'
for study_group in calibration-v1 diagnosis-pilot-v1 load-pilot-v1; do
  k cp "study-runner:/work/outputs/$study_group" "$STUDY_RESULTS/$study_group"
done
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_third_audit.py" calibration "$STUDY_RESULTS/calibration-v1" --receipt "$STUDY_RESULTS/calibration-validation.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_third_audit.py" pilot "$STUDY_RESULTS/diagnosis-pilot-v1" --receipt "$STUDY_RESULTS/diagnosis-pilot-validation.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_third_audit.py" load "$STUDY_RESULTS/load-pilot-v1" --receipt "$STUDY_RESULTS/load-pilot-validation.json"
"$STUDY_PYTHON" - "$STUDY_ROOT" "$STUDY_RESULTS" <<'PY'
from pathlib import Path
import datetime,hashlib,json,sys
root,out=map(Path,sys.argv[1:]);original=root/'docs/third-audit-20260925/execution-freeze.json'
f=json.loads(original.read_text());f['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
f['reproduction_of_freeze_sha256']=hashlib.sha256(original.read_bytes()).hexdigest()
f['calibration_threshold_sha256']=hashlib.sha256((out/'calibration-v1/threshold.json').read_bytes()).hexdigest()
f['calibration_threshold_ms']=json.loads((out/'calibration-v1/threshold.json').read_text())['threshold_ms']
(out/'execution-freeze.json').write_text(json.dumps(f,indent=2)+'\n')
PY
k cp "$STUDY_RESULTS/execution-freeze.json" study-runner:/work/source/execution-freeze.json
k exec study-runner -- sh -c 'python /work/source/run_measured.py > /work/measured-campaign.log 2>&1'
k exec study-runner -- python -c 'from pathlib import Path; import hashlib,json; root=Path("/work/outputs"); result={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}; Path("/work/copy-sha256.json").write_text(json.dumps(result,indent=2))'
for study_group in diagnosis-confirm-v1 diagnosis-replay-v1 load-confirm-v1; do
  k cp "study-runner:/work/outputs/$study_group" "$STUDY_RESULTS/$study_group"
done
k cp study-runner:/work/copy-sha256.json "$STUDY_RESULTS/copy-sha256.json"
for study_log in pilots measured-campaign measured-stage-0 measured-stage-1 measured-stage-2; do
  k cp "study-runner:/work/$study_log.log" "$STUDY_RESULTS/$study_log.log"
done
"$STUDY_PYTHON" - "$STUDY_RESULTS" <<'PY'
import json,hashlib,sys
from pathlib import Path
r=Path(sys.argv[1]);manifest=json.loads((r/'copy-sha256.json').read_text())
for name,sha in manifest.items():
    with (r/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha,name
print('Copy hashes verified:',len(manifest))
PY
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_third_audit.py" load "$STUDY_RESULTS/load-confirm-v1" --receipt "$STUDY_RESULTS/load-validation.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/analyze_third_audit.py" all --raw "$STUDY_RESULTS" --out "$STUDY_RESULTS/analysis"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_third_audit.py" replay "$STUDY_RESULTS/diagnosis-replay-v1" --corpus "$STUDY_RESULTS/diagnosis-confirm-v1" --calibration "$STUDY_RESULTS/calibration-v1" --analysis "$STUDY_RESULTS/analysis" --receipt "$STUDY_RESULTS/diagnosis-validation.json"
# Failures above preserve the namespace. Successful reproduction removes only its runner namespace.
k get pod study-runner -o json > "$STUDY_RESULTS/pod-end.json"
kubectl --context homelab delete namespace "$STUDY_NS" --wait=true --timeout=120s
printf 'Validated reproduction saved at %s\n' "$STUDY_RESULTS"
