# EU26-12 targeted artifact contract v1

Frozen: 2026-08-09, before candidate-local implementation and before any
source-native replay.

Status: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

Paper mapping: **`PAPER_EXPERIMENT_ARTIFACT_MAPPING`**

## Frozen source identity

- Paper DOI: `10.1145/3583131.3590417`.
- Legal arXiv manuscript: `https://arxiv.org/pdf/2304.09524`, 911,142 bytes,
  SHA-256
  `39b02abeea9c60dd923f5524fbb6f6972d8d634ea10cd659c2fbb71f23c020e8`.
- Paper-cited artifact DOI: `10.5281/zenodo.7624677`, immutable record
  `7624677`, record license CC-BY-4.0.
- Official repository: `Dvermetten/ModDE` at publication-era commit
  `b65062c66ecf22873f2e8f0aa4b12d04161d4bd5`, tree
  `b845e5b2677ed43768eb5d664c2481e8db022466`.
- Static `ModDE.zip`: 70,234 bytes, MD5
  `e28f5cade07b0145b355d124827bb69d`, SHA-256
  `566ada662621b98aabc3ee72eb960cfe5a31d19a0e6ad8c2761ee8d3f9eee688`.
  Its required text members, after CRLF-to-LF normalization, match the exact
  Git blobs at the frozen commit. Its embedded `LICENCE` is MIT.
- Official `Common_DE_runner.py`: 5,918 bytes, MD5
  `02e31dda03982d7a7f5cb7ace1e97ae0`, SHA-256
  `05b392177a29cff9825cecef10bcd9d8a56107ed4600a77710a4963a38227c12`.
- `raw_data.zip`: 4,785,454,278 bytes, Zenodo-declared MD5
  `649a5553abc54909b2d8958d1c0c586c`. It must never be vendored or downloaded
  in full by this study.

## Frozen range/ZIP64 identity

The last 65,536 bytes have SHA-256
`324174d314969a0d96729fbff6358ddb68afdb4e8207b78e4ed850453210b32c`.
The ZIP64 EOCD is at offset `4785454180`, its locator is at `4785454236`, and
the classic EOCD is at `4785454256`. The ZIP64 central directory contains
44,200 entries at offset `4778137904`, has 7,316,276 bytes, and has SHA-256
`06279742ca533ef829dd4209672a8dd67990d1f3c3bbd0c0a27f9b911110394c`.

Target JSON member:

```text
raw_data/Modde_common/F1_20D_L-SHADE/IOHprofiler_f1_Sphere.json
```

- local-header offset `14351998`;
- deflate method `8`, flags `0`;
- compressed bytes `8934`, uncompressed bytes `25475`;
- CRC32 `c20703c5`;
- SHA-256
  `f5c6ef22ae717593befa5728793724aff0b4595746f3693b15ec467d256f49e1`.

Companion DAT member:

```text
raw_data/Modde_common/F1_20D_L-SHADE/data_f1_Sphere/IOHprofiler_f1_DIM20.dat
```

- local-header offset `14264250`;
- deflate method `8`, flags `0`;
- compressed bytes `87642`, uncompressed bytes `245243`;
- CRC32 `cc5d84cb`;
- SHA-256
  `24d07c9de1714223ff75161b19211ad3d56f89ddc2cff3564c14a80e46997646`.

## Frozen endpoint and seed protocol

The selected configuration is paper Experiment 1's common L-SHADE variant:

- BBOB F1 Sphere, dimension 20, instance 0;
- runner seed 0, established by nested loops `iid in range(10)` then
  `seed in range(5)` and `np.random.seed(seed)` inside each run;
- 50 runs total for this function/dimension: five seeds for each of ten
  instances;
- requested budget 50,000;
- mutation base `target`, mutation reference `pbest`, binomial crossover;
- SHADE adaptation for `F` and `CR`, LPSR enabled, archive enabled;
- initial population `lambda=18*D=360`, default memory size 100, initial
  `F=CR=0.5`.

Exact JSON pointer `/scenarios/0/runs/0`:

