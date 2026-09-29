#!/usr/bin/env bash
# Reproduce the frozen extension in a new archive, strictly on homelab.
set -euo pipefail
STUDY_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STUDY_NS="trace-sampling-load-20260925"
STUDY_RESULTS="$STUDY_ROOT/data/raw/second-audit-reproduction-$(date -u +%Y%m%dT%H%M%SZ)"
STUDY_PYTHON="$STUDY_ROOT/.venv/bin/python"
STUDY_STAGE="$(mktemp -d /tmp/trace-load-source.XXXXXX)"
STUDY_ASSETS="$(mktemp -d /tmp/trace-load-assets.XXXXXX)"
k() { kubectl --context homelab -n "$STUDY_NS" "$@"; }
trap 'rm -rf "$STUDY_STAGE" "$STUDY_ASSETS"' EXIT
if [[ -n "$(kubectl --context homelab get namespace "$STUDY_NS" --ignore-not-found -o name)" ]]; then
  printf 'Refusing to reuse existing namespace %s\n' "$STUDY_NS" >&2
  exit 1
fi
mkdir -p "$STUDY_RESULTS"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/download_revision_assets.py" "$STUDY_ASSETS"
"$STUDY_PYTHON" - "$STUDY_ROOT" "$STUDY_STAGE" <<'PY'
from pathlib import Path
import datetime,hashlib,json,shutil,sys
root,stage=map(Path,sys.argv[1:]);original=root/'docs/second-audit-20260925/execution-freeze.json'
freeze=json.loads(original.read_text())
for name,sha in freeze['files'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
    shutil.copy2(root/name,stage/Path(name).name)
freeze['frozen_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
freeze['reproduction_of_freeze_sha256']=hashlib.sha256(original.read_bytes()).hexdigest()
(stage/'execution-freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
PY
cp "$STUDY_STAGE/execution-freeze.json" "$STUDY_RESULTS/execution-freeze.json"
cp "$STUDY_ROOT/experiments/second_audit/pod.yaml" "$STUDY_RESULTS/applied-pod.yaml"
kubectl --context homelab apply -f "$STUDY_RESULTS/applied-pod.yaml"
k wait --for=condition=Ready pod/study-runner --timeout=180s
k get pod study-runner -o json > "$STUDY_RESULTS/pod-start.json"
kubectl --context homelab get node homelab-01 -o json > "$STUDY_RESULTS/node.json"
k exec study-runner -- mkdir -p /work/source /work/downloads /work/outputs
k cp "$STUDY_STAGE/." study-runner:/work/source
k cp "$STUDY_ASSETS/otelcol-contrib_0.136.0_linux_amd64.tar.gz" study-runner:/work/downloads/otelcol-contrib_0.136.0_linux_amd64.tar.gz
k exec study-runner -- sh -c 'cd /work && tar xzf downloads/otelcol-contrib_0.136.0_linux_amd64.tar.gz otelcol-contrib'
# Functional pilots are excluded; they cannot alter the frozen measured design.
k exec study-runner -- sh -c 'python /work/source/load_study.py --pilot --rates 50,2000,8000,20000 --output /work/outputs/load-pilot > /work/load-pilot.log 2>&1'
k exec study-runner -- sh -c 'python /work/source/load_study.py --pilot --rates 20000 --policies head10,tail10,tail100 --output /work/outputs/load-policy-pilot > /work/load-policy-pilot.log 2>&1'
k exec study-runner -- sh -c 'python /work/source/diagnosis_study.py collect --pilot --output /work/outputs/diagnosis-pilot > /work/diagnosis-pilot.log 2>&1'
for study_group in load-pilot load-policy-pilot diagnosis-pilot; do
  k cp "study-runner:/work/outputs/$study_group" "$STUDY_RESULTS/$study_group"
done
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_second_audit.py" load "$STUDY_RESULTS/load-pilot"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_second_audit.py" load "$STUDY_RESULTS/load-policy-pilot"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_second_audit.py" corpus "$STUDY_RESULTS/diagnosis-pilot"
k exec study-runner -- sh -c 'python /work/source/run_measured.py > /work/measured-campaign.log 2>&1'
k exec study-runner -- python -c 'from pathlib import Path; import hashlib,json; root=Path("/work/outputs"); data={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}; Path("/work/copy-sha256.json").write_text(json.dumps(data,indent=2))'
for study_group in diagnosis-confirm-v1 diagnosis-replay-v1 load-confirm-v1; do
  k cp "study-runner:/work/outputs/$study_group" "$STUDY_RESULTS/$study_group"
done
k cp study-runner:/work/copy-sha256.json "$STUDY_RESULTS/copy-sha256.json"
for study_log in load-pilot load-policy-pilot diagnosis-pilot measured-campaign measured-stage-0 measured-stage-1 measured-stage-2; do
  k cp "study-runner:/work/$study_log.log" "$STUDY_RESULTS/$study_log.log"
done
k get pod study-runner -o json > "$STUDY_RESULTS/pod-end.json"
"$STUDY_PYTHON" - "$STUDY_RESULTS" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);manifest=json.loads((root/'copy-sha256.json').read_text())
for name,expected in manifest.items():
    with (root/name).open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==expected,name
print('Source-side copy checksums passed:',len(manifest))
PY
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_second_audit.py" load "$STUDY_RESULTS/load-confirm-v1" --receipt "$STUDY_RESULTS/load-validation.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/analyze_second_audit.py" --raw "$STUDY_RESULTS" --out "$STUDY_RESULTS/analysis" > "$STUDY_RESULTS/analysis-output.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_second_audit.py" replay "$STUDY_RESULTS/diagnosis-replay-v1" --corpus "$STUDY_RESULTS/diagnosis-confirm-v1" --analysis "$STUDY_RESULTS/analysis" --receipt "$STUDY_RESULTS/diagnosis-validation.json"
# Any failure above preserves the namespace and evidence for inspection.
kubectl --context homelab delete namespace "$STUDY_NS" --wait=true --timeout=120s
printf 'Collected and validated extension: %s\n' "$STUDY_RESULTS"
