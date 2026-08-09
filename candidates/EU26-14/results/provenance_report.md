# EU26-14 local verification report

Date: 2026-08-09.

## Outcome

Local Python outcome: **`PASS_TARGETED_ARTIFACT_REPLAY`** under status
**`TARGETED_ARTIFACT_REPLAY_ONLY`** and mapping **`PAPER_CONTEXT_ONLY`**.

Source-native optimization was not run and remains
`NOT_ATTEMPTED_OUT_OF_SCOPE`.

Independent pre-PR review stopped publication until the post-implementation
preregistration rewrite, contract drift, dtype type confusion, ancestor
symlinks, optional-only full CI, and forged cross-language report acceptance
were corrected. The two original preregistration documents are restored to
their frozen bytes. Amendment 001 records the timing and narrowly supersedes
the impossible reducer wording without changing the endpoint or claim ceiling.
The amended live contract is schema `1.1.0`, SHA-256
`47ac507e09bb9ad705fa934af672763bd6e2fd02d8b18fe74fedb1498b39ff49`.

## Authenticated inputs

| Input | Bytes | Verified identity |
|---|---:|---|
| `SHA256SUMS` | 344 | SHA-256 `7b6abb7ac47d15e836416cfe822cd04ff4a1a1f9bbda30705a7f6a3fa6dc28ff` |
| `source.tar.gz` | 20,992,578 | SHA-256 `351c5a68331c6c589dd7c23b1ab5dee150c50ce6bf8a963dead6555cafa9b2a9` |
| `msc_cec2020.tar.zst` | 317,976,046 | SHA-256 `22c0468ce1d01e03c30826abcd0952942a5d03d7822c0cc509897c6f7a40540e` |
| selected `f1.pkl` | 462,408 | SHA-256 `310f68adb1878ea8179c527e42831286b472ec8dc1bd96984c843b9e5f7d344b` |

The result tar contained 1,239 unique safe entries: 1,094 regular files and
145 directories. The selected header/data offsets were 481,444,864 and
481,445,376. The source tar contained 866 unique safe entries; all nine
required semantic source/runner/license members matched immutable Git blobs at
commit `a88841620b2eddd13a1fab85331fcfc8caa1e85f`.

## Safe endpoint checks

- protocol 5 parsed with 52,866 admitted opcodes;
- exactly two symbolic globals were observed:
  `numpy._core.numeric._frombuffer` and `numpy.dtype`;
- 109 statically validated `REDUCE` forms and 53 dtype-only `BUILD` states;
- all 51 seeds were contiguous and all improvement ledgers strictly ordered;
- cycle ledgers were contiguous, with 30 to 39 cycles per seed;
- even cycles spent 4,096 Phase-0 evaluations and odd cycles reused the sample
  at zero Phase-0 cost, including valid zero-evaluation/no-basin odd cycles;
- every recorded `nfev_total` was below the nominal budget.

Frozen run 0 matched exactly: error `0.0`, improvement shape `339 x 2`, first
row `[4096, 17928356740.02234]`, last row
`[2882691, 9.243294130101276e-09]`, 30 cycles, pre-refinement error
`0.8729793091438722`, `nfev_pre_refine=2876679`, and
`nfev_total=2893419`.

The create-only local JSON report had SHA-256
`55ab0eca2303fc361944e4546cb04e5f9c993219dd9a35c76762e714076a26f8`
and domain-separated report digest
`sha256:b134d1322fb746100f0bb79a5301fd146dc28dd9f36ed09d6a059f465167aef9`.
The report carries the amended contract identity.

## Tests

Python 3.13.5 with pinned zstandard 0.23.0 passed 45/45 tests with the complete
artifact directory supplied and `--require-full-artifact`; zero tests skipped.
Coverage included unit, protocol, complete integration, unsafe pickle forms,
strict dtype slot types, duplicate/path/link tar attacks, contract mutation,
leaf and ancestor symlinks, retained-descriptor path replacement, in-place
mutation, fixture arithmetic, claim ceiling, create-only output behavior,
duplicate JSON keys, non-regular report inputs, and forged/malformed Python
and Octave report rejection. The registry validator
passed and all 13/13 registry mutation tests passed.

The required pull-request workflow pins Python 3.13.5 and zstandard 0.23.0,
runs the same full suite with zero skips, and bounds every download before
complete-file size/hash authentication. It also runs the registry regression
and independent Octave jobs before the full integration job.

GNU Octave 8.4.0 from Ubuntu package `8.4.0-1build5` ran from an isolated
non-repository runtime. The `octave-cli` binary SHA-256 was
`9f09bcbadf9fd0a540437a364449e7b23246cfa97c9eeeb0b6539161bc00205f`.
It produced `PASS_CROSS_LANGUAGE_CONTROLS`; the Octave report SHA-256 was
`6517594b10675697bb92b6178d55080f359b75fea5c6bce2cd3169f0fdb22f7b`.
The actual Python/Octave finalizer also passed, producing a cross-language
report with SHA-256
`55f11aff15edd03199e3bdbf6677c56808e0cbd0e76830c2686946df767af49a`
and report digest
`sha256:41e3889ee5a6faea2612b1144b2dd582a98ab8e26684938cc8a18268ed4f3a9d`.
The create-only Octave writer rejected a second write with exit status 1.

The automatic required pull-request CI repeats the independent control and
full binder. The contract binds the control source's 48 static `assert()` call
sites instead of carrying an ambiguous assertion sentinel.

## Preserved conflict

Run 0 leaves 106,581 nominal evaluations unused. The paper/README wording that
refinement spends the remaining budget is therefore not repeated as a literal
fact. `PASS_FULL`, exact source-native replay, literal paper-cell mapping,
historical-environment proof, and budget-exhaustion confirmation remain
forbidden.
