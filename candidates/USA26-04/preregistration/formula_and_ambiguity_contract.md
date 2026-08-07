# USA26-04 formula-and-ambiguity validation contract

Frozen: 2026-08-07, before implementation or execution.

Scope: **`FORMULA_AND_AMBIGUITY_VALIDATION_ONLY`**

Overall scientific status: **`BLOCKED_G5_G9`**

Published-result status: **`INCONCLUSIVE_PUBLISHED_RESULT`**

This contract permits clean-room objective-function checks, three explicitly
separated reward interpretations, local controller-update oracles, ambiguity
witnesses, and fixed-tape portability checks. It forbids a full genetic
algorithm, a Table 1 replay, post-outcome selection among interpretations, and
any `PASS_FULL` or reproduced-paper claim.

## Frozen primary descriptive cell

The sole primary paper cell is fixed prospectively as:

| Field | Frozen value |
|---|---|
| method | Bandit |
| function | Rastrigin |
| dimension | 100 |
| initialization | independent \(\mathcal N(0,10^2I)\) |
| population | 100 non-elites + 1 unchanged elite |
| selection | truncation, size 10 |
| generations | 1000 |
| reported runs | 50 |
| Table 1 statistic | average final function value |
| descriptive value | 3686 |

The interval `[3685.5, 3686.5)` records only values that round to the printed
integer under round-to-nearest conventions. It is not a stochastic equivalence
margin and must never be evaluated as a reproduction gate. The accompanying
GESMR, SAMR, and LAMR-100 values (`4505`, `4772`, `815`) are context only.

All six Bandit values printed in Table 1 are retained verbatim in
`fixtures/published_table1_descriptive.csv`: Ackley `10.1`, Griewank
`4.69e-3`, Rastrigin `3686`, Rosenbrock `105`, Sphere `5.56e-8`, and Linear
`-2.91e46`. They remain descriptive; none is an executable target.

## Frozen function definitions

For nonempty finite \({\bf x}\in\mathbb R^d\), the clean-room ports implement
only Appendix A:

- Ackley:
  \(-20e^{-0.2\sqrt{d^{-1}\sum x_i^2}}
  -e^{d^{-1}\sum\cos(2\pi x_i)}+20+e\).
- Griewank: \(\sum x_i^2/4000-\prod\cos(x_i/\sqrt{i})+1\), with
  paper-native one-based \(i\).
- Rastrigin: \(10d+\sum[x_i^2-10\cos(2\pi x_i)]\).
- Rosenbrock:
  \(\sum_{i=1}^{d-1}[100(x_{i+1}-x_i^2)^2+(x_i-1)^2]\), requiring
  \(d\ge2\).
- Sphere: \(\sum x_i^2\).
- Linear: \(\sum x_i\).

The reported initialization standard deviations are respectively
`10, 1000, 10, 1, 10, 1`; all functions use dimension 100. The budget is 1000
generations except Linear, which uses 100.

## Three reward semantics, frozen before outcomes

No result may be used to choose between these interpretations.

| ID | Source-grounded interpretation | Formula | Domain | Role |
|---|---|---|---|---|
| P1 | function-minimization prose and Appendix D (`f(x)=x`, no transform) | `mean(E - E_child)` | equal, nonempty finite arrays | **primary formula-validation interpretation** |
| P2 | Eq. (2) direction, normalized as the prose's average | `mean(log1p(E) - log1p(E_child))` | P1 plus every entry `>-1` | secondary ambiguity branch |
| P3 | Algorithm 2 executable sign | `mean(log1p(E_child) - log1p(E))` | P1 plus every entry `>-1` | secondary ambiguity branch |

For `E=[9]` and `E_child=[3]`, the frozen oracles are P1 `6`, P2
`+log(2.5)`, and P3 `-log(2.5)`. The P2/P3 sign opposition is a required
ambiguity witness, not permission to resolve the article. Eq. (2) prints
indices `0..m` but divides by `m`; that is `m+1` entries divided by `m` and is
singular for a one-entry vector (`m=0`). The ports therefore expose the three
named, validated semantics but do not label the printed normalization as
repaired source code.

Linear values can be below `-1`, so P2/P3 may be undefined even though P1 is
defined. Domain rejection is a required adversarial test.

