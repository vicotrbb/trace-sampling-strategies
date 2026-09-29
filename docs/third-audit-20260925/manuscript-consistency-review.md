# Manuscript consistency and inference review

This internal review follows the new methods and earlier validated evidence. The runtime and final document receipts in this directory separately establish which checks passed on the delivered snapshot.

## Evidence definitions and mathematical scope

The witness endpoint and localization endpoint are different functions of retained evidence. The witness formula assumes independently retained interchangeable traces with no additional delivery loss. Requiring every indispensable trace instead gives p^d. Increasing incident evidence can therefore change a supported rate even before introducing a classifier. The new window-count statement supplies expected retained counts and empty-window probability, while deliberately providing no unsupported formula for median-ranking accuracy.

Protected-tail accounting concerns expected global trace counts. The protected fraction and background rule imply r < b when alpha>0 and b<1. This lowers unprotected coverage under shared priorities, without requiring equal trace sizes. Budgets below alpha are infeasible if every protected trace must be kept. Actual native hash selections remain deterministic measurements, not iid confidence experiments.

The diagnosis estimand is the difference of expected binary correctness on a uniform draw from a fixed observed corpus. Baseline failures are included and sampling can produce gains. The loss-only upper bound is a sufficient condition for the net-loss objective. Failure to meet it is inconclusive, not proof of unacceptable net deterioration. Independent replay trials produce binomial loss counts under the declared ideal model, even though archive incidents have different conditional difficulty. Shared masks and nested windows need not be independent across comparisons. Separate historical and new comparison families are not combined into a single simultaneous statement.

The new precision calculation was recorded before replay and allows a nonempty passing region. The selected largest discard is taken only from the fixed grid. It does not certify untested rates or monotonicity of scorer accuracy. Absolute full-data and sampled accuracy accompany relative deterioration. Stratum summaries remain descriptive and do not inherit aggregate confidence coverage.

The proofs remain model statements. The existing six Lean results cover only discrete retention identities and evidence preservation. They do not machine-prove statistical coverage, application correctness, or Collector behavior. The manuscript appendix supplies the probability arguments with their assumptions; the archived computation checks support implementation verification.

## Experiment and comparator scope

The original perfect-baseline per-request classifier is a preservation check. The partial-span intervention tests its particular evidence needs, including a truth-selected mask explicitly unavailable to a deployable sampler. The normal-request count reconciles: twenty full corpora of 3,000 requests minus 1,800 faults leaves 58,200 normal requests.

The new task receives known reference/incident windows and a three-service candidate set. Actual HTTP handling timestamps supply leaf durations, while the driver constructs OTLP-format spans. No SDK or Collector processes these localization traces. Root span duration covers all three sequential calls and associated overhead; the per-leaf lognormal median is a different quantity. Cause labels and injection controls remain outside observed span attributes and are unavailable to the scorer. The separate validator reconstructs the complete timing/parent relationship and the injection ledger.

Two six-hundred-incident corpora remain separate. The sensitivity corpus supplies nested prefixes, so its 1,800 window configurations are paired rather than independent incident observations. Shared execution infrastructure may correlate timings; corpus-conditional inference does not require independent observed incidents. A longer window also changes the full-data baseline and may contain more redundant evidence. The main interpretation must show those baselines rather than attributing all changes to sampling strategy.

The healthy-root calibration is disjoint from measured incident seeds. Its rule is frozen before observed fault outcomes. The threshold does not guarantee exactly five percent protected mass in the incident mixture. Calculating the measured protected mass equalizes expected budgets offline and does not imply that an operator knows future traffic composition.

## Resource boundaries

High-load trials measure Collector process CPU and JSON file export, not SDK recording or Jaeger costs. Head-like selection before ingress avoids receiving most spans. The new native probabilistic control receives all spans but selects the same trace IDs as its matched gate. Native sampling also adds tracestate metadata, preventing attribution of the entire paired difference to ingestion alone. The native gate's 14-bit fraction differs slightly from exactly 10 percent; it remains labeled nominal 10 percent with the exact fraction in Methods.

Tail treatment retains full ingress and changes buffering, decision work, grouping, and serialization. Retain-all tail can therefore change CPU and JSON bytes even when span content is preserved. The additive cost model has explicit fixed-work assumptions and does not identify processor overhead from total CPU. Earlier live SDK, backend, storage, and exporter/batching measurements retain their own boundaries.

Pointwise resource intervals use runtime blocks on one shared node, with matching configured inputs and randomized policy order. Five blocks do not prove distributional assumptions, long-run saturation, or fleet-wide effects. Lower-load and higher-load CPU directions must be reported with their pipeline boundaries. File size, memory, serialized bytes, and component CPU are not interchangeable measures of savings.

## Narrative and attribution

RQ1 now concerns delivery and diagnostic evidence; RQ2 concerns visibility and allocation. Results, introduction, model references, and conclusion must follow that numbering. The practical guidance links documented Collector mechanisms to the evidence endpoint and emphasizes measured window counts and class-specific protection.

The paper claims a controlled measurement contribution rather than a new sampler or state-of-the-art superiority. Existing primary-source attributions retain the earlier reviewed scope. The added native-sampler citation is pinned to the implementation directly inspected and archived. The original author, nine main sections, article template, data statement, AI-assistance disclosure, and conclusion remain.
