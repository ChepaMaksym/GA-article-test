# EU26-05 formula and transition validation contract v1

Evidence-authentication semantics are narrowed by
[`amendment-001-offline-evidence-boundary.md`](amendment-001-offline-evidence-boundary.md);
the scientific formula/source scope below is unchanged.

Frozen: 2026-08-07, before implementation tests and before any CEC-2017
outcome run.

Scope: **`FORMULA_AND_TRANSITION_VALIDATION_ONLY`**

Overall paper-level status: **`BLOCKED_SOURCE_BYTE_FREEZE_AND_STOCHASTIC_PROVENANCE`**

`PASS_FULL` is forbidden by this contract. The allowed result is limited to
formula, post-selection crossover-transition, objective-interface and
cross-environment portability validation. No CEC-2017 function suite or
published table/figure may be run under this contract.

## H0 source identity

- Exact chapter: José Ferreira, Mauro Castelli, Luca Manzoni and Gloria
  Pietropolli, *A Self-Adaptive Approach to Exploit Topological Properties of
  Different GAs' Crossover Operators*, DOI
  `10.1007/978-3-031-29573-7_1`, EuroGP 2023, LNCS 13986, pp. 3-18.
- Publisher record: `https://doi.org/10.1007/978-3-031-29573-7_1`.
- Lawful exact-title author postprint: University of Trieste ArTS handle
  `11368/3046333`, open access since 2024-03-30, component 3, exact OAI
  byte length `2921299`.
- Postprint bitstream URL: see `source_manifest/sources.csv`. On the freeze
  host, both the bitstream and retrieve URLs return a Cloudflare challenge to
  non-browser clients. ArTS OAI exposes the item identity and byte length but
  no checksum. Therefore the PDF SHA-256 is deliberately
  `SHA256_UNRESOLVED`; H0 is `PASS_METADATA_ONLY`, not a byte-level pass.
- Detailed antecedent source: José Pedro Ferreira's NOVA IMS thesis,
  60-page PDF, `1950181` bytes, SHA-256
  `fd0a947833b703d1729f5d44c4bee082b7e1999ba57ba2b8adccbc83d15e13ba`.
- Official CEC-2017 benchmark repository considered for provenance only:
  `P-N-Suganthan/CEC2017-BoundContrained` at
  `2c54cad22f015e803edb09ea86d4c961f5bab644`. The repository has no
  LICENSE/COPYING/NOTICE file at that revision. It is not authorized as an
  executable or redistributable input under v1.

The chapter is the publication authority. The thesis may clarify details but
cannot silently override a chapter conflict. Every use of a thesis-only detail
must retain that label.

## Frozen publication facts

The exact postprint reports:

- direct minimization of the 30 CEC-2017 functions in dimensions 10 and 30;
- selected cell `d=30`, represented by a 600-bit chromosome (20 bits per
  coordinate) over `[-100,100]^30`;
- population `400`, tournament size `3`, crossover probability `100%`,
  mutation rate `0%`, `200` generations, `80000` evaluations and `30`
  independent runs per function;
- P and P' adaptive variants with four preference levels labelled
  `tau in {0,1,2,3}`; the last level selects extension-ray crossover and the
  other levels select one-point crossover;
- initially equal preference probabilities;
- per-generation contribution
  `r_i = successful_crossovers_i / crossovers_i`;
- a 10% minimum probability for each of four types. The thesis states that
  the four types compete for the remaining 60%, and that an all-zero-success
  generation resets them to equal probability;
- a literal descriptive endpoint: in the `d=30` comparison, at least one of
  P/P' improves fitness on `27` of `30` functions.

The 27/30 statement is frozen only as a publication fact. Without author code,
raw values, seeds and a fully specified analysis/tie rule, it is not an
authorized executable acceptance gate.

## Exact conflicts and missing semantics

These are blockers, not implementation choices:

1. **Preference indexing.** The chapter defines `0 <= tau <= tau_max` but
   later uses four levels `0..3`. The thesis calls `tau_max=4`, initializes
   with `1/tau_max`, and elsewhere reserves the “last level” for extension
   ray. Treating `tau_max` as both a count and a maximum label creates an
   off-by-one conflict.
2. **Minimization sign.** The chapter's mate equation is explicitly for
   maximization: `argmax f(y_i) D(tau,d_i)`. CEC-2017 is a minimization suite.
   The thesis gives a minimization form for `D` but still prints `argmax` and
   does not freeze a fitness transform. P/P' parent selection is therefore
   outside v1.
3. **Contribution boundary.** The sources do not say what happens when one
   type has `#Cross=0`. The v1 probability oracle accepts only positive
   denominators for all four types. It never imputes an unsampled type.
