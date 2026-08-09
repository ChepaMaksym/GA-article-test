# EU26-12 provenance and verification report

Report date: 2026-08-09

Candidate: Vermetten et al., *Modular Differential Evolution*, GECCO 2023

DOI: [`10.1145/3583131.3590417`](https://doi.org/10.1145/3583131.3590417)

Outcome ceiling: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

## Frozen scope

This study authenticates one preregistered run from the paper-cited Zenodo
artifact. It does not claim a literal paper-table endpoint or a historically
locked source-native rerun.

| Field | Frozen value |
|---|---|
| Artifact | Zenodo record `7624677`, DOI `10.5281/zenodo.7624677` |
| Algorithm | L-SHADE |
| Problem | BBOB F1 Sphere, dimension 20 |
| Run | instance 0, seed 0, JSON pointer `/scenarios/0/runs/0` |
| Budget | requested 50,000; logged 50,002 |
| Endpoint | best evaluation 45,886; exact best `1.698652750709869e-14` |
| JSON member | `f5c6ef22ae717593befa5728793724aff0b4595746f3693b15ec467d256f49e1` |
| DAT member | `24d07c9de1714223ff75161b19211ad3d56f89ddc2cff3564c14a80e46997646` |
| Upstream reference | commit `b65062c66ecf22873f2e8f0aa4b12d04161d4bd5`; tree `b845e5b2677ed43768eb5d664c2481e8db022466` |
| Source mapping | `PARTIAL_14_OF_15_GIT_BLOB_CORROBORATION`; exact-tree match false |
| Source license | MIT |
| Artifact license | CC-BY-4.0 |

The live amended contract is
`31d7d0e219afde23522753cae4e3089f7483fc5a4f1fbbd6cfa5b9bb01346997`.
Amendment 001 preserves the original contract hash
`edfae20d92afbf7cb8c0d0d78c10c11efa223977e6bc1acb3e7ab0256fb1b35b`
and the post-freeze source-tree correction.
The legal arXiv paper PDF is 911,142 bytes with SHA-256
`39b02abeea9c60dd923f5524fbb6f6972d8d634ea10cd659c2fbb71f23c020e8`.

## Authenticated artifact replay

The real Zenodo execution passed all preregistered metadata, code-identity,
ZIP64, member, endpoint, DAT cross-check, and independent Python-control gates.

| Gate | Result |
|---|---|
| Zenodo metadata | `PASS_ZENODO_METADATA` |
| Static code identity | `PASS_CODE_IDENTITY` |
| ZIP64/member authentication | `PASS_RANGE_AUTHENTICATED_MEMBER` |
| Frozen JSON endpoint | `PASS_ARTIFACT_ENDPOINT` |
| Independent Python controls | `PASS_CONTROL_TRANSITIONS` |
| Overall claim | `TARGETED_ARTIFACT_REPLAY_ONLY` |

The static archive's complete 37-entry inventory is frozen. Fourteen
canonical files match 14 of the 15 tracked Git blobs at the upstream reference
commit. The tracked `.github/workflows/python_test.yml` is absent, while the
archive contains 17 checkpoint/cache files and six directory entries with no
tracked-file counterpart. This is partial blob corroboration, not an exact
commit-tree identity.

The verifier made exactly six HTTP 206 requests and received 7,478,587 bytes.
No request exceeded 8,000,000 bytes and the 4,785,454,278-byte raw archive was
not downloaded in full. It authenticated:

- the 65,536-byte ZIP tail with SHA-256
  `324174d314969a0d96729fbff6358ddb68afdb4e8207b78e4ed850453210b32c`;
- the 7,316,276-byte central directory with SHA-256
  `06279742ca533ef829dd4209672a8dd67990d1f3c3bbd0c0a27f9b911110394c`;
- all 44,200 directory records and both selected local headers, deflate
  streams, CRC32 values, uncompressed sizes, and member SHA-256 values.

The companion DAT member contains 50 runs and 12,915 improvement rows. Its
first-run final row is evaluation 50,002 with rounded value `0.0000000000`.
It is retained only as a rounded diagnostic; the exact endpoint comes from the
authenticated JSON member. Strict JSON-to-DAT terminal-evaluation matching
also preserves the two legitimate early-stop runs rather than imposing an
incorrect 50,002 total on every run.

Generated report details:

| Property | Value |
|---|---|
| Domain-bound report digest | `c58d3af2301938070d28f663e93a2ddfcaf800141768c18e1a4253839c5253f9` |
| Report file bytes | 5,244 |
| Report file SHA-256 | `3255bc4a0a75f6f703c8e8a892c7f8aef4a96cd468fbf13eceb611d004c348d6` |

The generated report is intentionally not committed. CI regenerates and
uploads it as short-lived evidence.

## Independent control transitions

The Python and MATLAB/Octave implementations do not import or execute the
released implementation. They independently encode the frozen source
semantics:

- strict-improvement weights and released weighted arithmetic F/CR memory;
- normal CR transform with clipping to `[0,1]`;
- Cauchy F redraw until positive, then cap at one;
- equality selects the offspring but does not count as an improvement;
- explicit ties-to-even linear population-size reduction;
- population-only `used_budget`, initial population accounted by IOH, and
  whole-generation stopping that reaches 50,002 evaluations.

The complete schedule has 582 generations, `used_budget=49,642`, 50,002
logged evaluations, and terminal population 6.

## Local verification

| Check | Exact local result |
|---|---|
| Candidate Python suite | 110 tests; 0 failures, 0 errors, 0 skips |
| Test-suite gate | `PASS_FAIL_CLOSED_SUITE` |
| Suite manifest | 32 members; 159,725 bytes; SHA-256 `77734583c2bae9704a711b180db0c3756431c3d772c4f8323cde50d7c8b9d73a` |
| Test report | digest `2118aed2cfe2eacc9ed424d1c713b5a4bfe03f07a67fa8b6576800cc6b377892`; file SHA-256 `8112fae668b95c2b7c4ac3220aae131994243dc0c8e62e515d41fa257ca651fa` |
| Frozen registry validator | `REGISTRY VALIDATION PASS` |
| Frozen registry regression suite | 13 tests; `OK` |
| Upstream reference checkout | exact reference commit/tree above; clean |
| MATLAB/Octave controls | `NOT_RUN_LOCAL_NO_OCTAVE`; required by candidate CI |
| Repository MATLAB suite | `NOT_RUN_LOCAL_NO_MATLAB` |

The suite manifest intentionally binds the executable Python and
MATLAB/Octave implementation, tests, and frozen JSON contract. Generated
reports and caches remain outside the repository.

## Source-native diagnostic blocker

The optional source-native diagnostic authenticated the released static code
archive, then stopped fail-closed because the local environment lacks `ioh`
and `numba`. Its evidence was:

| Property | Value |
|---|---|
| Gate | `SOURCE_NATIVE_BLOCKED_MISSING_DEPENDENCIES` |
| Python | 3.12.13 |
| NumPy / SciPy | 2.3.5 / 1.17.0 |
| Missing | `ioh`, `numba` |
| Historical environment proven | false |
| Report digest | `24ce18b5fc9841a4ba2b266712b4288fb3d2127a51c1352aa24c52acad0d6bc2` |
| Report file SHA-256 | `4337cc2d74aeabed995af9bbc34b3eefe6980d1501f2a75736ec3a0a6931639a` |

The upstream requirements use lower bounds rather than a complete historical
lock. A disposable attempt to build the artifact-era `ioh==0.3.5` source
distribution under Python 3.12 also failed in its legacy CMake dependency.
This diagnostic is not upgraded into source-native evidence.

## Mandatory conflicts and claim boundary

The following facts remain explicit conflicts rather than being silently
normalized away:

- the paper does not print this exact single-run objective;
- the paper does not pin the Git revision, and the Zenodo source archive
  matches only 14 of 15 tracked blobs rather than the exact Git tree;
- the dependency environment and NumPy version are not historically locked;
- legacy global `numpy.random` and default `argsort` tie behavior are used;
- released F memory uses an arithmetic, not Lehmer, mean;
- initialization is excluded from the algorithm's `used_budget`;
- the generation-granular stop overshoots 50,000 to 50,002;
- DAT precision rounds the exact JSON endpoint to zero;
- the 4.8-GB archive MD5 is Zenodo-declared and was not recomputed.

Therefore `PASS_FULL`, `PASS_LITERAL_PAPER_ENDPOINT`,
`HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN`, and
`FULL_ARCHIVE_MD5_RECOMPUTED` remain forbidden. The additional claim
`EXACT_ARTIFACT_GIT_TREE_MATCH` is also forbidden. No global registry or
research status was changed, and no publication action was taken.
