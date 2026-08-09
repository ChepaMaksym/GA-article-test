# EU26-14 local verification report

Date: 2026-08-09.

## Outcome

Local Python outcome: **`PASS_TARGETED_ARTIFACT_REPLAY`** under status
**`TARGETED_ARTIFACT_REPLAY_ONLY`** and mapping **`PAPER_CONTEXT_ONLY`**.

Source-native optimization was not run and remains
`NOT_ATTEMPTED_OUT_OF_SCOPE`.

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
`231f422a4161cd697c7dae6f7398c901c3537e2615b385435c33fa3167785863`.

## Tests

Python 3.12.13 with zstandard 0.25.0 passed 22/22 tests when the complete
artifact directory was supplied. Coverage included unit, protocol, complete
integration, unsafe pickle forms, duplicate/path/link tar attacks, identity
mutation, symlink, retained-descriptor path replacement, in-place mutation,
fixture arithmetic, claim ceiling, and create-only output behavior.

GNU Octave was not installed in the local execution environment, so this
report does not claim a local Octave pass. The independent Octave control and
an explicit CI job are committed; CI must produce
`PASS_CROSS_LANGUAGE_CONTROLS` before a cross-language evidence claim.

## Preserved conflict

Run 0 leaves 106,581 nominal evaluations unused. The paper/README wording that
refinement spends the remaining budget is therefore not repeated as a literal
fact. `PASS_FULL`, exact source-native replay, literal paper-cell mapping,
historical-environment proof, and budget-exhaustion confirmation remain
forbidden.
