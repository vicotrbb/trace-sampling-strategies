# Prospective revision protocol

Date: 24 September 2026. Recorded locally before the new measurement runs. This is a prospective local protocol, not a publicly preregistered study. Pilot adjustments, including failures, must be recorded in `amendments.md` before confirmatory execution. Original data remain unchanged.

## Objectives and boundaries

Correct the late-marker intervention description and the nonempty-population qualification. Independently verify original exports, raw metric counters, and complete incident coverage. Add controlled marker/timing probes, independent sampling calibration, and a live application evaluation of diagnosis and resource consumption. All workload execution is confined to `kubectl --context homelab` and namespace `trace-sampling-revision-20260924`. No existing workload or cluster-wide configuration is changed.

The extension measures two purpose-built applications, not a representative production fleet. Checkout computes an invoice from quantities and unit prices; document processing normalizes text and computes token counts. Each uses a gateway process, a separate HTTP worker process, and PostgreSQL. Actual OpenTelemetry Python SDK instrumentation exports to Collector Contrib 0.136.0 and Jaeger 1.76.0 using persistent Badger storage. Dependency versions, image digests, exact configurations, process endpoints, and executed-source hashes are retained. No monetary savings or human diagnosis-time claim is planned.

## Matched late-marker experiment

Use a factorial design with early root ERROR marker present/absent and database leaf delivery immediate/five seconds late. Within each early-marker level the entire span content is identical across timing treatments. Decision wait is two seconds. Test cache on/off and buffer churn on/off, 200 seven-span failed traces per treatment. Repeat with three fresh seeds. Keep raw exports, counters, expected input, and trace completeness. These are mechanism experiments with controlled faults, not estimates of production event frequency. Keep and correctly relabel the original six probes.

## Calibration experiment

Use 30 fresh seed blocks with 2,000 five-trace incidents per block, two independent ID constructions (separate Python random stream and SHA-256 of a seed/index), four salts, and both FNV-1a64 and BLAKE2b64 priorities. Incident labels and IDs use separate streams. Background retention is 0.08/0.98, corresponding to the original 10% total budget and 2% protected class. The original discrepancy remains a separately reported exploratory finding.

For every construction/hash/salt cell record the full histogram of 0 through 5 retained witnesses, trace retention, one-witness incident recovery, and block summaries. Compare pooled observed counts to the exact binomial model. Prespecify a family of 16 histogram goodness-of-fit tests with Holm correction at 0.05, merging categories with expected counts below five if needed. Passing a finite test means no detected departure at this sensitivity, not proof of independence. The 30 block means also provide repeatability intervals. Use a common priority function for a paired head versus protected-tail comparison, so this follow-up does not change the hash while changing the policy. Archive source hashes and per-block histograms; no selective reruns.

## Live application experiment

Pilot: test startup, SDK propagation, counter reconciliation, backend retrieval, diagnosis, and resource instrumentation. Pilot outcomes cannot be pooled with the measured study. Freeze source hashes and analysis rules before measured execution. If feasibility requires protocol changes, retain the failed evidence and record the change before proceeding.

Design: two applications, two load regimes (steady and bursty with the same mean offered rate), three policies (full retention, actual SDK head 10%, and protected tail with target 10% expected trace budget), and five seed blocks. Randomize policy order within each application/load/block. Each cell has a warmup excluded from inference and 60 seconds of measured requests, followed by a fixed draining interval. A fresh Collector and Jaeger process/database are used for every cell. Tail buffer is sized to turn over during the run, not to store the whole offered population. Identical seed/input schedules are paired across policies. The pilot sets feasible fixed offered rates before confirmation. Record achieved rate, scheduling delay, failures, and dropped telemetry.

