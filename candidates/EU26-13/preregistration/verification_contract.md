# EU26-13 targeted artifact contract v1

Frozen: 2026-08-09, before candidate-local implementation.

Status: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

Paper mapping: **`PAPER_CONTEXT_ONLY`**

Source-native status: **`BLOCKED_UNPINNED_TOOLCHAIN_DEPS`**

## Frozen sources

- Paper DOI: `10.1007/978-3-031-70068-2_17`.
- Legal manuscript: `https://arxiv.org/pdf/2405.01226`, 1,474,257 bytes,
  SHA-256
  `3e2274f8e819e5eb7c268a4fe8f30f723241a8f1af424791cd1c2e50442ea78c`.
- Artifact DOI: `10.5281/zenodo.10997200`, immutable record `10997200`,
  CC-BY-4.0.
- `repelling_code.zip`: 24,065,992 bytes, MD5
  `a4d4a132570f162c686123a46a78fc67`, SHA-256
  `4b3a99b4e3661f701276dc63426d14879ed6c2bb38563af67b7662bc83ec4a9b`.
  It has 498 duplicate-free, unencrypted entries, and its embedded `LICENSE`
  is MIT.
- The source snapshot contains Modular CMA-ES 1.0.6 and Eigen 3.4.0, but no
  Git revision is claimed.
- `repelling.zip`: 17,573,142,426 bytes, Zenodo-declared MD5
  `5bf7f5e28ca5c6f26859c94c3eb1fcee`. It must never be downloaded in full by
  this study.

## Outer ZIP64 identity

- last 65,536 bytes start at `17,573,076,890` and have SHA-256
  `f37de706cbe1c09bb11562c993c166be88696e55546fd82068f9396a7b25d0bd`;
- ZIP64 EOCD offset `17,573,142,328`;
- ZIP64 locator offset `17,573,142,384`;
- classic EOCD offset `17,573,142,404`;
- 60 entries;
- central-directory offset `17,573,135,462`, size 6,866 bytes, SHA-256
  `de9e084a48c68eb9c565ce05b782ef199f7abe5b6ceae239a2b9b728ae6e7347`.

Selected stored outer member:

```text
CMA-ES-BIPOP-repelling-c1000.0-elitist.zip
```

- local-header offset `410,334,475`;
- local-header length 100 bytes, SHA-256
  `fe8863dcb098fc7db1e79197d9057e49a4e970697746e3761170aa57d102a71f`;
- payload offset `410,334,575`;
- flags `0`, method `0` (stored);
- compressed and uncompressed size `385,093,474` bytes;
- CRC32 `e907dafc`.

The outer CRC is authenticated from central metadata but is not recomputed,
because the complete nested member is not downloaded.

## Nested ZIP and target member

All nested offsets are relative to the stored outer payload unless explicitly
labelled absolute.

- nested size `385,093,474` bytes;
- last 65,536 nested bytes have SHA-256
  `f04b183deefcc03302c59f150779c27383a384ae0eac8b7175e0fe47ff6c9dea`;
- 338 entries;
- central-directory offset `385,042,441`, size 51,011 bytes, SHA-256
  `53bdc3d6918143f159f8912f75915fadc87d1a4fe46f75b15af0c6bfe57ea855`;
- classic EOCD offset `385,093,452`.

Target member:

```text
CMA-ES-BIPOP-repelling-c1000.0-elitist/IOHprofiler_f1_Sphere.json
```

- nested local-header offset `378,912,545`;
- absolute local-header offset `789,247,120`;
- local-header length 123 bytes, SHA-256
  `bfe85301a1ab6db2ad151310338c81294f25f24af43d68a31d51718483a713ba`;
- absolute compressed-payload range `789,247,243..789,669,451`
  inclusive;
- flags `0`, method `8` (raw deflate);
- compressed size `422,209`, SHA-256
  `97b33f647c6afd990bc368a8b0e60e98f6fc14781203f4fb6090ff503a2e8dfc`;
- raw size `3,113,753`, SHA-256
  `ee9cb8f7e11803263f21d15563daa266e379ea32a435a425f5228f8c74dc0f9a`;
- CRC32 `63419fdd`.

## Frozen endpoint and seed protocol

Strict JSON identity:

- version `0.3.15`, suite `unknown_suite`, function ID `1`, function name
  `Sphere`, minimization;
- algorithm name exactly
  `CMA-ES-BIPOP-repelling-c1000.0-elitist`;
