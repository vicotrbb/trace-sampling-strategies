#!/usr/bin/env bash
# Reproduce the fixed-input cost intervention only on the authorized homelab.
set -euo pipefail
STUDY_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STUDY_NS="trace-sampling-final-20260925"
STUDY_RESULTS="$STUDY_ROOT/data/raw/final-cost-reproduction-$(date -u +%Y%m%dT%H%M%SZ)"
STUDY_PYTHON="$STUDY_ROOT/.venv/bin/python"
STUDY_ASSETS="$(mktemp -d /tmp/trace-cost-assets.XXXXXX)"
STUDY_INPUT="$STUDY_ROOT/data/raw/revision-20260924/confirm-v1/checkout-steady/seed-41001/full"
k() { kubectl --context homelab -n "$STUDY_NS" "$@"; }
trap 'rm -rf "$STUDY_ASSETS"' EXIT
if [[ -n "$(kubectl --context homelab get namespace "$STUDY_NS" --ignore-not-found -o name)" ]]; then
  printf 'Refusing to reuse existing namespace %s\n' "$STUDY_NS" >&2
  exit 1
fi
mkdir -p "$STUDY_RESULTS"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/download_revision_assets.py" "$STUDY_ASSETS"
cp "$STUDY_ROOT/experiments/final_cost/pod.yaml" "$STUDY_RESULTS/applied-pod.yaml"
kubectl --context homelab apply -f "$STUDY_RESULTS/applied-pod.yaml"
k wait --for=condition=Ready pod/cost-runner --timeout=180s
k get pod cost-runner -o json > "$STUDY_RESULTS/pod-start.json"
kubectl --context homelab get node homelab-01 -o json > "$STUDY_RESULTS/node.json"
k exec cost-runner -- mkdir -p /work/input /work/source /work/outputs
k cp "$STUDY_ASSETS/." cost-runner:/work/downloads
k exec cost-runner -- sh -c \
  'cd /work && tar xzf downloads/otelcol-contrib_0.136.0_linux_amd64.tar.gz otelcol-contrib && tar xzf downloads/jaeger-1.76.0-linux-amd64.tar.gz'
for study_name in traces.jsonl.gz truth.json warmup.json; do
  k cp "$STUDY_INPUT/$study_name" "cost-runner:/work/input/$study_name"
done
for study_file in experiments/final_cost/cost_study.py experiments/final_cost/pod.yaml \
  scripts/analyze_cost_study.py scripts/verify_cost_study.py docs/final-pass-20260925/protocol.md; do
  k cp "$STUDY_ROOT/$study_file" "cost-runner:/work/source/$(basename "$study_file")"
done
k exec cost-runner -- python /work/source/cost_study.py prepare
k exec cost-runner -- sh -c \
  'python /work/source/cost_study.py pilot --output /work/outputs/pilot-v1 > /work/pilot.log 2>&1'
k cp cost-runner:/work/outputs/pilot-v1 "$STUDY_RESULTS/pilot-v1"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_cost_study.py" "$STUDY_RESULTS/pilot-v1" \
  --receipt "$STUDY_RESULTS/pilot-validation.json"
"$STUDY_PYTHON" - "$STUDY_ROOT" "$STUDY_RESULTS" <<'PY'
import datetime, hashlib, json, pathlib, sys
root, output = map(pathlib.Path, sys.argv[1:])
files = ['experiments/final_cost/cost_study.py', 'experiments/final_cost/pod.yaml',
         'scripts/analyze_cost_study.py', 'scripts/verify_cost_study.py',
         'docs/final-pass-20260925/protocol.md']
receipt = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'stage': 'after pilot validation and before measured execution',
           'sha256': {f: hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files},
           'corpus_manifest_sha256': hashlib.sha256((output/'pilot-v1/corpus/manifest.json').read_bytes()).hexdigest()}
(output/'execution-freeze.json').write_text(json.dumps(receipt, indent=2)+'\n')
PY
k cp "$STUDY_RESULTS/execution-freeze.json" cost-runner:/work/source/execution-freeze.json
k exec cost-runner -- sh -c \
  'python /work/source/cost_study.py confirm --output /work/outputs/confirm-v1 > /work/confirm.log 2>&1'
k cp cost-runner:/work/outputs/confirm-v1 "$STUDY_RESULTS/confirm-v1"
for study_log in pilot confirm; do
  k cp "cost-runner:/work/$study_log.log" "$STUDY_RESULTS/$study_log.log"
done
k get pod cost-runner -o json > "$STUDY_RESULTS/pod-end.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_cost_study.py" "$STUDY_RESULTS/confirm-v1" \
  --receipt "$STUDY_RESULTS/validation.json"
# Failure leaves the namespace and collected evidence available for inspection.
kubectl --context homelab delete namespace "$STUDY_NS" --wait=true --timeout=120s
printf 'Collected and validated fixed-input cost study: %s\n' "$STUDY_RESULTS"
