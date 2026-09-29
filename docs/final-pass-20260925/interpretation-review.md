# Expected accuracy, incident recovery, and confidence

Checked 2026-09-25 against `paper/theory.tex`, `paper/formal-appendix.tex`, the RQ4 section of `paper/results.tex`, and the rewritten cost discussion. This is internal research interpretation review, not external peer review. No workloads were run and no paper, frozen source, or data files were changed. The unfinished cost experiment's outcomes are not assessed.

## Verdict and algebra

The new classification-budget corollary and the numerical example are correct under the stated perfect-classifier, unchanged-whole-trace, complete-delivery model. The text correctly separates an expected loss from an incident-recovery probability and an empirical confidence certificate.

Let `F` be the fixed, nonempty failing-request set. When all protected failures have inclusion probability one and each unprotected failure has marginal inclusion probability `r`, the perfect baseline gives

\[
\mathbb E[A]=\rho+(1-\rho)r,
\qquad \mathbb E[1-A]=(1-\rho)(1-r).
\]

For `0 <= rho < 1` and `0 <= r <= 1`, expected loss at most `epsilon` is therefore equivalent to

\[
r\ge\max\{0,1-\epsilon/(1-\rho)\}.
\]

With achieved expected trace fraction `b = alpha + (1-alpha)r` and `0 < alpha < 1`, substituting this threshold proves the stated budget inequality. Independence between trace decisions is unnecessary for this expectation identity. Dependence matters for distributions, variances, and recovery events, a distinction also explicit in the primary tracing-uncertainty work. [Coehlo, Merchant, and Stokely, Sections 2 and 3](https://www.usenix.org/system/files/mad12-final9.pdf).

| Objective in the example | Minimum selection rate | Minimum expected traffic retention | Maximum expected traffic discard |
| --- | --- | --- | --- |
| Uniform head, expected classification loss at most 0.05 | `p = 0.95` | `0.95` | `0.05` |
| Tail, aggregate expected classification loss at most 0.05 | `r = 1 - .05/(1/3) = .85` | `.02 + .98*.85 = .853` | `.147` |
| Tail, expected classification loss at most 0.05 within every stated fault family | `r = .95` | `.02 + .98*.95 = .951` | `.049` |

The per-family calculation uses the actual constructed classes: SQL and latency failures are wholly protected, while semantic failures are wholly unprotected. At the aggregate threshold, semantic expected accuracy is only 85%, although aggregate expected accuracy is 95%. Thus the aggregate criterion permits a 15-point expected loss in that family. At the per-family threshold, aggregate expected accuracy is about 98.33%, not merely 95%. These are analytical checks, not newly measured results.

## Quantifiers and endpoint cases

- `epsilon = 0` and `rho < 1` require `r = 1` and `b = 1`; any nonzero unprotected fault mass must be retained perfectly in expectation.
- If `epsilon >= 1-rho`, including `epsilon = 1`, `r = 0` is sufficient and the minimum feasible traffic budget is `b = alpha`. The maximum in the formula handles this correctly.
- `rho = 0` gives `b_min = 1 - (1-alpha)epsilon`; spending budget on protected traffic unrelated to the failing set offers no classification benefit.
- `rho = 1` is correctly handled separately: every failure is protected, so expected fault accuracy is one at every feasible background rate, including zero. Do not substitute this case into the expression dividing by `1-rho`.
- `alpha = 0` and `alpha = 1` are outside the stated corollary. No correction is necessary. In the fixed finite population, such endpoint values also constrain which `rho` values are feasible.
- The fractions describe existing subsets of one finite population. They are not independently arbitrary parameters: with failure prevalence `f = |F|/N`, consistency requires `rho*f <= alpha` and `(1-rho)*f <= 1-alpha`. The study's values `f=.03`, `rho=2/3`, `alpha=.02` satisfy these constraints. Stating this is optional; the existing fixed-set model already implies it.

One useful precision edit is to make the corollary self-contained: explicitly state `F != empty`, protected inclusion probability one, `r in [0,1]`, and **define `b` as the achieved expected retained fraction**. These follow from the surrounding model, but `b` is not bound within the corollary's own statement. If instead `b` means only an upper budget cap, the inequality establishes feasibility of an adequate rate, not adequacy of every policy spending less than that cap.

The perfect-baseline assumption is essential to these numerical thresholds. For an imperfect baseline, loss is the lost mass of correctly classifiable requests, and a single fraction of protected failures need not describe that mass. The manuscript currently keeps the assumption explicit.

## Four quantities that must stay distinct

| Quantity | Meaning and assumptions |
| --- | --- |
| `E[A]` | Mean accuracy over the declared sampling randomization on a fixed corpus. The corollary needs correct marginals, not independent decisions. |
| `P(D_j=1)` | Success of a specified incident evidence rule. For an unprotected incident, `B_(m,k)(r)` requires the stated independence and complete-delivery assumptions. This is not a classifier's mean per-request accuracy. |
| `P(A >= 1-epsilon)` | Probability that a realized corpus attains an accuracy target. Marginal inclusion probabilities and expected accuracy alone do not determine it. |
| Confidence coverage for an estimated parameter | Repeated-data coverage of a confidence procedure under its statistical assumptions. A 95% accuracy objective is not a 95% confidence level. [NIST interval construction](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). |

A small counterexample makes the distinction explicit without any experiment. Take 100 traces, of which three are failures: two protected and one unprotected. Then `alpha=.02`, `rho=2/3`, and independent background selection at `r=.85` give `E[A]=.95`. Yet realized accuracy is either `1` or `2/3`, and `P(A >= .95)=.85`. The expected-loss result therefore cannot be read as a 95% high-probability guarantee, even with independent sampling.

Likewise, requiring the expected-loss margin in each fault family means a collection of mean constraints. It does not mean all families simultaneously attain the realized target with probability 95%, nor that all estimated family means have simultaneous 95% coverage. Such probability or confidence objectives require an appropriate joint calculation or a valid simultaneous bound. [NIST's general Bonferroni inequality](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm).

The current RQ4 paragraph says these are model-derived expected-loss thresholds, which is correct. Add **“expected”** before its per-family margin and traffic-discard phrases to avoid an unintended hard-cap reading. The theoretical values also remain distinct from the deterministic native-hash curves: fixed hash outcomes are not automatically independent random draws. Withdrawing the empirical certification claim and retaining descriptive curves preserves the distinction. The stated requirement of 1,615 independent blocks for the particular zero-loss Hoeffding radius follows from the displayed formula; it is not a general sample-complexity lower bound. [Hoeffding's original independent-bounded-variable setting](https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf).

## Cost interpretation and causal language

No substantive unsupported causal decomposition was found in the rewritten linear-model interpretation. The equation `(1-b_V)D - A_T` is a conditional model identity. The text expressly says historical totals cannot identify its components and that retain-all tail processing can change downstream batching. “Explains the possible sign change” is defensible as a statement about possibilities, not identification of the cause of the historical observations.

Two small wording improvements would make that boundary sharper:

1. Describe `C_H` and `C_T` as **model-expected costs** when `p` and `b_V` are expected retained fractions. A nominal sampling rate does not make a linear cost formula an exact identity for every realized measurement cell.
2. In `paper/discussion.tex`, change “Batching changes downstream work even when retained spans are unchanged” to **“Batching can change downstream work even when retained spans are unchanged.”** The pinned implementation marshals each export batch, so the mechanism is real, but changing a configuration parameter need not change the realized batches or CPU. [Batch processor v0.136.0](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.136.0/processor/batchprocessor/README.md), [file exporter v0.136.0](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.136.0/exporter/fileexporter/file_exporter.go#L23).

Retain the explicit restriction to defined configuration contrasts. Neither a future factorial interaction nor the linear accounting model should be described as identifying every component of intrinsic tail overhead or completely explaining the earlier cross-experiment contrast. No direction, magnitude, or significance of the still-running cost experiment is inferred here.
