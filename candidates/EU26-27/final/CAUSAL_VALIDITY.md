# EU26-27 causal-attribution boundary

## Question

Can the observed OLD-versus-HYBRID difference be described as the isolated causal effect of changing offspring count `lambda` while mutation adaptation is otherwise completely unaffected?

## Answer

**No. The implementation intervention is localized to offspring-count control, but the algorithmic effect is an interaction between that controller and the unchanged TwoRate mutation adaptation.**

The frozen author `TwoRate` implementation generates the first half of the offspring with mutation probability `r/(2n)` and the second half with `2r/n`. Its adaptation step then evaluates the resulting offspring, determines which half supplied the best metric value, and probabilistically halves or doubles `r`.

The HYBRID patches preserve the source code and update law of `TwoRate::adapt`, including its RNG draw. They add only an online controller for `lambda`. Nevertheless, changing `lambda` changes:

1. the total number of offspring sampled in the generation;
2. the number of offspring sampled from the low-rate and high-rate halves;
3. the set of metric values presented to the unchanged TwoRate adaptation rule;
4. the probability that the best observed offspring comes from either half;
5. consequently, the stochastic trajectory of the original mutation-strength variable `r`.

Therefore the valid causal statement is:

> The experiment estimates the effect of adding the specified offspring-count controller to the exact-reproduced TwoRate GSEMO system.

The following stronger statements are not supported:

- `lambda` has an effect independent of mutation adaptation;
- the mutation process is behaviorally identical between OLD and HYBRID merely because the TwoRate formula is unchanged;
- all observed OLD-versus-HYBRID differences are caused directly by reset, rollback, or the cap alone;
- a negative HYBRID result proves that the source parameter-control mechanism itself is ineffective in its original algorithm.

## Why the experiment remains valid

This interaction does not invalidate the transfer study. The research question is whether a source-grounded offspring-count controller improves the **complete TwoRate GSEMO system** while the published TwoRate update law is preserved as the baseline mechanism. The exact OLD regression before every HYBRID evaluation establishes that the additive patch does not alter ordinary TwoRate behavior when the hybrid controller is not selected.

The appropriate interpretation is therefore an external-validity / systems-interaction result:

> On the frozen OneMinMax `n=100` testbed, the tested combinations of success-based offspring-count control with the existing hypervolume-driven TwoRate adaptation did not establish the preregistered independent FE-efficiency improvement.

This boundary must be retained in the thesis discussion of causality and scientific novelty.
