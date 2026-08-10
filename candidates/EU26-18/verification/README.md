# EU26-18 formula, algorithm, and portability verification

Requirements tag: `STRICT_ADAPTIVE_GA_2026-08-10`

Strict status: `UNKNOWN`

The source audit confirms that the published method is a non-hybrid NSGA-II
whose only disclosed dynamic control is the polynomial-mutation distribution
index `eta_m`. Exact executable semantics are incomplete, so this package does
not turn that conceptual classification into `PASS_STRICT` or `PASS_FULL`.

## What is executable here

- Algorithm 4's mean plus one supplied Gaussian realization and a declared
  clean-room boundary profile.
- Algorithm 2's two polynomial-mutation branches under the explicit assumption
  that the undefined `x_c` means the current coordinate `x`.
- The novelty ordering at Algorithm 3 lines 6-11: select, update index,
  crossover, mutate child 1, mutate child 2, append.
- Formula invariants, boundary cases, fail-closed invalid inputs, and fixed
  golden vectors.
- Scheduling-independent formula probes for 1, 2, and 4 spawn-based process
  workers.
- A quantized cross-machine digest aggregated across Linux, macOS, and Windows.

## What is not executable here

- The authors' unavailable Java/jMetal source.
- A complete NSGA-II reproduction.
- An author RNG stream or the thirty author seeds.
- Published HV, IGD+, generalized-spread, variance, p-value, or table
  reproduction.
- Hardware speedup claims.

The exact assumptions and claim boundary are frozen in
[`verification_contract.json`](verification_contract.json). Evidence gaps and
the material impact of each are in [`blockers.md`](blockers.md). Formula and
pseudocode traceability is in
[`formula_and_algorithm_audit.md`](formula_and_algorithm_audit.md).

## Commands

Run all candidate tests from the repository root:

```bash
python -m unittest discover -s candidates/EU26-18/tests -p "test_*.py" -v
```

Generate a local 1/2/4-worker report:

```bash
python candidates/EU26-18/verification/run_verification.py \
  --workers 1 2 4 \
  --cases 96 \
  --output machine-report.json
```

The worker report uses an exact `float.hex()` digest within one machine. CI
also compares a 12-decimal scientific digest across operating systems. The
rounded cross-machine gate is appropriate for the fixed formula probes; it is
not a claim that a branch-sensitive full evolutionary trajectory must be
bitwise identical across runtimes.
