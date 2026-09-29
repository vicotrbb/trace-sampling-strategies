# Statistical design review: conditional incident replay

Date: 2026-09-25. This is a bounded pre-freeze review of the design supplied by the study lead. The proposed protocol file did not yet exist at the expected path when this review began, so the review concerns the stated design rather than an inspected implementation. No workloads or Monte Carlo experiments were run. Numerical checks below are deterministic binomial/beta calculations with the artifact's pinned SciPy environment. Only this note was written.

## Verdict

The proposed procedure is mathematically valid and has useful attainable precision, provided the estimand is explicitly conditional on the fixed 600-incident archive and the replay trials follow an iid randomized-replay model. It can bound mean accuracy deterioration over uniform draws from that archive. It does not create 5,000 new application incidents or supply confidence coverage for future production incidents.

The loss-only construction correctly accommodates sampling gains and full-data classifier errors. It gives a conservative upper bound on net deterioration, rather than incorrectly assuming sampled accuracy is monotone in retained evidence. No acceptance filter based on full-data correctness should be introduced.

## Estimand and coverage argument

Freeze the archive C, truth labels, classifier including tie/abstention rules, sixteen policy/budget specifications, and replay sample size before the confirmatory replay. Let I be uniform on the 600 incident indices, sampled with replacement. Let B(I) indicate correct full-data localization and A_j(I,U) indicate correct sampled localization at comparison j, where U contains that trial's sampling randomness. All probabilities below condition on C and these frozen choices.

Define Y_j=B(I)(1-A_j) and G_j=(1-B(I))A_j. Both are Bernoulli indicators. Pointwise, B-A_j=Y_j-G_j, so the target deterioration is

delta_j = E[B] - E[A_j] = P(Y_j=1) - P(G_j=1) <= q_j,

where q_j=P(Y_j=1). This identity requires neither classifier monotonicity nor independence between B and A. The exact full-data accuracy is the mean of B across all 600 cases, not an estimate based on the 5,000 replay draws.

