#!/usr/bin/env bash
# Runs only in homelab. Leaves all evidence in place after any failure.
set -euo pipefail
STUDY_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STUDY_NS="trace-sampling-revision-$(date -u +%Y%m%d%H%M%S)"
STUDY_RESULTS="$STUDY_ROOT/data/raw/revision-reproduction-$(date -u +%Y%m%dT%H%M%SZ)"
STUDY_PYTHON="$STUDY_ROOT/.venv/bin/python"
STUDY_DOWNLOAD="$(mktemp -d /tmp/trace-revision-assets.XXXXXX)"
k() { kubectl --context homelab -n "$STUDY_NS" "$@"; }
trap 'rm -rf "$STUDY_DOWNLOAD"' EXIT
existing="$(k get namespace "$STUDY_NS" --ignore-not-found -o name)"
if [[ -n "$existing" ]]; then
  printf 'Refusing to reuse namespace %s\n' "$STUDY_NS" >&2
  exit 1
fi
mkdir -p "$STUDY_RESULTS"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/download_revision_assets.py" "$STUDY_DOWNLOAD"
"$STUDY_PYTHON" -m pip download --dest "$STUDY_DOWNLOAD/wheels" \
  --platform manylinux2014_x86_64 --python-version 312 --implementation cp --abi cp312 \
  --only-binary=:all: --require-hashes -r "$STUDY_ROOT/requirements-live.lock"
sed "s/trace-sampling-revision-20260924/$STUDY_NS/g" "$STUDY_ROOT/experiments/revision/pod.yaml" > "$STUDY_RESULTS/applied-pod.yaml"
kubectl --context homelab apply -f "$STUDY_RESULTS/applied-pod.yaml"
k wait --for=condition=Ready pod/revision-runner --timeout=180s
k get pod revision-runner -o json > "$STUDY_RESULTS/pod-start.json"
kubectl --context homelab get node homelab-01 -o json > "$STUDY_RESULTS/node.json"
k cp "$STUDY_DOWNLOAD/." revision-runner:/work/downloads -c runner
k cp "$STUDY_ROOT/requirements-live.lock" revision-runner:/work/requirements-live.lock -c runner
k exec revision-runner -c runner -- sh -c \
  'cd /work && tar -xzf downloads/otelcol-contrib_0.136.0_linux_amd64.tar.gz otelcol-contrib && tar -xzf downloads/jaeger-1.76.0-linux-amd64.tar.gz && python -m pip install --no-index --find-links=/work/downloads/wheels --require-hashes -r /work/requirements-live.lock'
k exec revision-runner -c runner -- mkdir -p /work/code
COPYFILE_DISABLE=1 tar --exclude='__pycache__' --exclude='._*' -cf - -C "$STUDY_ROOT/experiments/revision" . | \
  k exec -i revision-runner -c runner -- tar -xf - -C /work/code
k exec revision-runner -c runner -- python -c \
  'from pathlib import Path; [p.unlink() for p in Path("/work/code").rglob("._*")]'
k cp "$STUDY_ROOT/experiments/runner.py" revision-runner:/work/runner.py -c runner
k cp "$STUDY_ROOT/tests/verify_model.py" revision-runner:/work/verify_model.py -c runner
k cp "$STUDY_ROOT/experiments/revision/pg-metrics.sh" revision-runner:/tmp/study-pg-metrics.sh -c postgres
k exec revision-runner -c postgres -- sh -c \
  'chmod +x /tmp/study-pg-metrics.sh && nohup busybox nc -lk -s 127.0.0.1 -p 9081 -e /tmp/study-pg-metrics.sh >/tmp/study-pg-metrics.log 2>&1 </dev/null &'
k exec revision-runner -c runner -- sh -c \
  'python /work/code/live_study.py --mode pilot --label pilot-reproduction > /work/pilot-reproduction.log 2>&1'
k cp revision-runner:/work/revision/pilot-reproduction "$STUDY_RESULTS/pilot-reproduction" -c runner
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_revision.py" "$STUDY_RESULTS/pilot-reproduction" > "$STUDY_RESULTS/pilot-validation.json"
# Readiness and independent checks must pass before measured execution.
k exec revision-runner -c runner -- sh -c \
  'python /work/code/live_study.py --mode confirm --label confirm-v1 > /work/confirm-v1.log 2>&1 && python /work/code/calibration.py > /work/calibration.log 2>&1 && python /work/code/matched_probes.py > /work/matched-probes.log 2>&1 && python /work/code/counterfactual.py > /work/counterfactual.log 2>&1 && python /work/verify_model.py > /work/revision/model-verification.json'
k cp revision-runner:/work/revision/. "$STUDY_RESULTS" -c runner
for study_log in pilot-reproduction confirm-v1 calibration matched-probes counterfactual; do
  k cp "revision-runner:/work/$study_log.log" "$STUDY_RESULTS/$study_log.log" -c runner
done
k get pod revision-runner -o json > "$STUDY_RESULTS/pod-end.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_revision.py" "$STUDY_RESULTS/confirm-v1" > "$STUDY_RESULTS/live-validation.json"
"$STUDY_PYTHON" "$STUDY_ROOT/scripts/verify_followups.py" "$STUDY_RESULTS" > "$STUDY_RESULTS/followup-validation.json"
# This final deletion targets only the namespace created above, after all receipts pass.
kubectl --context homelab delete namespace "$STUDY_NS" --wait=true --timeout=120s
printf 'Collected and independently validated: %s\n' "$STUDY_RESULTS"
