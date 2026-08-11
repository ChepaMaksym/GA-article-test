# Amendment 002 - MATLAB paper-profile runner

Date: 2026-08-11

This amendment was created after the authenticated Python artifact replay had
already passed. It does not alter the frozen `Jump_4`, `n=20` author-artifact
target, its 500-row acceptance rule, or any retained artifact digest.

## Reason

The candidate previously contained independent MATLAB/GNU Octave formula and
fixed-random-tape checks, but its complete stochastic replay path remained in
Python. The new requirement is to make MATLAB the primary language for the
independent reproduction of the paper algorithm while retaining Python only as
the author-source and artifact reference.

## Added scope

The amendment admits the following implementation work:

- a logical bit-vector `Jump_k` objective without the encoded-integer `n<=53`
  restriction;
- a complete stochastic MATLAB/GNU Octave implementation of paper Algorithm 3;
- a batch runner with an explicit seed ledger, quantiles, standard deviations
  and optional CSV output;
- full-run invariants and fail-closed tests under GNU Octave.

## Frozen paper-profile semantics

The new runner is named `paper_algorithm3_fixed_order` and uses:

1. `lambda_0=1`, `p=lambda/n`, `c=1/lambda`;
2. nearest-integer offspring counts with exact halves rounded upward;
3. one binomial mutation strength per generation;
4. exact distinct-position mutation for every mutant;
5. uniform tie-breaking among best candidates;
6. the selected best mutant plus crossover offspring as the final pool;
7. exclusion of candidates identical to the parent from final selection;
8. strict success relative to the pre-replacement parent;
9. reset to one after an unsuccessful generation whose current real lambda is
   already equal to `n`;
10. logical accounting of `2*round(lambda)` offspring evaluations per completed
    generation, with no charge for the initial parent.

Item 8 is an explicit resolution of the printed Algorithm 3 line-order
ambiguity. The pseudocode replaces `x` before the following line compares
`f(y)>f(x)`, while the surrounding proof treats success as leaving the current
fitness level. The runner therefore stores the old fitness before replacement.

## Outcome-exposure and claim boundary

No full MATLAB experiment was inspected before selecting these semantics. The
semantics come from the paper pseudocode, its explanatory text, and the already
frozen paper/source conflict fixtures. The small CI smoke runs added by this
amendment test invariants and portability only; they are not used to choose an
experiment cell, seed ledger, tolerance, or published-result interpretation.

This amendment can establish:

- `PASS_MATLAB_PAPER_RUNNER_TESTS`;
- support for paper-scale bit-vector dimensions such as `n=60`;
- deterministic replay for a declared MATLAB/GNU Octave environment and seed.

It cannot establish:

- `PASS_FULL`;
- equality with the Python author artifact;
- reproduction of a paper figure or statistical comparison;
- the authors' historical MATLAB environment, because no such environment was
  published;
- a paper-level numerical pass until an experiment cell, seed protocol,
  accounting convention and acceptance rule are frozen separately.
