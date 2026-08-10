# EU26-18 verification blockers

Requirements tag: `STRICT_ADAPTIVE_GA_2026-08-10`

The blockers below do not show a forbidden hybrid or out-of-set adaptive
control. They prevent an exact method implementation and published numeric
reproduction. B02-B04 also prevent the frozen `update_rule_specified` gate from
receiving `PASS`, so the strict eligibility decision is `UNKNOWN`.

| ID | Severity | Blocker | Material effect | Evidence needed to resolve |
|---|---|---|---|---|
| B01 | HARD | Author implementation, exact jMetal revision, and JDK revision are unavailable | A clean-room implementation cannot be compared line-for-line with the executed algorithm | Author source archive with commit and build environment |
| B02 | HARD | Algorithm 2 uses undefined `x_c` | The coordinate update cannot be transcribed literally without interpreting `x_c` as current `x` | Author correction or source line implementing the update |
| B03 | HARD | Algorithm 4 calls undefined `repair` | Clamp, reflection, resampling, rejection, and wrap produce different boundary dynamics | Exact repair function and bound semantics |
| B04 | HARD | Parent copy/reference and child `eta_m` inheritance semantics are absent | In-place parent mutation and different crossover storage models change later selection and strategy propagation | Data model plus selection/crossover source code |
| B05 | HARD | Author seeds, PRNG, stream policy, and raw thirty-run vectors are absent | Exact trajectories, pairing, means, variances, and p-values cannot be authenticated | Seed ledger, RNG implementation, raw per-run metrics |
| B06 | HARD | `offspringSize` and terminal-batch behavior are unspecified | With population 300, a 25000 threshold does not align with full 300-offspring batches | Exact offspring/mating-pool sizes and evaluation-loop source |
| B07 | HARD | Metric inputs are incomplete | HV, IGD+, and generalized-spread values depend on reference points/fronts, normalization, and implementation | Exact reference files, reference points, metric revision, and normalization settings |
| B08 | MEDIUM | Initial `eta_m` is only described as random between bounds | Uniform, discrete, truncated, and endpoint choices create different initial strategy populations | Initialization source and distribution |
| B09 | MEDIUM | Detailed method evidence is primarily the accepted manuscript | Springer algorithm images match, but full post-acceptance text/code corrections cannot be exhaustively checked | Accessible version-of-record full text or author confirmation |
| B10 | HARD | Exact parent selector, comparator order, and tie-breaking are not specified | Tournament ties and selection order can change the complete branch-sensitive trajectory | Selection source and comparator configuration |
| B11 | HARD | Statistical variants and pairing are not pinned | “Wilcoxon”, Levene, Welch, and paired Student tests cannot be reconstructed from means and variances | Raw values, pairing ledger, library/version, test options, and tie handling |

## Evaluation-budget sensitivity witness

At inspected official jMetal commit `52fdf0f`, the
[`NSGAIIBuilder`](https://github.com/jMetal/jMetal/blob/52fdf0fe6a985eeb362120a4b2010741802c9c07/jmetal-algorithm/src/main/java/org/uma/jmetal/algorithm/multiobjective/nsgaii/NSGAIIBuilder.java)
defaults both mating-pool and offspring-population sizes to the population size
and uses a sequential evaluator. The corresponding
[`NSGAII`](https://github.com/jMetal/jMetal/blob/52fdf0fe6a985eeb362120a4b2010741802c9c07/jmetal-algorithm/src/main/java/org/uma/jmetal/algorithm/multiobjective/nsgaii/NSGAII.java)
initializes the evaluation count with the population size, adds one full
offspring size after each iteration, and stops when the count is greater than
or equal to the threshold.

Under that specific profile, population `300` and threshold `25000` produce:

```text
300, 600, ..., 24900, 25200 -> stop
```

This proves that the missing terminal-batch rule is material. It does not prove
that the authors used this commit, default builder, or overshoot behavior; the
paper pins none of them.

## Machine and worker boundary

The included CI tests five OS/Python profiles and process worker counts 1, 2,
and 4. This verifies portability of the clean-room formula kernel only.

The paper identifies Windows 11, 8 GB RAM, and an unspecified Intel Core i5,
but does not state the exact CPU model, worker count, evaluator, or parallel RNG
policy. Therefore:

- worker speedup is not a source claim;
- GitHub-hosted runner timings are not comparable scientific benchmarks;
- bitwise identity of a complete branch-sensitive GA across operating systems
  is not required;
- exact same-machine digest and cross-machine quantized formula digest are the
  defensible gates for this limited kernel.

## Current decision

```text
SCIENTIFIC_CLASSIFICATION = PASS
UPDATE_RULE_SPECIFIED = UNKNOWN
STRICT_DECISION = UNKNOWN
CLEAN_ROOM_FORMULA_KERNEL = CONFORMS_TO_DECLARED_INTERPRETATION
AUTHOR_IMPLEMENTATION = NOT_AVAILABLE
PUBLISHED_NUMERIC_REPRODUCTION = BLOCKED
PASS_FULL = NOT_CLAIMED
```
