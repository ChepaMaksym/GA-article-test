# EU26-09 verification and provenance report

Report date: 2026-08-09.

Final study status: **`TARGETED_ARTIFACT_REPLAY`**

Paper mapping: **`PAPER_FIGURE_CONTEXT_ONLY`**

## Authenticated target

The clean official checkout resolved to commit
`49949a55208359ac93b7110afb23ed276bda158d` and tree
`a9d1a04fbbafbb114585ff7caf10bddc6381755a`. Eight contract-required members
were authenticated by size, SHA-256, and Git blob before and after use. The
checkout remained clean.

The selected non-vendored raw member was 48,918 bytes with SHA-256
`22177154c4375290632476ab8e82845465d4a7261a31c78f63701ef7e901714a`.
The strict parser accepted exactly 500 contiguous solved rows and independently
recomputed:

| Quantity | Total | Exact mean |
|---|---:|---:|
| generations | 98,168 | 196.336 |
| evaluations | 447,632 | 895.264 |
| fitness | 50,000 | 100.0 |
| final logged rounded lambda | 4,946 | 9.892 |

Result: **`PASS_ARTIFACT_ENDPOINT`**. Generated local report digest:
`fb71f382f95e6c1a8e6a3a04d545213bcd4e5e7b0271831ebda1137bd6549fb9`.

## Source-native replay

The frozen README command ran in a disposable clone under:

- Python 3.12.13;
- NumPy 2.3.5;
- SciPy 1.17.0;
- Matplotlib 3.10.8; and
- Linux x86-64, glibc 2.39.

All 500 seed-derived rows and every footer regenerated exactly. The generated
file was 48,918 bytes, had the target SHA-256, and was a byte-for-byte match.
No tracked upstream member changed. Runtime was 17.812789 seconds. The process
returned zero; stdout was 48,925 bytes (SHA-256
`c2ed94c7bb1b12af0d4aedc4c690aed803726e862803b1464ba5157fc39d9512`),
and non-fatal stderr was retained by size and digest: 438 bytes, SHA-256
`568c0a054def5764296af9e77f1b489d05006bc77ec486a6d9eb55ea627b77be`.

Result: **`PASS_SOURCE_NATIVE_RAW_REPLAY`**. Generated local report digest:
`12deca0077fdd17b02979079602d34c2950b60b0ad8f6f9702c11aec3324aa53`.

This pass is bound only to the recorded modern environment. Upstream provides
no historical dependency lock, so it does not prove the authors' execution
environment.

## Tests and cross-language state

The complete Python suite ran 83 tests with zero failures, zero errors, and
zero skips. It covers source identity, strict parsing, exact aggregation,
control transitions, source/paper rounding conflicts, mutations, report
non-overwrite, claim boundaries, CLI integration, and cross-language report
composition. Suite manifest: 21 members, 83,526 bytes, SHA-256
`3addb54c26ccda0eb6e5b471575c66fb726fcd74cf5819caf6d8f7ec4466b447`.
Generated test-report digest:
`99047710911ad70f6ae865e2d7e5b69a5a4d79d6cc226f24e5d5c9451fea6130`.

An independent MATLAB/Octave parser and control-transition implementation is
included with 25 assertions. No Octave or MATLAB executable exists in the
local audit runtime, so the local cross-language execution status is
**`NOT_RUN_LOCAL_NO_OCTAVE`**. This is not reported as a pass. The
candidate-local CI workflow installs GNU Octave, authenticates the same raw
member, runs those assertions, and binds their JSON result to an independently
generated Python report. Cross-language composition success and mutation
failure paths were exercised by the Python protocol suite, but that does not
substitute for an actual Octave run.

## Retained conflicts and claim boundary

- Figure 5 provides paper context for 500-run OneMax means but no literal
  numeric mapping to this exact artifact.
- Paper pseudocode uses `ceil(lambda)` offspring; source uses Python
  ties-to-even `round(lambda)`.
- The paper does not pin a Git revision, and upstream does not lock dependency
  versions.
- The source evaluation counter excludes the initial parent and counts
  `2*round(lambda)` even when mutation strength is zero.
- Raw rows retain final pre-transition controls only, not complete per-generation
  RNG and control traces.

Therefore `PASS_FULL`, `PASS_LITERAL_PAPER_ENDPOINT`, and
`HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN` remain forbidden regardless of the
exact artifact and source-native passes.
