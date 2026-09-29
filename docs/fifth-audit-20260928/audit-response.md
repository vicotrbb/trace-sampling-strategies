# Response to the latest audit

This revision preserves the author, title, article template, nine main sections, conclusion, and earlier evidence. It strengthens the measurement contribution without claiming a new sampling algorithm. The final validation report identifies the delivered PDF and completed checks.

## 1. Cross placement with a substantial export path

The new placement experiment has forty cells in five randomized blocks at 40,000 offered spans/s. Four policies are crossed with JSON-only and JSON-plus-Jaeger export. The pre-ingress and native uniform treatments retain exactly the same IDs. Every treatment is retained in the analysis.

Native uniform selection increases Collector CPU by 3.2% at the JSON-only boundary and reduces it by 24.2% with dual export. Both directions occur in all five blocks. The export-path difference in the native-minus-full contrast is -2.162 CPU-seconds, with a pointwise 95% interval of [-2.390, -1.934]. This is now the abstract's primary quantitative result. The resource-model interpretation appears once next to the result: sampler work exceeds avoided downstream work at the JSON boundary; the added export path reverses that balance for native uniform selection.

Tail still increases Collector CPU in both paths, although its paired penalty falls from 53.9% to 13.9%. Collector-plus-Jaeger process CPU falls substantially for both sampled policies. The paper distinguishes that sum from instrumentation, generator preparation, transport, and fleet-wide cost. Native tracestate adds 44 serialized bytes per retained span, so equal selected IDs do not imply equal bytes.

Evidence: `placement-validation.json`, `placement-contract-validation.json`, and `data/derived/fifth-audit-20260928/placement-summary.json`.

## 2. Repeat retain-all versus bypass at higher offered load

The extension repeats both batch timeouts with dual export and byte-identical SDK-template input in five blocks. The final protocol uses 5,000 spans/s, twenty times the original 250-span/s operating point. The fixed-input figure presents both campaigns with separate horizontal scales. The result text reports both configured contrasts and the batch-counter explanation, without treating the cross-campaign comparison as an isolated rate effect.

The earlier reversal does not persist. Retain-all tail adds 2.024 Collector CPU-seconds at each timeout, with pointwise intervals [1.897, 2.151] at 100 ms and [1.917, 2.131] at 1,000 ms. Every block has the same positive direction. Bypass now sends 1,000 entirely size-triggered batches at either timeout; tail sends 1,200 and 1,154 respectively. The earlier reduction in batch count is absent. Both measured contrasts are reported, including the result that does not preserve the earlier headline.

The execution history is explicit. The initial five-second pilot accepted 20,000 spans/s. The first measured cell then failed backend completion: 1,373,900 successful saves out of 1,400,000 supplied warmup-plus-measured spans. The campaign stopped. Amendment 2 required full-duration pilots at the next predefined rates. A 10,000-span/s pilot passed completion but exceeded the 500 ms scheduling-lag criterion; all four 5,000-span/s treatments passed. The selected rate was frozen before the amended measured campaign. No CPU-effect sign selected the rate, and no incomplete paired block enters the result.

The failed measured attempt remains `batching-confirm-v1`; it has not been relabeled as a pilot. The final archive is `batching-confirm-v2`. All pilot attempts and the separate freezes remain. `exclusion-validation.json` checks the failure reasons directly from counters and receipts. These results establish operating points, not saturation limits.

## 3. Restore the SDK boundary

The main text restores a four-row SDK resource table from the sixty-cell live application study. SDK head sampling reduces gateway-plus-worker CPU by 15.4–18.0% and Collector CPU by 31.3–36.5% across the four application/traffic conditions. These are separate lower-load measurements at fifty requests/s with their own paired intervals. The underlying forty full/head cells were reconstructed from raw process ticks.

The perfect-baseline classifier is not restored as a general diagnostic result. Its original acceptance condition and pipeline-check role remain documented in the technical supplement.

## 4. Make delivery evidence available in the main paper

The grouped matched-probe table and mechanism interpretation are now a main-results subsection. All sixteen factor combinations and three repeats remain represented. The text states the imposed arrival order, two-second decision wait, five-second delayed leaf, and joint churn/capacity intervention. It also retains the separate sixteen-slot burst result. Operator guidance points to this main-text material, not an unpublished proceedings appendix.

## 5. Match RQ4's statistics to its illustrative role

The localization figure and prose report accuracy, paired net loss including gains, and Monte Carlo standard errors. They remove the largest-qualifying-discard paragraph and exact-bound derivation from the active paper. The same 240,000 replay rows are used; no new trials or incident observations are invented.

At 200 requests per window and 20% expected retention, accuracy is 97.72% for head and 92.68% for tail, with MCSEs of 0.21 and 0.37 percentage points. At twenty requests per window and 65% head retention, 260 losses and 139 gains produce net loss 2.42 points and MCSE 0.40 points. All eighty-four accuracy/loss standard errors across forty-two feasible configurations were separately reconstructed.

The original conditional limits and their derivation remain in the artifact as historical, mathematically valid outputs of their fixed-corpus model. Increasing replay count can reduce simulation uncertainty without adding application evidence. The paper does not turn that precision into a production discard guarantee.

## Smaller points and presentation

- The upper-rate load-sweep table is now included, together with the pre-ingress gate saving in prose.
- The active bibliography contains only resolved, cited entries. Removed entries remain in `unused-bibliography.bib`.
- The reader PDF is named `trace-sampling-collector-boundary.pdf`, matching the current title.
- The methods identify automated homelab workloads as the source of archived program observations. AI assistance and author responsibility remain disclosed.
- Repeated caveats have been consolidated. The interpretation distinguishes configured treatment contrasts from universal coefficients once in the discussion.
- “Diagnostic Evidence” remains in the title because the window example and delivery probes are now substantive main-text results, with their distinct endpoints stated.
- The paper preserves the requested template. An internal ACM conversion checks length without replacing the reader manuscript. It is not an anonymized submission artifact.

## Additional correctness checks

The mathematical statement about no universal positive guarantee now explicitly ranges over unbounded numbers of indispensable traces. Little's-law usage states finite means, stationarity, and arrival regularity. The six Lean statements retain their narrow, disclosed scope.

A scope review found that protocol wording about generator/gate CPU was broader than the implementation. Generator CPU measures sending and monitoring only; input preparation and gate hashing are outside its endpoint. The methods and README now state that boundary. No broader gate-cost measurement is claimed.

The final report separates reconstruction checks, source preservation, primary-source review, document verification, and visual inspection. All remain part of the same AI-assisted workflow. Neither checksum agreement nor a passing proof kernel establishes external replication, authenticated preregistration, venue acceptance, or scientific perfection.
