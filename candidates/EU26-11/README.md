# EU26-11 — deterministic CMA-ES Figure 1 verification

Paper: de Nobel, Vermetten, Back, and Kononova, *Sampling in CMA-ES: Low
Numbers of Low Discrepancy Points* (ECTA 2024), DOI
[`10.5220/0013000900003837`](https://doi.org/10.5220/0013000900003837).

Status: **`TARGETED_DETERMINISTIC_FIGURE1_REPLAY_ONLY`**

This candidate verifies one literal paper result: Figure 1, row `OPT-128`,
dimension `20`, displayed `log10(L2-star) = -4.16`. The authenticated Zenodo
point set is parsed without vendoring, its L2-star discrepancy is recomputed
from the defining equation, and the result is compared with the authenticated
numeric block used by the authors' plotting notebook.

The qualifying optimizer is a complete CMA-ES. During every generation it
updates its population mean, evolution paths, step size, and covariance
matrix. The paper directly optimizes the 24 BBOB functions at dimensions
2, 5, 10, 20, and 40. The target selected here is 20-dimensional.

## What a pass means

- `PASS_TARGET_ARTIFACT_REPLAY`: the authenticated point set independently
  gives L2-star discrepancy `6.89263855598324e-05`, whose base-10 logarithm
  displays as `-4.16`.
- `PASS_ARCHIVED_NUMERIC_CELL`: the authenticated `discr.pkl` numeric block
  contains the same full-precision `OPT-128`, 20D value. The verifier extracts
  the inert binary64 block with `pickletools`; it never unpickles the file.
- `PASS_SOURCE_ADAPTATION_GATE`: the MIT-licensed ModularCMAES tag `v1.0.8`
  has the frozen source identity and the generation step invokes mutation,
  selection, recombination, and state adaptation in that order.
- `PASS_CROSS_LANGUAGE_FORMULA`: Python and GNU Octave independently evaluate
  the defining formula within the preregistered tolerance.

These checks do not replay the 2.7-GB BBOB database or establish the paper's
empirical performance conclusions. `PASS_FULL`, `PASS_BBOB_EMPIRICAL`, and
`PASS_AUTHOR_EXECUTION_REPLAY` are forbidden by the frozen contract.

## Local commands

With authenticated downloads and the exact source checkout:

```bash
EU2611_POINT_SET=/tmp/Sub_Sobol_20_128.txt \
EU2611_PICKLE=/tmp/discr.pkl \
EU2611_SOURCE=/tmp/ModularCMAES-v1.0.8 \
PYTHONDONTWRITEBYTECODE=1 \
  python candidates/EU26-11/tests/run_python_tests.py

python candidates/EU26-11/environments/python/run_artifact_verification.py \
  --point-set /tmp/Sub_Sobol_20_128.txt \
  --numeric-block /tmp/discr.pkl \
  --source-checkout /tmp/ModularCMAES-v1.0.8 \
  --output /tmp/eu26-11-report.json
```

See `preregistration/verification_contract.md` for the frozen claim boundary
and `source_manifest/audit_notes.md` for provenance details.
