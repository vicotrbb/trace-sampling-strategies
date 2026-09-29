# Response to the second external audit

This revision addresses the audit's scientific and presentation concerns by changing the evidence and the argument. It does not treat successful internal validation as a guarantee of acceptance or novelty. The original template, author, and nine main sections remain; historical raw observations and frozen sources are preserved.

## Cost measurements at meaningful load

The completed design crosses four rates, from 250 to 100,000 offered spans/s, with full retention, head 10%, tail 10%, and retain-all tail in five randomized blocks. The upper rate was selected by a predefined resource-pressure and delivery pilot, before the measured source freeze. It was not selected from favorable sampler contrasts. The eighty-cell campaign completed at 2026-09-25T15:10:39Z; the separate validator reconstructs all 57,855,375 exported spans including warmup, with no recorded CPU throttling, early drop, refusal, or failed export.

At 100,000 offered spans/s, the full control uses 14.004 CPU-seconds, or 40.0% of one core over the nominal 35-second window. Head 10% saves 82.2% across paired blocks; tail 10% increases CPU by 59.1% while reducing JSON by 89.1%. Retain-all tail increases CPU by 90.1%. Every upper-rate block has these respective directions. The abstract now leads its resource evidence with this measured tradeoff, rather than the earlier 0.17-second low-load reversal.

The new boundary is Collector process cost with JSON file export. Generator CPU and SDK recording are outside it. CPU endpoints, planned ingress, send receipts, complete exports, early drops, failed sends, sampled RSS, and serialization are checked separately. The paper does not extrapolate this boundary to high-load Jaeger or claim saturation capacity. The old 250-span/s exporter experiment remains a low-load configuration intervention and is no longer the main resource claim.

## A diagnostic task beyond retention arithmetic

The new observed corpus has 600 incidents, forty requests per incident, and three possible delayed leaf services. Real HTTP handling times supply the evidence. A frozen median-change scorer compares healthy-reference and incident windows, both of which are sampled. Its full-data accuracy is 568/600, and all 32 errors remain in the analysis. Correctness was not an execution acceptance condition. The scorer receives no injection parameters or truth labels.

The earlier per-request classifier is retained only as a preservation check and a basis for the partial-span intervention. Its aggregate sampled accuracy cannot establish general diagnostic effectiveness, and the article says so explicitly. The new scorer can change its ranking when individual traces are removed, even when both windows remain nonempty.

## A distinct, attainable RQ4

The new RQ4 concerns expected accuracy loss conditional on this frozen corpus, scorer, and ideal randomized-replay law. It is distinct from the one-witness probability in RQ1. Five thousand trials per comparison draw incidents uniformly with replacement and use fresh per-trace priorities. Sixteen prespecified policy/budget comparisons share the draws; the union-bound procedure does not require independence between comparisons.

The loss-only construction accommodates both full-data errors and sampling-induced improvements. Exact one-sided binomial upper limits, with error allocation 0.05/16, conservatively bound net deterioration. Its finite-sample precision was checked before collection: zero losses give an upper limit near 0.001153, and up to 208/5,000 harmful changes can meet the declared five-point objective. The old infeasible Hoeffding design remains withdrawn and is not pooled with the new estimand.

At 80% expected retention, head and tail achieve 92.10% and 92.02% replay accuracy, with simultaneous conditional upper loss limits of 4.53 and 4.60 percentage points. Both meet the objective. At 65%, the upper limits are 7.47 and 7.45 points, so favorable point estimates do not suffice. Twenty percent is the largest tested discard supported by this bound. It is neither a continuous threshold nor a future-production guarantee. Replay trials are not additional application incidents. All rates, losses, gains, abstentions, and descriptive workload strata remain available.

## A scientific argument with a narrower scope

The title now reads *How Much Can We Sample? A Controlled Study of Head and Tail Sampling with OpenTelemetry*. The introduction identifies delivery, allocation, resource boundaries, and the explicit localization task. The results lead with matched late-evidence probes. Elementary probability provides reference assumptions rather than a novelty claim.

Historical calibration detail, the withdrawn design, Lean scope, and the reproduction guide move to the artifact and technical supplement. The main formal section gives short statements; a concise appendix supplies the self-contained proofs. The 19/100 discrepancy receives its adjusted value and a brief interpretation, rather than an extended anomaly narrative. Repeated qualifications are consolidated in the discussion. The corroboration model is explicitly optional and is not presented as an observed human diagnostic requirement.

The requested single-column template remains, with the complete manuscript reduced from 35 to 21 pages. This is not yet an anonymized ACM submission layout. The venue note distinguishes ICPE's ten-page double-column requirement from this artifact's formatting, and correctly identifies EERCS as part of its Research Track. No venue acceptance or competitive superiority over advanced samplers is claimed.

## Literature and validation terminology

Sieve's original full text was obtained and read. MicroRank, TraceRCA, Spectroscope, and the original Clopper-Pearson treatment support the new task and inference discussion. STEAM is omitted from the active article rather than cited beyond the evidence read. The primary-source review and final attribution check are retained beside the protocol.

Checks are called separate reimplementations or internal validation. They are not described as independent investigators or external replication. The six Lean statements retain their exact restricted scope in the artifact and no longer carry the paper's contribution. AI assistance remains disclosed. No em dashes are used in the active manuscript.

## Verification record

The original, live, matched-probe, calibration, ablation, and controlled-export archives and the six Lean statements pass renewed checks. The diagnosis validator reconstructs all 80,000 replay rows; a separate binomial-tail inversion checks the analysis's beta-quantile limits. Ten deliberate corruptions are rejected. Additional post-freeze contract checks verify the immutable design, source copies, injected-delay ledger, and copy checksums without changing the measured experiment or prospective analysis.

The final validation report records the completed load validation, final PDF inspection, raw-evidence preservation, and homelab cleanup. It links the retained receipts so these checks can be inspected separately from the manuscript's scientific interpretation.
