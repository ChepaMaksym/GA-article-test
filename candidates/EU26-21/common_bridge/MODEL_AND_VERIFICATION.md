# Mathematical model, verification and thesis claims

The bridge studies transfer of an established self-adjusting search mechanism,
not invention of `(1+(lambda,lambda))` GA. Its comparator is harmonized CHC
feature-mask search, not the complete printed CHC-QX instance-selection and
evolution-control pipeline. Sources: [Hevia Fajardo and Sudholt (2022)](https://mhevia.com/assets/pdf/journal_oplclga.pdf)
and [Altarabichi et al. (2023)](https://arxiv.org/pdf/2404.03996).

## Model and elementary invariants

For `z in {0,1}^40`, nonempty-mask fitness is the lexicographic pair
`(WBA_validation(h_z), -sum(z)/40)`; the frozen empty-mask shortcut is `(0,-1)`.
The search classifier is fitted on the common active training sample. The
terminal classifier is refitted on the internal training partition after the
validation-only terminal mask and both traces are frozen.

Lambda state is `(parent, parent_fitness, lambda, call_counter, RNG_state)`.
CHC state includes population, distance, mask history, counter and RNG state.
Fixed inputs and isolated RNG streams determine the transitions.

With `F=1.5`, a strict success sets `lambda'=max(1,lambda/F)`; otherwise
`lambda'=min(40,lambda*F^(1/4))`. Induction from `lambda=1` gives bounds `[1,40]`,
so `p=lambda/40` and `c=1/lambda` remain valid probabilities. Mutation flips
distinct positions; crossover chooses parental alleles, preserving binary
masks. The common terminal best only changes on strict lexicographic
improvement, so its primary best-so-far trajectory cannot decrease. Each
objective invocation has one ledger record; guarded batches and the frozen
terminal-prefix rules prevent exceeding 400 calls.

Own algebraic interpretation, conditional on a state whose updates are not
clipped: with strict-success probability `s`, expected log-lambda increment is
`(1-5s)*log(F)/4`. Zero drift is at `s=1/5`. This is a feedback interpretation,
not a novel convergence theorem or a guarantee for feature-selection fitness.
No lower bound on improvement probabilities or preserved surrogate ranking is
established for the new landscape. Thus source runtime theorems are not
asserted to transfer.

## Claim-to-check map

| Claim | Implementation boundary | CI evidence |
| --- | --- | --- |
| Binary masks and exact call unit | `search.BudgetLedger` | Reject coercible nonintegers; duplicates still count; cap and earliest tie tests |
| Lambda control and valid offspring | `search.run_lambda_no_reset` | Independent transcript update, parent, mutant-distance, crossover-allele and paired-tail checks |
| Harmonized CHC semantics | `search.run_harmonized_chc` | Pinned-source HUX/RNG comparison; stable population, history, distance and partial-prefix checks |
| No test-driven mask choice | `run_seed` and validation-only objective | Poisoned test access; both trace files exist before terminal evaluation; changed test inputs cannot affect objective |
| Reproducible terminal models | `model_evidence.evaluate_and_persist` | Exact preprocessing/prediction/probability round trip on a non-test training probe |
| Complete authenticated observations | runner, source ledger and aggregator | 30 pairs, seven files each, hashes, schema, attempt identity, missing/duplicate/corrupt inputs |
| Statistical decision correctness | `aggregate` | Independent nonconstant BCa reference, strict gate boundaries, negative-result CLI success |

## Scientific interpretation remains conditional

Quality requires the lower paired 95% BCa endpoint above `-0.001`; only then may
a positive lower AUC endpoint support efficiency. Failure of the quality gate
blocks a joint efficiency or subset-size advantage. AUC is mean best-so-far
validation WBA per logical call, not ROC-AUC or elapsed time.

Thirty seeds on Census with one fixed official test file provide conditional
seed/split replication, not cross-dataset validation. Bootstrap replication
does not increase the number of seed pairs. Without a fixed-lambda ablation,
the two-arm experiment does not isolate adaptation itself as the causal factor.
Reset is disabled; CHC cataclysmic restarts are not lambda resets.

The thesis should report proposed integration, verified implementation,
prespecified tests, all outcomes, uncertainty and limitations. Historical
source-compatible and corrected evidence remains separate. A negative or null
bridge outcome is reportable, not grounds to alter thresholds. Final tables,
figures, run URLs, artifact IDs and digests are added only after the full
scientific campaign and authenticated reaggregation have completed.

## Independent theoretical review clarifications (2026-09-08)

These are interpretive clarifications, not changes to the frozen protocol.
The canonical source Algorithm 1 starts with one uniformly sampled bit string.
The bridge instead evaluates 50 shared, nonempty source-density masks and
selects the lambda parent uniformly among their lexicographic best masks.
This initialization, the weighted lexicographic objective, the 400-call cap,
the truncated last paired batch and the best-queried terminal mask are explicit
adaptations. The complete optimizer is not a literal source Algorithm 1 replay.
See [Hevia Fajardo and Sudholt, Section 2.1](https://mhevia.com/assets/pdf/journal_oplclga.pdf).

The protocol's phrase `full printed CHC-QX/Algorithm 1 profile` has an imprecise
algorithm-number reference: the applied paper's Algorithm 1 concerns active
sampling; its complete CHC-QX pipeline is Algorithm 3. This does not change the
comparator definition or execution. Frozen protocol bytes are retained and the
reference is clarified here instead. See [Altarabichi et al., Section 4.2 and
Algorithms 1-3](https://arxiv.org/pdf/2404.03996).

Own algebraic observation: the shared first 50 calls imply, for every pair,
`Delta AUC(1..400) = (350/400) * Delta AUC(51..400)`.
Subtract the two 400-term sums: their first 50 terms cancel and the remaining
350-term sum is exactly 350 times the tail mean. Thus the tail contrast merely
rescales the primary contrast by `400/350`; it is not independent corroboration.
In exact arithmetic, paired medians and BCa endpoints with identical resampling
indices scale by the same positive factor. The confirmatory gate still uses
only the frozen full-horizon AUC. Quality non-inferiority concerns the median
paired difference over the specified seed/split distribution, not every seed.
