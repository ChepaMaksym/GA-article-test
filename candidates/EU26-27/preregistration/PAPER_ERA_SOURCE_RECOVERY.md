# EU26-27 — paper-era source revision recovery

Status: `DISCOVERY_ONLY / HYBRID_BLOCKED`

## Why this recovery exists

The frozen final author commit `FurongYe/GSEMO@fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380` is source-native and buildable, but the 100-run OLD does not exactly replay the authenticated Zenodo matrix under GCC9 or GCC10 with IOHexperimenter v0.3.9. Both environments produce the same scientific mismatch, so a GCC9-vs-GCC10 library explanation is rejected.

The public GSEMO history contains multiple distinct `src/gsemo.hpp` blobs during the paper-development window while `src/main.cpp` already exposes the same HV command profile and `random::seed(10)`. Therefore this recovery tests every unique public algorithm generation in that window exactly once, rather than selecting commits from numerical outcomes.

## Frozen discovery matrix

All jobs use:

- IOHexperimenter `v0.3.9`, commit `f223c682dff0749067d00b870f83ad754f7d96f5`;
- Docker `gcc:10` / GCC10 libstdc++;
- command `./gsemo 1 100 TwoRate 10 1 1 100000 100`;
- one sequential RNG stream seeded once by the author code;
- unchanged author source at the exact candidate commit;
- authenticated Zenodo comparison through the existing diagnostic comparator.

Unique algorithm generations, selected by `src/gsemo.hpp` blob identity before running this matrix:

| label | author commit | expected `src/gsemo.hpp` blob |
|---|---|---|
| S01 | `c96da79a25a11a0ff93b99cf2027ac7750ea0430` | `52f5b2fe4d9d396508445eacd479a07eeea4ea36` |
| S02 | `4b0a812dc3c13c46bb9ac741b3837c620154205b` | `9dbb189cc973259dfecda4a9361acecb08743eed` |
| S03 | `518d6c0c9cad2fe0ae320d5aab75c88a24fe18ea` | `f4c15978403b457e5c8e9aa42151c257456108ce` |
| S04 | `5046331456a2a15218d44e6146d9d69ab8c77595` | `ab4b99327ebd0309bfc7ec3ad731f9b37165f4c2` |
| S05 | `81da3b13a31b2970a79b7fc184aa1de2ead31e7a` | `863ce132325ae928cac543c12508c0088babcc3b` |
| S06 | `b2e8c325074297dc3a8f60e30d2d8c09b038bbb3` | `601d30c45f3a5769a24edf949c378cdb48c90591` |
| S07 | `fc87136e655275307fa4a222b9574445c0f08812` | `218aed78fea38155e9643b45a9d1f278065cfbe4` |
| S08 | `78d0d39539a2362ca37e6569f18698427d52422a` | `6965a2c20f84d6f51243278aba045eb257a9bfd4` |
| S09 | `fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380` | `2693144bcfccff902343a02c6c8e48d7dd263257` |

`src/main.cpp` for the pre-submission generations is blob `673290675b6523902ea0a6a6f4e80005c692c67b`; the final submission commit deliberately has its later main blob and is already independently audited.

## Discovery decision

A source revision is only a recovery candidate if the diagnostic reports all of:

- complete runs `100/100`;
- exact `101 x 100` first-hit matrix equality;
- exact 100-run endpoint equality;
- raw mean consistent with the authenticated Zenodo matrix and published rounded endpoint.

A green job alone is not a scientific PASS because the diagnostic intentionally exits successfully on mismatches.

## Confirmation rule

If exactly one paper-era revision is an exact match, create a new immutable confirmatory head that locks that source SHA, source blob SHA, IOH SHA, compiler image/digest and OLD command. Repeat the strict OLD without a discovery matrix. Only that independent strict rerun may declare `PASS_SOURCE_NATIVE_OLD` and authorize HYBRID.

If no source revision exactly matches, HYBRID remains blocked and the next recovery axis must be preregistered before testing (dependency revision / build environment), without changing the OLD numerical criterion.