- dimensions in archived order `[9, 4, 3, 20, 5, 10, 6, 7, 8]`;
- the `D=20` scenario is `/scenarios/3` and contains 500 runs;
- run order is 50 repetitions of each instance 1 through 10;
- driver order is instance outer, run inner, with seed `42 * run`.

Exact target `/scenarios/3/runs/0`:

| Field | Frozen value |
|---|---:|
| instance | 1 |
| run index | 0 |
| inferred driver seed | 0 |
| evals | 2,173 |
| best.evals | 2,173 |
| best.y | `7.379046076174201e-09` |
| length(best.x) | 20 |

The decimal token must match exactly. No tolerance or rounded DAT substitute
is allowed.

## Independent controls

Python and Octave independently implement these source-grounded controls:

1. Driver schedule: instances `1..10`, runs `0..49`, seeds `42*run`, exactly
   500 rows in instance-major order.
2. First BIPOP restart for `lambda0=12`, `mu0=6`, budget `200000`, and 1,000
   evaluations: budget split `99,500/99,500`, large population `24`, `mu=12`.
   A supplied uniform `u=0.5` gives unused small-population proposal `2`.
3. Second BIPOP restart after another 2,000 evaluations: large budget becomes
   `97,500`, small budget remains `99,500`, large population proposal becomes
   `48`; supplied `u=0.25` selects even small population `8`, `mu=4`; supplied
   sigma draw `v=0.75` gives `0.06324555320336758`.
4. Repelling radius for `D=20`, search volume `10^20`, `sigma0=2`,
   `coverage=1000`, two finalized restarts, and `n_rep=3` is
   `8.378500086238091`. Shrinkage is `0.99^(1/20) =
   0.9994976094477416`; after five rejected draws the effective radius is
   `8.357474826211032`.
5. CSA control uses the released formula
   `sigma *= exp((cs/damps)*(norm(ps)/chiN - 1))`; the frozen scalar fixture
   yields `2.05354060920934`.
6. Hill-valley interpolation uses `k/(n+1)`, returns different-basin only when
   an intermediate value is strictly greater than both endpoint values, and
   counts each evaluation.

These controls validate formulas and ordering only. They do not recreate the
source-native stochastic trajectory.

## Gates

| Gate | Requirement |
|---|---|
| A1 metadata | Exact Zenodo record, license, file names, sizes, and declared MD5 values. |
| A2 code | Exact code bytes/SHA-256; safe, duplicate-free ZIP; pinned member bytes and MIT license. |
| A3 outer ZIP64 | Exact content range, tail, EOCD/locator, entry count, directory coordinates/hash, and unique safe entries. |
| A4 nested ZIP | Stored outer-member identity, local header, exact nested tail/EOCD/directory, and unique safe entries. |
| A5 target member | Central/local agreement, exact range, raw deflate, compressed/raw hashes, size, and CRC32. |
| A6 endpoint | Strict schema/order/counts and exact frozen decimal endpoint. |
| A7 controls | Python seed, BIPOP, repelling, CSA, and hill-valley fixtures pass. |
| A8 cross-language | Octave independently reproduces endpoint/schema, seed, BIPOP, repelling, and CSA fixtures. |
| A9 fail closed | Any metadata, range, ZIP, path, duplicate, method, flag, size, CRC, hash, schema, order, endpoint, fixture, or claim mutation is rejected. |
| A10 boundary | Reports retain targeted-only/context-only labels, declared-only MD5, no Git revision, and the source-native blocker. |
| A11 source-native | Must remain `BLOCKED_UNPINNED_TOOLCHAIN_DEPS`; no execution can upgrade it under v1. |

## Allowed outcomes

- `PASS_ZENODO_METADATA`
- `PASS_CODE_ARCHIVE_IDENTITY`
- `PASS_RANGE_AUTHENTICATED_MEMBER`
- `PASS_ARTIFACT_ENDPOINT`
- `PASS_INDEPENDENT_CONTROLS`
- `PASS_CROSS_LANGUAGE_CONTROLS`
- `BLOCKED_UNPINNED_TOOLCHAIN_DEPS`

The candidate-level conclusion may be
`TARGETED_ARTIFACT_REPLAY_VERIFIED_WITH_SOURCE_NATIVE_BLOCKED` only if A1–A10
pass and A11 remains blocked. It is not `PASS_FULL`.
