# Primary literature for the second revision

Reviewed 2026-09-25 using public author, publisher, conference, and author-repository sources. Sieve's original author PDF is now available and was read in full. STEAM's full text remains unavailable through the checked routes. MicroRank, TraceRCA, and Spectroscope provide primary grounding for a deliberately simple healthy-reference localization baseline. No manuscript or experiment files were edited, and no workloads were run.

The [literature manifest](/Users/victorbona/Code/Research/trace-sampling-strategies/docs/second-audit-20260925/literature/manifest.json) records request URLs, outcomes, retrieval times, lengths, and SHA-256 hashes. Four PDFs are archived, along with readable derivatives and supporting records. Failed access attempts are retained rather than represented as full-text verification.

## Sieve: full-text grounding now available

**Verified record:** Zicheng Huang, Pengfei Chen, Guangba Yu, Hongyang Chen, and Zibin Zheng. *Sieve: Attention-based Sampling of End-to-End Trace Data in Distributed Microservice Systems*. ICWS 2021, pp. 436-446, DOI [10.1109/ICWS53863.2021.00063](https://doi.org/10.1109/ICWS53863.2021.00063). The [coauthor's publication page](https://yuxiaoba.github.io/publications) explicitly links the [11-page author PDF](https://yuxiaoba.github.io/files/ICWS21/sieve.pdf). Publisher-deposited metadata is archived as `sieve-crossref.json`.

Sections III-IV encode root-to-span paths and latencies into variable-dimensional vectors. An adapted robust random cut forest scores uncommonness; recent scores determine sampling probabilities. Its “attention” is this structural/temporal scoring mechanism, not a neural attention architecture.

Section V evaluates four datasets: a simulated system, an ISP challenge dataset, Online Boutique, and production telecommunications traces. Endpoints include uncommon-trace sampling probabilities, sensitivity, uncommon-trace preservation, API-type representation, retained counts, and sampler latency. It does not evaluate a downstream root-cause localizer or human diagnosis time.

Section V-C's budget comparison stops processing after the budget is exhausted and randomly fills any remaining budget afterward. Section V-D instead matches competing sample sizes to Sieve's realized count. These comparisons are not an unchanged online sampler with an inherent fixed budget. Section V-E times encoding, scoring, and probability calculation, reporting 3-33 ms with twenty trees; it does not establish deployed pipeline CPU savings.

The author PDF's Table VI contains arithmetic inconsistencies: 85/34,167 is approximately 0.249%, not the printed 2.5%; 114/2,000 is 5.7%, not 5.9%. The rendered page is archived. Avoid importing these percentages as verified storage savings. [Original, Sections III-V and Table VI](https://yuxiaoba.github.io/files/ICWS21/sieve.pdf).

**Current manuscript:** the sentence identifying attention-based trace sampling and distinguishing the 2017 metrics Sieve is supported. It can now be strengthened to “Sieve uses structural and temporal uncommonness to bias online trace selection.” No new superiority or diagnosis claim is warranted.

## STEAM: explicitly limited attribution

**Verified record:** Shilin He, Botao Feng, Liqun Li, Xu Zhang, Yu Kang, Qingwei Lin, **Saravan Rajmohan**, and Dongmei Zhang. *STEAM: Observability-Preserving Trace Sampling*. ESEC/FSE 2023 Industry, pp. 1750-1761, DOI [10.1145/3611643.3613881](https://doi.org/10.1145/3611643.3613881). ACM-deposited metadata records publication on 2023-11-30; its full author list and venue are archived in `steam-crossref.json`.

The [authors' Microsoft abstract](https://www.microsoft.com/en-us/research/publication/steam-observability-preserving-trace-sampling/) supports GNN trace representations, logical clauses encoding domain knowledge, and selection emphasizing dissimilar traces. It reports evaluation on four benchmark applications plus a production system. It does not expose the exact evaluation endpoints, baseline configurations, hardware, confidence treatment, or cost boundary needed for a numerical comparison. Its approximately four seconds for 15,000 traces is insufficient to infer end-to-end infrastructure savings.

Access attempts and their limits:

| Route | Observed outcome |
| --- | --- |
| [ACM PDF](https://dl.acm.org/doi/pdf/10.1145/3611643.3613881) | Direct retrieval returned HTTP 403; web retrieval also failed. No PDF was archived. |
| [ACM article](https://dl.acm.org/doi/10.1145/3611643.3613881) and [full-text endpoint](https://dl.acm.org/doi/full/10.1145/3611643.3613881) | Web retrieval errors; no full text was inspected. |
| [Microsoft publication page](https://www.microsoft.com/en-us/research/publication/steam-observability-preserving-trace-sampling/) | Accessible abstract; its publication link points to the same ACM PDF. |
| [First author's publications](https://shilinhe.github.io/publications.html) and [public site repository](https://github.com/ShilinHe/shilinhe.github.io) | Publication listing found; the inspected current repository tree contained no PDF or STEAM file. |
| [Official conference record](https://2023.esec-fse.org/details/fse-2023-industry/22/-Remote-STEAM-Observability-Preserving-Trace-Sampling) | Abstract and DOI available; no independently accessible full paper found. |
| Publisher metadata and an OpenAlex discovery lookup | Returned only the same publisher route. OpenAlex was used for locating a copy, not as evidence for scientific claims. |

These failures establish an access limitation in this review, not a claim that the paper is paywalled or absent elsewhere. No access controls were bypassed and no author was contacted.

**Current manuscript:** retain only explicitly limited attribution, for example: “STEAM's authors describe a sampler that combines learned trace representations and domain constraints to favor informative, dissimilar traces.” Keep the full-text limitation visible in the research provenance. Remove any detailed performance or evaluation comparison unless the full paper becomes available; there is no need to remove this modest, primary-abstract-supported reference.

## Primary grounding for a simple duration-change localizer

**MicroRank, Sections 3-5.** The [original author PDF](https://yuxiaoba.github.io/files/WWW21/microrank.pdf) defines localization from normal/abnormal traces and their operation relationships. Section 4.2 estimates healthy operation handling-time means and standard deviations, then constructs a trace latency threshold from operation counts. Its full localizer adds PageRank and weighted spectrum ranking. Section 5 evaluates latency faults in Hipster-Shop and a production-derived challenge dataset, including simultaneous faults. This is evidence for using healthy timing context and explicit localization endpoints, not for calling a mean-shift ranking algorithm “MicroRank.” The [author repository](https://github.com/IntelligentDDS/MicroRank) also acknowledges broken-trace and intermittent-failure limitations.

The inspected [preprocessing implementation](https://github.com/IntelligentDDS/MicroRank/blob/efd85e8e6f0fad30f6f8aaf0555e3324d8f5f982/preprocess_data.py#L131) subtracts child durations from parents before calculating healthy operation means/SDs. Commit `efd85e8e6f0fad30f6f8aaf0555e3324d8f5f982` is confirmed by the archived branch-reference response. This supports distinguishing inclusive elapsed time from local handling time; it does not prove that naive child-duration subtraction is correct for every asynchronous or overlapping span topology.

**TraceRCA, Section III-A.** The [original laboratory-hosted PDF](https://netman.aiops.org/wp-content/uploads/2021/05/1570705191.pdf) models healthy per-caller/callee feature values with a mean and SD and computes normalized deviations. It combines recent and previous-period references, excluding known faulty intervals. The complete method additionally selects multiple metrics, mines suspicious service sets, and ranks services using abnormal invocation relationships. Section IV uses 222 faults across Train-Ticket and an ISP system, with Top-k accuracy and rank endpoints. Because its features include HTTP status and system-resource metrics as well as latency, a trace-duration-only baseline is not a reproduction of the complete TraceRCA method.

**Spectroscope, Sections 3-5.** The [NSDI 2011 original](https://static.usenix.org/event/nsdi11/tech/full_papers/Sambasivan.pdf) compares request-flow timing and structure between non-problem and problem periods. It groups identically structured requests, computes per-period statistics, and uses distribution tests and critical-path edge comparisons. This establishes prior art for reference-versus-incident trace comparison. A service-level mean-change score is a simpler, newly stipulated experimental endpoint, not an implementation or validation of Spectroscope. [Official conference record](https://www.usenix.org/conference/nsdi11/diagnosing-performance-changes-comparing-request-flows).

## Recommended specification and claim boundary

The following are methodological recommendations for this study, rather than guarantees from the cited papers:

1. Describe the task as **localizing a known incident's affected service from retained traces and a specified healthy reference**. An externally supplied incident window means the experiment does not test incident detection. Specify whether the target is an operation, service, instance, or injected resource.
2. Freeze the candidate set, operation-to-service aggregation, timing definition, and score before examining measured outcomes. A simple possible score is the positive healthy-normalized change, `max(0, mean_incident - mean_healthy) / max(sd_healthy, epsilon)`. Its floor, minimum counts, tie handling, and abstention rule must be specified. This is a ranking score, not a z-test, calibrated confidence, or causal probability.
3. Compare like operations/request types. Different request mixtures can change a service's mean without a local fault. Inclusive durations can make ancestors look slow because they wait for a downstream fault; if local time is used, define how overlapping child intervals and missing children are handled. For concurrent children, subtracting their summed durations can double-count overlap; subtracting their covered-time union is the relevant accounting operation under a compatible timing model.
4. Keep healthy and incident data provenance explicit. A fixed unsampled healthy reference makes the sampling result conditional on that reference being available. If both windows are sampled, evaluate both. An error/latency tail rule can change the observed duration distribution, so unweighted sampled means are not automatically unbiased full-population estimates.
5. Treat insufficient evidence and abstention as reported outcomes. Do not silently drop unsolved incidents from the denominator. Keep fault labels, injected delays, and precomputed correct locations outside the diagnostic input; they belong only in the independent evaluator.
6. Report Top-1 success, coverage/abstention, and paired changes relative to the full-retention baseline across independent incident repetitions. An observed ranking success, an expected success probability, and a confidence bound on that probability are different claims. Do not advertise these results as human diagnosis time, arbitrary-failure recovery, algorithmic novelty, or superiority to the full published localizers.

The manuscript can therefore cite established trace-comparison and localization work while evaluating a transparent baseline chosen for an interpretable sampling experiment. A comparison against every advanced sampler or localizer is unnecessary unless the paper claims competitive algorithmic performance.

## Citation records for the new baseline sources

- Guangba Yu, Pengfei Chen, Hongyang Chen, Zijie Guan, Zicheng Huang, Linxiao Jing, Tianjun Weng, Xinmeng Sun, and Xiaoyun Li. 2021. *MicroRank: End-to-End Latency Issue Localization with Extended Spectrum Analysis in Microservice Environments*. Proceedings of the Web Conference 2021, pp. 3087-3098. DOI [10.1145/3442381.3449905](https://doi.org/10.1145/3442381.3449905). Publisher metadata archived in `microrank-crossref.json`.
- Zeyan Li, Junjie Chen, Rui Jiao, Nengwen Zhao, Zhijun Wang, Shuwei Zhang, Yanjun Wu, Long Jiang, Leiqin Yan, Zikai Wang, Zhekang Chen, Wenchi Zhang, Xiaohui Nie, Kaixin Sui, and Dan Pei. 2021. *Practical Root Cause Localization for Microservice Systems via Trace Analysis*. 2021 IEEE/ACM 29th International Symposium on Quality of Service (IWQOS), pp. 1-10. DOI [10.1109/IWQOS52092.2021.9521340](https://doi.org/10.1109/IWQOS52092.2021.9521340). Publisher metadata archived in `tracerca-crossref.json`.
- Raja R. Sambasivan, Alice X. Zheng, Michael De Rosa, Elie Krevat, Spencer Whitman, Michael Stroucken, William Wang, Lianghong Xu, and Gregory R. Ganger. 2011. *Diagnosing Performance Changes by Comparing Request Flows*. 8th USENIX Symposium on Networked Systems Design and Implementation (NSDI 11). [Official publication record and BibTeX](https://www.usenix.org/conference/nsdi11/diagnosing-performance-changes-comparing-request-flows).
