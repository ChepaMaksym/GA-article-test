# Hybrid 1 test and CI audit

Status: `AUDIT_PASS_WITH_LIMITATIONS`.

This audit is separate from the scientific H1-H3 result. It verifies that the
implementation is tested for the claimed behavior, invalid states fail closed,
deliberate algorithm defects are detected, scientific null/negative results are
not hidden as CI errors, and GitHub Actions preserves evidence when execution
fails.

No merge was performed. PR #19 remains an open draft.

## Final independent audit run

```text
workflow: EU26-21 independent test and CI verification audit
run id: 32029855098
head commit: 6a5165b535bbc05d72a27e9acd42b2643192da13
conclusion: success
```

All four independent jobs passed:

1. current scientific row-generation code matches immutable evidence commit;
2. positive, negative, and failure-reporting test discovery;
3. workflow-trigger, retirement, action-pinning, and failure-semantics audit;
4. strict H1-H3 recomputation from immutable 30-seed rows.

## Scientific-code fingerprint

The audit compared the current result-generating implementation against the
immutable matrix evidence commit:

```text
evidence commit: 6a9e9faba1fe4e7691fbb88cec1e5d2e84232a04
diff exit code: 0
matches: true
```

Compared files include the Hybrid core, benchmarks, Census bridge, paired OLD
and Hybrid protocol, first-hit tracking, isolated seed runner, and frozen
requirements. Therefore the audit did not need to regenerate 30 expensive
optimizer rows merely to verify documentation and CI changes.

Artifact:

```text
name: eu26-21-evidence-code-fingerprint
id: 9288451995
sha256: a7ed57f434d79e89b1e11b8ddfb4befb1aa22d09c0757cfb9b831f011e5b22ac
```

## Complete test discovery

The independent audit compiled all Hybrid 1 modules and tests, then used test
discovery rather than a hand-selected subset:

```text
Ran 53 tests in 8.130s
OK
```

The suite includes positive and deliberately failing synthetic campaigns,
invalid NFE values, malformed digests, inconsistent masks, wrong reset
configuration, non-monotone first-hit ledgers, objective exceptions, parallel
ordering, Jump critical points, OneMax, worker invariance, Census boundaries,
and H1-H3 confidence/coverage decisions.

## Deliberate-mutant sensitivity

A separate test-sensitivity audit first required the unmodified baseline suite
to pass and then introduced six critical defects one at a time:

1. mutation probability changed away from `lambda/n`;
2. crossover probability changed away from `1/lambda`;
3. reset disabled after failure at the cap;
4. exact parent copies allowed into final selection;
5. neutral candidates incorrectly rejected;
6. logical NFE undercounted.

Result:

```text
baseline_pass: true
killed: 6
total: 6
pass: true
```

Each mutant produced a concrete test failure associated with its topic. This is
evidence that the focused tests are sensitive to real semantic defects rather
than only executing the code.

```text
workflow run: 32028306923
job: 95382361963
artifact: 9287903313
sha256: 6e79e5960e9d9d6bc36dd2203f767627448479ad4f3aa6836fc1c3e86732a1c2
```

## Immutable H1-H3 revalidation

The strict audit downloaded the original 30 seed rows from run `31934321927`.
It did not rerun or retune OLD or Hybrid 1. It validated:

- complete seed ledger `1..30`;
- expected seed and search seed;
- reset enabled in both Hybrid endpoints;
- exact single-worker first-hit mode for H3;
- hexadecimal active-sample and initial-mask digests;
- selected-feature indices consistent with binary masks;
- monotone first-hit NFE across increasing targets;
- target hits supported by recorded best evaluated fitness;
- positive first hits inside the initial population;
- H2 conditional on H1;
- separation of scientific failure from protocol failure.

All protocol and audit gates passed. The recomputed decisions remained:

```text
H1 = PASS_CONFIDENCE_BOUND
H2 = PASS
H3 = PASS_CONFIDENCE_BOUND
```

Primary H3 target `0.946` was reproduced exactly:

```text
OLD reached: 29/30
Hybrid reached: 30/30
OLD median capped NFE: 319.0
Hybrid median capped NFE: 141.5
paired median reduction: 55.4990%
95% BCa interval: 34.9110% to 64.9701%
```

Artifact:

```text
name: eu26-21-immutable-row-revalidation
id: 9288452041
sha256: 789a9e49b5e8323b3b97702ef4f4cd9bf308518c409a631520e35574baee2061
```

## CI topology audit

The static CI audit passed every critical gate and produced no warnings:

```text
pass: true
warnings: []
```

Verified properties:

