# Diagnostic harness failure log

## 2026-07-30 — Q1 output-format failure

- Scope: harness output only; no scientific conclusion was evaluated.
- Gate status before failure: all 42 outcome-free unit tests passed.
- Failure point: the first Q1 run had been computed and atomically saved, then MATLAB rejected the string-valued `fprintf` format in `jcga.run_failure_diagnostics`.
- MATLAB identifier/message: `fprintf: Invalid file identifier. Use fopen to generate a valid file identifier.`
- Preserved partial cache: `outputs/failure_diagnostics/Q1_STRICT_HORIZONS/run_01.mat`
- Partial-cache SHA-256: `a0fb76bb54ab4aa9b23ab137e31decc1e3a2392fef4c6068cce39295989eb6cd`
- Resolution: changed only the console format literal from MATLAB `string` syntax to a character-vector format. No outcome-affecting source, profile, seed, instance, population, budget, or objective changed.
- Reuse rule: the partial cache remains non-authoritative unless the rerun passes the entire unit/provenance gate and `jcga.validate_diagnostic_cache` recomputes and authenticates it against the unchanged diagnostic implementation signature.

## 2026-07-30 — Q1 pre-conclusion provenance hardening stop

- Scope: harness integrity and evaluation accounting; no scientific conclusion was evaluated or written.
- Stop point: runs 1–7 had atomically saved caches; run 8 was active and had no terminal cache.
- Reason for stopping: an independent read-only audit confirmed the Q1 stochastic trajectory differed from the primary only by the intended strict horizon comparisons, but identified two acceptance blockers:
  1. diagnostic population logging reevaluated all 21 chromosomes after the post-variation best evaluation, inflating `EvaluationCount` by 21 calls per completed generation;
  2. cache validation authenticated the configuration and terminal chromosome but did not bind the complete result/log/event contents or fully validate stop/termination timing.
- Additional hardening: pin every operator/profile field independently rather than relying only on a digest recomputed from the current profile definition.
- Process handling: the exact MATLAB processes created for this attempt were stopped before any Q1 summary or P1–P4 verification was produced.
- Preserved non-authoritative caches:
  - `run_01.mat`: `a0fb76bb54ab4aa9b23ab137e31decc1e3a2392fef4c6068cce39295989eb6cd`
  - `run_02.mat`: `20aacd11f5351fdbf6f20fc6cb7a100b6cfd1c805d5809954bb7484980f7eee8`
  - `run_03.mat`: `106cdefa18392d4dc5ce7f142e446309711d4b6cb10665eeedbe563d57a0c3f9`
  - `run_04.mat`: `e2683b650c519cdfa967c898de9865e22e581471f2b665d812758b3b82a42e57`
  - `run_05.mat`: `8fcc1029ac0e5dc74c3876fa1b8655f4d913599e230e981b955bb4a0743570ad`
  - `run_06.mat`: `a633845cedb42a664b03559c56c969731afb5712305869d3ee2616cf2bcb1c51`
  - `run_07.mat`: `ccba42537570e24044fdcc78a9dec2c0f226687e81ddc4c55f9489a65bdd96b9`
- Archive location: `outputs/failure_diagnostics_invalidated/2026-07-30_q1_pre_hardening/Q1_STRICT_HORIZONS/`
- Reuse rule: none. These caches predate the hardened outcome-affecting implementation and must never contribute to a diagnostic conclusion.
