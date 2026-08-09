# EU26-14 targeted artifact contract v1

Frozen: 2026-08-09, before candidate-local implementation and before any
source-native replay.

Status: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

Paper mapping: **`PAPER_CONTEXT_ONLY`**

## Frozen source identity

- Paper: arXiv `2606.15830v3`, DOI `10.48550/arXiv.2606.15830`; PDF
  1,491,426 bytes, SHA-256
  `db6fd539753f6adf36caea298de6ae31791491779f8967ff22c261169d3c2f4b`.
- Repository: `https://github.com/snenovgmailcom/cma_es_project` at commit
  `a88841620b2eddd13a1fab85331fcfc8caa1e85f`, MIT.
- Zenodo record: `21483843`, DOI `10.5281/zenodo.21483843`, version `1.0.0`,
  CC-BY-4.0.
- `SHA256SUMS`: 344 bytes, MD5 `972d3b03271f232507b2467ef684b6d0`,
  SHA-256
  `7b6abb7ac47d15e836416cfe822cd04ff4a1a1f9bbda30705a7f6a3fa6dc28ff`.
- `source.tar.gz`: 20,992,578 bytes, MD5
  `f9e838739cd44502deff1c958b15efe3`, SHA-256
  `351c5a68331c6c589dd7c23b1ab5dee150c50ce6bf8a963dead6555cafa9b2a9`.
  Its root is `src-a888416`; required code and license bytes must match the
  frozen Git commit.
- `msc_cec2020.tar.zst`: 317,976,046 bytes, MD5
  `b6bf0e94f37139893edcaaf75fc16f2a`, SHA-256
  `22c0468ce1d01e03c30826abcd0952942a5d03d7822c0cc509897c6f7a40540e`.
  The SHA-256 must also occur exactly once in the authenticated
  `SHA256SUMS` file.

## Frozen member and endpoint

Selected tar member:

```text
experiments/cec2020/d15/MSC-CMA/maxevals_3000000/f1.pkl
```

- uncompressed tar data offset: `481445376`;
- payload size: `462408` bytes;
- payload SHA-256:
  `310f68adb1878ea8179c527e42831286b472ec8dc1bd96984c843b9e5f7d344b`.

The safe parser must establish:

- suite `cec2020`, dimension 15, function 1, optimum 100;
- algorithm `MSC-CMA`, budget 3,000,000;
- 51 runs, ordered seeds 0 through 50;
- metadata environment Python 3.13.5, NumPy 2.3.1, SciPy 1.15.3,
  cma 4.4.2, minionpy 1.5.0.

Frozen run-0 values:

| Pointer | Exact value |
|---|---:|
| `errors[0]` | `0.0` |
| `improvements.shape` | `339 x 2` |
| `improvements[0]` | `[4096, 17928356740.02234]` |
| `improvements[-1]` | `[2882691, 9.243294130101276e-09]` |
| `len(cycles)` | `30` |
| `pre_refine_error` | `0.8729793091438722` |
| `nfev_pre_refine` | `2876679` |
| `nfev_total` | `2893419` |

Cycle 0 freezes `nfev_start=0`, `nfev_end=49960`,
`best_end=138.7076282341263`, phase-0 cost 4096, 25 basins,
`phi=1.1490020177074536`, and mode `alt-0`.

Cycle 1 freezes `nfev_start=49960`, `nfev_end=143428`,
`best_start=138.7076282341263`, `best_end=101.47263506942203`, phase-0 cost
zero with sample reuse, five basins, `phi=1.1154715908615365`, improvement
`37.23499316470428`, and mode `alt-1`.

## Safe parsing contract

The result payload is untrusted input. General pickle execution is forbidden.
The implementation must use `pickletools` or a stricter no-execution parser,
maintain its own value stack/memo, and materialize only primitive containers
and numeric byte buffers after validating shape, dtype, byte count, and finite
values. The only symbolic references admitted by the frozen payload are:

```text
numpy._core.numeric._frombuffer
numpy.dtype
```

All other globals and all extension, persistent-reference, dynamic-global,
reducer, instance, object-construction, or unexpected opcodes fail closed.

## Verification gates

| Gate | Requirement |
|---|---|
| A1 contract | Strict schema, immutable claim ceiling, and frozen constants pass. |
| A2 metadata | Zenodo identity/version/license and every relevant file identity pass. |
| A3 source | Complete source archive hash, safe tar structure, MIT license, frozen root, and Git-byte mapping pass. |
| A4 results | Complete 317,976,046-byte archive SHA-256 and `SHA256SUMS` binding pass before decompression. |
| A5 member | Streaming zstd/tar locates one regular member at the exact offset/size/hash; duplicates, links, unsafe names, trailing data, and malformed padding fail. |
| A6 parser | No-execution pickle parser accepts only the frozen protocol and symbolic references; all unsafe or unexpected paths fail. |
| A7 endpoint | Strict metadata, seed order, array shapes, finite numbers, and every frozen run/cycle literal pass. |
| A8 fixture | A committed JSON/CSV fixture is derived only from the authenticated safe parse and carries the source archive/member identities. |
| A9 cross-language | Octave independently checks fixture identity, seed order, alternation/reuse, evaluation arithmetic, and cycle improvement arithmetic. |
| A10 adversarial | Hash, size, offset, duplicate, path, tar type, zstd, pickle opcode/global/reducer, dtype, shape, seed, endpoint, overwrite, and claim-boundary mutations fail closed. |

## Allowed outcomes and claim ceiling

Allowed evidence gates are `PASS_ZENODO_METADATA`, `PASS_SOURCE_IDENTITY`,
`PASS_FULL_ARCHIVE_IDENTITY`, `PASS_SAFE_PICKLE_PARSE`,
`PASS_FROZEN_ENDPOINT`, and `PASS_CROSS_LANGUAGE_CONTROLS`. Their conjunction
may be labelled `PASS_TARGETED_ARTIFACT_REPLAY` while retaining study status
`TARGETED_ARTIFACT_REPLAY_ONLY` and paper mapping `PAPER_CONTEXT_ONLY`.

The following claims are forbidden in every output:

- `PASS_FULL`;
- `PASS_EXACT_SOURCE_NATIVE`;
- `PASS_LITERAL_PAPER_ENDPOINT`;
- `HISTORICAL_ENVIRONMENT_PROVEN`;
- `PAPER_BUDGET_EXHAUSTION_CONFIRMED`.

No source-native run is part of contract v1. The raw/code stop-semantic
conflict must remain visible even when all targeted artifact gates pass.