Fault composition is fixed before sampling: 1% SQL schema errors, 1% actual slow database queries, and 1% unflagged domain-invariant violations. Private injection controls are not exported as span names, attributes, events, or request routes. Incident identities are opaque. The tail rule protects ERROR or duration at least 250 milliseconds. Nominal background probability is (0.10-0.02)/0.98. Pilot data must establish whether unintended protected traffic is negligible; if not, freeze a revised rule or budget before confirmation. Report actual protected fractions and realized trace/byte rates in every case, even if they differ from target.

## Diagnostic endpoint

A separately implemented deterministic scorer sees only exported trace content. It receives no injection labels, truth ledger, treatment name, or lookup table from trace IDs to faults. It predicts the failing service and one of three failure mechanisms from SQLSTATE/exception evidence, an abnormally slow database span, or a domain-invariant violation. Missing evidence produces an explicit abstention. The scorer may use partial traces. Normal requests are evaluated for false accusations. This validates a bounded automated task, not general root-cause analysis or human debugging.

Primary endpoint: correct cause-and-service identification per injected failing request, counting missing traces and abstentions as unsuccessful. The full-retention condition establishes diagnostic baseline accuracy, including any errors in the scorer itself. Compare full-trace completeness with diagnostic success to test whether completeness is necessary or sufficient in these tasks. Report false-positive rate on normal requests. Scorer and scoring rules are frozen after pilot and before confirmation.

For selection sensitivity, apply additional rates 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, and 1.00 to the full-retention live exports on homelab, using the documented SDK and tail selection rules. Mark these results as offline counterfactual selection, distinct from executed resource treatments. Also form five-request incident groups within the same cause after fixing group order, and evaluate whether any request yields the correct diagnosis. This directly tests the interchangeable-evidence model on live traces while retaining its explicitly constructed grouping.

Material deterioration is a prespecified absolute decrease greater than five percentage points in diagnosis success relative to full retention. The 95% witness-survival objective remains a separate theoretical risk choice. Report estimated differences and uncertainty. A rate is empirically supported at this margin only if the appropriate upper confidence bound on diagnostic loss is at most 0.05. Do not announce a precise continuous threshold from a discrete tested grid or claim simultaneous coverage from marginal intervals.

## Resource endpoints and statistics

Save exact before/after Linux process CPU snapshots and sampled RSS for application processes, Collector, and Jaeger; include SDK sampling/export work in application measurements. Preserve PostgreSQL process statistics where the shared PID namespace permits reliable accounting. Keep load-generator/controller cost separate. Process CPU sums describe the measured pipeline, not host/kernel cost or provisioned capacity.

Retain OTLP counters, logical export sizes, Badger directory bytes before/after clean shutdown, backend query receipts, and backend-restart query checks. Distinguish logical bytes, allocated file size, and fixed storage overhead. Query measurements occur after the ingestion interval and are separately reported. Report resource ratios paired within seed/application/load blocks, with all five block values and Student-t intervals as descriptive small-sample uncertainty. Inspect temporal RSS behavior and buffer drops; do not infer steady state or saturation from a finite fixed-load run.

Use blocks as the unit for diagnostic and resource uncertainty. Five blocks cannot establish broad deployment diversity. Additional incident-level binomial intervals, if shown, must be identified as conditional model summaries and must not substitute for block uncertainty. All rates and endpoint families remain visible. Prespecified threshold families use simultaneous bounds or a conservative correction. No p-value alone proves practical equivalence.

## Acceptance and preservation

Publish every attempted measured cell and every failure. A cell with transport failure, an unplanned application failure, unmatched backend/export counts, or incomplete baseline evidence is flagged and investigated, not silently omitted. A corrected implementation gets a new run label and prospective amendment. Preserve original archives, exact executed versions, raw counters, truth, queries, classifications, and source hashes. Keep historical CPU endpoint limitations explicit. Fresh data must not be substituted into the original 70-cell results.

Final checks include an independent archive validator, proof checks, source-to-result consistency, primary-source citations, no em dashes in the revised manuscript, compilation, and visual review of every PDF page. Conclusions must follow measured endpoints and retain remaining limits.
