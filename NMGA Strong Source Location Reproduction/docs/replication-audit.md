# NMGA Article Replication Audit

## Scope
This audit checks whether the local MATLAB project is a faithful replication package for:

**Application of New Modified Genetic Algorithm in Inverse Calculation of Strong Source Location**

- DOI: `10.3390/atmos14010089`
- Source URL: https://www.mdpi.com/2073-4433/14/1/89
- Local project status: synthetic replication package, not raw-data reproduction.

The article states that data sharing is not applicable, so this repository must not claim exact raw-data reproduction of Table 1. The correct claim is:

```text
public-text exact MGA/NMGA operators and parameters reproduced on synthetic observations
```

## Replication Classification

| Area | Status | Notes |
|---|---|---|
| Forward model | Partially faithful | Uses Gaussian plume concentration model consistent with the article workflow. Exact article monitoring data are unavailable. |
| Search vector | Faithful | Optimizes `[x, y, Q, H]`, matching source location, release rate, and effective height. |
| Article parameters | Faithful after audit fix | `article_exact_spec` stores population `100`, MGA generations `2000`, NMGA generations `1000/500`, `P1 = 0.6`, `P2 = 0.01`, `b = 2`, `beta = 0.7`, `gamma = 0.5`, `SetMax = 20`. |
| NMGA dynamic rates | Faithful after audit fix | Uses `Pc = P1 * (1 - gen / maxgen)^b`, `Pm = P2 * (1 + gen / maxgen)^b`, with `P1 = 0.6`, `P2 = 0.01`, `b = 2`. |
| Raw data and sensors | Not fully reproducible | Exact figure-eight sensor coordinates and observed concentrations are not available in this workspace. |
| Reported Table 1 values | Encoded for comparison | Article means/std/relative errors are stored in `article_reported`; reports must not treat synthetic results as exact Table 1 duplication. |
| NMGA crossover/elimination-pool mechanics | Public-text equivalent | Article-exact mode uses AGP/EGP split helpers, beta crossover, SetMax branch logic, and nonuniform mutation. This is still not a raw-data reproduction. |
| Adaptive-control claim | Correctly bounded | Current method is generation-scheduled parameter control, not feedback-adaptive control. |

## Test Audit

Current tests are good for deterministic smoke/regression verification:

- project structure exists;
- Gaussian plume output is finite;
- downwind concentrations can be positive;
- centerline concentration exceeds off-center concentration;
- upwind concentration is zero;
- article NMGA rate parameters are encoded;
- Table 1 sentinel values are encoded;
- `nmga_adaptive_rates` follows article Formula 7/8 exactly;
- exact Formula 7/8 values are checked at generations `1`, `SetMax`, `500`, and `1000`;
- MGA fixed `Pc = 0.6` and `Pm = 0.01` are checked;
- `article_exact` profile uses `100` repeats and generations `2000/1000/500`;
- AGP/EGP split, EGP inheritance child, and nonuniform mutation shrinkage are checked with deterministic fixtures;
- `article_sse` objective is checked against raw SSE;
- rate histories are monotonic and within configured bounds;
- optimizer output respects physical bounds;
- optimizer history arrays match generation count;
- diversity, stagnation, generation-to-best, and runtime diagnostics are finite;
- repeated runs with the same seed are reproducible;
- adaptive audit is deterministic in no-write test mode.

## Test Gaps

The test suite still does not prove full article replication. Remaining gaps:

- no test runs the full `100` repeated calculations because that is expensive;
- unit tests only smoke-check article report generation with profile `unit`, not full `article_exact`;
- no test proves exact Table 1 reproduction, because raw monitoring data are unavailable;
- no independent fixture of the article's original sensor coordinates exists.

## Logic Audit

### Corrected Logic

- `article_reported` now stores the article dynamic-rate parameters `P1`, `P2`, and `b`.
- `nmga_options` now exposes those article parameters through NMGA options.
- `nmga_adaptive_rates` now implements the article generation schedule directly.
- `article_exact_spec` is the structured local source of truth for public article constants, formulas, bounds, and Table 1 reference values.
- `nmga_options('NMGA', 'article_exact')` separates the article Table 1 protocol from quick/sandbox profiles.
- `source_objective` supports `article_sse` for article-exact mode and keeps `normalized_mse` for sandbox checks.
- `run_article_exact_reproduction` writes `article_exact_report.md`, `operator_audit_report.md`, and MAT artifacts for convergence/error arrays.
- `run_nmga_adaptive_audit_impl(profile, writeOutputs)` can run with `writeOutputs = false` so unit tests do not overwrite generated reports.
- `main` explicitly runs a lightweight `unit` adaptive audit and prints a summary.

