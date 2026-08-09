# EU26-13 retained verification evidence

Candidate-local JSON attestations are generated write-once after their
respective gates pass:

- `python-test-attestation.json` records the offline unit/mutation suite;
- `octave-controls.json` records independent GNU Octave controls;
- `verification-report.json` records the seven authenticated Zenodo range
  requests and the exact raw endpoint.

These files can support only
`TARGETED_ARTIFACT_REPLAY_VERIFIED_WITH_SOURCE_NATIVE_BLOCKED`. They cannot
clear `PAPER_CONTEXT_ONLY`, establish `PASS_FULL`, recompute the complete
17.6-GB archive MD5, map the code snapshot to a Git revision, or execute the
unfrozen source-native dependency environment.

Retained identities from the completed local run:

| File | Bytes | SHA-256 |
|---|---:|---|
| `python-test-attestation.json` | 378 | `80df71056f0735f88bbc656e2a7cbe52d0760bbe5062c6a06dea7681c5c3b5eb` |
| `octave-controls.json` | 937 | `cc8fb17b0b45d8d4db4da64db19adb5103bc85ac33607e09ef49f33a1982d9df` |
| `verification-report.json` | 8,054 | `c852b183712a543bbb8a31097b9026fe5edb6459237b6a460753d214fe57a7fb` |

The final report contains exactly seven range requests totaling 611,381
bytes. The selected endpoint is `/scenarios/3/runs/0`: instance 1, inferred
seed 0, 2,173 evaluations, best at evaluation 2,173, exact objective token
`7.379046076174201e-09`, and 20 coordinates.
