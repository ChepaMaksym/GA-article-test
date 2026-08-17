# Hybrid 1 test and CI audit

Status: `AUDIT_RECHECK_RUNNING`.

This audit is separate from the scientific H1-H3 result. It checks whether the
implementation is tested for the claimed behavior, whether invalid states fail
closed, whether deliberate algorithm defects are detected, and whether GitHub
Actions preserves evidence when a test or experiment fails.

No merge is part of this stage.

## Historical failures retained as evidence

### Original matrix aggregate failure

The immutable 30-seed matrix run `31934321927` completed all 30 seed jobs, but
its original aggregate job failed. The cause was an analysis guard that rejected
a first target hit with NFE below 50. Such a hit is valid because any of the 50
initial masks may reach a target at objective call 1 through 50.

This was not an optimizer failure and not a failed scientific hypothesis. The
fix is now in the canonical strict aggregator and directly regression-tested.
The original red job remains part of the provenance.

### First independent negative-test failure

The first audit run also produced one deliberately retained test-design failure:
a non-hex digest test changed only the top-level digest, so the older consistency
check correctly failed before the intended hexadecimal-format check. The test
was corrected to corrupt both consistent copies and now reaches the intended
invariant. No optimizer output or seed row was regenerated.

### First CI topology fixture failure

After adding the mutation-sensitivity workflow, three CI-audit mutation tests
failed because their temporary fixture did not copy that new workflow. The
fixture was incomplete; the production workflow topology was not the cause. The
fixture now copies every audited workflow and includes a regression that rejects
an expensive `pull_request` trigger.

## Test traceability

| Topic | Main tests | What is checked |
|---|---|---|
| Offspring controls | `test_hybrid_1_core.py` | half-up offspring rounding, `p=lambda/n`, `c=1/lambda` |
| Lambda transitions | core and extended semantic tests | strict-success shrink, failure growth, reset only after a failed generation already at the cap |
| Mutation | core and extended semantic tests | one shared exact strength, distinct-bit flips, zero-strength endpoint |
| Crossover | core and extended semantic tests | biased crossover and probability-zero/probability-one endpoints |
| Final pool | core tests | best mutant retained, exact parent copies excluded |
| Acceptance | core and extended semantic tests | neutral acceptance but strict-success-only parameter shrink |
| NFE accounting | core and extended semantic tests | no budget overshoot and objective-call count equals recorded logical NFE |
| Parallel workers | worker and extended semantic tests | ordered outputs, exception propagation, exact 1/2/4-worker scientific signatures |
| Jump | Jump tests plus 50-seed campaign | local optimum/valley/global optimum definition and reset/no-reset effect |
| OneMax | control tests | reset is unnecessary and does not change solved endpoints |
| Census boundary | synthetic and real smoke tests | empty-mask penalty, validation-only search, held-out test evaluation |
| OLD source | source/campaign tests | pinned HUX, adaptive distance, restart, source endpoint, numerical gates |
| H1-H3 | paired-comparison tests | positive and deliberately failing synthetic ledgers, confidence and coverage gates |
| Immutable rows | strict audit tests | seeds, reset flag, digests, masks, monotone first-hit NFE, best-fitness support |
| Scientific failure reporting | strict audit tests | valid negative H1/H3 results remain scientific results; H2 is blocked when H1 fails |
| CI topology | CI audit tests | trigger scope, action SHA pinning, retired workflows, partial-failure artifacts |
| Test sensitivity | mutation audit | six deliberate critical-code defects must each make focused tests fail |

## Deliberate-mutant result

The baseline focused suite passed and all six deliberate defects were detected:

1. mutation probability changed away from `lambda/n`;
2. crossover probability changed away from `1/lambda`;
3. reset disabled at the cap;
4. exact parent copies allowed into final selection;
5. neutral candidates incorrectly rejected;
6. logical NFE undercounted.

The mutation audit run `32028306923` killed `6/6` mutants and produced artifact
`9287903313` with digest
`sha256:6e79e5960e9d9d6bc36dd2203f767627448479ad4f3aa6836fc1c3e86732a1c2`.

## CI failure semantics

### Implementation or protocol failure

Malformed/missing rows, wrong seeds, inconsistent masks, invalid NFE, wrong
reset configuration, worker-dependent output, source-provenance mismatch, and
test failures make CI fail. Logs and partial artifacts use `if: always()`.

### Scientific hypothesis failure

A confidence interval crossing a threshold or a null/negative algorithm effect
is written as a scientific `FAIL...` decision in the report. The canonical
aggregator does not convert an honest negative H1/H3 result into a protocol
error.

## Trigger audit and correction

GitHub evaluates `paths` for pull requests using a three-dot diff against the
merge base, whereas pushes to an existing branch use a two-dot diff between the
previous and new heads. On this large PR, that meant later audit-only commits
continued to match old scientific files and repeatedly retriggered expensive
campaigns.

The corrected topology is:

- expensive OLD, Hybrid, mutation, and 30-seed workflows are `push` plus manual
  dispatch only;
- push path filters are specific to the files that can alter each result;
- the independent audit remains a push-scoped check visible on the PR head;
- superseded v1/v2 comparison workflows remain manual-only;
- the canonical matrix no longer watches unrelated CI-audit tests or result-only
  documentation;
- canonical third-party actions are pinned to full commit SHAs.

## Claim limitations retained

- NFE means logical wrapper-objective calls, not wall time or equal CPU work.
- H3 compares complete search layers and does not prove reset alone caused the
  full NFE difference.
- Reset-specific causal evidence comes from paired reset/no-reset controls.
- The printed CHC-QX paper and public source are not claimed to be identical.
- The PR remains draft and is not merged.

## Final gate

This status changes to `AUDIT_PASS`, `AUDIT_FAIL`, or
`AUDIT_PASS_WITH_LIMITATIONS` only after the corrected independent audit
workflow completes. Any red workflow is retained and analyzed rather than
renamed as success.
