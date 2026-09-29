# Prospective experimental protocol

Recorded before confirmatory data collection on 2026-09-23. This is a timestamped local protocol, not a public preregistration. Changes and pilot failures must be retained separately.

## Scope and hypotheses

Mechanism study of complete-trace retention and resource use in OpenTelemetry Collector Contrib 0.123.0 under controlled synthetic OTLP replay on Kubernetes context `homelab` only. No claims of human debugging effectiveness, real customer traffic, production readiness, worldwide novelty, or universally optimal sampling.

RQ1: independent uniform head sampling of an incident with m distinct witness traces retains at least k with Binomial(m,p) survival probability. Check against deterministic seeded trials and observed collector exports. RQ2: error/latency tail policies protect recognizable witnesses but reduce the background inclusion probability at a matched expected trace budget; evaluate an unflagged semantic failure alongside the protected classes. RQ3: record offered OTLP application bytes, exported JSON bytes, gzip archive bytes, collector process CPU, and sampled peak RSS. Separate measured resources from cost models. RQ4: define a material deterioration as incident witness-recovery probability below 0.95 (primary), with sensitivity at 0.90 and 0.99. This is an explicit study decision, not an industry standard or a validated human threshold.

## Main experiment

- Container: Python 3.12.10 slim, published official Collector 0.123.0 linux/amd64 release binary, checksum verification against release checksums; save image digest and binary SHA256.
- One disposable namespace `trace-sampling-study-20260923`; runner pod pinned to `homelab-01`; limit 2 CPU and 1536 MiB; emptyDir only; no production namespaces or telemetry.
- Five independent seed blocks, seeds 1101 through 1105. Randomize treatment order within each block using that block seed. Reuse the identical trace corpus for all treatments within a block. One collector process per treatment; no collector concurrency.
- 20,000 synthetic request traces per block, offered at 2,000 traces/s in 100-trace batches for 10 s. Complete traces fit within one request. Flush for decision_wait + 2 s after ingress. The target rate is an offered replay rate, not a measured service throughput or saturation capacity.
- Traffic composition: 97% normal, 1% explicitly failed, 1% high latency, 1% unflagged semantic failures. Explicit errors have ERROR span status; latency witnesses exceed 250 ms; hidden semantic failures have neither. Every failure class has 200 traces grouped into 20 incidents with one witness, 20 with five witnesses, and four with twenty witnesses.
- A diagnostic witness requires the full causal span chain and a class-specific leaf attribute. Sampling policies cannot inspect incident identifiers, ground-truth fault labels, or the diagnostic evaluator. Evaluate at least one witness (k=1) and corroboration (k=3, applicable only when m>=3). These are deterministic evidence-retention tasks, not observed human diagnoses.
- 14 treatments: full retention; head rates 0.1%, 1%, 2.5%, 5%, 10%, 25%, 50%; protected-only tail (2% expected); tail budgets 2.5%, 5%, 10%, 25%, 50%. Tail is an OR of error-status, latency, and background probabilistic policies. Background rate r=(p-0.02)/0.98. No infeasible tail budget below the 2% protected mass is advertised.
- Head filter selects complete traces before OTLP export using a deterministic uniform hash threshold independent of the injected faults. This measures an upstream export gate, not an SDK instrumentation-overhead benchmark. Collector ingestion/serialization/export cost can be measured; avoided application instrumentation is modeled only.
- Tail decision_wait=2s, num_traces=50,000, expected_new_traces_per_sec=2,000. All main-experiment traces arrive complete; delayed spans and undersized buffers are sensitivity experiments and do not get silently pooled.
- Common receiver HTTP/JSON and batch/file exporters. Record exact configuration. Native uncompressed file sizes and deterministic gzip size are archive proxies, not a backend index or replicated storage benchmark.

## Measurements and statistics

Reconstruct retained trace/span IDs from the actual file exporter. Verify zero unexpected IDs, no duplicates, and full-span witnesses for every retained main-experiment trace. Compare ingress/exports to collector telemetry; any unexplained loss invalidates a cell. Retain pilot failures and invalid cells with reasons; do not selectively drop inconvenient resource observations.

Collector CPU is delta of Linux process user+system CPU ticks, measured immediately before offered load and after flush; peak RSS is the maximum /proc sample at 50 ms intervals, not a kernel-guaranteed peak. Keep startup and generation outside the primary collector load interval. Resource ratios are paired against the full-retention treatment within each seed. Report individual observations and mean paired savings with Student t 95% intervals across five seed blocks; do not interpret intervals as covering deployment diversity. An interval crossing zero is not demonstrated CPU savings.

Incident recovery is stratified by fault class, m and k; theoretical probabilities are primary. Report empirical counts and Wilson 95% intervals, conditional on this synthetic witness model. Common-input paired treatments are dependent; do not run unpaired significance tests. Global multiple-comparison superiority claims are out of scope. Deterministic resampling seeds are declared, not selected after seeing outcomes.

## Sensitivity experiments

After main measurements, run labeled separate cases: (1) late error-bearing leaf spans after the decision window with a nonsampled decision cache; (2) undersized tail trace buffer under burst input; (3) marker-blind/protected-only policy on hidden failures. Compare known loss mechanisms with formal assumptions. Document exact realized load and loss rather than promising the collector must produce a preconceived result.

## Formal and computational validation

Prove binomial visibility, monotonicity and threshold inversion, multi-witness recovery, the equal-budget tail tradeoff, irreversible upstream loss, resource decomposition, and impossibility of a universal positive discard guarantee. Do not represent a finite computational check as a general proof. Machine-check a clearly identified finite combinatorial core if feasible; distinguish it from paper proofs over real probabilities and empirical validity.

## Cleanup

Copy all raw data and environment records locally, validate hashes, then delete only the experiment namespace. Keep replay scripts and commands that explicitly hard-code/refuse any context other than `homelab`.
