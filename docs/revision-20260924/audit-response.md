# Response to the scientific audit

This revision preserves the original raw evidence, corrects the confirmed errors, extends the study prospectively, and narrows claims that the evidence cannot support. The exact completed validations and final experimental counts are recorded in `../validation-report.md`; a proposed extension is not itself evidence of success.

## 1. Confounded original late-span description

The original intervention both removes the early root ERROR marker and delays the database ERROR leaf. The method, results, probe interpretation, and artifact descriptions now say so. Original counts and inputs remain unchanged. A separate 48-cell design crosses early marker placement, delivery timing, decision caching, and buffer churn over three fresh seeds. Matched payload hashes ensure identical span content within timing comparisons. The original result is no longer described as an isolated timing effect.

## 2. Calibration and native hash differences

The original semantic-tail result of 19 recovered incidents out of 100 remains prominent, along with the ideal prediction and Wilson interval. Exact FNV agreement establishes which implementation decisions were made; it does not establish independent Bernoulli calibration. The extension uses thirty fresh seed blocks, two ID constructions, two hashes, four salts, all 0-through-5 histograms, and sixteen prespecified Holm-adjusted goodness-of-fit comparisons. Both native priorities and a separate shared-priority control are retained. Finite tests cannot prove independence or conclusively explain the historical realization.

## 3. Diagnostic usefulness and material deterioration

The original complete-witness predicate remains a stipulated evidence contract. The extension adds actual SDK-instrumented requests, database operations, and a fixed trace-only classifier with no access to injection labels, request controls, policy names, or ground-truth lookups. Every offered failing request remains in the accuracy denominator. Normal requests quantify false accusations. Independent classification and partial-span ablations test whether the fixed task needs a complete trace.

The service label means the predefined operation location. An undefined-relation SQLSTATE does not distinguish an incorrect client query from a missing schema object. The revised paper therefore does not equate its bounded failure-family/operation-location endpoint with discovering arbitrary root causes or expert diagnosis. Its five-request groups remain constructed evidence groups.

Material deterioration is prospectively defined as more than five percentage points of absolute loss. The ten-rate offline curves are explicitly conditional selection experiments, not additional online resource measurements. The prespecified 160-comparison simultaneous bound has radius 0.898382 with five blocks and cannot certify a nontrivial sampled rate at the 0.05 margin. This limitation is stated directly, rather than using a favorable point estimate or a nonsignificant test as an equivalence claim.

## 4. Resource boundaries and sustained operation

The original percentages remain Collector/file measurements and retain the omission of head-gate CPU. The extension records exact application, Collector, and Jaeger process CPU endpoints, the PostgreSQL container cgroup, component RSS, controller work, throttling, schedule lag, request latency, exported bytes, and Badger logical and allocated file sizes. Complete backend queries are checked before and after clean restart. The live CPU interval contains the measured schedule and drain; storage receipts include warmup and measurement. File-mirror and measurement-helper overheads are disclosed.

Sixty-second schedules and steady/bursty arrivals provide longer operation and buffer turnover. They do not constitute a mean-load sweep, capacity study, stationary memory proof, long-term compaction experiment, replicated storage evaluation, or deployment diversity. Comparisons use expected trace budgets and report byte outcomes; they are not presented as equal-byte-budget experiments. No monetary, energy, physical-network, human-time, or production-capacity saving is invented. Fresh-store database images are removed after restart validation, so archived queries and file-stat receipts do not allow independent reopening of an archived storage image.

## 5. Prior work and novelty

The revision disambiguates the trace-sampling Sieve (ICWS 2021) from the metrics-oriented Sieve (Middleware 2017), and adds STEAM, TraStrainer, the 2012 aggregate-uncertainty paper, and a 2026 tracing-overhead benchmark. It compares objectives, evaluation tasks, native versus repaired budgets, and measurement boundaries. Sifter and Hindsight already cover important utility and cost tradeoffs. The article claims an auditable methodological connection and bounded baseline evaluation, not a new sampler, new elementary probability theory, priority for diagnostic evaluation, or superiority to advanced methods. Access limitations for Sieve and STEAM full texts are retained in the source review.

## 6. Independent validation and provenance

The original archive validator no longer imports the generator's selection or diagnostic functions. It reparses both metric snapshots, reconstructs selections and witness predicates, and requires all 132 unique incidents in every main cell. Adversarial checks reject missing/duplicate incidents and changed raw counters. Exact historical CPU endpoints were never archived and cannot be reconstructed retrospectively; the paper says so.

New validators separately reconstruct SDK decisions and parent propagation, every request outcome, trace-only predictions, raw CPU counters, exported and stored span identities, parent links, attributes, durations, and calibration/offline decisions. Eight additional corruption checks cover omitted outcomes, false predictions, inconsistent CPU, changed counters, duplicate backend spans, changed backend content, changed source, and leaked injection controls. The final source freeze precedes measured execution; pilots and their adjustments remain separate. The exact upstream probability source was also retrieved successfully and matches the original archived file byte for byte, resolving the audit's source-identity access gap.

Local hashes establish content identity, not an independently authenticated preregistration timestamp. The delivered archive documents retained attempts but cannot logically prove that no unarchived execution ever occurred. These provenance limits remain explicit.

## 7. Mathematical domain and formal scope

The singleton averaging theorem now requires N >= 1. The independent-rate impossibility explicitly ranges over unbounded finite population sizes. A separate fixed-classifier proposition states the unchanged-content and abstention conditions required to connect trace selection with task accuracy. The cost model includes both head and tail decision overhead. An appendix gives the simultaneous confidence-bound derivation and its assumptions.

The Lean artifact remains exactly a six-statement discrete core. Its successful kernel check is not described as formal verification of the real-valued probability space, entire paper, classifier, statistical coverage, or telemetry implementation. Computational enumeration supplies additional finite checks, not general proofs.

## Remaining scientific limits

The revised work can be assessed as a bounded empirical and methodological study. Representative production incidents, unfamiliar diagnostic tasks, human evaluation, multiple deployments, a sustained load/capacity sweep, distributed durability, and comparisons with advanced samplers remain outside its evidence. The manuscript's title and RQs motivate those operational questions, while its definitions, endpoints, results, discussion, and conclusion specify the part actually answered. Neither this revision nor an internal validation report can guarantee perfection, novelty, peer-review acceptance, or production transfer.
