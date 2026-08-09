# EU26-15 verification contract

This contract was frozen before the clean-room implementation and its test
outcomes. The machine-readable authority is
[`../config/verification_contract.json`](../config/verification_contract.json).

## Allowed execution

The verifier may:

1. hash and token-probe an exact checkout of the licensed upstream revision;
2. prove that the two paper-era Python sources are byte-identical to the
   licensed revision;
3. evaluate frozen synthetic fuzzy inputs in standard-library Python and
   MATLAB/GNU Octave;
4. derive `fv`, `ft`, `mlc`, and `ssc` from frozen synthetic populations;
5. optionally count columns and rows in a user-supplied CSV.

The verifier must not import or execute upstream `GARBO.py`, train a random
forest, launch islands, deserialize upstream pickle files, infer missing
folds, or compare a generated model with Table 2.

## Frozen numerical semantics

- Binary64 arithmetic is used.
- Universes reproduce NumPy's effective-step `arange` construction:
  `n = ceil((stop-start)/step)`,
  `effective_step = (start+step)-start`, and
  `x[i] = start + i*effective_step` for `i=0..n-1`.
- Triangular and trapezoidal memberships are first sampled on those
  universes. Antecedent values use zero-outside linear interpolation.
- Rule conjunction and implication use `min`; aggregation uses `max`.
- Centroids integrate each line segment exactly as a rectangle, left/right
  triangle, or general trapezoid before dividing first moment by area.
- Zero total fuzzy area is an error.
- Numerical fixture comparisons use absolute tolerance `5e-12`.

## Frozen branch coverage

The fixture set contains the 3×3 low/medium/high peaks for every 9-rule
matrix, mixed-membership points, lower endpoints, `ssc == 0.75`, an
`ssc > 0.75` override, a population-derived transition, all nine feature-rank
rules, and fail-closed adversarial inputs.

The mutation regression at `ft=0.015, mlc=20` must produce approximately
`0.2` by using `intFV`. A superficially corrected `intFT` implementation
would produce approximately `0.15` and must fail.

## Source probe

The mandatory probe requires:

- Git HEAD `9727e017371484dd5837a0859b41c195a87fd8d0`;
- tree `995ee6c51315ea52d0e82211fb708e32b45800bb`;
- exact SHA-256 values for `GARBO.py`, `runGARBO.py`, and `LICENSE`;
- the literal `intFV(ft_input)` quirk, universe declarations, strict
  similarity condition, override constants, and substitution formula;
- byte identity of the two Python files at paper-era commit
  `1854385ffb0be85ef8deeeda45980aaed6e50207`.

An optional CSV probe requires exactly 1,600 header fields, final field
`class`, and 1,599 predictors. This is a structural observation only.

## Result vocabulary

Permitted successful labels:

- `PASS_SOURCE_IDENTITY`
- `PASS_PYTHON_TRANSITION_FIXTURES`
- `PASS_OCTAVE_TRANSITION_FIXTURES`
- `PASS_FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY`

Forbidden labels or implications:

- `PASS_FULL`
- `REPRODUCED`
- `TABLE_2_REPLAYED`
- any claim that the dataset license was established

No test result can alter the frozen candidate status
`CONDITIONAL_NONELIGIBLE`.
