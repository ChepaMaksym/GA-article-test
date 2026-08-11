# EU26-21 - CHC-QX Census-Income OLD-first candidate

Status: `PREREGISTERED_OLD_ONLY`.

Paper: Mohammed Ghaith Altarabichi, Sławomir Nowaczyk, Sepideh Pashami, and Peyman Sheikholharam Mashhadi, **Fast Genetic Algorithm for feature selection - A qualitative approximation approach**, Expert Systems with Applications 211 (2023) 118528, DOI `10.1016/j.eswa.2022.118528`.

## Why this candidate is materially stronger

- Applied wrapper feature selection for income classification, not a synthetic objective.
- Census-Income contains 199,523 observations and **41 task features**, exceeding the required 15 task variables.
- Binary feature masks make the later scientific comparison with PR #8 technically clean, but HYBRID remains forbidden until OLD passes.
- The search landscape is combinatorial (`2^41` masks), with premature convergence and false/local optima discussed explicitly in the paper.
- The underlying CHC adaptive search changes its incest-prevention distance threshold as progress stalls and triggers cataclysmic mutation/restart when convergence is detected.
- The authors publish complete Python source, the exact Census-Income dataset, an executed notebook endpoint, and the article carries a Code Ocean reproducibility badge.
- Table 2 provides a ten-run numerical endpoint: Census-Income baseline Decision Tree `92.87%`, CHC-QX median test accuracy `94.94%`, standard deviation `0.07` percentage points.

## Frozen author evidence

Repository: `Ghaith81/Fast-Genetic-Algorithm-For-Feature-Selection`.

Commit: `6ac5a7ec77f8a7c096ab4d019254fcc897988fd6`.

Pinned blobs:

- `code/Dataset.py`: `18c8d417f7236ef0af3c8a35279a1914679cac74`;
- `code/Evolution.py`: `05b0d8afc02faee688e5d1ff8e24531ae41307c7`;
- `code/Example.ipynb`: `87d2ea5caada5278853553de2c73d2ec6083f9b6`;
- `data/census-income.data`: `e780a25c2dec3f1a10d65cca9ea05001a77b37b6`.

The executed notebook records one non-seeded source endpoint:

- meta-model training sample size `14,964`;
- best validation fitness `0.9491` at generation `60`;
- test accuracy `94.96%`;
- selected features `[12, 16, 17, 19, 40]`.

That notebook row is an authenticated artifact target, not a historical-seed claim.

## OLD tracks

OLD is deliberately split into non-interchangeable verification tracks:

1. `notebook_artifact` - authenticate the executed notebook outputs and exact upstream identities.
2. `author_source_seeded` - run the pinned author code with an auditor-defined seed ledger and no algorithm tuning.
3. `paper_cleanroom` - only after source behavior is understood, independently implement the printed CHC-QX flow and compare it with source behavior.

A successful source run by itself is not sufficient for `PASS_OLD_FULL`.

## Hard gate

`hybrid/` must contain no executable optimizer unless all of the following are true:

- exact source/data identities pass;
- data preprocessing and 60/20/20 split pass independent checks;
- CHC adaptive distance and cataclysmic restart semantics pass fixed-tape tests;
- the seeded source campaign completes all preregistered runs deterministically;
- the Census-Income baseline and CHC-QX Table 2 endpoint satisfy the frozen numerical gate;
- an independent paper-profile implementation is completed and its divergences from source are resolved or explicitly bounded.

If the numerical OLD endpoint cannot be reproduced after a bounded verification cycle, this candidate is rejected and no PR #8 hybrid is created.

## Current work

- source and artifact contract: in implementation;
- source-compatible single-seed runner: in implementation;
- ten-seed numerical gate: preregistered before execution;
- independent paper profile: blocked until source smoke and campaign evidence;
- HYBRID: documentation-only.
