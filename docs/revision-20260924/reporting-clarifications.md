# Post-freeze reporting clarifications

Recorded UTC: 2026-09-24T22:09:25.226277+00:00.

## Baseline-classification acceptance condition

A consistency review during the ongoing confirmatory run identified a difference in specificity between the frozen prose protocol and the frozen implementation. The prose calls for measuring full-retention baseline accuracy, including scorer errors. The executed harness records those predictions but also appends `baseline_diagnosis_failure` to a cell's error list if any injected fault in a full-retention cell is misclassified. It writes the result and then halts on that error. Successful baseline classification is therefore an execution acceptance condition in the implementation.

This is a protocol-to-implementation clarification and a limitation of the design. The condition was already present in the source whose SHA256 is `d234ff8c68d31f05925c34d369b0ee2874fbe98a3f89575e1afbede8da55456f`, frozen at 2026-09-24T21:16:57Z before confirmatory execution. It is not a new acceptance rule added after inspecting results. Neither the frozen source nor the protocol/amendment files were changed. The live run continues under the original frozen code; any failed cell would remain archived rather than being silently replaced.

The manuscript now describes this condition explicitly and limits the endpoint to preserving a deliberately recognizable, known diagnostic task. The baseline is not an out-of-sample challenge set for a general diagnostic algorithm. Independent scoring establishes implementation/evidence consistency within that task. This disclosure should accompany the original protocol, rather than rewriting its history.

## Statistical and denominator precision

The calibration analysis uses Pearson chi-square goodness-of-fit statistics with exact binomial expected counts and asymptotic p-values, followed by Holm adjustment. Exact expected counts do not make those p-values an exact finite-sample test. The manuscript states the approximation and does not claim exact finite-sample familywise coverage for these goodness-of-fit results.

False accusations on normal requests use all offered measured normal requests as their denominator. Retained-normal conditional counts remain separately available in the derived data and are not substituted for that population denominator. These reporting clarifications do not change collected data, the fixed scorer, or the primary diagnostic-loss family.
