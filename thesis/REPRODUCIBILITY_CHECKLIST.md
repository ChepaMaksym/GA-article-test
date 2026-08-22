# Thesis reproducibility checklist

This checklist is adapted to the actual EU26-27 workflow and is intended to be completed before thesis submission.

## Research question and claims

- [x] Primary algorithmic endpoint is explicitly defined: FE to complete OneMinMax Pareto front.
- [x] OLD, v1, v2 and v3 claims are separated.
- [x] Green CI execution is separated from scientific hypothesis PASS.
- [x] Failed preregistered claims remain visible.
- [x] Prior art prevents claiming first adaptive-lambda MOEA.
- [ ] Final v3 claim inserted only from independent holdout report.

## Source identity

- [x] Exact GSEMO commit recorded.
- [x] Exact IOHexperimenter commit recorded.
- [x] Critical source blob hashes recorded.
- [x] Historical dependency path reconstruction documented.
- [x] Hybrid modifications applied as audited additive patches.
- [x] Plain TwoRate mode regression-tested after every hybrid patch.

## Randomness

- [x] v1 seed ledger recorded: 27001..27030.
- [x] v2 seed ledger recorded: 28001..28030.
- [x] v3 holdout ledger recorded before outcomes: 29001..29030.
- [x] Seed roles are explicit: historical confirmation vs development vs new confirmation.
- [x] Bootstrap RNG seeds recorded.
- [x] Seed ledgers checked for overlap in CI.

## Development / tuning

- [x] v3 cap candidate set frozen before development execution.
- [x] v3 cap-selection metric frozen.
- [x] Tie-break rule frozen.
- [x] Development data are explicitly marked non-confirmatory.
- [x] New confirmation set does not participate in selection.
- [ ] Final selected cap recorded from machine-generated JSON.

## Raw measurements

- [x] Canonical OLD first-hit matrix retained/checked against authenticated artifact.
- [x] v1 raw outputs retained in workflow artifact.
- [x] v2 raw `.dat` and controller traces retained in workflow artifact.
- [ ] v3 raw development outputs retained.
- [ ] v3 raw holdout outputs retained.
- [ ] Final artifact digests copied into thesis evidence map.

## Analysis

- [x] Paired effect is defined on same-seed OLD/HYBRID runs.
- [x] Marginal median is not used as substitute for paired primary statistic.
- [x] 50,000-resample bootstrap is deterministic for confirmatory H1.
- [x] Acceptance criterion is lower 95% interval endpoint > 0.
- [x] Incomplete full-front runs fail closed.
- [x] Statistical analysis code is versioned with the experiment.
- [ ] Final thesis tables regenerated directly from machine-readable reports.

## Reporting

- [x] Exact OLD reproduction described separately from hybrid effect.
- [x] v1 negative result included.
- [x] v2 negative result included.
- [ ] v3 result included regardless of sign.
- [x] Threats to internal, construct, external and statistical validity drafted.
- [x] FE and wall-clock claims explicitly separated.
- [ ] Any multi-machine result is labeled robustness/performance evidence, not substituted for H1.

## Software / hardware environment

For every final benchmark table record:

- [ ] operating system and version;
- [ ] CPU model;
- [ ] physical/logical cores;
- [ ] RAM;
- [ ] compiler and version;
- [ ] build type/options;
- [ ] worker count;
- [ ] concurrent load condition;
- [ ] relevant package/library revisions.

## Artifacts

The final thesis package should contain or reference:

- [x] source revision identifiers;
- [x] preregistration protocols;
- [x] seed ledgers;
- [x] patch-generation scripts;
- [x] CI workflows;
- [x] analysis scripts;
- [ ] final raw v3 data;
- [ ] final CSV/JSON result tables;
- [ ] final figures generated from retained data;
- [ ] SHA-256 digest for each published evidence archive;
- [ ] permanent archival snapshot / DOI if thesis submission rules permit.

## Final fail-closed thesis gate

The thesis must not state that the final hybrid is more FE-efficient than OLD unless the independent v3 (or a later independently preregistered) confirmatory result satisfies its frozen PASS rule. If no hybrid passes, the thesis conclusion must remain a reproducibility-and-negative-results contribution rather than inventing a superiority claim.
