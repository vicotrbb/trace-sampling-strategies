# Technical and historical supplement

The current article keeps its nine-section structure while moving detailed verification history here. This supplement does not enlarge the scientific claims in the manuscript. Every earlier raw archive and frozen source remains unchanged.

## Earlier diagnosis design and its withdrawal

The original offline classifier curves used five application seed blocks and a declared family of 160 comparisons. The proposed simultaneous Hoeffding radius was

`radius = sqrt(log(160 / 0.05) / (2 * 5)) = 0.898382`.

It exceeded the intended absolute five-point loss margin even at zero observed loss. Consequently that design could not establish the planned objective before any data were collected. The certification claim was withdrawn; the curves remain descriptive. Under that same bound, a radius no greater than 0.05 would need at least 1,615 independent blocks per comparison at zero observed loss. This is not a universal lower bound for other valid designs.

The initial 600-incident HTTP study has a different task and estimand. Its 5,000 independent randomized-replay trials per comparison quantify conditional selection uncertainty over one fixed corpus. They do not repair the earlier design or supply thousands of application replications. The loss-only binomial method accommodates incorrect full-data diagnoses and sampled improvements. Its simultaneous bounds and precision were specified before the measured execution. The pre-freeze design review is `second-audit-20260925/statistical-design-review.md`; the final frozen contract and its hashes are in the same directory.

## Selected 19/100 replay result

At tail budget 10%, background probability is 0.08/0.98. For five interchangeable unprotected witnesses, the binomial reference probability is `1-(1-0.08/0.98)^5 = 0.346746...`. The selected observed recovery is 19/100. Its two-sided reference p-value is 0.000714507, and a retrospective Bonferroni calculation over 130 nondegenerate replay checks gives 0.092886. The family includes 105 head strata and 25 unprotected tail strata. This is exploratory multiplicity context, conditional on the binomial model, not a prespecified confirmatory test.

A separate native FNV implementation reconstructs all thirty original tail selections. Fresh calibration uses thirty seeds, two ID streams, four salts, and two hashes; none of sixteen declared histogram tests rejects after Holm correction. The smallest adjusted p-value is 0.324041. Calibration does not establish independent Bernoulli behavior of a deterministic hash, and exact reconstruction is not a randomness test. Raw IDs and counts remain in `data/raw/revision-20260924/`; results are in `data/derived/revision/calibration-tests.json`.

## Full controlled-export results

`data/derived/final-cost-20260925/cost-summary.json` contains all twelve treatment summaries, eight primary sampler contrasts, and ten interactions, with every paired block value. The 96 measured cells reuse one translated application corpus and measure runtime variation, not independent deployments. The twelve-cell setup pilot is excluded.

`data/derived/final-cost-20260925/serialization-inspection.json` is an explicitly post-collection descriptive inspection. It reconciles measured-phase JSON bytes, resource groups, scope groups, and spans in every raw export. Equal retained span content does not imply equal serialized framing. No compressed wire-byte claim is derived from the JSON mirror.

## Formal and computational scope

The standalone mathematical supplement, `proofs/reference-results.tex` and `output/pdf/trace-sampling-mathematical-supplement.pdf`, proves the witness, window-count, and protected-budget statements under their explicit assumptions. The per-request preservation identity remains in the preserved prior manuscript. The former conditional loss derivation is retained in `fifth-audit-20260928/retained-formal-appendix.tex`. That analysis uses a one-sided exact binomial limit and a union bound: sixteen comparisons in the initial fixed-window study, and forty-eight in the separate window-sensitivity extension. Each family has its own conditional coverage statement. It does not require independence between comparisons, classifier monotonicity, or a perfect baseline. The active paper reports descriptive Monte Carlo standard errors, including gains, instead of qualifying-discard thresholds.

