# EU26-27 — historical IOHexperimenter dependency recovery

Status: `DISCOVERY_ONLY / HYBRID_BLOCKED`

## Why one additional dependency state remains

The complete paper-era GSEMO source-revision recovery (S01–S09) found no exact replay of the authenticated Zenodo `TwoRateL10P1HVOneMaxD100.csv` matrix when paired with IOHexperimenter v0.3.9. Compiler recovery also rejected GCC9-vs-GCC10 as the explanation because both produced the same scientific mismatch.

The author GSEMO repository stores `include` as a developer-local symlink to:

```text
/home/jacob/code/IOHexperimenter/include/
```

so the actual experiment dependency was a local Jacob de Nobel IOHexperimenter checkout, not a pinned release.

## Correction trail before numerical outcome

The first dependency preregistration named `8f72d8f8cd3e7a746c35f446bc65c60965deb0be` as D01. Its CI job stopped at the **identity gate before build and before any OLD numerical run**. The immutable checkout proved that this commit still has:

```text
include/ioh/common/random.hpp = b916f4e7e1a96ef739a89602b468f839b4fad491
```

which is the old `gen` API, not the `GENERATOR` symbol required by the frozen GSEMO source. Therefore `8f72d8f...` is `SOURCE_INCOMPATIBLE / NO_NUMERICAL_OUTCOME` and is removed from the executable dependency candidates without using any result data.

The next public commit in the same Jan-06 transition, `8d21f4f6b46844d037c6a8740db2a56a1c940e0f`, has the required `GENERATOR` RNG while retaining the pre-Jan-11 problem/constraint core. Jan-10 commit `41dfe4edfc19b8bda765e707aa61e4174a7a18a5` has the same critical core fingerprint, so running both would duplicate one dependency state.

## Outcome-blind dependency reduction

The GSEMO source requires both:

- `ioh::problem::IntegerSingleObjective`;
- `ioh::common::random::GENERATOR`.

The public history reduces to two executable core states:

### D01 — compatible old-core state — UNTESTED

Representative commit:

```text
8d21f4f6b46844d037c6a8740db2a56a1c940e0f
2023-01-06
```

Critical blobs:

```text
include/ioh/common/random.hpp       b032b0b6df43083d58ff287b2112958ddc3d572e
include/ioh/problem/constraints.hpp b64d88fac38a7e3a1c4be7c35d9557f4d4a1074a
include/ioh/problem/problem.hpp     8ee2fa46233a7730267bd10edc50f33aef46100c
include/ioh/problem/single.hpp      d9f4143424bd20abac6f9922a89ec7e5fd642a17
include/ioh/problem/pbo.hpp         1d74dbf2d12612c18ad425e167baeede6c178705
```

`41dfe4edfc19b8bda765e707aa61e4174a7a18a5` has the same critical fingerprint and is therefore not a separate hypothesis.

### D02 — Jan-11 through v0.3.9 core state — ALREADY TESTED

By commit:

```text
0275c40d90353c2b3e22cde5f6a01aeb359c3909
```

the critical blobs are already the same values later present at v0.3.9:

```text
include/ioh/common/random.hpp       b032b0b6df43083d58ff287b2112958ddc3d572e
include/ioh/problem/constraints.hpp e9aed3b7af252aa67f01662a56ceeaa3e70000ce
include/ioh/problem/problem.hpp     bc39fa71fd596ea33f6ea13ff01fb280ccbc06eb
include/ioh/problem/single.hpp      730a131422100e0a0be25d298acd228073c7ae3a
include/ioh/problem/pbo.hpp         1d74dbf2d12612c18ad425e167baeede6c178705
```

Those same core blobs are present at v0.3.9 commit `f223c682dff0749067d00b870f83ad754f7d96f5`, which has already failed exact OLD replay. Re-running every intervening unrelated commit would be outcome fishing rather than a dependency hypothesis.

## Frozen D01 discovery experiment

GSEMO is held fixed at the final author source:

```text
FurongYe/GSEMO@fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
```

with source blobs verified before and after execution.

Environment:

- IOHexperimenter D01: `8d21f4f6b46844d037c6a8740db2a56a1c940e0f`;
- Docker GCC10 image, with digest recorded in evidence;
- command: `./gsemo 1 100 TwoRate 10 1 1 100000 100`;
- 100 sequential runs under the author's one global RNG stream seeded once with 10;
- no changes to GSEMO algorithm source;
- authenticated Zenodo comparator identical to prior recovery stages.

## Decision

D01 is a recovery candidate only if it yields all of:

- build and source-integrity PASS;
- `100/100` complete runs;
- exact `101 x 100` first-hit matrix equality;
- exact 100-run endpoint-vector equality;
- raw mean consistent with the authenticated Zenodo matrix and published rounded endpoint.

A green diagnostic job by itself is not scientific PASS.

If D01 is an exact match, a **new immutable confirmatory OLD head** must lock GSEMO SHA/blobs, IOH SHA/core blobs, compiler image digest and frozen command. That separate confirmatory run must fail closed on any mismatch. Only it may declare `PASS_SOURCE_NATIVE_OLD` and authorize HYBRID.

If D01 is not an exact match, the publicly recoverable source/dependency/compiler axes have not produced an exact historical environment; HYBRID remains blocked under the current exact-replay contract and the unresolved environment gap must be documented rather than hidden by threshold relaxation.
