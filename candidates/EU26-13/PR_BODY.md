## Summary

This PR adds the preregistered, candidate-local EU26-13 verification for de
Nobel et al., *Avoiding Redundant Restarts in Multimodal Global Optimization*
(PPSN 2024, DOI `10.1007/978-3-031-70068-2_17`).

It authenticates one exact `D=20` raw JSON endpoint from Zenodo record
`10997200` through seven bounded HTTP ranges (611,381 bytes total), rather
than downloading the 17,573,142,426-byte outer archive. The verified first
run reports seed 0, 2,173 evaluations, and exact best objective token
`7.379046076174201e-09`.

## Claim boundary

- Candidate status: `TARGETED_ARTIFACT_REPLAY_ONLY`.
- Paper mapping: `PAPER_CONTEXT_ONLY`.
- Source-native status: `BLOCKED_UNPINNED_TOOLCHAIN_DEPS`.
- `PASS_FULL`, literal-paper, public-Git-equivalence, historical-environment,
  and full-archive-MD5 claims remain forbidden.
- No source-native CMA-ES extension was executed.

The preregistration was committed first as
`918dcad2b3f530595294e1a3e679b3e6e950a060`, based on
`eeac926e15107503377cbe09cdc8e830a6607fa5`. Initial implementation is
`0ae6701a14b275b49e68512bb2873103954724d9`; corrective fail-closed
hardening follows in a third, separate commit.

## What is included

- fail-closed Zenodo-only HTTP access with initial/final URL validation and
  exact `206 Content-Range` framing;
- component-wise no-follow retained-file access with regular-file, inode,
  parent re-resolution, and write-once output binding;
- bounded ZIP64, nested-ZIP, central/local-header, path, duplicate, method,
  flag, size, hash, deflate, and CRC validation;
- exact IOH 0.3.15 schema/order/run/decimal validation;
- source-snapshot identity and semantic audit without assigning a Git commit;
- independent Python and GNU Octave controls for seed order, BIPOP restarts,
  repelling radius/shrinkage, CSA, and hill-valley semantics;
- write-once attestations bound to an implementation manifest;
- candidate-only GitHub Actions workflow.

## Verification

- Python: 117/117 tests pass, including 99 negative mutation tests and zero
  skips, expected failures, or unexpected successes.
- GNU Octave 8.4.0: 9/9 independent checks pass.
- Live Zenodo replay: all A1–A10 gates pass; A11 remains
  `BLOCKED_UNPINNED_TOOLCHAIN_DEPS`.
- Retained report SHA-256:
  `0a1ea00cd318cac3d74bebe535f3ef02b255989d0c9a4b1ceac07495c645e549`.
- Python attestation SHA-256:
  `a749aea85c2ac5103248f9bd33576dc98121a38b1292a06e1de62daf41d8bfe6`.
- Octave attestation SHA-256:
  `cc8fb17b0b45d8d4db4da64db19adb5103bc85ac33607e09ef49f33a1982d9df`.

## Reviewer checklist

- [ ] Confirm the preregistration commit precedes all implementation files.
- [ ] Confirm the complete large-file MD5 remains Zenodo-declared only.
- [ ] Confirm exactly seven range requests and 611,381 total ranged bytes.
- [ ] Confirm no Git revision is assigned to the Zenodo source snapshot.
- [ ] Confirm the result never upgrades the paper or source-native gates.
- [ ] Run the candidate-local workflow and compare retained hashes.
