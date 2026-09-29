#!/usr/bin/env bash
# Reproduction creates only this study's homelab namespace. No context switching.
set -euo pipefail
STUDY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STUDY_NS=trace-sampling-study-20260923
K=(kubectl --context homelab -n "$STUDY_NS")
if "${K[@]}" get namespace "$STUDY_NS" >/dev/null 2>&1; then
  echo "Refusing to reuse existing namespace $STUDY_NS. Preserve/collect its data first." >&2
  exit 1
fi
STUDY_RUN="$STUDY_ROOT/data/raw/reproduction-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$STUDY_RUN"
STUDY_DOWNLOAD="$(mktemp -d ${TMPDIR:-/tmp}/trace-sampling-release.XXXXXX)"
trap 'rm -rf "$STUDY_DOWNLOAD"' EXIT
ARCHIVE=otelcol-contrib_0.136.0_linux_amd64.tar.gz
BASE=https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v0.136.0
curl --fail --location --retry 3 "$BASE/$ARCHIVE" -o "$STUDY_DOWNLOAD/$ARCHIVE"
curl --fail --location --retry 3 "$BASE/opentelemetry-collector-releases_otelcol-contrib_checksums.txt" -o "$STUDY_DOWNLOAD/release-checksums.txt"
python3 - "$STUDY_DOWNLOAD/$ARCHIVE" <<'PY'
import hashlib,sys
from pathlib import Path
assert hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()=='e642146998b9559929c34f5b85525e27ca6430585e2951fa88a403ff5ebf9f47'
PY
kubectl --context homelab apply -f "$STUDY_ROOT/experiments/pod.yaml"
"${K[@]}" create configmap study-scripts --from-file="$STUDY_ROOT/experiments/runner.py"
"${K[@]}" wait --for=condition=Ready pod/study-runner --timeout=180s
"${K[@]}" get pod study-runner -o json > "$STUDY_RUN/pod.json"
kubectl --context homelab get node homelab-01 -o json > "$STUDY_RUN/node.json"
"${K[@]}" cp "$STUDY_DOWNLOAD/$ARCHIVE" "study-runner:/work/$ARCHIVE"
"${K[@]}" cp "$STUDY_DOWNLOAD/release-checksums.txt" study-runner:/work/release-checksums.txt
for file in runner.py sensitivity.py; do "${K[@]}" cp "$STUDY_ROOT/experiments/$file" "study-runner:/work/$file"; done
"${K[@]}" cp "$STUDY_ROOT/tests/verify_model.py" study-runner:/work/verify_model.py
"${K[@]}" exec study-runner -- python /work/runner.py bootstrap | tee "$STUDY_RUN/bootstrap.log"
"${K[@]}" exec study-runner -- python /work/runner.py pilot | tee "$STUDY_RUN/pilot-console.jsonl"
"${K[@]}" exec study-runner -- python /work/runner.py main | tee "$STUDY_RUN/main-console.jsonl"
"${K[@]}" exec study-runner -- python /work/sensitivity.py | tee "$STUDY_RUN/sensitivity-console.jsonl"
"${K[@]}" exec study-runner -- python /work/verify_model.py > "$STUDY_RUN/model-verification.json"
for dir in main pilot sensitivity; do "${K[@]}" cp "study-runner:/work/$dir" "$STUDY_RUN/$dir"; done
"${K[@]}" cp study-runner:/work/environment.json "$STUDY_RUN/environment.json"
"${K[@]}" cp study-runner:/work/runner.py "$STUDY_RUN/executed-runner.py"
python3 "$STUDY_ROOT/scripts/verify_artifact.py" "$STUDY_RUN" | tee "$STUDY_RUN/validation.json"
python3 "$STUDY_ROOT/scripts/summarize_probes.py" "$STUDY_RUN" | tee "$STUDY_RUN/probe-validation.json"
# A failed experiment or copy leaves the namespace for evidence recovery.
# Delete only after successful collection and independent archive validation.
kubectl --context homelab delete namespace "$STUDY_NS" --wait=true --timeout=120s
printf 'Collected and validated: %s\n' "$STUDY_RUN"
