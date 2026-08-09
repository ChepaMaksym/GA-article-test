# EU26-12 preregistration amendment 001 — artifact tree scope

Amended: 2026-08-09, after implementation and before the implementation
commit. The original preregistration commit `660982d` is preserved unchanged
in history.

## Finding

Final source-inventory review disproved the preregistered shorthand
`artifact_maps_to_commit=true`. The Zenodo `ModDE.zip` does not normalize to
the complete Git tree
`b845e5b2677ed43768eb5d664c2481e8db022466` at commit
`b65062c66ecf22873f2e8f0aa4b12d04161d4bd5`.

The archive's 14 canonical source, test, documentation, and license members
normalize to 14 exact Git blobs at that commit. The commit contains 15 tracked
file blobs: `.github/workflows/python_test.yml`, blob
`ec3048da336bfb60f708cceb5d27d8ed10c2bbb3`, is absent from the Zenodo
archive. Conversely, the archive contains 23 entries with no tracked-file
counterpart: 17 checkpoint/cache files and six directory entries.

## Exact superseding mapping

| Property | Corrected value |
|---|---|
| Exact artifact-to-tree match | `false` |
| Mapping status | `PARTIAL_14_OF_15_GIT_BLOB_CORROBORATION` |
| Matching tracked blobs | 14 |
| Tracked blobs at commit | 15 |
| Missing tracked path | `.github/workflows/python_test.yml` |
| Missing tracked blob | `ec3048da336bfb60f708cceb5d27d8ed10c2bbb3` |
| Artifact-only entries | 23 total: 17 files, 6 directories |

The exact artifact-only ZIP inventory, in archive order, is:

1. `modde/`
2. `modde/.ipynb_checkpoints/`
3. `modde/.ipynb_checkpoints/modularde-checkpoint.py`
4. `modde/.ipynb_checkpoints/parameters-checkpoint.py`
5. `modde/.ipynb_checkpoints/population-checkpoint.py`
6. `modde/.ipynb_checkpoints/sampling-checkpoint.py`
7. `modde/.ipynb_checkpoints/utils-checkpoint.py`
8. `modde/.ipynb_checkpoints/__init__-checkpoint.py`
9. `modde/__pycache__/`
10. `modde/__pycache__/modularde.cpython-38.pyc`
11. `modde/__pycache__/parameters.cpython-38.pyc`
12. `modde/__pycache__/population.cpython-38.pyc`
13. `modde/__pycache__/sampling.cpython-38.pyc`
14. `modde/__pycache__/utils.cpython-38.pyc`
15. `modde/__pycache__/__init__.cpython-38.pyc`
16. `tests/`
17. `tests/.ipynb_checkpoints/`
18. `tests/.ipynb_checkpoints/create_expected-checkpoint.py`
19. `tests/.ipynb_checkpoints/test_modularde-checkpoint.py`
20. `tests/.ipynb_checkpoints/__init__-checkpoint.py`
21. `tests/__pycache__/`
22. `tests/__pycache__/test_modularde.cpython-38.pyc`
23. `tests/__pycache__/__init__.cpython-38.pyc`

The implementation authenticates the complete ZIP by its frozen 70,234-byte
SHA-256 and freezes this exact 37-entry inventory. The upstream commit and tree
remain corroborating references only; report fields must not call them a
normalized artifact commit or tree.

## Contract effect

The original contract bytes have SHA-256
`edfae20d92afbf7cb8c0d0d78c10c11efa223977e6bc1acb3e7ab0256fb1b35b`.
The live superseding contract bytes have SHA-256
`31d7d0e219afde23522753cae4e3089f7483fc5a4f1fbbd6cfa5b9bb01346997`.
The live validator rejects restoration of `artifact_maps_to_commit`, any
promotion to `artifact_exact_tree_match=true`, a 15-of-15 match count, removal
of the missing workflow, or mutation of the artifact-only inventory.

This amendment does not change the preregistered algorithm, problem,
dimension, instance, seed, endpoint, range hashes, or claim ceiling. The
Zenodo source is still legal, immutable, SHA-pinned, and versionable without a
Git mapping. The allowed outcome remains
**`TARGETED_ARTIFACT_REPLAY_ONLY`**. Exact-tree claims are forbidden.
