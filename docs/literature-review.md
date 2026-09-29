# Literature and source verification

For **How Much Can We Sample? Evaluating Trace Sampling Strategies for Production Observability**. Verified on 23 September 2026. Citation keys refer to `paper/references.bib`.

This is a focused primary-source review, not a systematic literature review. It distinguishes peer-reviewed results, a production technical report, normative specifications, implementation documentation, and mathematical foundations. It supplies grounding and boundaries for the study; it does not establish novelty, experimental outcomes, or publication acceptance.

## Evidence boundaries for the four research questions

| Question | Defensible claim and required evidence | Primary grounding |
| --- | --- | --- |
| RQ1: rate and failure visibility | Derive inclusion and incident-witness probabilities under a declared probability model. Validate the implementation against known input/output trace IDs. The number of requests containing a useful witness, the time window, and any required corroboration must be stated. A representative aggregate sample does not automatically preserve a singleton failure. | [Dapper](https://research.google.com/archive/papers/dapper-2010-1.pdf), [Sifter](https://vaastavanand.com/assets/pdf/lascasas2019sifter.pdf), [Hindsight](https://www.usenix.org/conference/nsdi23/presentation/zhang-lei). |
| RQ2: head versus tail | Compare strategies at a common expected or measured budget, with a precise meaning of diagnostic usefulness. Content-aware selection can favor recognizable problems; its results do not establish superiority for unrecognized failures. Causal completeness and policy-visible symptoms are separate properties. | [OpenTelemetry sampling](https://opentelemetry.io/docs/concepts/sampling/), [Pivot Tracing](https://cs.brown.edu/~rfonseca/pubs/mace15pivot.pdf), [TracePicker](https://doi.org/10.1145/3729351). |
| RQ3: infrastructure savings | Separate application instrumentation, ingress, sampler processing/buffering, export, and backend work. Measure process CPU, sampled RSS and serialized bytes independently. Export byte savings alone do not establish deployed storage, cluster, energy, or monetary savings. | [Hindsight](https://www.usenix.org/conference/nsdi23/presentation/zhang-lei), [versioned Collector source](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.136.0/processor/tailsamplingprocessor/README.md), [Little](https://pubsonline.informs.org/doi/abs/10.1287/opre.9.3.383). |
| RQ4: material deterioration | State an operational loss criterion before evaluating it. A mathematical retention guarantee is conditional on witness frequency, independence and delivery assumptions; a synthetic witness task is a proxy for diagnosis. A universal safe discard percentage requires assumptions that cannot be supplied by a homelab experiment alone. | [X-Trace, discussion of evaluation](https://www.usenix.org/legacy/events/nsdi07/tech/full_papers/fonseca/fonseca.pdf), [Canopy](https://cs.brown.edu/people/jcmace/papers/kaldor2017canopy.pdf), [Wilson/NIST intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). |

The analytical expressions and impossibility argument proposed below are deductions for this manuscript, not results attributed to these systems papers. The papers motivate which distinctions the model must preserve.

## Directly relevant research

### Dapper, `sigelman2010dapper`

Sigelman and colleagues, **Dapper, a Large-Scale Distributed Systems Tracing Infrastructure**, Google technical report dapper-2010-1, April 2010. This is an influential first-party production report, not a peer-reviewed conference paper. It documents low-overhead, continuous tracing with sampling and discusses the usefulness of sparse samples for common tasks. It supports the motivation for sampling and the historical design lineage; its deployment observations are not a universal lower bound on the rate necessary for rare-failure diagnosis. [Google paper](https://research.google.com/archive/papers/dapper-2010-1.pdf).

### X-Trace, `fonseca2007xtrace`

Fonseca, Porter, Katz, Shenker and Stoica, **X-Trace: A Pervasive Network Tracing Framework**, NSDI 2007, pp. 271–284. It reconstructs causally connected task trees and discusses report loss and coherent request-level sampling. Its discussion explicitly separates demonstrated diagnostic scenarios from measuring whether people diagnose problems faster. This is a useful precedent for calling the current endpoint “witness recovery” unless a human or independently validated diagnostic procedure is evaluated. [USENIX proceedings PDF](https://www.usenix.org/legacy/events/nsdi07/tech/full_papers/fonseca/fonseca.pdf).

Bibliographic correction: the current USENIX landing-page BibTeX omits Ion Stoica, but the published PDF lists him. The bibliography follows the paper itself.

### Pivot Tracing, `mace2015pivot`

Mace, Roelke and Fonseca, **Pivot Tracing: Dynamic Causal Monitoring for Distributed Systems**, SOSP 2015, pp. 378–393, DOI `10.1145/2815400.2815415`. Dynamic instrumentation and happened-before joins support cross-component diagnostic queries. This grounds why causally connected information can matter more than counting error-tagged traces. It is not an evaluation of head versus tail sampling or a guarantee that every retained trace enables diagnosis. [Author manuscript](https://cs.brown.edu/~rfonseca/pubs/mace15pivot.pdf).

### Canopy, `kaldor2017canopy`

Kaldor and colleagues, **Canopy: An End-to-End Performance Tracing and Analysis System**, SOSP 2017, pp. 34–50, DOI `10.1145/3132747.3132749`. It supports user-customized sampling, derived features and exploratory performance analysis. Section 4.1 distinguishes rate limits from user-directed probability/rate policies; Section 4.2 addresses delayed or missing events. Its diagnostic workflows include hypothesis formation and aggregates, so retaining an anomalous trace is only one part of useful diagnosis. Canopy is a production architecture and experience study, not a controlled evaluation of the present policies. [Author manuscript](https://cs.brown.edu/people/jcmace/papers/kaldor2017canopy.pdf).

### Sifter, `lascasas2019sifter`

Las-Casas, Papakerashvili, Anand and Mace, **Sifter: Scalable Sampling for Distributed Traces, without Feature Engineering**, SoCC 2019, pp. 312–324, DOI `10.1145/3357223.3362736`. Sifter learns a compact model of common trace behavior and favors poorly represented executions. It directly establishes that utility-aware trace sampling predates this study. A simple error/latency policy comparison does not evaluate Sifter, nor establish superiority over learned or diversity-oriented samplers. [Author manuscript](https://vaastavanand.com/assets/pdf/lascasas2019sifter.pdf), [first-party publication record](https://www.microsoft.com/en-us/research/publication/sifter-scalable-sampling-for-distributed-traces-without-feature-engineering/).

### Hindsight, `Hindsight2023`

Zhang, Xie, Anand, Vigfusson and Mace, **The Benefit of Hindsight: Tracing Edge-Cases in Distributed Systems**, NSDI 2023, pp. 321–339. Hindsight introduces retroactive retrieval from locally buffered tracing data when a programmatically detectable symptom triggers collection. Its relevance is architectural: centralized tail sampling and retroactive sampling have different ingestion costs. The current replay experiment should not claim that its centralized Collector costs apply to all methods that decide after execution. Hindsight also depends on detectable triggers and retained local history; it is not an oracle for every unknown failure. [USENIX publication and BibTeX](https://www.usenix.org/conference/nsdi23/presentation/zhang-lei), [paper](https://www.usenix.org/system/files/nsdi23-zhang-lei.pdf).

### TracePicker, `xie2025tracepicker`

Xie, Wang, Li, Chen, Xuan and Li, **TracePicker: Optimization-Based Trace Sampling for Microservice-Based Systems**, Proceedings of the ACM on Software Engineering 2(FSE), article FSE081, pp. 1802–1823, 2025, DOI `10.1145/3729351`. It evaluates multiple aspects of sampling quality and combines anomaly retention with allocation and group selection for normal traces. This recent work supports evaluating sample-set characteristics beyond anomaly recall. Our witness-oriented mechanism study would complement that objective, but a comparison restricted to head and fixed-rule tail policies cannot rank TracePicker. [ACM publisher article](https://doi.org/10.1145/3729351), [authors' replication repository](https://github.com/WHU-AISE/TracePicker).

### Scope exclusions

Sieve is relevant to reducing monitoring data in general, but the verified Middleware 2017 work is **Sieve: Actionable Insights from Monitored Metrics in Distributed Systems**: its units are monitored metric time series and inferred dependencies, not trace-retention decisions. It should not be described as a head/tail trace sampler or used to transfer its resource-reduction percentages to this study. [Authors' project](https://sieve-microservices.github.io/), [paper](https://sieve-microservices.github.io/assets/sieve-middleware-2017.pdf). A full survey of recent learned, span-level and streaming samplers is outside this focused baseline comparison; do not advertise exhaustive coverage.

## Standards and implementation facts

### Definitions, `otelSampling`

OpenTelemetry defines head sampling as deciding early without inspecting the whole trace and tail sampling as using all or most spans. Its examples include error, latency and attribute policies; it also describes the operational burden of stateful tail samplers. These definitions support an architecture-specific comparison, not the assertion that every head policy is uniform or that every tail policy is better. [Official concepts documentation](https://opentelemetry.io/docs/concepts/sampling/).

### SDK decisions and propagation, `OTelSamplingSpec`, `W3CTraceContext`

The SDK specification distinguishes `DROP`, `RECORD_ONLY` and `RECORD_AND_SAMPLE`; recording and export are not interchangeable. `ParentBased` delegates root decisions and respects the appropriate parent case. Current documentation warns about cross-SDK compatibility of `TraceIdRatioBased`; its exact algorithm was not completely specified. An upstream replay filter should therefore be documented as the implemented model, not as a benchmark of application SDK overhead. [Tracing SDK](https://opentelemetry.io/docs/specs/otel/trace/sdk/).

The W3C Trace Context Recommendation specifies trace identity, propagation and a sampled flag. Section 4.3 explicitly states that setting that flag does not guarantee recording. A complete-trace theorem needs assumptions about instrumentation, routing, delivery, retention and reconstruction in addition to sampling consistency. [W3C Recommendation, 23 November 2021](https://www.w3.org/TR/2021/REC-trace-context-1-20211123/).

### Probability attribution, `otelProbabilitySampling`

The current development specification describes randomness, rejection thresholds and adjusted counts equal to inverse inclusion probability. Unknown sampling probabilities must not be represented as known thresholds. Shared randomness across stages matters: independent Bernoulli filtering has multiplicative inclusion probabilities, whereas nested consistent thresholds can yield the minimum rate. Use the actual conditional inclusion probability in the paper; do not multiply nominal configuration percentages automatically. This living development specification provides terminology and a contemporary design, not a claim that the older evaluated Collector implements it. [Official probability-sampling specification](https://opentelemetry.io/docs/specs/otel/trace/tracestate-probability-sampling/).

### Evaluated Collector source, `otelTailSampling0136`

The selected **distribution** is v0.136.0. Its official builder manifest pins the `tailsamplingprocessor` **module** to v0.136.0. The bibliography links that exact source version. Earlier candidate versions were superseded before the main experiment; the protocol amendment is the record of that choice. [Distribution manifest](https://github.com/open-telemetry/opentelemetry-collector-releases/blob/v0.136.0/distributions/otelcol-contrib/manifest.yaml), [versioned processor README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.136.0/processor/tailsamplingprocessor/README.md).

That version groups spans by trace ID, requires a trace to reach the same Collector, and times decisions from the first observed span. `num_traces` limits buffered trace count; overflow can remove traces before evaluation. Late spans may inherit an existing decision or be evaluated again after its eviction; decision caches change that behavior. `latency` measures the interval between the earliest start and latest end observed, not necessarily critical-path service time. These are concrete reasons to separate selection error from delivery/buffer loss. [Versioned implementation documentation](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.136.0/processor/tailsamplingprocessor/README.md).

The current `main` README also describes a newer `span-ingest` strategy, so do not generalize this older implementation's decision timing to every contemporary tail sampler. [Current source documentation](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/tailsamplingprocessor/README.md).

### Jaeger, `jaegerSampling211`

Version 2.11 documentation distinguishes head/tail sampling and describes remotely configured, adaptive sampling for service/endpoint targets. This establishes that adaptive head sampling is a relevant additional alternative, beyond a single global fixed rate. It does not turn a Collector-only replay into a Jaeger storage benchmark. The citation is intentionally versioned and is not a claim that 2.11 is the latest release. [Official versioned documentation](https://www.jaegertracing.io/docs/2.11/architecture/sampling/).

## Mathematical and statistical foundations

### Inclusion probabilities, `HorvitzThompson1952`

Horvitz and Thompson, JASA 47(260):663–685 (1952), DOI `10.1080/01621459.1952.10483446`, establish estimation with unequal inclusion probabilities. For a finite population with known positive probabilities, the manuscript can derive unbiasedness of the total estimator `sum(I_i y_i / pi_i)` directly by linearity of expectation. Positive inclusion and probability knowledge are essential; a deterministic policy with zero chance of retaining a class cannot reconstruct that class's unseen values by reweighting. A ratio estimator for a mean is not automatically exactly unbiased. [Publisher](https://www.tandfonline.com/doi/abs/10.1080/01621459.1952.10483446), [scan of the original article](https://www.stat.cmu.edu/~brian/905-2008/papers/Horvitz-Thompson-1952-jasa.pdf).

### Wilson intervals, `wilson1927probable`, `nistProportionIntervals`

Wilson's original article is JASA 22(158):209–212 (1927), DOI `10.1080/01621459.1927.10502953`. NIST documents score-test inversion and distinguishes Wilson from adjusted Wald intervals. For `x` successes among `n` independent Bernoulli trials, use `p_hat=x/n`, denominator `1+z^2/n`, center `(p_hat+z^2/(2n))/(1+z^2/n)`, and half-width `z*sqrt(p_hat*(1-p_hat)/n+z^2/(4*n^2))/(1+z^2/n)`. Report `n` and the independent unit; spans within the same incident are not independent incident trials. [Original article DOI](https://doi.org/10.1080/01621459.1927.10502953), [NIST method](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

Wilson intervals are approximate confidence procedures, not universal probability bounds or proofs of real-world diagnostic performance. Stratifying on witness count and fault class makes the estimand more explicit. Correlation between repeated observations, treatment comparisons and selection among many candidate rates needs separate treatment; marginal 95% intervals do not imply a simultaneous 95% guarantee for an entire frontier. These are methodological consequences to state, rather than extra experimental findings.

### Exact binomial coverage, `clopper1934confidence`

Clopper and Pearson, Biometrika 26(4):404–413 (1934), DOI `10.1093/biomet/26.4.404`, are the original reference for exact binomial confidence limits. The R statistical software's own documentation identifies its implementation and explains its at-least-nominal coverage. This is an alternative when conservative binomial coverage is required, not the interval method currently specified for the main experiment. [Publisher record](https://academic.oup.com/biomet/article/26/4/404/291538), [R implementation documentation](https://www.stat.ethz.ch/R-manual/R-devel/library/stats/html/binom.test.html).

### Concentration, `hoeffding1963probability`

Hoeffding, JASA 58(301):13–30 (1963), DOI `10.1080/01621459.1963.10500830`, derives concentration bounds for sums of bounded independent random variables and discusses related extensions. It can support explicitly assumption-limited absolute-error bounds for averages. Such a bound does not convert a coarse average into a rare-event visibility guarantee and cannot simply be applied to arbitrarily correlated spans or bursts. Prefer exact binomial calculations when the manuscript's independent fixed-witness model permits them. [Publisher abstract and metadata](https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830).

### Buffer occupancy, `Little1961`

Little, Operations Research 9(3):383–387 (1961), DOI `10.1287/opre.9.3.383`, relates mean population, arrival rate and residence time under stated stationarity/regularity assumptions. It motivates average occupancy proportional to arrival rate times waiting time. It is not a peak-memory or no-overflow guarantee; object sizes, bookkeeping, burstiness and late arrivals remain implementation/workload properties. A measured RSS maximum is therefore a separate observation. [Publisher abstract and metadata](https://pubsonline.informs.org/doi/abs/10.1287/opre.9.3.383).

### Paired resource analysis, `nistPairedObservations`

NIST defines paired observations and the statistic based on within-pair differences. For five independent seed blocks, the declared interval on mean paired savings uses the block-level differences and four degrees of freedom; individual traces are not extra process-CPU replications. Exact Student-t coverage requires the usual normal-difference model, a strong condition with only five blocks. Publish individual block values and call the interval model-based; it cannot represent deployment-to-deployment variation. [NIST analysis of paired observations](https://www.itl.nist.gov/div898/handbook/prc/section3/prc311.htm).

## Deductions the paper can prove without overstating the sources

1. **Visibility, conditional on independent complete-trace selection.** With `m` distinct useful witnesses and inclusion probability `p`, the count retained is binomial. At least one appears with probability `1-(1-p)^m`; at least `k` requires the binomial survival sum. The proof is elementary and should be included, with delivery/completeness assumptions explicit.
2. **A task-dependent threshold.** Requiring one-witness visibility at least `gamma` gives `p >= 1-(1-gamma)^(1/m)` for `m>=1`. A singleton already gives the necessary lower bound `p>=gamma`. This directly rules out a workload-independent claim that an aggressive fixed discard rate preserves every rare incident.
3. **Budget transfer, not unconditional tail dominance.** If a recognized class occupies fraction `a` and is always retained, a trace budget `q>=a` leaves background inclusion `(q-a)/(1-a)`. A useful witness outside the recognized class then receives the background probability. The classification model and equal-cost trace budget are assumptions, not empirical truths.
4. **Irrecoverable upstream loss.** A downstream keep decision cannot recover a trace never supplied to it. The combined inclusion probability is the probability of both stages accepting; product formulas need independence or the appropriate conditional probability.
5. **Different cost denominators.** Equal trace retention does not ensure equal span or byte retention when selected traces differ in size. If `B_i` is trace size, expected retained bytes are `sum(pi_i B_i)`. This is a linearity-of-expectation result, not a claim that CPU, memory, index size or money obey the same ratio.
6. **A scope-qualified conclusion.** Formal claims quantify defined witness recovery under their assumptions. Measured claims describe the synthetic replay, pinned software and homelab conditions. General production diagnosis, human mean time to repair, storage-engine amplification and prices need additional evidence.

## Bibliographic verification notes

- Dapper metadata came from Google's report and publication record; X-Trace and Hindsight from their USENIX papers/proceedings. Preserve Dapper's technical-report classification.
- Sifter, Pivot Tracing and Canopy titles/authors/DOIs were verified in author-hosted papers; pagination and proceedings names were cross-checked with publisher-deposited [Crossref metadata](https://api.crossref.org/works/10.1145/3357223.3362736), [Pivot metadata](https://api.crossref.org/works/10.1145/2815400.2815415), and [Canopy metadata](https://api.crossref.org/works/10.1145/3132747.3132749). Crossref stores some of these as a short title plus subtitle; the bibliography combines them to match the published paper.
- TracePicker metadata and scope were read from the ACM publisher article. Wilson pagination was checked using its [publisher-deposited metadata](https://api.crossref.org/works/10.1080/01621459.1927.10502953); the original article scan is [available through McGill](https://jhanley.biostat.mcgill.ca/c607/ch08/wilson_jasa_1927.pdf). Wilson method details were checked against NIST.
- Horvitz–Thompson, Hoeffding, Clopper–Pearson and Little metadata came from publisher records, with the Horvitz–Thompson original scan also checked. Clopper–Pearson's publisher full text was not available to this browsing session; no claim of having reviewed its full proof is made.
- The v0.136.0 manifest and v0.136.0 README were fetched from the official GitHub repositories. Living specification access dates do not assert a publication year or implementation support.
- The bibliography has 20 entries. It includes sources for optional foundations; the final article should cite only those it actually uses, rather than padding the reference list.
