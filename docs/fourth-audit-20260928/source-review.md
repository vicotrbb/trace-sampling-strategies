# Primary-source and venue review

Checked 28 September 2026. Downloaded full-text HTML and its SHA256 are retained in `sources/manifest.json`. A reference to a primary paper here does not imply that its implementation was reproduced.

## Added related work

- **Mint**, Huang et al., version 1, 7 November 2024. The introduction and Sections 3.3-3.4 describe separating common patterns and variable parameters, collecting a compact representation of all requests, and retaining fuller information for selected requests. This supports the manuscript's distinction between representation compression and whole-trace retention. [Versioned primary text](https://arxiv.org/html/2411.04605v1).
- **UniSage**, Zhu et al., version 2, 4 February 2026. Sections 3.1-3.3 describe analyzing correlated telemetry before dual sampling and relating selection to downstream analysis. The arXiv identifier dates from 2025, but the bibliography gives the 2026 date of the version actually read. The abstract record is titled “A Unified and Post-Analysis-Aware Sampling for Microservices”; the rendered full text uses “UniSage: Towards Unified and Post-Analysis-Aware Sampling for Microservices.” The bibliography follows the versioned abstract record rather than inventing a proceedings citation. [Versioned primary text](https://arxiv.org/html/2509.26336v2), [record](https://arxiv.org/abs/2509.26336v2).
- **Gleaner**, Yang et al., version 1, 18 April 2026. Section 3 describes event-pair representations including log information, alarm-guided quotas, and diversity selection. The manuscript uses these distinctions to describe its utility objective; it does not rank Gleaner against the measured controls. [Versioned primary text](https://arxiv.org/html/2604.16810v1).

Mint and Gleaner full-text headers contain incomplete publisher-template fields. The bibliography therefore cites the verified arXiv versions and does not copy placeholder DOIs or assert unverified proceedings metadata. STEAM was not part of the active related-work argument and its uncited bibliography entry was removed. Prior primary-source checks for Sifter, Sieve, TraStrainer, TracePicker, MicroRank, TraceRCA, and Reichelt et al. remain in the preceding review records.

## Collector mechanics and span lifetime

The [OpenTelemetry Trace API, End](https://opentelemetry.io/docs/specs/otel/trace/api/#end) permits child spans to remain active after their parent ends. It does not guarantee root-last delivery. This supports rejecting an unconditional ordering assumption, not claiming that early-root ordering is common. The paper's supporting probe explicitly imposes Collector arrival order.

The [v0.136.0 tail processor README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.136.0/processor/tailsamplingprocessor/README.md) documents the 30-second default wait, decision timing, caches, late spans, and eviction. The paper reports its deliberately configured two-second wait and binary arrival intervention. The pinned processor and file-exporter implementation citations support the release/grouping explanation; measured counters and complete retained exports supply its empirical evidence.

## Publication and AI assistance

The [ICPE 2027 Research Track call](https://icpe2027.spec.org/tracks-and-submissions/research-paper-track/) identifies EERCS as a category of the Research Track. It permits insights from established methods, requires technical quality and useful insight, specifies ten double-column pages excluding references and appendices, and requires anonymity. Appendices are not published. These rules do not make the requested single-column reader PDF submission-ready.

The main [ACM authorship-policy URL](https://www.acm.org/publications/policies/new-acm-policy-on-authorship) returned HTTP 403 during direct retrieval. Search-indexed text from ACM's own policy mirror indicated disclosure in Methods for AI assistance in research. The complete currently served publisher page could not be inspected, so this artifact does not assert a verbatim policy or certify venue compliance. The manuscript supplies a detailed Methods disclosure plus the author-responsibility statement. Final submission preparation must check the publisher policy and venue form actually in force.

## Statistical interpretation

The retained Clopper-Pearson calculation bounds a Bernoulli loss-event probability under the fixed-corpus replay model; its union bound needs no independence across comparisons. It does not estimate a future incident population. The gain inequality makes its relation to net accuracy loss explicit. The new document checker independently inverts all 42 feasible limits through binomial CDF roots. No bootstrap inference or exact integration over all selection masks is claimed.
