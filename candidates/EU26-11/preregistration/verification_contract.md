# EU26-11 deterministic Figure 1 contract v1

Frozen: 2026-08-09, before verifier implementation.

Status: **`TARGETED_DETERMINISTIC_FIGURE1_REPLAY_ONLY`**

## Literal target

- Paper DOI: `10.5220/0013000900003837`.
- Figure: 1.
- Row: `OPT-128`.
- Dimension: 20.
- Published display: `-4.16`.
- Point-set member: `Sub_Sobol_20_128.txt`, 23,229 bytes, SHA-256
  `129d27fbf9711ff270c966f618ec360667582d873094f30cb1dd7e9f78fd2472`.
- Numeric block: `discr.pkl`, 1,705 bytes, SHA-256
  `b2431beff3f660c3a1a0f7e96a3a6e6b095a1acd0d2786a44d5e05851f8381f2`.

The full-precision preimplementation oracle is L2-star
`6.892638555983242e-05`, with `log10 = -4.1616144949364955`. The absolute
formula tolerance is `5e-16`; the log tolerance is `1e-10`. These tolerances
were not selected from candidate-local implementation deviations.

## Independent equation

For `N` points `x_i` in `[0,1]^d`, the clean-room verifier computes:

`D^2 = 3^-d - (2^(1-d)/N) sum_i prod_k(1-x_ik^2)
       + (1/N^2) sum_i sum_j prod_k(1-max(x_ik,x_jk))`.

The reported L2-star discrepancy is `sqrt(D^2)`. The implementation uses no
SciPy, pandas, notebook execution, or author optimizer code.

## Gates

| Gate | Requirement |
|---|---|
| A1 identity | Point set, numeric block, source commit/tree/tag, required source members, sizes, and SHA-256 values match. |
| A2 parser | Header, 128 rows, 20 six-decimal coordinates, range, line endings, and finite values are exact. |
| A3 formula | Independent Python equation equals the frozen full-precision oracle within `5e-16`. |
| A4 numeric block | Inert binary64 extraction yields the same `OPT-128`, 20D value; deserialization execution is forbidden. |
| A5 paper cell | `format(log10(D), '.2f')` is exactly `-4.16`. |
| A6 adaptation | Authenticated source performs mutation, selection, recombination, then mean/path/step-size/covariance adaptation. |
| A7 cross-language | GNU Octave independently evaluates the equation and differs from Python by at most `5e-16`. |
| A8 fail closed | Mutated identity, metadata, dimensions, row count, format, range, non-finite value, or numeric block fails. |
| A9 claim boundary | Reports retain `TARGETED_ARTIFACT_ONLY_NOT_FULL_REPRODUCTION` and explicitly forbid `PASS_FULL`. |

## Outcomes

- `PASS_TARGET_ARTIFACT_REPLAY`: A1 through A5 and A8 pass.
- `PASS_SOURCE_ADAPTATION_GATE`: A1 and A6 pass.
- `PASS_CROSS_LANGUAGE_FORMULA`: A7 passes after binding to the Python report.
- `PASS_FULL`, `PASS_BBOB_EMPIRICAL`, and `PASS_AUTHOR_EXECUTION_REPLAY`:
  forbidden by contract v1.
