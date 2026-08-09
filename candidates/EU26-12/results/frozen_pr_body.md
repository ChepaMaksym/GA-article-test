# Research: add EU26-12 range-authenticated Modular DE replay

## Summary

Adds an isolated verification study for Vermetten et al., *Modular
Differential Evolution* (GECCO 2023, DOI `10.1145/3583131.3590417`). The
allowed outcome is frozen at **`TARGETED_ARTIFACT_REPLAY_ONLY`**.

The preregistered target is the lexicographically first eligible artifact run:
L-SHADE, BBOB F1 Sphere, dimension 20, instance 0, seed 0. The authenticated
JSON endpoint is 50,002 evaluations, best evaluation 45,886, and exact best
objective `1.698652750709869e-14`.

## What this change includes

- candidate-local eligibility audit and byte-frozen verification contract;
- strict HTTPS range reader and fail-closed ZIP64 parser;
- authentication of immutable Zenodo metadata, the static code archive,
  runner, central directory, selected JSON/DAT members, CRC32, and SHA-256;
- independent Python and MATLAB/Octave control-transition implementations;
- unit, integration, adversarial, mutation, and cross-language protocol tests;
- candidate-local GitHub Actions workflow and provenance report.

The 4,785,454,278-byte raw archive is neither vendored nor downloaded in full.
The successful real replay used six bounded HTTP 206 requests totaling
7,478,587 bytes.

## Frozen evidence

- `PASS_ZENODO_METADATA`
- `PASS_CODE_IDENTITY`
- `PASS_RANGE_AUTHENTICATED_MEMBER`
- `PASS_ARTIFACT_ENDPOINT`
- `PASS_CONTROL_TRANSITIONS`
- overall: `TARGETED_ARTIFACT_REPLAY_ONLY`

The static Zenodo source archive is MIT-licensed and SHA-pinned. Its 14
canonical members match 14 of 15 tracked blobs at upstream commit
`b65062c66ecf22873f2e8f0aa4b12d04161d4bd5`. It is not an exact match for
tree `b845e5b2677ed43768eb5d664c2481e8db022466`: the tracked CI workflow is
absent and the archive has 23 checkpoint/cache/directory-only entries.

## Verification

- candidate Python suite: 110 tests, 0 failures, 0 errors, 0 skips;
- frozen registry validator: pass;
- frozen registry regression suite: 13 tests, pass;
- real Zenodo endpoint report:
  `c58d3af2301938070d28f663e93a2ddfcaf800141768c18e1a4253839c5253f9`;
- local source-native diagnostic:
  `SOURCE_NATIVE_BLOCKED_MISSING_DEPENDENCIES` (`ioh`, `numba`);
- local Octave: unavailable; the candidate workflow installs Octave and binds
  independent control evidence to the authenticated Python report.

## Claim boundary

This is not a literal paper-table reproduction and not a proven historical
source-native replay. The exact single-run value is absent from the paper,
dependencies are not fully locked, DAT rounds the exact JSON result to zero,
and the full archive MD5 is Zenodo-declared rather than recomputed.

The verifier therefore forbids `PASS_FULL`, `PASS_LITERAL_PAPER_ENDPOINT`,
`HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN`, and
`FULL_ARCHIVE_MD5_RECOMPUTED`. It also forbids
`EXACT_ARTIFACT_GIT_TREE_MATCH`.

No global registry/status file is modified by this change.
