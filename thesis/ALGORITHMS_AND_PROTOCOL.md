# Formal algorithm and experimental protocol specification

Цей файл є технічним додатком до магістерського рукопису. Формули тут мають відповідати executable implementation; якщо код і текст розходяться, claim блокується до виправлення.

## A. Canonical OLD — TwoRate GSEMO

### State

- Pareto archive `P`;
- problem dimension `n=100`;
- offspring count `lambda=10`;
- TwoRate state `r`, initialized from `p0*n`, where `p0=1/n`;
- adaptation metric: hypervolume.

### Generation

For offspring index `i`:

```text
if i < lambda/2:
    p_i = r/(2n)
else:
    p_i = 2r/n

l_i ~ Binomial(n, p_i) conditioned on l_i >= 1
select parent uniformly from current Pareto archive
flip l_i bit positions
evaluate candidate
```

After producing the generation, the source TwoRate controller selects the best offspring according to the configured Pareto metric and updates `r` using its original stochastic multiplicative rule bounded to the author implementation limits. The thesis does not replace this rule with a clean-room approximation.

Archive update then retains nondominated solutions according to the source implementation.

### Completion endpoint

```text
T = first function-evaluation count at which all 101 OneMinMax Pareto points are first-hit
```

`T` is the primary runtime endpoint in hybrid comparisons.

## B. HYBRID invariant

Every hybrid profile must satisfy:

```text
source code base = exact authenticated GSEMO revision
problem = OneMinMax
n = 100
initial mutation state = OLD
parent selection = OLD
mutation implementation = OLD
TwoRate r update = OLD
archive update = OLD
objective / HV calculation = OLD
primary endpoint = OLD
```

Only the offspring-count controller may differ.

Before evaluating a hybrid profile, the patched executable is run in plain `TwoRate` mode for the canonical 100-run replay. Hybrid evaluation is authorized only if the resulting `101 x 100` first-hit matrix and 100 endpoint values are exactly equal to the authenticated OLD reference.

## C. HYBRID v1 — reset controller

State:

```text
L0 = 10
F = 1.5
Lmin = 1
Lmax = n
```

A generation is a strict success iff the best candidate contribution yields a Pareto-metric value strictly greater than the metric value before the generation.

Update:

```text
success:
    L <- max(L/F, Lmin)

failure when L is at cap and reset enabled:
    L <- Lmin

other failure:
    L <- min(L * F^(1/4), Lmax)

lambda_next = floor(L + 0.5)
```

A no-reset ablation removes only the reset case.

## D. HYBRID v2 — baseline-preserving rollback

Constants:

```text
F = 1.5
U = 5
lambda_floor = 10
lambda_max = 100
Delta_initial = 10
```

State:

```text
lambda_real
lambda_base
bad_count B
rollback interval Delta
```

Initialization:

```text
lambda_real = 10
lambda_base = 10
B = 0
Delta = 10
```

Update after the unchanged TwoRate update:

```text
if strict_success:
    lambda_real <- max(lambda_real/F, 10)
    lambda_base <- lambda_real
    B <- 0
    Delta <- 10
else:
    B <- B + 1
    if B == Delta:
        B <- 0
        Delta <- Delta + 1
    lambda_real <- min(lambda_base * F^(B/(U-1)), 100)

lambda_next = floor(lambda_real + 0.5), clipped to [10,100]
```

Ablation `HYBRID_FLOOR`:

```text
success: lambda_real <- max(lambda_real/F, 10)
failure: lambda_real <- min(lambda_real*F^(1/4), 100)
```

## E. HYBRID v3 — capped development family

Constants shared by all candidates:

```text
F = 1.5
lambda_floor = 10
C = {15,20,30,40,60,100}
```

For each fixed `c in C`:

```text
success:
    lambda_real <- max(lambda_real/F, 10)

failure:
    lambda_real <- min(lambda_real*F^(1/4), c)

lambda_next = floor(lambda_real + 0.5), clipped to [10,c]
```

No other component is allowed to depend on `c`.

## F. V3 development selection

Development ledger:

```text
D = {28001,...,28030}
```

This ledger was previously used as v2 confirmation and is therefore retired from confirmatory claims. Its explicit role in v3 is controller development.

For each seed `s` run paired exact OLD and every capped profile. For cap `c` compute:

```text
r_s(c) = (T_OLD(s) - T_c(s)) / T_OLD(s)
S(c) = median_s r_s(c)
```

Deterministic selection:

```text
c* = argmax_c S(c)
```

If several caps have exactly identical `S(c)`, choose the numerically smallest cap.

The program must persist `c*` in `selected_cap.json` before any v3 holdout command executes.

## G. V3 independent confirmation

Holdout ledger:

```text
H = {29001,...,29030}
```

It must be disjoint from all previous confirmation ledgers.

For each `s in H` run paired:

```text
OLD(s)
HybridCap(c*)(s)
```

Primary per-pair effect:

```text
q_s = (T_OLD(s) - T_V3(s)) / T_OLD(s)
```

Primary statistic:

```text
theta = median_s q_s
```

Uncertainty:

```text
paired percentile bootstrap
B = 50,000 resamples
bootstrap RNG seed = 29029
95% interval = [2.5th percentile, 97.5th percentile]
```

Confirmatory acceptance:

```text
PASS iff:
    OLD complete = 30/30
    V3 complete = 30/30
    CI_lower > 0
```

Any other result is `FAIL` for the preregistered improvement claim.

## H. Distinguishing evaluation efficiency from wall-clock efficiency

The primary endpoint counts logical objective evaluations. This prevents hardware scheduling from changing the algorithmic comparison.

Wall-clock evaluation is a separate robustness/performance study and must specify:

- OS;
- CPU model;
- physical/logical core count;
- worker count;
- compiler/build mode;
- concurrent background load;
- run scheduling strategy;
- whether a generation evaluates offspring serially or in parallel.

A wall-clock result cannot replace the primary FE result.

## I. Required negative controls

The verification suite should contain synthetic controls demonstrating that the analysis layer can return:

- clearly positive paired effect -> PASS;
- clearly negative paired effect -> FAIL;
- interval crossing zero -> FAIL / no confirmatory evidence;
- incomplete Pareto run -> fail closed;
- wrong seed ledger -> fail closed;
- changed OLD output after patch -> block hybrid execution.

## J. Claim hierarchy

```text
Level 0 — source identity
Level 1 — OLD exact reproduction
Level 2 — implementation correctness of new controller
Level 3 — independent statistical effect on OneMinMax n=100
Level 4 — cross-platform / worker robustness
Level 5 — benchmark generalization
Level 6 — practical/application generalization
```

Passing a lower level does not imply passing a higher level.
