# Research 2 - план, OLD/HYBRID аудит і порівняння наукової новизни

Research tag: `RESEARCH_2`

Дата аудиту: 2026-08-21.

## 1. Поточний стан останнього PR

Останній за номером кандидатний PR: `#22`.

```text
PR #22: CLOSED
merged: false
candidate: EU26-27 / self-adaptive GSEMO
base: research/EU26-07-reset-jump-verification
research tag: RESEARCH_2
OLD: REJECTED
HYBRID: BLOCKED_NOT_AUTHORIZED
```

PR закрито коректно: невдалий OLD не був перетворений на позитивний HYBRID
результат і не був merged до базової гілки.

## 2. Що вже пройдено в EU26-27

### PASS - вхідні та формальні ворота

- [x] 2024 publication / eligible EU affiliation;
- [x] decision dimension `n=100`;
- [x] genuine in-run adaptive mutation control is printed in the paper;
- [x] Zenodo record `7880836` authenticated;
- [x] selected archive member authenticated;
- [x] 100 raw runs available for the frozen selected profile;
- [x] selected schema audit;
- [x] selected parser mapping;
- [x] objective micro-oracles;
- [x] hypervolume/archive micro-oracles;
- [x] effort-accounting tests;
- [x] negative controls;
- [x] deterministic smoke tests on a subset of Linux/macOS/Windows jobs.

### FAIL - OLD scientific gates

- [ ] independent 100-run distributional reproduction;
- [ ] exact author implementation/source-revision provenance;
- [ ] full cross-machine binder as a positive OLD result.

The authoritative full OLD workflow run `32413804943` reported:

```text
raw median FE: 57717.5
independent median FE: 119601.0
median ratio: 2.072179148438515
ratio CI95: [1.9015896717026757, 2.3347756733466567]
empirical Kolmogorov distance: 0.74
status: FAIL_OLD_DISTRIBUTIONAL_COMPATIBILITY
```

Therefore:

```text
OLD = FAIL
```

The branch also fails the independently preregistered author-source gate.
Changing either gate after observing the result is forbidden.

## 3. HYBRID verification

HYBRID was not scientifically authorized because OLD did not pass.

Correct status:

```text
HYBRID implementation accepted: false
HYBRID confirmatory campaign: not run
HYBRID cross-machine result: not available
HYBRID improvement: not established
HYBRID NFE reduction: not established
HYBRID iteration reduction: not established
HYBRID wall-clock speedup: not established
```

This is a positive quality-control outcome: the project did not manufacture a
hybrid result on top of a failed OLD baseline.

## 4. Research-2 scientific novelty

### Intended hypothesis

The intended Research-2 hypothesis is broader than simply replacing one
formula with another:

> Under a frozen and independently reproduced OLD protocol, replacing or
> augmenting the original adaptive search-control law with the verified reset
> self-adjusting `(1+(lambda,lambda))` control may reduce search effort and/or
> iterations while preserving the task-level quality criterion.

A valid Research-2 positive result therefore requires simultaneously:

```text
valid OLD reproduction
AND equal/frozen experimental unit
AND equal objective/evaluation accounting
AND paired OLD-HYBRID seeds/initial states
AND quality non-inferiority or superiority
AND predeclared efficiency criterion
AND worker/machine reproducibility
```

### What EU26-27 contributes

EU26-27 does not prove the positive hypothesis. Its contribution is
methodological:

1. artifact selection was frozen before outcome inspection;
2. raw endpoint authentication was separated from independent algorithm
   reproduction;
3. distributional compatibility was tested rather than accepting a nearby
   displayed mean;
4. source provenance remained a mandatory gate after results were seen;
5. HYBRID was blocked automatically after OLD failure.

This contribution can be discussed as research-method hardening, but not as a
successful new optimization method.

## 5. План наступної ітерації Research 2

### Stage A - candidate selection

- [ ] search only EU/USA candidates satisfying the current hard requirements;
- [ ] require >10 decision variables;
- [ ] require a genuine adaptive GA component;
- [ ] require immutable paper/source identity;
- [ ] require author code or an exact author implementation revision;
- [ ] require raw numerical rows or a literal reproducible paper endpoint;
- [ ] require legal code/data provenance;
- [ ] reject before implementation if any hard gate is unavailable.

### Stage B - OLD freeze

Before reading confirmatory outcomes, freeze:

- [ ] exact problem/instance/dataset;
- [ ] dimension;
- [ ] OLD formulas and transition ordering;
- [ ] population/offspring settings;
- [ ] stopping/evaluation budget;
- [ ] seeds and run count;
- [ ] RNG/runtime version;
- [ ] primary metric;
- [ ] literal external endpoint;
- [ ] acceptance tolerance/statistical rule;
- [ ] machine/worker matrix;
- [ ] complete effort ledger.

### Stage C - OLD verification

- [ ] formula fixed-tape tests;
- [ ] objective and representation oracles;
- [ ] exact source-transition tests;
- [ ] deterministic same-seed repeat;
- [ ] full independent run campaign;
- [ ] distributional comparison with retained author/paper evidence;
- [ ] workers `1/2/4` equality;
- [ ] Linux/macOS/Windows matrix;
- [ ] negative controls and deliberate formula mutants;
- [ ] professor red-team audit.

Only `PASS_OLD` opens Stage D.

### Stage D - HYBRID preregistration

Freeze the intervention before outcomes:

- [ ] exact PR #8 control formula being transferred;
- [ ] what OLD state/control is retained;
- [ ] what single search-control layer changes;
- [ ] same problem/data/initial state/seed ledger;
- [ ] same objective budget;
- [ ] total-work ledger, not logical NFE alone;
- [ ] primary quality non-inferiority/superiority rule;
- [ ] primary efficiency rule;
- [ ] reset/no-reset or component ablation when causality is claimed.

