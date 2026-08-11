# EU26-20 final OLD status

Status: `REJECTED_OLD_REPRODUCTION`

Decision date: 2026-08-11.

No executable HYBRID was created. The candidate must not be merged as a successful reproduction and must not be used as the base for a PR #8 hybrid.

## Decision summary

A complete bounded OLD verification cycle was performed on the Colon endpoint from Nematzadeh et al. (Knowledge-Based Systems 301, 2024, 112345):

- exact author commit and source/data/feature blobs authenticated;
- author-source compatibility profile executed separately from the printed-paper profile;
- independent clean-room printed-paper implementation completed;
- fixed-tape, deterministic, provenance, geometry, adaptive-control, fitness, NFE, and fail-closed repository tests passed;
- primary ten-seed campaign completed for the clean-room paper profile;
- bounded ten-seed campaign attempted for the author source;
- five preregistered sensitivity campaigns tested the main paper/source ambiguities without changing the primary acceptance rule.

The reported Colon accuracy was reproducible, but the reported average subset length was not reproduced by the independent paper profile. The public source was additionally unstable because its external-repository generation could fail to terminate. No single documented ambiguity resolved both problems.

## Frozen paper targets

Table 5 / Section 5.4 target:

- baseline accuracy: `0.69`;
- CMF-AGAwER mean accuracy: `0.94`;
- mean selected subset length: `6`;
- 10 runs with stratified 5-fold cross-validation.

Table 8 diagnostic:

- mean NFE: `788`;
- not a literal pass/fail gate because its caption says 3 runs while nearby prose says 10 runs.

## Independent printed-paper profile

Profile: `paper_cleanroom_feature_geometry`.

Frozen semantics include:

- actual 62-dimensional feature-vector geometry for Algorithms 2-4;
- printed `ceil()` offspring counts;
- complete current-population roulette ledger;
- decision tree with `random_state=42` and unshuffled stratified 5-fold CV;
- exact fitness rounding and NFE accounting;
- beta=2 external-repository radius;
- 20-failure stopping rule;
- auditor seeds `1..10`, plus exact repeat of seed 1.

All ten runs completed and the repeated seed was exact.

| Metric | Paper | Observed | 95% CI | Gate |
|---|---:|---:|---:|---|
| Baseline accuracy | 0.69 | 0.69 | fixed | PASS |
| Final accuracy | 0.94 | 0.941 | [0.92575, 0.95625] | PASS |
| Subset length | 6 | 8.2 | [5.99383, 10.40617] | **FAIL** |
| NFE | 788 diagnostic | 870.8 | [740.85, 1000.75] | diagnostic |

The preregistered subset gate required both:

1. mean absolute difference from 6 at most 1.5;
2. 95% confidence interval containing 6.

The interval contains 6, but the observed mean differs by 2.2, so `P4_subset_length_alignment` fails. The rule was frozen before the campaign and was not relaxed after seeing the result.

Per-seed final `(accuracy, subset length, NFE)`:

1. `(0.98, 8, 1192)`
2. `(0.97, 7, 982)`
3. `(0.94, 3, 708)`
4. `(0.92, 9, 728)`
5. `(0.93, 8, 890)`
6. `(0.92, 13, 708)`
7. `(0.95, 6, 1006)`
8. `(0.95, 13, 1058)`
9. `(0.93, 9, 780)`
10. `(0.92, 6, 656)`

Primary verdict: `BLOCKED_PAPER_NUMERIC_MISMATCH`.

## Pinned author-source compatibility profile

The source profile preserves source-level behavior, including Python ties-to-even `round()` and the public notebook's search semantics, while applying only documented experiment-selection/reporting repairs and a fail-closed repository attempt guard.

Result:

- 9/10 primary seeds completed;
- repeated seed 1 completed exactly;
- seed 4 failed during main-loop iteration 1 after 20,000 attempts to generate the required 10 diverse repository candidates.

Partial results from the nine completed seeds:

