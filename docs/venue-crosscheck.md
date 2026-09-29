# Publication venue cross-check: SPE and ACM SoCC

Checked 2026-09-23 against official venue/publisher pages and an author-hosted research paper. This is reviewer-readiness advice, not a prediction of acceptance. No experiments were run and no manuscript, data, or checksum manifest was changed.

## Manuscript basis

Read `paper/abstract.tex`, `paper/theory.tex`, and `paper/discussion.tex`. The current contribution is an explicit diagnostic-evidence model, carefully bounded probability and cost arguments, a reproducible comparison of existing head/tail policies, and operational failure probes. The elementary probability results are expressly not claimed as new probability theory. The study has five randomized blocks of fourteen treatments, not seventy independent application environments. It uses synthetic OTLP replay, one topology/load/Collector release, and a file exporter. Its diagnostic endpoint is predefined witness recovery; the 95% target is an explicit risk choice, not a validated threshold for human or automated root-cause performance.

These distinctions should drive venue selection. The mathematical care and reproducibility strengthen validity but do not by themselves establish a novel systems contribution or production generality.

## 1. Software: Practice and Experience (Wiley)

### Published requirements and scope

SPE covers practical software/system design and implementation, including distributed/cloud systems. Its key criterion remains a novel contribution useful to designers or implementers. It explicitly welcomes unique comparative analyses and practical experience with established techniques. An **Experience report** may cover academic as well as industrial environments; **Research Article** is another possible category. Theory should support the practical contribution. The overview describes short communications up to ten pages and substantial articles exceptionally up to forty pages. [Official aims, scope, and article categories](https://onlinelibrary.wiley.com/page/journal/1097024x/homepage/productinformation.html).

The current author page offers **free-format initial submission**, a Research Exchange portal, consistent references, and the normal research sections. It recommends Wiley's NJD LaTeX template if a template is needed, rather than requiring the current paper to adopt a specific conference layout. Its instructions include an ORCID and applicable integrity/data/funding disclosures, and encourage a cover letter identifying the relevant scope topic. The page warns that out-of-scope submissions are often rejected before review. [Official author guidelines](https://onlinelibrary.wiley.com/page/journal/1097024x/homepage/forauthors.html).

**Availability:** The ordinary submission route is available; no general submission deadline is stated in those guidelines. This is a regular-journal route, not a claim that a currently advertised special issue fits this manuscript. The live author page contains some legacy instructions alongside the newer free-format/Research Exchange directions; confirm upload details at submission.

### Assessment and recommended changes, our advice

**Most realistic of these two venues.** The current comparative engineering study and reproducibility package fit an experience report better than a claim of a new sampling algorithm. Nevertheless, SPE still expects a useful original contribution. Repeating the familiar fact that tail policies retain known errors, or that collectors must ingest traces before tail decisions, would be insufficient.

The publishable center should be the measured relationship among explicit diagnostic objectives, policy blind spots, and the complete operational cost boundary. Strengthen it with live instrumented applications and reproducible injected failures, then show whether the predefined witness criterion predicts independently scored diagnosis success. Add an actual tracing backend, longer repeated runs, a load sweep, and varied trace sizes/durations; these address the current mismatch between an infrastructure-savings RQ and file-export/Collector-only evidence. A sharply scoped, genuinely new empirical finding could be enough without inventing a sampler.

These experiments are reviewer-readiness advice, **not formal SPE requirements for a particular number of systems, machines, or trials**. A homelab is acceptable as an environment; realism, task validity, measurement precision, and generalization matter more than its label.

## 2. ACM Symposium on Cloud Computing (SoCC)

### Published requirements and scope

SoCC 2026 explicitly includes tracing/monitoring systems and cloud reliability. Full research papers allow **12 pages plus references** and emphasize novelty. Short research papers allow **6 pages plus references**, but retain the same standards and must evaluate a complete idea. Industry papers permit 12 pages, require at least one non-academic/industry-affiliated author, and concern industrial advances or real-world applications. Vision papers are a different, speculative contribution type. The CFP evaluates originality, technical merit, relevance, community value, and discussion potential. It requires ACM `sigconf, review, anonymous` formatting, 9-point text, and dual-anonymous research submissions. [Official SoCC 2026 CFP](https://acmsocc.org/2026/papers.html).

**Availability:** The final 2026 paper deadline was **July 14, 2026 AoE**; notifications are September 26 and the conference November 18–20 in Singapore. Thus it is closed to a new paper as of this check. No verified 2027 CFP was located; future dates and unchanged categories must not be assumed. [Official SoCC 2026 CFP](https://acmsocc.org/2026/papers.html).

### Assessment and recommended changes, our advice

**Strong topical fit, substantial stretch for this manuscript.** Do not recommend immediate submission of the current version as a competitive full research paper. A short paper is not a lower novelty or evaluation bar, and the homelab study should not be relabeled an industrial deployment merely to use the industry category.

A future SoCC submission would need a clearly differentiated contribution: for example, a new diagnosis-aware policy with implementable guarantees, or a surprising and broadly demonstrated systems finding that changes how existing sampling systems should be designed. A new algorithm is not a formal prerequisite, but existing head/tail mechanics plus elementary probability are a weak novelty claim.

The convincing evaluation would compare relevant adaptive/diversity-aware policies on the same diagnostic tasks and budgets; test several application/workload families, fault types and workload changes; stress late/out-of-order spans, bursts, routing and overload; and measure application, collector, network, and backend costs. An independent root-cause scorer or a suitably designed human study could validate the diagnosis endpoint. Which comparison is meaningful depends on the actual claimed contribution; implementing every prior sampler is not automatically required.

These are proposed ways to meet the research bar, **not CFP-mandated experimental counts or a demand for access to a commercial production fleet**. All added experiments can remain on the authorized homelab.

## Prior work that raises the novelty burden

**Sifter, SoCC 2019**, is direct venue precedent: it introduced a biased trace sampler, compared against alternatives, and used HDFS/YARN/Spark, DeathStar and production traces. Its Section 2 already explains the head/tail cost boundary and the tradeoff between uniform sampling and preferential retention of unusual traces. Consequently, neither the existence of that tradeoff nor trace-volume reduction alone is a fresh SoCC contribution. Sifter does not make the present exact experimental findings redundant, but the paper must identify what useful new understanding those findings add. [Author-hosted Sifter paper](https://jonathanmace.github.io/papers/lascasas2019sifter.pdf), [official SoCC 2019 accepted papers](https://acmsocc.org/2019/accepted-papers.html).

## Position for the consolidated recommendation

Recommend SPE as the journal option for a stronger practical comparative study; describe SoCC as a future stretch target conditional on substantial novelty and evaluation work. The original twenty-two-page template is an artifact format, not compliance with a venue's page limit: reformat and recount before submission. This note does not establish worldwide novelty and gives no acceptance probability.