### Remaining Logic Risks

- Public-text operator equivalence is implemented and unit-tested, but no original author code is available for line-by-line equivalence.
- `article_exact` uses raw SSE as the minimized objective and stores reciprocal fitness in details; sandbox workflows still use normalized MSE.
- Sensor-grid scenarios are documented approximations, not article coordinates.

## Result Audit

Existing quick synthetic reports are useful for workflow behavior, but not final article-result evidence.

Results are acceptable only under this interpretation:

```text
synthetic smoke/reproduction results showing whether the local implementation behaves plausibly
```

Results are not acceptable under this interpretation:

```text
exact reproduction of article Table 1 from original monitoring data
```

After the rate-schedule correction, generated reports should be regenerated before being treated as current:

```matlab
main
run_article_exact_reproduction
run_nmga_reproduction
run_nmga_adaptive_audit
run_sandbox_deviation_check
```

For article-sized verification:

```matlab
run_nmga_reproduction('full')
run_nmga_adaptive_audit('full')
run_article_exact_reproduction('article_exact')
```

## Verification Plan

### Level 1: Static Verification

1. Run `git diff --check`.
2. Confirm required files with `verify_project_structure`.
3. Confirm every generated report labels data as `synthetic_reproduction`.
4. Confirm README and verification guide do not claim raw-data reproduction.

### Level 2: Unit Verification

1. Run `run_unit_tests`.
2. Confirm rate formula tests pass.
3. Confirm deterministic optimizer and audit tests pass.
4. Confirm `run_article_exact_reproduction_impl('unit')` writes smoke reports labeled `synthetic_reproduction`.

### Level 3: Workflow Verification

1. Run `main`.
2. Confirm structure checks pass.
3. Confirm unit tests pass.
4. Confirm reproduction, article-exact smoke/full, adaptive audit, and sandbox reports are written when their commands are executed.
5. Confirm `main` prints the adaptive audit summary.

### Level 4: Result Verification

1. Inspect `sandbox/results/article_exact_report.md`.
2. Confirm it reports `synthetic_reproduction` and raw exact status is blocked.
3. Inspect `sandbox/results/operator_audit_report.md`.
4. Confirm each article operator maps to a local function and unit-test proof.
5. Inspect `sandbox/results/nmga_reproduction_report.md`.
6. Confirm synthetic metrics are not described as article raw results.
7. Compare synthetic trends against article Table 1 only qualitatively unless original data become available.
8. Inspect `sandbox/results/nmga_adaptive_audit_report.md`.
9. Confirm `Pc` decreases from near `0.6` to `0`, and `Pm` increases from near `0.01` to `0.04` under article schedule.
10. Confirm MGA/NMGA comparison uses equal budgets when reported as same-budget.

### Level 5: Full Repetition Verification

Run only when runtime is acceptable:

```matlab
run_nmga_reproduction('full')
run_article_exact_reproduction('article_exact')
```

Acceptance criteria:

- full profile completes without errors;
- all generated reports state limitations;
- aggregate NMGA behavior is plausible and stable;
- no exact Table 1 claim is made unless raw data and exact sensor coordinates are added.

## Known Errors Found During Audit

| Error | Status | Fix |
|---|---|---|
| NMGA rate schedule did not match article Formula 7/8 | Fixed | Replaced bounded reinterpretation with article formula. |
| `article_reported` Table 1 std/relative-error fields were inconsistent with the article | Fixed | Corrected sentinel values and added tests. |
| Unit tests overwrote adaptive audit report | Fixed | Added no-write audit mode for tests. |
| `main` did not explicitly summarize adaptive audit | Fixed | Added unit-profile adaptive audit summary. |
| Generated reports may be stale after rate-schedule correction | Open | Regenerate with `main` when MATLAB runtime is available. |
| Exact NMGA operator equivalence is not proven | Improved | Added public-text operator helpers and tests; still no author-code equivalence proof. |
| Raw article sensor/monitoring data unavailable | Open by source limitation | Keep all local generated data labeled synthetic. |

## Final Replication Claim

The current project should claim:

```text
This is a public-text exact MGA/NMGA operator and parameter replication on synthetic observations.
```

The current project should not claim:

```text
This exactly reproduces the article's original Table 1 calculations from raw monitoring data.
```