| Metric | Partial mean | Values |
|---|---:|---|
| Accuracy | 0.94444 | 0.98, 0.92, 0.95, 0.95, 0.97, 0.98, 0.90, 0.93, 0.92 |
| Subset length | 7.22222 | 9, 5, 6, 7, 8, 9, 10, 3, 8 |
| NFE | 966.67 | 948, 804, 1116, 1020, 1308, 1212, 900, 684, 708 |

Source verdict: `BLOCKED_SOURCE_REPOSITORY_NONTERMINATION`.

## Material paper/source differences and source defects

The verification preserved rather than hid these differences:

1. paper `ceil()` offspring counts vs source Python `round()`;
2. paper feature-vector geometry vs source numeric feature-identifier geometry;
3. printed 20-failure stop vs source effective 19-failure stop;
4. source notebook cells overwrite the selected dataset during linear execution;
5. stale `Xn=X[Xn]` notebook state crashes direct execution;
6. source roulette refresh writes `Fits[i]` inside `for j`, using stale `i`;
7. source external-repository loops are unbounded.

The independent profile repaired unequivocal coding defects but did not tune parameters or introduce a subset-size preference absent from the paper.

## Preregistered sensitivity study

Sensitivity campaigns used the same Colon data, 128-feature pool, classifier, fitness, seed ledger, and unchanged numerical gate. Sensitivity results were never eligible to become `PASS_OLD_REPRODUCTION`.

| Variant | Complete | Mean accuracy | Mean subset | Mean NFE | Result |
|---|---:|---:|---:|---:|---|
| Primary printed-paper profile | 10/10 | 0.941 | 8.2 | 870.8 | subset mismatch |
| Legacy MT19937 only | 10/10 | 0.932 | 8.2 | 884.2 | accuracy and subset mismatch |
| Source `round()` only | 10/10 | 0.939 | 7.9 | 969.0 | subset mismatch |
| Source effective stop at 19 | 10/10 | 0.941 | 8.2 | 848.8 | subset mismatch |
| Numeric feature-ID geometry only | 10/10 | 0.947 | 7.4 | 875.8 | subset target outside 95% CI |
| Source-like bundle | 8/10 | 0.94625 partial | 6.375 partial | 1094.0 partial | 2 repository-generation failures |

The source-like bundle was the only profile approaching a mean subset near 6, but it simultaneously combined four source-visible deviations and failed to complete 2/10 runs. It therefore cannot justify replacing the printed-paper profile or claiming successful reproduction.

## Artifact identities

Primary workflow run: `31504574147`.

- independent paper campaign artifact digest: `sha256:ef4440aa9f0b80e2195a5fb26eb328b6280375c38c83338c1de362d84c3f2953`;
- bounded source campaign artifact digest: `sha256:f9670932ddbbb0466a74299a26459eb78b5cdca633f2e8498ea3a12c47b30a9f`.

Sensitivity workflow run: `31506833292`.

- legacy MT19937: `sha256:4721c2ed4635b061278c89fb1f0176bc5e1dccf8869e4bf02b4d08a9e3f3253a`;
- source rounding: `sha256:81bd5fee44588b06dda3691655ad6d50213944c494bc02621ddf3b82dafed76c`;
- source stop 19: `sha256:668dc23856f26957f93ec679db98f14b4c13b339457bd9ee2cc0bb190a14e8d7`;
- numeric identifier geometry: `sha256:9cd096e2c2eb10a6cc4320d0e4bc56f5adcb4f660a0aef115a1abd5c597302b7`;
- source-like bundle: `sha256:749399a30582e776735b562ffd74a87df31b1329ed9107e728179ba776b3e74a`.

## Final decision

This candidate does not satisfy the project's OLD quality requirement:

- a stable public-source ten-run endpoint was not obtained;
- the independent paper implementation reproduced accuracy but not the reported average subset length under the frozen gate;
- bounded sensitivity analysis found no single defensible paper ambiguity that repairs the mismatch;
- the closest source-like configuration remained unstable.

Therefore:

- candidate status is `REJECTED_OLD_REPRODUCTION`;
- PR #18 must remain unmerged and may be closed as a rejected research candidate;
- `hybrid/` remains documentation-only;
- no PR #8 mechanism may be applied to this candidate;
- the next candidate must start from the shared PR #8 base, not from this rejected branch.