## Controller formula scope

Only these locally specified equations may be implemented:

1. paper tile index
   \(i=\lfloor(x-o-l)/w\rfloor+1\), reported as a paper-style integer;
2. history statistic: append the immediate reward, retain at most
   `len_history`, and use the maximum of the populated entries;
3. \(g=2(v-r_{max})\);
4. \(m' = \mu m+g\);
5. \(v'=v-\gamma(g+\mu m')\).

The micro-oracle `v=0`, `m=0`, `gamma=0.001`, `mu=0.9`, `r_max=1` yields
`g=-2`, `m'=-2`, and `v'=0.0038`. Negating the reward yields `v'=-0.0038`.

`fixtures/fixed_controller_tape.json` supplies synthetic initial values,
histories, branch values, and random variates. Those values are test inputs
chosen by this project; they are not attributed to the article. The fixture
uses a unique maximum and an interior tile, so it validates an equation/update
port without resolving the article's initialization, tie, boundary, or RNG
choices.

## Mandatory ambiguity and absence findings

The following remain unresolved and keep G5/G9 blocked:

1. Eq. (2) and the narrative reward improvement; Algorithm 2 has the exact
   opposite sign.
2. Function minimization explicitly uses the identity proxy without a log,
   while Algorithm 2 hard-codes `log(1+error)`.
3. Eq. (2)'s divisor/index mismatch is undefined for its one-dimensional
   function-minimization use if read literally.
4. Initial tile values, momenta, reward deques, behavior of empty/partially
   filled histories, and the ensemble's initial state are not specified.
5. `argmax` tie-breaking, random-bandit choice details, RNG family, RNG stream
   partitioning, and seed IDs are not specified.
6. Boundary construction is inconsistent. For `l=-100`, `r=100`, and
   `res=0.03`, `floor((r-l)/res)=6666`. Restricting selected tiles to
   `0..6665` leaves `[99.98,100]` uncovered; tile 6666 covers
   `[99.98,100.01]` and overshoots the declared range. A test must demonstrate
   both facts and must not silently choose one behavior.
7. The continuous-vector mutation transition, parent/child wiring, elite
   update order, and exact function-minimization driver are not present in the
   paper-specific artifacts. No full GA may be inferred from a related paper.
8. No paper-specific controller source, exact revision, dependency lock,
   environment image, seed ledger, raw run endpoints, or per-run uncertainty
   artifact was found. The reported bootstrap confidence intervals and Welch
   tests do not supply numeric intervals or samples.
9. The Appendix D standard-deviation derivation is internally inconsistent.
   For \(\log(2^U)=U\log2\), \(U\sim U[-1,1]\), the SD is
   \(\log2/\sqrt3\approx0.4001887113\). The printed symbolic expression
   \(\sqrt{2\log2/12}\approx0.3398889967\), not the stated `0.223`.

## Frozen validation gates

| Gate | Requirement | Pass meaning |
|---|---|---|
| H0 | pinned source identities, license notes, Git/source hashes, and machine-readable absence manifest all agree | provenance/absence audit only |
| H1 | objective anchors, P1/P2/P3 signs and domains, Nesterov oracle, and boundary/tie witnesses pass | local formulas/ambiguities validated |
| H2 | Python and MATLAB/Octave consume the same fixed tape and produce matching controller-transition fields | deterministic port agreement only |
| H3 | finite/nonempty/domain/schema checks and adversarial/property tests fail closed | implementation robustness only |
| H4 | serial and 4-/8-worker formula-case outputs match exactly; one warm-up and five retained timings are recorded | independent-case batch safety only |
| H5 | Work-4, Work-8, and GitHub-4 reports have identical frozen source hashes and formula-case digests | tested-profile portability only |

Passing H0-H5 cannot alter `BLOCKED_G5_G9`,
`INCONCLUSIVE_PUBLISHED_RESULT`, or registry `conditional_noneligible`.

## Forbidden claims and actions

- no full genetic algorithm or continuous mutation implementation;
- no random reconstruction of the article's missing controller state;
- no execution against the six Table 1 values;
- no equivalence/non-inferiority margin for a published result;
- no `PASS_FULL`, reproduced, replicated, or source-native replay claim;
- no promotion of USA26-04 to an eligible cohort record.