`proofs/TraceSampling.lean` contains six discrete statements about finite retention words, counting, and evidence preservation. It does not formalize the general real-probability formulas, OpenTelemetry implementation, experimental validity, or confidence intervals. `proofs/README.md` gives its exact scope. The latest Lean kernel receipt is in `final-publication-20260928/lean-validation.log`.

The archived homelab computational model check enumerates 32,760 weighted outcome words, 312 binomial cases, 9,840 subset pairs, 3,636 monotonicity comparisons, and 341 budget identities. Its 56 Monte Carlo estimates have maximum absolute error 0.005996. These finite checks are implementation tests, not proofs of general statements. The executed source remains byte-identical to `tests/verify_model.py`.

The previous long manuscript also gives a correlated all-or-none expected-budget comparison and a protected-fault-mixture corollary. They remain valid within their models but are not central claims of the shorter empirical paper. Their exact source is preserved in the archive below.

## Historical manuscript and checks

The earlier 35-page source, paper, reports, and manifest are preserved in `second-audit-20260925/prerevision-source-and-paper.tar.gz`, SHA256 `46c98cc16fdea05e52b67edab12fa8a9bf331aa1329fa88d731aa36f78f72acf`. Its 35-page PDF has SHA256 `774a296b0325829ad2839aedc98c59eb3596085f7d21c699c4e049522c872548`. This is a historical local snapshot, not a public technical-report deposit.

Older protocol freezes, source snapshots, pilot failures, and validation receipts remain in `revision-20260924/` and `final-pass-20260925/`. The current `validation-report.md` describes the delivered revision. Historical reports describe their historical snapshots and should not be read as current status.

Source freezes, checksums, and local timestamps establish the recorded artifact sequence and integrity. They are not independently authenticated preregistration, external replication, or evidence that no unarchived run ever occurred. The original replay omitted exact CPU endpoint snapshots. Later studies retain them. Live Badger stores were removed after successful content and footprint checks, so the artifact retains evidence receipts rather than reopenable database images.

## Fixed-window example and subsequent sensitivity extension

The initial HTTP corpus has twenty reference and twenty incident requests per episode. Full-data accuracy is 568/600. Its frozen 80 ms root-protection threshold includes only 68/24,000 traces, and head/tail outcomes are close. Under its original sixteen-comparison rule, 80% expected retention is the smallest tested qualifying rate. The 20% supported discard is conditional on those window sizes, scorer, observations, policies, and loss-only criterion. It is not carried forward as a general tolerance.

At 65% head retention, 323 loss events and 88 gains across 5,000 trials give 4.70 percentage points of net observed deterioration. The loss-event fraction is 6.46%, with simultaneous upper bound 7.47 points. The bound is conservative because it omits gains, not because the net-loss arithmetic is wrong. A gain-aware procedure might sharpen inference, but the original primary rule was not replaced after inspecting outcomes.

The prospective extension in `third-audit-20260925/protocol.md` collects a separate 600-incident corpus with 200 requests per window and evaluates nested 20/50/200 prefixes. A disjoint healthy calibration supplies the nearest-rank root-duration 95th percentile. All 48 window/policy/budget comparisons remain reported, including infeasible budgets. Dependent prefixes are not new independent incidents. The main article reports the sensitivity results; full trial and stratum data are in `data/derived/third-audit-20260925/diagnosis-summary.json`.

## Preserved 21-page version

The 21-page version, together with its sources, reports, and delivered-file manifest, is preserved in `third-audit-20260925/prerevision-source-and-paper.tar.gz`, SHA256 `310aa931a250cd8bb6ae8ac99243800cd0351f4b752f160dc2c44cc8e4100b72`. Its reader PDF has SHA256 `4641b2673ccc6e03b7f5fffc5546c48ec144e59fe52b6e122b375e5bf65912be`. This is an immutable local history record, not a public deposit. Existing source freezes and raw evidence are rechecked without modification.

## Preserved 22-page version and subsequent scope