4. **Floor order.** “10% each, compete for 60%, after normalized” supports
   `p_i = 0.10 + 0.60*r_i/sum(r)` when `sum(r)>0`, and equal `0.25` when all
   `r_i=0`. This is validated only for complete positive-denominator fixtures;
   no broader full-GA claim is made.
5. **Success equality.** The chapter accepts an offspring equal or better than
   both parents and discusses a non-coincident equal-fitness offspring. The
   thesis explicitly requires the successful offspring's representation to
   differ from both parents. v1 validates supplied success counts and does not
   classify objective/genotype tuples.
6. **Binary decode.** The sources give 20 bits per coordinate and bounds but
   do not give endianness, integer-to-real endpoint convention or rounding.
   The decode functions require these as explicit arguments and are interface
   anchors, not a paper-faithful decoder.
7. **One-point details.** A random cut and swapped tails are described, but cut
   endpoint eligibility and RNG mapping are absent. v1 uses only explicit
   interior cuts from a frozen tape.
8. **Extension ray.** The thesis describes its maximum binary form: copy the
   second parent and complement every common locus, applied in both
   directions. v1 tests only this labelled thesis profile; it does not claim
   that the missing author implementation used it byte-for-byte.
9. **P/P' selection/replacement.** Candidate sampling with/without
   replacement, tie-breaking, the duration of P' removals, fitness transform,
   full replacement and evaluation-count placement are not executable without
   invention. v1 starts after two parents and a preference type are supplied.
10. **CEC and analysis provenance.** No exact licensed CEC code/data revision,
    author implementation, environment lock, seed ledger, raw run table,
    per-function 30-run values or exact 27/30 tie rule was published.

## Authorized formula profiles

### Probability update

For four vectors of integer successes `s_i` and positive integer crossover
counts `n_i`, require `0 <= s_i <= n_i` and set `r_i=s_i/n_i`.

- If every `r_i=0`, return `[0.25,0.25,0.25,0.25]`.
- Otherwise return `p_i=0.10+0.60*r_i/sum(r)`.

Required invariants are finite values, `sum(p)=1` and
`0.10 <= p_i <= 0.70`. A zero denominator fails closed.

### Post-selection crossover transition

Inputs are two equal-length binary parents, a supplied preference label in
`{0,1,2,3}`, and a supplied interior cut for labels `0..2`.

- Labels `0..2`: two-child one-point tail swap.
- Label `3`: thesis maximum-extension profile in both directions. Algebraically
  the described copy/complement construction yields the complement of the
  first ray origin in each direction.

This transition is shared by P and P' only after their different parent
selection procedures have finished. It is not a P/P' selection replay.

### Binary/objective anchors

The decoder maps a binary block through an explicitly supplied bit order and
an explicitly labelled closed-endpoint linear convention. The objective anchor
only checks 30 decoded coordinates in `[-100,100]` and delegates evaluation to
an injected toy/test function. It must reject any attempt to label the injected
function as an authenticated CEC-2017 implementation.

## H0-H5 gates

| Stage | Required result |
|---|---|
| H0 provenance | DOI/handle/OAI identity, source rows and all conflicts validate; status remains `PASS_METADATA_ONLY` until the exact postprint bytes are SHA-256 frozen. |
| H1 unit/formula | Probability, decode-anchor and crossover unit fixtures pass independently in Python and MATLAB/Octave. |
| H2 property/adversarial | Probability simplex/floor, binary closure, Hamming/geometric properties, invalid-input rejection and exhaustive small-parent cases pass. |
| H3 fixed transition | Offline envelopes produce the exact same canonical transition payload and digest: `PASS_H3_PAYLOAD_FORMULA_EQUIVALENCE_ONLY`. Native execution remains `NOT_EVALUATED_EXTERNAL_EXECUTION_AUTH_REQUIRED`. |
| H4 repeatability | Work4 and Work8 each execute the formula suite five times; every same-profile report is byte-identical. GitHub4 uses the same logical four-worker contract. |
| H5 portability/comparator | Strict offline comparator requires identical contract/source/fixture digests, gate sets and formula payloads across Work4, Work8 and GitHub4, but cannot authenticate GitHub/API/artifact provenance. Even complete offline content remains `NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED`. |

The strongest possible v1 label is
`PASS_FORMULA_AND_TRANSITION_PORTABILITY`. The paper result remains
`BLOCKED_MISSING_AUTHOR_CODE_RAW_SEEDS_AND_COMPLETE_SEMANTICS`, and
`PASS_FULL` remains forbidden even if H0-H5 formula checks pass.