| Field | Frozen value |
|---|---:|
| `instance` | 0 |
| `evals` | 50,002 |
| `best.evals` | 45,886 |
| `best.y` | `1.698652750709869e-14` |

The exact decimal string is the acceptance target. No numeric tolerance and no
rounded DAT substitution is allowed.

## Independently implemented controls

The released-source profile is frozen as follows:

```text
delta_i = abs(old_f_i - new_f_i) for strict improvements
weight_i = delta_i / sum(delta)
CR_memory[k] = sum(weight_i * successful_CR_i)
F_memory[k]  = sum(weight_i * successful_F_i)  # arithmetic, not Lehmer
CR_next_i = clip(Normal(CR_memory[r_i], 0.1), 0, 1)
F_next_i  = min(positive Cauchy(F_memory[r_i], 0.1), 1)
lambda_next = ties_even_round((3 - 360) / 50000 * used_budget + 360)
```

Replacement keeps the parent only for `parent_f < offspring_f`; equality
therefore selects the offspring. Only strict fitness decrease is a successful
adaptation event. Initialization consumes 360 IOH evaluations but zero
`used_budget`; whole-generation termination yields 582 generations,
`used_budget=49642`, and `IOH evals=50002`.

Frozen formula fixtures are stored in `config/verification_contract.json`.
Python and MATLAB/Octave must implement them independently. In particular,
the success-memory fixture yields `F=0.4` and `CR=31/70`, and the schedule
fixture must reproduce the 50,002-evaluation overshoot exactly.

## Verification gates

| Gate | Requirement |
|---|---|
| A1 metadata | Zenodo record ID/DOI/license and file sizes/checksums match the frozen contract. |
| A2 code | Static code/runner bytes match; safe ZIP rules pass; required member hashes and normalized Git blobs match the frozen commit. |
| A3 ZIP64 | Exact archive size, tail, ZIP64 EOCD/locator, entry count, directory offset/size/hash, and duplicate-free directory parse pass. |
| A4 member | Central/local metadata agree; target compressed payload inflates exactly; CRC32, size, and SHA-256 match. |
| A5 endpoint | Strict JSON schema, 50-run instance order, finite values, and exact frozen pointer/value pass. |
| A6 controls | Independent memory, sampling-transform, replacement, ties-even LPSR, and evaluation schedule fixtures pass. |
| A7 cross-language | MATLAB/Octave independently reproduces all frozen controls and Python agrees on the canonical fixture report. |
| A8 source-native | Optional authenticated disposable execution records exact versions and either matches the frozen endpoint or preserves a mismatch/blocker. |
| A9 fail closed | Mutated identity, response range, EOCD, directory, duplicate, path, header, method, flags, CRC, size, hash, schema, run order, numeric literal, fixture, output overwrite, or claim boundary is rejected. |
| A10 boundary | Every report retains `TARGETED_ARTIFACT_REPLAY_ONLY`, paper mapping, conflicts, declared-only full-archive MD5, and all forbidden claims. |

## Outcomes

- `PASS_ZENODO_METADATA`: A1 passes.
- `PASS_CODE_IDENTITY`: A2 passes.
- `PASS_RANGE_AUTHENTICATED_MEMBER`: A3 and A4 pass.
- `PASS_ARTIFACT_ENDPOINT`: A1 through A6 and A9 pass.
- `PASS_CROSS_LANGUAGE`: A7 passes without weakening a blocker.
- `PASS_SOURCE_NATIVE_ENDPOINT_REPLAY`: A8 matches exactly under the recorded
  auditor environment; this does not establish the historical environment.
- `SOURCE_NATIVE_BLOCKED_<reason>` or `SOURCE_NATIVE_MISMATCH`: A8 cannot run
  or differs; evidence is retained and no acceptance gate is upgraded.

`PASS_FULL`, `PASS_LITERAL_PAPER_ENDPOINT`,
`HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN`, and
`FULL_ARCHIVE_MD5_RECOMPUTED` are forbidden under contract v1.
