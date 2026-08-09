# EU26-11 eligibility audit

Frozen: 2026-08-09, before candidate-local implementation.

## Scientific gates

- Date: ECTA 2024, within the frozen 2020--2026 window.
- Geography: the paper lists LIACS, Leiden University, Netherlands.
- Direct task: continuous black-box optimization of 24 BBOB functions.
- Dimension: experiments use 2, 5, 10, 20, and 40 variables; the selected
  endpoint uses 20 variables.
- Full evolutionary optimizer: CMA-ES samples a population, ranks candidates,
  recombines selected candidates, and updates its search distribution.
- Within-run adaptation: after every generation, the frozen source updates
  the mean, conjugate evolution paths, step size, and covariance matrix.
- Artifact: publisher paper, CC-BY-4.0 Zenodo data, MIT source, exact tag,
  deterministic point set, compact numeric cell, and explicit seed formula
  for the excluded stochastic runs are present.

All admission gates pass for a targeted deterministic artifact verification.

## Admission decision

Status: **`ADMITTED_TARGETED_EVIDENCE`**

The target is frozen to Figure 1 `OPT-128`, dimension 20, value `-4.16`. This
cell can be checked from two authenticated artifact members and an independent
equation without the 2.7-GB empirical database.

This is not admission for full-paper reproduction. The database, BBOB EAF,
AUC, optimizer performance, and author execution environment remain outside
the claim. No passing result may be promoted to `PASS_FULL`.
