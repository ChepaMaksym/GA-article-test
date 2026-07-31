# Final failure record — USA-001 Johnson–Carnegie adaptive GA

Date: 2026-07-30  
DOI: [10.3390/a15020045](https://doi.org/10.3390/a15020045)  
Country/category: United States / USA  
Implementation: MATLAB R2026a Update 4  
Status: primary failed; Q1 failed; Q2 failed; Q3 failed; diagnostic limit exhausted

## Frozen primary result

The paper-faithful ten-run profile used the preregistered instances,
initial populations, and three-stream seed ledger. No run was replaced,
retried, screened, or stopped early.

| Gate | Published target | Reproduced | Result |
|---|---:|---:|---|
| P1 perfect by generation 1000 | 0.9 | 0.9 (9/10) | PASS |
| P2 perfect by generation 2000 | 1.0 | 0.9 (9/10) | FAIL |
| P3 median reported iteration | 1000 | 1000 | PASS |
| P4 all terminal objectives zero | 10/10 | 9/10 | FAIL |

Run 8 remained nonzero through the complete 100000-generation budget:

- instance/population/operator seeds:
  `202204508 / 202214508 / 202224508`;
- final paper objective: `0.0546230331460566`;
- final release-scale objective: `0.000546230331460566`;
- final recovery RMSE: `0.140724169457518`;
- objective evaluations: `14,314,290`;
- termination: `max_generations`.

A read-only recomputation localized the complete remaining objective to
one observation: agent 18 at time 2 was predicted in ordinal bin 1 while
the observed value was in bin 2. The continuous deviation and objective
contribution were both `0.0546230331460566`.

The reproduced recovery mean was `0.153522060578515` (sample SD
`0.031504301881188`) versus the author-row mean
`0.134743212907013` and author-row 95% t interval
`[0.116338050296472, 0.153148375517555]`. It is narrowly outside that
interval and has 13.94% relative error, so it also fails the user-wide
numeric matching rule.

## Provenance

The live fail-closed audit recomputed all ten source, instance,
configuration, implementation, RNG-chain, result, terminal chromosome,
objective, recovery, and CSV/cache relationships successfully.

Primary provenance token:
`8cd76dbad8b9bc11a570d0c77be1bc9d063fd7caee8bf395350fc11a36671bdb`

| Artifact | SHA-256 |
|---|---|
| `outputs/primary/Runs_Raw.csv` | `027a97f895820539578675b17ac9ffa132d78a8bb654f5dbdf145038a2be1697` |
| `outputs/primary/Generation_Log.csv` | `cc2dd4a828b977e0e83a9d088ca29c13d64f863b3f3cbec5e43a17a0fe38db97` |
| `outputs/primary/Adaptation_Events.csv` | `564493e047bd4f7ed336311f4de0c225adefd7f2a52a06cdb69bb056aa8085db` |
| `outputs/verification/Published_vs_Reproduced.csv` | `dfc0a603f4e3553bca77b30d47cfca64d74bbdc48170d0bd173c7c116af5778e` |
| `outputs/verification/primary_verification.mat` | `d156cd3bc86261fcc0070a4a505f9035c943b14277f97df4c4d03f43417bfbb6` |

## Diagnostic protocol

At most three source-grounded profiles are permitted, using the same
instances, populations, seeds, run count, and maximum budget:

1. Q1: released strict stagnation thresholds (`counter > horizon`);
2. Q2: released selection/reintroduction/blending/survival semantics with
   the paper objective and completed-generation checkpoint;
3. Q3: combined released-code compatibility including pre-variation
   stopping and normalized objective, excluding the unsafe whole-row
   mutation defect.

These profiles may explain the failure but cannot be relabeled as the
paper-faithful primary result.

## Diagnostic Q1 — strict stagnation horizons

Q1 changed only the released-code threshold convention from
`counter >= horizon` to `counter > horizon` for control adaptation and
elite reintroduction. The instances, initial populations, seeds, paper
objective, safe mutation, structural operators, completed-generation
checkpoint, ten-run design, and 100000-generation budget remained frozen.

Before execution, an independent equivalence audit found and corrected
diagnostic-only evaluation overcounting and cache-integrity gaps. Seven
pre-hardening partial caches were archived as explicitly unusable. The
hardened implementation passed 46/46 outcome-free tests, including exact
Q1-versus-primary trajectory/RNG/evaluation-count equivalence before the
threshold, intended-only threshold divergence, full-payload hashing, a
coordinated early-stop forgery rejection, and Q3 terminal invariants.
The live primary provenance token remained unchanged.

| Gate | Published target | Q1 result | Result |
|---|---:|---:|---|
| P1 perfect by generation 1000 | 0.9 | 0.9 (9/10) | PASS |
| P2 perfect by generation 2000 | 1.0 | 0.9 (9/10) | FAIL |
| P3 median reported iteration | 1000 | 1000 | PASS |
| P4 mean final paper objective | 0 | `0.00554888537341592` | FAIL |

Run 8 again exhausted the complete budget:

- final paper objective: `0.0554888537341592`;
- final recovery RMSE: `0.140208152237321`;
- objective evaluations: `14,311,777`;
- termination: `diagnostic_max_generations`;
- complete remaining objective: agent 18, time 2, observed bin 2,
  predicted bin 1, continuous deviation and contribution both
  `0.0554888537341592`.

Thus Q1 preserved the same single-cell failure mechanism and made the
run-8 objective 1.5851% larger than the primary value. The Q1 recovery
mean was `0.155466040934392`, which is above the author-row 95% interval
by `0.00231766541683701` and has 15.3795% relative error. Strict horizon
semantics therefore do not explain either the P2/P4 failure or the
user-wide recovery mismatch.

Q2 is evidence-led because the released structural operators alter
selection, reintroduction indexing, blending, and survival—the remaining
source-grounded mechanisms that can directly change exploration of the
same unresolved cell. Q1 is diagnostic-only and does not change the
paper-faithful primary conclusion.

| Q1 artifact | SHA-256 |
|---|---|
| `Runs_Raw_DIAGNOSTIC_ONLY.csv` | `47e10c16b29285e7d4384f8946078650a73c57d46eac8dfcede8e89b4ed324eb` |
| `Generation_Log_DIAGNOSTIC_ONLY.csv` | `249452559d83e5912be6d82258f0d3aa6c9f8eb9ae26cefd935b4f88504e50ab` |
| `Events_DIAGNOSTIC_ONLY.csv` | `819e6bd35e7c87183c7a2a0a9d1fcf296f206ea4ff1efdbd7653d829722d23c5` |
| `Published_vs_Diagnostic_Reproduced_DIAGNOSTIC_ONLY.csv` | `343bef84bc3a57b28669d368699ceabce3c8d3d976603b9ddae84dd997491c44` |
| `Summary_DIAGNOSTIC_ONLY.csv` | `76f60f6b28376b7e115e5c1117a17f15eeec4e7dead98ae8e7343fb0f9cc5e2e` |
| `run_08.mat` | `c9dd6986d8880df768de00802fb1bb5e2ab76eb042f4e522b21c361424625248` |
| `Diagnostic_Provenance.mat` | `a9fcff7a0074224d4ea1b1584022df70b92ef1055da55b367c43a111e1d39b93` |

## Diagnostic Q2 — released structural operators

Q2 retained the paper objective, `>=` horizon semantics, safe constrained
mutation, and completed-generation checkpoint, but used the released
hard-coded-index-5 selection, stale pre-reorder reintroduction index,
sequential-alias blending, and offspring-wins-tie survival. All seeds,
instances, initial populations, run counts, and generation budgets were
identical to the primary and Q1.

| Gate | Published target | Q2 result | Result |
|---|---:|---:|---|
| P1 perfect by generation 1000 | 0.9 | 0.9 (9/10) | PASS |
| P2 perfect by generation 2000 | 1.0 | 0.9 (9/10) | FAIL |
| P3 median reported iteration | 1000 | 1000 | PASS |
| P4 mean final paper objective | 0 | `0.00500823612629955` | FAIL |

Run 8 again exhausted the full budget:

- final paper objective: `0.0500823612629955`;
- final recovery RMSE: `0.131904286469602`;
- objective evaluations: `14,531,174`;
- termination: `diagnostic_max_generations`;
- complete remaining objective: agent 18, time 2, observed bin 2,
  predicted bin 1, continuous deviation and contribution both
  `0.0500823612629955`.

The released structural operators reduced the run-8 objective by 8.3127%
relative to the primary, but did not remove the same single-cell failure.
The ten-run recovery mean improved to `0.132874920666047`, only 1.3866%
from the author mean and inside the author interval; the numeric recovery
gate therefore passes in isolation. The required exact-fit P2/P4 gates
still fail, so Q2 is not a successful reproduction.

Q3 remains evidence-led because it tests the source-released driver as a
combined interaction: Q2 showed that released structural operators move
the residual materially, while Q1 showed that strict horizons alone do
not solve it. Q3 combines those paths with the released normalized
objective and pre-variation checkpoint, still excluding the unsafe
whole-row mutation defect. It remains diagnostic-only and cannot alter
the primary conclusion.

| Q2 artifact | SHA-256 |
|---|---|
| `Runs_Raw_DIAGNOSTIC_ONLY.csv` | `521fb27a9eda91b230a2aff8f9fcd12ffe32a503b743481cee20fd961a423e87` |
| `Generation_Log_DIAGNOSTIC_ONLY.csv` | `eb24e6bd268e2254f4da0f306b9a29b1e4f969b0c8d298b02b674879d4db8286` |
| `Events_DIAGNOSTIC_ONLY.csv` | `7de4b50ea7ba1006e764634758e20d889f57fc3e6f943c71cf2a50537714f8a3` |
| `Published_vs_Diagnostic_Reproduced_DIAGNOSTIC_ONLY.csv` | `72582156c738f717591bd664061a7ccdf54127d148c310d58aad31711e7d4062` |
| `Summary_DIAGNOSTIC_ONLY.csv` | `87aa435cb222e60c5fe0a958f3c211d81ed5e6a2b4aec4dcc9225a8445b92290` |
| `run_08.mat` | `97f1c710430333eaac6138196f6944fa428659d327a3273cfb1c534fb234a726` |
| `Diagnostic_Provenance.mat` | `6f850ba4b1f750fe225dccc4e73afd31a2b4743b8c678715f141fd19d98d760e` |

## Diagnostic Q3 — combined released-driver compatibility

Q3 combined the released structural operators with strict `>` horizon
semantics, the released normalized objective, and the released
pre-variation checkpoint. It retained the safe constrained Gaussian
mutation because the released whole-row mutation can violate the
chromosome's structural zeros and row-sum constraints. The frozen
instances, initial populations, seeds, ten-run design, and
100000-generation ceiling were unchanged.

The hardened diagnostic suite again passed 46/46 tests before the sealed
run was accepted. Its cache validator pinned every profile field,
recomputed evaluation accounting and terminal invariants, verified the
full-payload signatures, and rejected early-stop or truncation
substitutions. The suite's printed `Primary published-result verification:
PASS` line comes from a synthetic pass-logic fixture; it is not the real
primary or Q3 outcome.

| Gate | Published target | Q3 result | Result |
|---|---:|---:|---|
| P1 perfect by generation 1000 | 0.9 | 0.9 (9/10) | PASS |
| P2 perfect by generation 2000 | 1.0 | 0.9 (9/10) | FAIL |
| P3 median reported iteration | 1000 | 1000 | PASS |
| P4 mean final paper objective | 0 | `0.00500589166342626` | FAIL |

Run 8 again exhausted the complete budget:

- final paper objective: `0.0500589166342626`;
- final normalized/release-scale objective: `0.000500589166342626`;
- final recovery RMSE: `0.133550628010981`;
- objective evaluations: `14,523,557`;
- termination: `diagnostic_max_generations`.

A read-only recomputation from the sealed terminal chromosome and frozen
instance reproduced the objective as `0.050058916634262582`. Exactly one
cell remained nonzero: agent 18 at time 2, observed bin 2, predicted bin
1. The predicted continuous value was `0.099941083365737413` versus the
observed-bin midpoint `0.14999999999999999`; continuous deviation and
objective contribution were both `0.050058916634262582`.

The Q3 run-8 objective is 8.3557% lower than the primary value but still
nonzero. Its ten-run recovery mean was `0.135384551339175` (sample SD
`0.0296102090097873`; reproduced 95% t interval
`[0.114202683837324, 0.156566418841025]`), only 0.4760% from the author
mean and inside the author 95% interval. As in Q2, recovery therefore
matches in isolation, but the required P2 and P4 published endpoints
fail.

Embedded Q3 provenance signature (stored and independently recomputed):
`b0f8036760fb563439f54c9c2ac4c7d7dba680d2b5f673cfbc87fabb6c9fdcb7`.

| Q3 artifact | SHA-256 |
|---|---|
| `Runs_Raw_DIAGNOSTIC_ONLY.csv` | `3ea2258a789b3c028267599abf423f98b9b99f5047562c903f29cf893e86d729` |
| `Generation_Log_DIAGNOSTIC_ONLY.csv` | `51e91f9311559dd05eee6e5d1d00cf2094d4f6a46b130aecc3c9bb5dbea03f3d` |
| `Events_DIAGNOSTIC_ONLY.csv` | `b3e15566ecef233ab6e8314769f4d410ebbd8bf1c0b1e5a79adfd8aea6064038` |
| `Published_vs_Diagnostic_Reproduced_DIAGNOSTIC_ONLY.csv` | `0fa5c0cbb9220a6641d2ab18783c582a9f47e0adc53f34f24a11ebb44a13ab7a` |
| `Summary_DIAGNOSTIC_ONLY.csv` | `6f3bfa5bedae293a5c1240bcfb4fbc3ccdbced717b58922e59b20dfbd217018d` |
| `run_08.mat` | `6107c78e77652dac092aa2a39b369b9b6054edb5675216af1ae2fc164112a0f5` |
| `Diagnostic_Provenance.mat` | `a4744eef668c60de0b208815f3a1a1d774ac4e1c84605f69e3c245441b6c3937` |

## Final conclusion

The paper-faithful primary and all three permitted, source-grounded
diagnostics failed the same P2/P4 endpoints. Q1 preserved the miss; Q2
and Q3 brought recovery statistics inside the author interval but left
the same run-8 observation unresolved through the full budget. No
diagnostic may replace the primary result, and the three-cycle limit is
now exhausted.

USA-001 is therefore a documented failed reproduction, not a successful
candidate. The fixed-GA comparison, ablations, success workbook, and
reproducibility package were not run or generated because their
preregistered entry condition—successful published-result
verification—was never met.

## Cleanup and preserved audit evidence

After this failure was written to the general and detailed external
logs, the exact failed-candidate directory
`candidate_02_degroot_adaptive_ga` was resolved as a direct child of the
workspace and deleted. The operation removed 202 files totaling
457181299 bytes; a postcondition check confirmed that the directory no
longer exists.

A compact external audit bundle remains in
`failure_logs/USA-001_evidence`. Its full pre-deletion candidate inventory
has SHA-256
`2add8ec03e683b3091a0151840adcd0ee39b3cb6749f07a3745a3503a645c1a0`.
The final 25-entry compact-evidence manifest has SHA-256
`1ded599074afc64d21a5092072f4a40633d1e3bc192d3fa44e40442d8c1f3b5e`.