For each j, 5,000 iid draws of (I,U) make X_j=sum(Y_j) binomial with parameters n=5,000 and q_j. The one-sided Clopper-Pearson upper limit is U_j=BetaQuantile(1-alpha_j; X_j+1,n-X_j) when X_j<n, and U_j=1 when X_j=n. Equivalently, it inverts the binomial lower tail. With alpha_j=.05/16, each limit has coverage at least 1-alpha_j; discreteness makes it conservative. [Clopper and Pearson 1934, original publication](https://academic.oup.com/biomet/article/26/4/404/291538), [NIST exact binomial limits](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm).

A union bound gives P(all sixteen delta_j<=q_j<=U_j | C)>=.95. Hence declaring a comparison certified only when U_j<=.05 controls erroneous five-point certificates across the declared family. Independence between comparisons is unnecessary. Sharing each trial's incident and random priorities across budgets or policies is therefore permitted, while successive trial vectors must satisfy the iid model. This argument supplies the simultaneous coverage directly; no additional Holm test is needed.

## Precision verified before outcomes

The per-comparison tail probability is .003125. At zero losses, U=1-(.003125)^(1/5000)=0.001152998984, or **0.11530 percentage points**. The proposed approximation is correct.

| Loss count out of 5,000 | Observed loss probability | One-sided simultaneous-family upper limit |
|---:|---:|---:|
| 0 | 0% | 0.11530% |
| 50 | 1.00% | 1.45043% |
| 100 | 2.00% | 2.60478% |
| 150 | 3.00% | 3.72142% |
| 200 | 4.00% | 4.81810% |
| 208 | 4.16% | 4.99225% |
| 209 | 4.18% | 5.01399% |
| 250 | 5.00% | 5.90179% |

Thus at most 208 observed losses yield the five-point certificate; 209 do not. This is an exact numerical inversion of the declared rule, not an observed study outcome.

Under the assumed binomial model, the probability of certification at true loss-only probability q is P(Binomial(5000,q)<=208). It is approximately 99.9998% at q=.03, 73.2480% at q=.04, and 12.9522% at q=.045. At q=.05 it is .2900%, below the per-comparison .3125% tail allocation. These are probabilities for an individual comparison, not the probability that all sixteen certify. Precision is feasible but not reliably decisive close to the margin. Since q can exceed net deterioration when gains occur, a small net loss can still fail this conservative procedure.

## Conditions to freeze explicitly

1. **Sampling with replacement.** Each trial must independently choose an incident uniformly from the same fixed 600-case corpus. Deliberately visiting every incident equally often, sampling without replacement, or changing selection weights during replay produces a different count distribution and cannot simply use the same binomial argument. Unequal fixed probabilities are possible, but then the target is their weighted corpus average.
2. **Fresh randomized selection.** Generate fresh per-trace priorities for each replay trial. Hashing an archived trace ID with a fixed salt every time instead evaluates a fixed deterministic selection on that corpus, not the intended expectation over randomized sampling. The distinction changes the estimand even though random incident draws alone can still produce Bernoulli observations. Use separate declared random streams for incident selection and trace priorities; record the PRNG and seeds. Exact coverage belongs to the ideal iid replay model. Deterministic pseudorandom output does not itself prove independence.
3. **Trial-level independence is the relevant condition.** Trace durations and failure effects within an archived incident may be correlated; the incident is fixed here. Even a policy that correlates inclusion decisions within a trial can use this construction if independently repeated whole-trial draws have the same law. In contrast, a policy that updates its state across replay trials changes that law unless explicitly modeled.
4. **Keep the entire corpus.** Include full-data errors, ties, abstentions, missing evidence and difficult incidents. Do not select incidents for replay based on B=1. A loss fraction conditional only on correct full-data cases is a different quantity. If operational recording failures invalidate collection, retain the failed evidence and explain the corpus decision rather than silently replacing hard cases.
5. **Freeze the sixteen comparisons and n=5,000.** State the eight rates, the two policies, the 0.05 absolute margin, and the exact upper-limit implementation. Do not continue a comparison until it certifies, rerun unfavorable seeds, or choose a narrower method after inspecting results. Further causes, magnitudes, fractions, services or endpoints do not inherit this sixteen-comparison simultaneous claim.
6. **Specify infeasible budgets prospectively.** A tail policy retaining all protected traces cannot meet a budget below protected mass. State whether each policy uses expected trace count, fixed count, or bytes, and whether it acts on the two windows jointly or separately. Do not tune a tail rule with the injected location or remove infeasible incidents after drawing them. Mark infeasibility or apply a predeclared fallback while retaining the target's meaning.
7. **Define the scorer completely.** Specify candidate-service enumeration, span aggregation, minimum samples in each window, empty-window abstention, median convention for even counts, ties, and whether a nonpositive median increase still yields a label. Sampling can create both errors and improvements, so retain the paired 2x2 table of B and A at every comparison. Report q, gain frequency, net paired difference, the exact full-data accuracy, and sampled absolute accuracy.
8. **Keep absolute quality visible.** If the full-data scorer is poor, a small relative deterioration can be trivial. A full-data accuracy near zero gives q near zero for every sampler. A five-point certificate must therefore appear beside absolute accuracy. It is not an assertion that diagnosis itself is adequate. Any separate certified absolute-accuracy requirement needs its own prespecified inference and family allocation.

## Workload and interpretation pitfalls

The median-change scorer is a reasonable transparent baseline, but delay magnitude and affected-request fraction determine what it can identify. An affected fraction below one half may have little influence on the median, especially with tightly concentrated unaffected durations; finite samples and service noise can produce errors even at full retention. Retain those outcomes rather than adjusting magnitudes or fractions to ensure success after seeing the data. Freeze factor balance and ordering before collection.

Specify what a service duration represents. An upstream inclusive span can inherit a downstream delay, so ranking inclusive median increases may identify an ancestor rather than the injected service. Exclusive service work, a dedicated local-operation span, or inclusive latency are each legitimate choices, but they define different localization tasks and must not be interchanged after results. The fixed scorer should be described as a baseline, not an independently validated general root-cause engine.

The experiment supplies reference/incident window boundaries and a three-service candidate set. It consequently evaluates closed-set localization given those boundaries. It does not demonstrate detection of unknown incident onset. Twenty healthy reference requests also do not create no-fault incident controls for measuring false alarms. Those are scope limits, not defects in the conditional confidence calculation.

Uniform weighting across the 600 incidents is a deliberate corpus distribution. An average-loss certificate need not hold for each incident, service, magnitude or affected fraction. Report subgroup descriptive performance so aggregate success cannot hide an important difficult class. The sixteen-comparison rule does permit selecting the largest certified discard level among the predeclared grid points, but does not certify intermediate rates or a continuous threshold. A classifier that changes rankings as evidence is removed need not have monotone accuracy in the retention rate.

More replay trials narrow Monte Carlo uncertainty about this particular frozen corpus and policy law. They do not increase application diversity, measurement replication, or evidence about production deployment. The earlier five-block result and this new certificate concern different estimands and should be presented separately; the new replay must not be described as retroactively repairing the earlier empirical uncertainty.

## Suggested coverage wording

“Conditional on the archived 600-incident corpus, the frozen classifier and sampling policies, and an iid randomized-replay model, the simultaneous one-sided bounds cover the mean accuracy deterioration over uniform incident draws with probability at least 95%. A tested policy/budget is certified at the declared five-percentage-point margin only when its loss-event upper bound is at most .05. Replay trials quantify conditional sampling uncertainty and are not additional application incidents or a guarantee about production failures.”

This design is ready to freeze after the implementation choices above are made explicit. The proposed mathematical approach itself does not need correction.

## Pre-freeze implementation review, 2026-09-25

Scope: static reading of `experiments/second_audit/diagnosis_study.py`, `scripts/analyze_second_audit.py`, `scripts/verify_second_audit.py`, and `docs/second-audit-20260925/protocol.md`. No workload, replay, validator, or analysis was executed in this pass. Findings concern the inspected implementation and validation coverage, not observed confirmatory outcomes.

### Statistical implementation agrees with the contract

- **Replay law.** `diagnosis_study.py:81-90` creates `Random(990000+trial)`, chooses an episode with `randrange`, then draws one priority for each of its forty records. The episode list is unchanged and there is no removal, balancing, or rejection, so the intended law is uniform sampling with replacement. All sixteen comparisons share that trial's episode and priorities. Such dependence between comparisons is allowed by the union-bound argument. Fresh trial seeds implement the declared independent-trial PRNG model. A single stream for episode selection followed by priorities is sufficient under that model; **separate streams are not mathematically necessary**. This corrects the overly prescriptive separate-stream sentence in condition 2 above. Python documents its range selection and uniform floating-point generator, but also explicitly describes the generator as deterministic. Consequently the exact coverage statement remains conditional on the ideal iid replay model, not a proof of physical randomness or independence from consecutive seeds. Record the Python runtime with the seed schedule for reproduction. [Python random documentation](https://docs.python.org/3/library/random.html).
- **Inclusion and budget.** The two windows are sampled together at the trace level. Head retains each trace when its priority is below b. Tail retains all roots at least 80 ms and otherwise uses r=(b-alpha)/(1-alpha), with alpha computed once across the full fixed corpus. Because every episode has forty traces and episode draws are uniform, alpha+(1-alpha)r is the expected global retained trace fraction under the ideal priority model. It is not an exact per-trial count, a per-window budget, or a byte budget. Budgets below alpha are marked infeasible for every trial and remain in the sixteen-comparison family. No incident is selectively discarded for feasibility. (`diagnosis_study.py:76-90`; protocol lines 23-27.)
- **Losses, gains, and full-data errors.** `before and not after` is Y, `after and not before` is G, and `(loss-gain)/n` has the correct sign for deterioration. An abstention is incorrect. The collector stores every successfully recorded incident without filtering on full-data correctness; replay draws from that full list. The analysis separately totals exact corpus baseline correctness and replay baseline correctness, and reports gains, sampled correctness, abstentions, and descriptive strata. (`diagnosis_study.py:50-69,89-90`; `analyze_second_audit.py:27-45`.)
- **Confidence endpoint.** `beta.ppf(1-.05/16, loss+1, n-loss)`, with endpoint 1 when loss=n, is the correct one-sided Clopper-Pearson upper limit. The family remains sixteen when some budgets are infeasible, and certification uses upper<=.05. No second adjustment is required for shared comparison randomness. The certificate is for the fixed-corpus mean loss bound, while stratum results are descriptive. (`analyze_second_audit.py:38-47`; [NIST exact binomial limits](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm).)
- **Fixed scorer.** The code computes an ordinary median per service/window, using the mean of the two middle values for an even count. The first name in `SERVICES=['service-a','service-b','service-c']` wins an exact tie. Only an empty reference or incident window produces an abstention; even one retained trace in each window suffices, and a maximum score of zero or below still yields a service label. The independently written scorer has the same rules. Checking emptiness through the first service is valid here because every selected complete trace contains all three services, an invariant the corpus validator checks. Leaf timings have no children, and root duration is excluded from the score. (`diagnosis_study.py:13-28,40-47`; `verify_second_audit.py:11-20,103-121`.)

### Corrections needed to fulfill the stated verification contract

1. **Enforce the exact trial/comparison grid.** `verify_second_audit.py:129-144` checks sequential trial IDs, unique keys, allowed values from the supplied design, and total row count. It does not assert the frozen eight budgets, exactly 5,000 trial IDs numbered 0 through 4,999, or all sixteen comparison keys for every trial. Total rows alone do not prove this: 5,001 consecutive trials with sixteen omitted keys distributed across trials still permit 80,000 unique rows. The analyzer then uses each observed group length as n. Before treating an archive as confirmatory, require the exact Cartesian product of trial IDs, two policies, and eight fixed budgets, check the immutable design values, and require a constant feasibility flag within each comparison. This is a validation gap, not evidence that the producer emits an incorrect grid.
2. **Independently verify confidence calculations.** The protocol at line 31 promises reconstruction of interval arithmetic. The inspected validator reconstructs selections, predictions, losses, and gains, but neither reads the derived diagnosis summary nor checks its CP upper limits, net-loss arithmetic, sixteen-comparison metadata, or certification flags. Add a separate derived-summary check against reconstructed counts and binomial-tail inversion, including x=0 and x=n boundaries, or narrow that validation promise. The analysis formula itself is correct on inspection; the missing piece is the promised independent receipt.

### Small scope clarifications

The protocol describes protection as ERROR or root duration >=80 ms, whereas this diagnosis replay implements only the duration condition. All generated spans are explicitly OK and the corpus validator requires that status, so the two rules are equivalent on this fixed corpus and the current probability calculation is unaffected. State that ERROR protection has no exercised cases here, or describe this experiment's policy as latency protection. Do not infer preservation of error traces from this replay. (`diagnosis_study.py:45-46,77,88`; `verify_second_audit.py:110`; protocol line 23.)

For a fully explicit scorer freeze, state the even-count median convention and that nonpositive scores still produce a prediction when both windows are nonempty. These behaviors are already fixed consistently in the two implementations. They are documentation clarifications, not reasons to change the scorer after observing outcomes.

No mathematical blocker was found in the inspected replay, loss/gain, or confidence-bound implementation. The two required actions above concern the prospective archive-validation contract. They do not require changing workload parameters or the declared statistical method.
