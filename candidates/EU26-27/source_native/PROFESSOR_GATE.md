# Professor gate — EU26-27 single source-native OLD

Research tag: `RESEARCH_2`

## Scope

The only OLD implementation under scientific evaluation is the frozen author
repository `FurongYe/GSEMO@fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380`.
No project reimplementation may substitute for it in the OLD decision.

## Questions that must be answered before PASS

1. **Source identity** — Are the exact author commit and critical algorithm
   blobs authenticated before and after build?
2. **Dependency identity** — Does the selected paper-era IOHexperimenter
   revision compile the unchanged author source and reproduce the retained raw
   artifact? If not, dependency identity remains unresolved.
3. **Experimental unit** — Are exactly 100 sequential runs generated from the
   author's one-time `random::seed(10)` stream?
4. **Problem identity** — Is the command exactly OneMinMax `n=100`, TwoRate,
   `lambda=10`, `p=1`, HV, budget `100000`, runs `100`?
5. **Raw equivalence** — Does the generated 101×100 first-hit matrix match the
   authenticated Zenodo matrix exactly, not merely in mean/median?
6. **Published endpoint identity** — Does the Zenodo raw mean agree with the
   matching paper Table 1 row, **OneMinMax / two-rate / HV / lambda=10 =
   `61624 FE`**, under the predeclared ±1 FE formatting tolerance?
7. **Anchor audit** — Is `61618 FE` explicitly excluded from this OLD gate
   because it belongs to **AGSEMO in Table 2**, not TwoRate+HV in Table 1?
8. **Accounting** — Are first-hit values objective-evaluation indices produced
   by the original logger, with no alternate NFE definition introduced by the
   project?
9. **CI honesty** — Are cross-OS jobs treated as build/smoke portability only,
   while the historical sequential RNG batch remains unchanged?
10. **Graph provenance** — Are ECDF and run-by-run figures generated only from
   the immutable comparison report and bound by SHA-256?
11. **Claim boundary** — Is HYBRID blocked unless every mandatory OLD gate
   passes on the current head?

## Fail-closed decision

```text
PASS_SOURCE_NATIVE_OLD
    only if exact first-hit matrix == Zenodo
    AND exact endpoint vector == Zenodo
    AND 100/100 runs complete
    AND Zenodo raw mean is consistent with matching Table 1 value 61624 FE
    AND source/blob identity checks pass

otherwise
    FAIL_SOURCE_NATIVE_OLD
    HYBRID = BLOCKED_NOT_AUTHORIZED
```

No post-hoc tolerance widening, seed replacement, alternate aggregation,
partial-run selection or manual graph editing is admissible.

## Corrected publication anchor

The article reports two nearby but different values for different algorithms:

```text
Table 1: OneMinMax, two-rate GSEMO, HV, lambda=10 -> 61 624 FE
Table 2: OneMinMax, AGSEMO, lambda=10             -> 61 618 FE
```

The frozen OLD command generates `TwoRateL10P1HV`, so Table 1 is the only
profile-compatible publication anchor. The authenticated Zenodo endpoint mean
is `61623.78 FE`, which rounds to `61624 FE`. Correcting the earlier AGSEMO
anchor is a profile-identity correction, not a numerical relaxation: the exact
raw matrix and endpoint equality requirements remain unchanged.

## Academic interpretation

An exact source-native replay demonstrates reproducibility of the published
experimental artifact for the frozen environment. It does **not** by itself
constitute new scientific novelty. Novelty can only enter in Stage 2, where a
new hybrid controller is introduced under a separately frozen protocol and
shown to improve a preregistered efficiency/quality criterion relative to this
single OLD baseline.

If exact replay cannot be recovered despite source- and provenance-grounded
environment reconstruction, the thesis may report a reproducibility limitation:
the public source, public raw artifact and documented seed/profile are
individually identifiable but insufficient to reconstruct the exact historical
stochastic trajectory without additional environment provenance. Such a
finding does not authorize a HYBRID performance comparison against a falsely
claimed reproduced OLD.

## Wording to avoid

Do not write:

- “the algorithm is universally reproduced”;
- “cross-platform identical results” unless raw equality is actually shown;
- “workers 1/2/4 reproduce OLD” — parallelizing the historical global RNG
  stream changes the source experiment;
- “HYBRID improves the paper” before the HYBRID primary gate passes;
- “first in the world” or other priority claims without a dedicated literature
  review.

Preferred wording after a successful OLD gate:

> The unchanged paper-era author implementation reproduced the authenticated
> Zenodo first-hit matrix for the frozen OneMinMax TwoRate+HV configuration.
> The corresponding Zenodo mean (61623.78 FE) is consistent with the paper's
> Table 1 value (61624 FE). This establishes a source-native baseline for the
> subsequent preregistered hybrid experiment; it is not itself the contribution
> claimed as scientific novelty.
