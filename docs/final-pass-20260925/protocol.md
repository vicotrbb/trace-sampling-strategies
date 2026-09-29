# Prospective controlled cost intervention

Prepared 25 September 2026 before pilot or measured execution. The final source and analysis hashes will be frozen after the setup pilot and before measured execution. All workload execution is restricted to `kubectl --context homelab`.

## Question and estimands

The earlier replay and live studies changed several factors simultaneously. They establish opposite net Collector CPU effects but do not identify the cause. This intervention tests the conditional effects of export fanout, batching timeout, and tail buffering/selection on a single fixed input corpus. It does not retroactively identify every cause of the earlier difference.

The three crossed factors are:

1. Export path: JSON file only, or the same JSON file plus OTLP/HTTP to fresh Jaeger 1.76.0 Badger storage.
2. Batch timeout: 100 ms or 1,000 ms, with target 256 spans and maximum 512 spans fixed.
3. Sampler: bypass; tail with all three policies and 100% probabilistic background; or tail with ERROR, duration >= 250 ms, and background 0.08/0.98. The last policy targets 10% trace retention with 2% protected traffic. The retain-all tail treatment runs the same policy implementations and changes only the probability threshold relative to the sampled tail treatment.

The full factorial has twelve treatments per runtime block. Eight blocks (51001 through 51008) give 96 measured cells. Treatment order is randomized independently inside each block using a declared seed string. No outcome-dependent stopping or additional block collection is planned. The primary endpoint is Collector process user-plus-system CPU during the measured schedule and common drain. Secondary endpoints are Jaeger CPU, raw batching counters and sizes, complete output identities, JSON bytes, component RSS, schedule lag, and cgroup throttling.

Primary reported contrasts, in CPU-seconds, are: tail10 minus bypass within each exporter/timeout combination; tail100 minus bypass to assess buffering and batching at unchanged output volume; and the difference between those paired policy contrasts after adding the Jaeger export path. Changes in those contrasts between timeouts assess the controlled batching intervention. The paper will distinguish observed treatment effects from a decomposition into intrinsic per-span or per-request costs. A retain-all tail control is not a zero-cost control: it changes buffering, release timing, and grouping.

## Fixed input and execution

The input is the archived full-retention checkout/steady corpus from seed 41001 of the previous live study. It contains 500 warmup and 3,000 measured requests, with five spans each. Resource and scope attributes, trace and span IDs, parent links, status, and durations are preserved. A single timestamp translation prepared on homelab moves the complete corpus into the present query window. That translated corpus and serialized batch bytes remain identical across all measured cells. The input is replay of actual recorded application traces, not a new application workload or additional diagnostic cases.

Ten complete traces are offered in one OTLP/HTTP JSON request every 200 ms, giving 50 traces/s. Every cell uses fresh Collector and Jaeger processes and a fresh store. Jaeger runs even in the file-only treatment, with its own tracing disabled, to keep the background process configuration common. The ten-second warmup is followed by a five-second drain, then a sixty-second measured schedule and another five-second drain. CPU endpoints exclude startup, warmup, verification, and shutdown. No per-treatment drain extension is permitted. Final outputs must reconcile at those endpoints. Badger is local and unreplicated, with a 24-hour TTL to accommodate the common timestamp translation. Data are queried before removing the temporary store.

Collector v0.136.0, Jaeger v1.76.0, their release archives, Python image digest, node, GOMAXPROCS=2, tail decision wait=2 s, capacity=512, both decision caches=10,000, batch sizes, and exporter queue/retry settings are fixed. The CPU limit is four CPUs, memory limit 4 GiB, and the namespace is isolated without public services or persistent volumes. Other workloads remain on the shared node. Exact process-stat snapshots and raw cgroup counters are retained. CPU ticks have 0.01-second resolution on the intended host; very small differences will not be interpreted as precisely resolved mechanism costs.

The added OTLP/HTTP path explicitly uses protobuf encoding, gzip compression, a five-second request timeout, and disabled retry and sending queue. Exporter-helper asynchronous batching is therefore inactive. Both tail settings explicitly disable first-match short circuiting and evaluate policies in ERROR, latency, background order. Collector internal metrics are detailed and scrape schedules are identical. These settings are part of the treatment definition.

## Pilot and validation gates

A distinct seed-50001 pilot exercises all twelve configurations with a four-second warmup and ten-second measurement. It checks schema, readiness, delivery, trace content, backend queries, counters, and source capture. It does not select treatment factors, tune an effect direction, or contribute to reported CPU estimates. Any setup corrections will be logged, and all attempts retained.

A measured cell is accepted only if every input HTTP request completes, the full configured schedule is offered, no unknown/duplicate/partial output occurs, outputs exactly match the configured native policy, receiver/exporter counters reconcile, the measurement interval ends with complete expected output, and no refusal, export failure, or early tail-buffer drop is recorded. File-only Jaeger must contain no study traces; dual-export Jaeger must reproduce the file export's span identities and content. A failure is archived and stops the run; no cell is silently replaced. Schedule lag and throttling are reported as observations, not filtered away because they make a treatment look worse.

A separate validator will reconstruct policy decisions, payload hashes, CPU differences, batch summaries, full factor coverage, and backend content without importing the experiment's selection or counter functions. The measured source, protocol, and analysis plan will remain unchanged after the freeze.

## Analysis and interpretation

Each contrast uses the eight within-block differences. Report all block values, the mean, and a model-based two-sided 95% Student-t interval with seven degrees of freedom. These intervals describe runtime repeatability conditional on this corpus and host; they are not a familywise significance or equivalence procedure. No p-value screening chooses which contrasts appear. Randomized order reduces systematic time-order effects, but independence and normality of eight runtime differences are not guaranteed. With the fixed count, precision is reported rather than promised.

Batch metric counts and sums will reveal whether timeout changes materially change batching. In particular, a 256-span target is close to one second of the offered 250 spans/s. The timer setting alone will not be taken as evidence that actual batch sizes differ. A result consistent with cheaper export will be described as a conditional mechanism finding, with any unresolved interactions retained.

The earlier 160-comparison Hoeffding procedure remains in the historical archive. Its inability to certify the five-point margin was built into its design, so the main manuscript will report existing RQ4 curves descriptively and disclose the abandoned certification aim in the appendix. No newly chosen uncertainty model will be labeled prespecified for those old data.