### Stage E - HYBRID campaign

- [ ] paired OLD/HYBRID runs;
- [ ] final quality statistics;
- [ ] first-hit NFE/evaluation statistics;
- [ ] iteration/generation counts;
- [ ] total mutation/crossover/offspring work;
- [ ] wall-clock as a secondary hardware-dependent measure;
- [ ] 1/2/4 worker invariance;
- [ ] multi-OS CI;
- [ ] load profiles;
- [ ] graphs and immutable CSV/JSON rows.

### Stage F - academic acceptance

A candidate enters the thesis only when:

```text
PASS_OLD
AND PASS_HYBRID_PRIMARY_GATE
AND PASS_REPRODUCIBILITY
AND PASS_PROFESSOR_AUDIT
```

Otherwise executable candidate files are removed and the next candidate starts
from the verified PR #8 base.

## 6. Порівняння наукової новизни PR #17 та PR #19

| Criterion | PR #17 / EU26-18 | PR #19 / EU26-21 |
|---|---|---|
| Core idea | self-adaptive `eta_m` mutation-strength state inside NSGA-II | transfer reset self-adjusting `(1+(lambda,lambda))` search to CHC-QX feature selection |
| Type of novelty | algorithm/formula interpretation of an existing paper | incremental integration + empirical/methodological contribution |
| Exact adaptive control | mutation distribution index `eta_m` | mutation/crossover/search effort through self-adjusting `lambda` |
| OLD numeric reproduction | not established | source-compatible OLD numeric alignment established |
| HYBRID | none | implemented and evaluated |
| Evidence | formula/order/worker portability tests | 30 paired seeds, quality, subset size, logical NFE, corrected official-UCI profile |
| Strongest supported result | `UNKNOWN` because repair/inheritance semantics are unspecified | `SUPPORTED_SOURCE_COMPATIBLE_ONLY` for joint search-efficiency H2 |
| Main limitation | exact update/application semantics cannot be reconstructed without assumptions | positive source-compatible result does not transfer to corrected official-UCI quality gate |
| Thesis suitability | literature/method audit, not final positive novelty evidence | substantially stronger thesis evidence, but must retain protocol-specific limitation |

### PR #17 - novelty assessment

PR #17 verifies that the paper's novel state is the per-individual polynomial
mutation distribution index `eta_m`. The scientific idea is that mutation
strength becomes inheritable/selection-mediated rather than globally fixed.
This is a meaningful adaptive-GA mechanism. However the paper leaves `repair`,
`x_c`, parent copy/reference semantics and child inheritance under-specified.
Thus the PR correctly remains `UNKNOWN`; the audit cannot promote its own
clean-room interpretation to the authors' exact algorithm.

Professor-style verdict:

```text
conceptual novelty: STRONG
reconstruction certainty: INSUFFICIENT
empirical thesis claim: NOT ESTABLISHED
```

### PR #19 - novelty assessment

PR #19 does not claim invention of CHC-QX, `(1+(lambda,lambda))`, reset, wrapper
feature selection or BCa bootstrap. Its novelty is the reproducible integration
and controlled comparison of these existing lines, including paired seeds,
logical-NFE accounting, worker invariance, negative/mutation controls and an
official-UCI corrected track.

Its strongest source-compatible result is the joint H2 criterion:

```text
quality non-inferiority: PASS_CONFIDENCE_BOUND
median selected features: 5.5 OLD -> 5.0 Hybrid
median capped NFE: 319.0 OLD -> 141.5 Hybrid
paired median NFE reduction: 55.4990%
95% BCa NFE reduction: [34.9110%, 64.9701%]
H2 = SUPPORTED_SOURCE_COMPATIBLE_ONLY
```

The corrected official-UCI profile does not satisfy C-H1 non-inferiority, so
PR #19 cannot claim universal transfer or corrected-profile superiority.

Professor-style verdict:

```text
conceptual novelty: MODERATE_INCREMENTAL
reproducible empirical novelty: STRONGER_THAN_PR17
claim generality: LIMITED_BY_PROTOCOL
thesis suitability: HIGHER_THAN_PR17
```

## 7. Підсумок порівняння

PR #17 has the cleaner *algorithmic self-adaptation idea* but lacks enough
semantics and numerical reproduction to make it a strong thesis result.

PR #19 has less fundamental algorithmic novelty, because it integrates known
mechanisms, but it has much stronger *demonstrated research novelty*: the
intervention is measurable, paired, reproducible and bounded by a corrected
negative result.

For a master's thesis, PR #19 is therefore stronger evidence than PR #17.
For Research 2, the goal should be to combine the best properties of both:

```text
PR17-level clarity of the adaptive mechanism
+
PR19-level independent OLD reproduction and paired HYBRID evidence
+
strict source provenance and total-effort accounting
```

## 8. Required wording for Research 2

Allowed before a positive new candidate is found:

> `RESEARCH_2` denotes the second controlled research line investigating
> whether replacement or augmentation of an OLD adaptive-control formula by a
> verified reset self-adjusting search-control law can improve search
> efficiency under equal and reproducible experimental conditions. EU26-27 is
> retained as a rejected methodological case and does not constitute positive
> evidence for the hypothesis.

Forbidden until a new candidate passes all gates:

- "Research 2 proved improvement";
- "the new formula reduces iterations";
- "HYBRID is more efficient";
- "the result was verified on different machines";
- "the new method is universally better";
- "EU26-27 reproduced the paper".
