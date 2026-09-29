# Restricted Lean proof scope

The paper's mathematical supplement is included as an appendix in the named preprint and as a separate anonymous PDF in the review package. It gives the model assumptions and written derivations.

`TraceSampling.lean` supplies six restricted discrete statements. Run it with Lean 4.24.0; no external Lean packages are required:

```sh
lean TraceSampling.lean
```

The statements concern monotonicity of the number of retained witnesses, impossibility of recovering upstream-discarded evidence by selecting a subset, loss of a discarded singleton, the weighted finite-outcome identity `seen(c,d,m) + d^m = (c+d)^m`, positivity of missed outcome weight, and strict loss when a discard outcome is available. Only the standard `propext` and `Quot.sound` axioms are reported; one theorem uses no axioms.

For rational probability `p=c/(c+d)`, dividing the partition identity by `(c+d)^m` gives the one-witness complement formula when `c+d>0`. The division, arbitrary real probabilities, the full binomial law, statistical intervals, resource models, and Collector implementation behavior are not machine-formalized here. Their arguments and assumptions are in the paper and mathematical supplement. A Lean PASS does not establish empirical validity or external replication.