- expensive OLD, Hybrid, mutation, and 30-seed workflows are push/manual only;
- push path filters cover the scientific files capable of changing each result;
- the canonical matrix uses the strict aggregator;
- superseded v1/v2 comparison workflows are manual-only;
- matrix execution uses `fail-fast: false`;
- per-seed logs and partial artifacts are retained with `if: always()`;
- aggregate status is written even when rows are missing or invalid;
- canonical actions are pinned to full commit SHAs;
- result-only documentation does not retrigger unrelated expensive campaigns;
- scientific H1/H3 failure is reported as a result, not transformed into a
  protocol error.

Artifact:

```text
name: eu26-21-ci-topology-audit
id: 9288452105
sha256: 8a662836e9240ec1be1926f412af57a91319b01d0d4dad7c233100ec486452aa
```

## Historical failures retained and analyzed

### Original 30-seed aggregation failure

The seed jobs completed, but the original aggregate job rejected first-hit NFE
below 50. That assumption was wrong because any initial mask may reach a target
at objective call 1 through 50. The red job remains historical evidence. The
canonical strict aggregator now accepts every positive first-hit NFE and rejects
zero, negative, boolean, fractional, or out-of-budget values.

### Negative digest-test failure

The first non-hex test changed only the top-level digest. An earlier consistency
check therefore failed before the intended format check. The fixture was
corrected to corrupt both matching copies, proving the hexadecimal validator is
actually reached.

### CI fixture failure

After adding the mutation workflow, three CI-audit mutation tests failed because
the temporary fixture omitted the new workflow. The production topology was not
the cause. The fixture now copies every audited workflow and contains a
regression that rejects accidental expensive `pull_request` triggers.

These failures were not deleted or described as algorithm successes. Each was
classified by layer and corrected with a targeted regression test.

## Test traceability

| Topic | Verification |
|---|---|
| `p=lambda/n`, `c=1/lambda`, offspring rounding | direct fixed-value assertions and deliberate mutants |
| Shared exact mutation strength | fixed-tape child checks and generation-wide strength assertion |
| Crossover endpoints | probability 0 and 1 tests |
| Final pool and parent-copy exclusion | fixed pool test and parent-copy mutant |
| Neutral acceptance vs strict success | direct transition test and neutral-rejection mutant |
| Reset timing | transition-to-cap vs failure-at-cap test and reset mutant |
| Logical NFE | budget, objective-call equality, first-hit and undercount mutant |
| Parallel workers | exact 1/2/4 signatures, ordered mapping, exception propagation |
| Jump | landscape critical points and reset/no-reset confirmation |
| OneMax | no-regression control |
| Census | empty-mask penalty, nonempty subset, validation/test boundary |
| OLD source | pinned provenance, HUX, adaptive distance, restart, numerical campaign |
| H1-H3 statistics | passing and deliberately failing paired ledgers |
| CI/CD | triggers, action pinning, retirement, artifacts, failure semantics |

## Failure semantics

### CI must fail

- implementation test failure;
- malformed or missing seed row;
- source or commit mismatch;
- inconsistent feature mask;
- invalid or non-monotone NFE;
- worker-dependent scientific output;
- wrong experiment configuration;
- test suite unable to kill a declared critical mutant.

### CI may stay technically valid while the scientific decision is negative

- H1 confidence bound crosses the non-inferiority margin;
- H2 does not improve sparsity after H1 passes;
- H3 lower confidence bound does not exceed 20%;
- reset produces no meaningful Jump or Census effect.

Such outcomes must be recorded as `FAIL...`, `BLOCKED...`, or a null scientific
result, not hidden by tuning or rewritten as an infrastructure error.

## Remaining limitations

1. NFE is logical wrapper-objective calls, not wall-clock time or equal CPU work.
2. H3 compares complete OLD and Hybrid search layers. It does not prove reset
   alone caused the full NFE reduction.
3. Printed CHC-QX Algorithm 1 and the public source are not claimed to be
   identical; the divergence register remains authoritative.
4. The final audit revalidated immutable rows plus a byte-level scientific-code
   fingerprint. It did not rerun the entire expensive 30-seed matrix after
   documentation/CI-only edits.
5. GitHub currently emits Node 20 and `punycode` deprecation warnings for the
   pinned official actions. They did not fail execution, but should be monitored
   when newer action commits are adopted.
6. Repository governance such as branch protection and required-check policy is
   outside this algorithm/test audit.

## Final decision

`AUDIT_PASS_WITH_LIMITATIONS` means:

- the current scientific generator matches the immutable evidence generator;
- all 53 discovered tests pass;
- all 6 deliberate critical mutants are detected;
- immutable H1-H3 decisions reproduce under stricter validation;
- CI trigger, pinning, evidence-retention, and failure semantics pass;
- the limitations above remain explicit.

PR #19 remains draft, open, mergeable, and unmerged.