The 22-page manuscript, source, reports, and manifest are preserved in `fourth-audit-20260928/prerevision-source-and-paper.tar.gz`, SHA256 `b2a383c3f43baf3c5f3ae11672d8f152d077bb80faee81672337f1971467e636`. Its PDF SHA256 is `c4378423b3d1814ae84fb96137f893363559682d0cc32ada28ebb516445057da`. The subsequent 19-page revision centered on Collector placement, batching/export, and offered load, treating localization as an illustrative example. That revision added no experiments.

The older live classifier's perfect full-retention accuracy was an acceptance requirement. Its sampled aggregate therefore measures pipeline preservation, not independent evidence of general diagnostic capability. Full details and the indicator identity remain in the preserved version and `data/derived/revision/`. The main paper no longer presents that classifier.

Two separate older comparisons both round to 47.9%: the original replay's tail Collector CPU increase and the Documents-S live study's tail Collector CPU saving. They have different baselines, workloads, export paths, and measurement windows. Their identical rounded magnitudes are coincidental. The fixed-input exporter/batching experiment supplies the controlled interaction evidence used by the current paper; the older contrast alone cannot identify a cause.

The complete localization loss/gain tables remain in `data/derived/third-audit-20260925/diagnosis-summary.json` and the generated `paper/window-supported-rows.tex`. The current figure connects accuracy to retained reference and incident counts with conditional Monte Carlo standard errors. The original complete matched-probe table remains in `paper/matched-probe-rows.tex`; its grouped presentation is now in the main results section and groups only combinations whose outcomes agree in every repeat.

## Preserved 19-page version and export-path extension

The preceding 19-page manuscript, source, reports, and manifest are preserved in `fifth-audit-20260928/prerevision-source-and-paper.tar.gz`, SHA256 `af52d62e3e204139552270d8498a46efed540782e1205ddcd4fc65dbf250979d`. Its PDF SHA256 is `71e6fdfaea568e1153a7a6645f87559064a06d2a5a387f64b73af5d0eecf1ef2`. The new protocol crosses placement with export path and adds a higher-load retain-all batching comparison. Its source freeze and excluded-pilot records are under `fifth-audit-20260928/`; the observations are under `data/raw/fifth-audit-20260928/`.

The descriptive localization presentation is an explicit post-collection change. It uses the same replay rows and includes gains in paired loss. It removes the largest-qualifying-discard paragraph because simulation precision on a fixed corpus is not evidence about future incidents. Increasing the number of replay trials reduces Monte Carlo error without adding observed application episodes. All original frozen analyses and the former proof remain available.

The new placement campaign completed forty cells at 40,000 offered spans/s. The original higher-load batching campaign stopped after its first measured cell at 20,000 spans/s failed the final successful-save equality check: Collector reported 1,400,000 exported warmup-plus-measured spans, while Jaeger had recorded 1,373,900 successful saves and no save errors. This is an incomplete measured attempt, not an excluded pilot, and no paired estimate uses it. Its raw files and remaining Badger store are retained in `data/raw/fifth-audit-20260928/batching-confirm-v1/`.

`fifth-audit-20260928/batching-amendment-2.md` prospectively extended subsequent capacity pilots to the full sixty-second input duration, retaining all acceptance thresholds and testing the next declared lower rates. At 10,000 spans/s, backend completion passed but schedule lag reached 697.2 ms, exceeding the 500 ms criterion. All four configurations passed at 5,000 spans/s, which was separately frozen before `batching-confirm-v2`. These attempts describe feasibility under the protocol, not a throughput ceiling. `exclusion-validation.json` reconstructs the recorded failure reasons; no CPU-effect sign determined rate selection.

The live resource comparison is restored without restoring the perfect-baseline classifier as a diagnostic result. Its SDK decision can avoid application instrumentation work; the pre-ingress gate is downstream of span construction. The application and Collector endpoints are reported separately. New experiments and these retained SDK observations do not estimate a total production bill.
