# Amendment 002 — authenticated exact-object output binding

Recorded: 2026-08-07, after the outcome-blind v1 contract and after the
formula fixture were fixed, but before formal Work4/Work8/GitHub4 profiles.

This amendment binds deterministic outputs of objects already frozen by hash.
It does not select a new cell, change an endpoint, enlarge a tolerance or
authorize a stochastic outcome run.

The exact authenticated Zenodo member yields 100/100 completion values with:

- minimum `30344`, maximum `131875`, sum `6162378`;
- exact arithmetic mean `61623.78`;
- exact population variance (`ddof=0`) `327085104.6716`;
- completion-vector SHA-256 under the candidate canonical domain
  `d75a9f7f9b2d3ba27adcdcc2905ac4267b58948db69555907b987c2666c2b417`;
- completion-statistics SHA-256
  `937f5d3a538a90eceda702d08bfe0c0098b7b2de22cd713685d85df6af409652`.

The mean rounds to the preregistered published `61624`, and the population
variance rounds to four significant digits as the preregistered published
`3.271e+08`.

The fixed-tape file SHA-256 is
`28e37d5607714cfd847dbd1c132b159f6db92f097f7ecb3c81d27da77e769d63`.
Its canonical independent-formula result digest is
`fc6d078b10dac0968d6ab8ca052828017e58e62e971f3f838bb80cffb7580034`.
All formal digest bindings are recorded in
`config/hardware_expected_digests.json`.

These exact values may establish `PASS_ARCHIVE_EXACT` and deterministic
formula/portability gates only. They do not resolve the literal Algorithm 2
4/6 versus prose/source 5/5 split, unspecified paper tie behavior, missing
100-seed ledger, unavailable dependency revision, absent code license or
source-native replay. The paper-level status remains
`BLOCKED_SOURCE_NATIVE_REPLAY`, eligibility remains
`conditional_noneligible`, and `PASS_FULL` remains forbidden.
