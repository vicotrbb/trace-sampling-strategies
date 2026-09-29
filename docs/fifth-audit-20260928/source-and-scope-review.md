# Source and scope review

Reviewed 28 September 2026 for the active manuscript. This is an internal check in the same AI-assisted workflow, not external peer review.

## Pinned backend completion mechanism

The exact Jaeger v1.76.0 source is preserved with URLs and SHA256 values in `primary-sources/manifest.json`. In `cmd_collector_app_span_processor.go`, construction enables the exporterhelper queue. `ProcessSpans` calls `ConsumeTraces` and can acknowledge queued work; `pushTraces` calls `WriteTraces` and then increments the successful or failed save metric for the spans. The corresponding OTLP receiver, metrics definition, and dependency file are also retained. This supports requiring save counts rather than relying solely on Collector acknowledgments. It does not establish crash durability or the absence of subsequent compaction work. [Pinned source](https://github.com/jaegertracing/jaeger/blob/v1.76.0/cmd/collector/app/span_processor.go).

The first pilot left the successful-save count short at the ending scrape. Its archive is retained. Before measured collection, acceptance was strengthened to exact successful-save equality at both phase endpoints, with zero errors. The repeated pilot selected the highest candidate that passed this stronger rule. `pilot-amendment-1.md` and `endpoint-instrumentation.md` record the sequence. No CPU-effect sign was used to choose a rate.

The first measured batching attempt subsequently failed backend completion at 20,000 spans/s. `batching-amendment-2.md` retains that attempt and extends the next declared lower-rate pilots to the full measured duration. A 10,000-span/s pilot fails pacing; the four 5,000-span/s configurations pass. `batching-execution-freeze-v2.json` records the chosen rate and seventeen source/contract files before the amended measured run. These changes do not alter the already completed forty-cell placement campaign or replace acceptance criteria after observing an effect.

## Retained literature and mathematical scope

The related-work assertions remain at the level checked against primary sources in `../second-audit-20260925/final-source-check.md` and `../fourth-audit-20260928/source-review.md`. Mint, UniSage, and Gleaner retain versioned records, including the actual 2026 date of the read UniSage version. Sieve refers to the 2021 trace sampler whose primary paper was later obtained, not the unrelated 2017 metrics system. Coehlo is the published author spelling. The manuscript claims no measured superiority over these systems.

The active bibliography retains only cited entries. `bibliography-pruning.json` identifies eighteen removed entries and their retained copy. The new Jaeger citation points to the exact implementation. The restored SDK citation points to Python v1.37.0, whose lower-64-bit trace-ID ratio and parent-based semantics correspond to the archived application configuration.

The witness formula requires independent whole-trace inclusion. The no-universal-discard statement now explicitly ranges over populations with unbounded indispensable evidence, avoiding an implicit change from fixed N to unbounded d. Protected-budget accounting follows linearity and does not equate trace and byte budgets. Window nonemptiness is separate from scorer correctness. The cost model has fixed grouping assumptions, which the retain-all intervention can violate. Little's-law usage names finite means, stationarity, and the required arrival regularity. None of these identities identifies a universal production sampling rate.

The former exact loss bound is mathematically valid under its fixed-corpus trial model but unnecessary for the current descriptive role. Its derivation and frozen primary outputs remain in the artifact. The active paired standard error includes negative losses from gains. Repeating randomized masks improves conditional simulation precision without adding independent incidents. The paper makes no future-incident or subgroup certification claim.

## Measurement scope and manuscript form

`measurement-scope-review.md` corrects the protocol's broad generator/gate wording: the observed generator CPU covers sending and monitoring only, while preparation and gate hashing are not timed. The higher-load comparison is a separate operating point with larger state capacity and cloned templates. Its within-campaign contrasts control input bytes; comparing campaigns does not isolate load alone.

The nine main sections, author block, article class, and margins remain. Delivery mechanisms now have a main-text table. SDK resource results are restored without using their perfect-baseline classifier as a diagnostic endpoint. The abstract, results, and conclusion must follow the complete measured contrasts, regardless of whether the earlier reversal persists.

## Venue rules

The current [ICPE 2027 Research Track call](https://icpe2027.spec.org/tracks-and-submissions/research-paper-track/) was read again. EERCS remains a category of the Research Track, with ten ACM double-column pages excluding references and appendices. Appendices are not published; submissions and associated code must be anonymous. Prior arXiv release is allowed subject to those instructions. These facts motivate keeping essential delivery findings in the main text. The retained reader template and an internal layout estimate do not constitute a submission-ready artifact or an acceptance forecast.
