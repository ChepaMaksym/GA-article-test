# EU26-18 - Self-adaptive polynomial mutation in NSGA-II

Requirements tag: `STRICT_ADAPTIVE_GA_2026-08-10`

Status: `UNKNOWN`

This candidate is Jose L. Carles-Bou and Severino F. Galan, "Self-adaptive
polynomial mutation in NSGA-II", *Soft Computing* 27, 17711-17727 (2023),
DOI [`10.1007/s00500-023-09049-0`](https://doi.org/10.1007/s00500-023-09049-0).

The selected algorithm is standard NSGA-II with one self-adaptive control:
the polynomial-mutation distribution index `eta_m`. This index controls
mutation strength. Lower values produce broader, larger perturbations; higher
values concentrate mutations near the current value. The mutation probability
itself remains fixed at `1/n`.

The scientific classification is supported: the method is a non-hybrid GA and
the only disclosed dynamic control is mutation strength. The final strict
decision is nevertheless `UNKNOWN`, because the paper does not define the
`repair` helper, the `x_c` symbol in Algorithm 2, parent copy/reference
semantics, or exact inheritance of `eta_m` through crossover. Under the frozen
fail-closed requirements these gaps cannot be repaired by assumption.

## Files

- [`preregistration/strict_requirements_contract.md`](preregistration/strict_requirements_contract.md)
  freezes the new PASS/FAIL/UNKNOWN protocol.
- [`preregistration/eligibility_audit.md`](preregistration/eligibility_audit.md)
  binds every hard gate to primary-source evidence.
- [`config/eligibility_contract.json`](config/eligibility_contract.json)
  contains the machine-checkable decision.
- [`source_manifest/sources.csv`](source_manifest/sources.csv) records the
  publisher and author-institution sources used by the audit.
- [`tests/test_strict_eligibility.py`](tests/test_strict_eligibility.py) fails
  closed if the dynamic-control set or decision boundary drifts.

## Exact boundary

The Gaussian perturbation of `eta_m` is not accepted by itself as feedback.
The paper supports a selection-mediated self-adaptation concept because
`eta_m` is stored in the genome and selected parent values are updated before
crossover. It does not, however, specify enough object and inheritance
semantics to reconstruct the exact child state without assumptions.

The paper cites evolutionary strategies as inspiration for this representation,
but Algorithm 3 does not execute an ES or another optimizer. Its pipeline remains
NSGA-II selection, SBX crossover, polynomial mutation, evaluation, and
non-dominated survivor reduction. No local search, PSO, DE, fuzzy controller,
reinforcement learning, neural controller, genetic programming, meta-GA, or
adaptive operator selection is present in the selected variant.

## Verification stage

The candidate-scoped [`verification/`](verification/) package transcribes the
novel formula kernel under a declared clean-room profile, tests Algorithms 2 and
4 plus the novelty ordering in Algorithm 3, checks exact determinism for 1, 2,
and 4 process workers, and compares a quantized digest across Linux, macOS, and
Windows CI jobs. These checks validate the declared interpretation only. They
do not recover the authors' jMetal execution or published numeric results.

## Non-blocking preference

The source reports benchmark decision-vector dimensions from 2 to 30, including
several cases above 10. This audit does not reinterpret decision variables as
"more than 10 other parameters". That preference remains `UNKNOWN` and does not
affect the strict decision.
