# EU26-15 eligibility audit

Freeze date: 2026-08-09

Candidate: GARBO

Decision: `CONDITIONAL_NONELIGIBLE`

Permitted scope: `FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY`

## Source-grounded positives

| Gate | Evidence | Decision |
|---|---|---|
| 2020–2026 paper | Bioinformatics 2020, DOI `10.1093/bioinformatics/btaa144` | pass |
| EU author affiliation | University of Eastern Finland is listed for the author team | pass |
| direct adaptive GA | Each generation recalculates crossover probability, mutation probability, and insertion/deletion/substitution operator weights; a strict similarity branch overrides all three | pass for formula scope |
| applied decision dimension | The author repository's erlotinib mRNA CSV has 1,599 columns after removing `class` | pass for dimension only |
| author-linked code | Greco-Lab repository and paper authors/contact information align | pass |
| open code revision | GPL-3.0 is present at exact commit `9727e017...`; code hashes are frozen | pass for code only |
| literal paper endpoint | Table 2 reports erlotinib mRNA GARBO overall score `0.86`, average size `4.5`, F1 `0.80` | context only |
| no external solver in formula check | The clean-room transition requires only standard arithmetic | pass for formula scope |

The applied dimension is not inferred from a benchmark function. The
repository header contains 1,599 measured-expression predictor names and one
`class` target. This establishes a high-dimensional biomarker-selection
decision space, but it does not establish a lawful data-reuse chain.

## Exact adaptive transition

After offspring evaluation, the source computes

\[
fv = \frac{\max(f)-\bar f}{\max(f)}, \qquad
ft = |\bar f-\bar f_{previous}|,
\]

\[
mlc = \operatorname{mean}(|C_i|), \qquad
ssc = \operatorname{mean}_{i>j}
\frac{|C_i\cap C_j|}{|C_i\cup C_j|}.
\]

If `ssc > 0.75`, the next state is exactly
`cxpb=0`, `mutpb=1`, `mutop=[0.9, 0.1, 0]`. Otherwise, four Mamdani-style
9-rule systems and sampled-universe centroid defuzzification produce `cxpb`,
`mutpb`, insertion probability, and deletion probability. Substitution is
then set to `1 - (pDeletion + pInsertion)`; there is no additional
renormalization.

The update occurs after the current generation's variation and evaluation,
so the resulting probabilities govern the next generation.

## Mandatory source quirks

- `mutationFLRules(ft_input, mlc_input)` calls `intFV(ft_input)`. The dormant
  `intFT` definition must still be represented, but must not replace this
  call.
- Every universe follows NumPy `arange(start, stop, step)` with an exclusive
  nominal stop and floating-point step semantics. For example, the final
  sampled `fv` value is `0.6989999999999994`; decimal `0.699` is outside that
  sampled universe for `interp_membership(..., zero_outside_x=True)`.
- Defuzzification is the centroid of the piecewise-linear area between
  adjacent sampled points, not a discrete weighted average.
- The similarity override is strict `>`, not `>=`.

## Decisive blockers

| Required evidence | Finding | Consequence |
|---|---|---|
| complete RNG control | `random.seed(64)` and per-island Python seeds exist, but NumPy RNG is never seeded | exact stochastic replay blocked |
| exact splits and seeds | paper fold identities and full run seed ledger are absent | empirical identity blocked |
| raw runs | no paper run logs, island pickle ledger, or per-fold raw outputs are committed | aggregation replay blocked |
| lawful data manifest | code license is GPL-3.0, but dataset provenance/license is not fully documented | full lawful data gate blocked |
| fixed paper release | no tags/releases; GPL was added more than four years after the paper-era source | release gate blocked |
| pinned runtime | Python 2.7 and unpinned sklearn/deap/numpy/skfuzzy/scipy stack | source-native environment blocked |

## Decision

The direct adaptive mechanism and applied dimension justify a narrow
transition audit. The missing RNG, split, raw-ledger, data-license, release,
and environment evidence decisively prohibit empirical/Table-2 replay and
`PASS_FULL`. Tests added after this preregistration may only establish
`FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY`; they cannot promote the
candidate.
