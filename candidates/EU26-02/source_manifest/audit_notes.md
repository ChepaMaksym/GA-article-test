# EU26-02 source audit

Audit date: 2026-08-07. No formal solver run was used to choose or alter the
contract.

## Eligibility

- 2024, EU affiliation (Université d'Angers, France).
- Direct graph-coloring optimization, not an inverse or calibration problem.
- The Table 2 graphs have 121–4000 vertex assignments, all above the required
  dimension threshold.
- AHEAD selects one of six GA action pairs formed by three GPX crossover
  variants and two local searches. Deleter removes actions during a run.
- Code and instance repositories are MIT licensed and pinned to immutable
  commits.

The candidate remains `conditional_noneligible`: G5 and G8–G10 are unresolved
because the paper, frozen code, archived execution and build environment do
not define one common reproducible protocol.

## Exact Deleter semantics recovered from source

The old registry description of a “10% exploration floor” was incorrect; that
floor belongs to other policies. At the frozen revision Deleter does this:

1. Start with action indices `0..5` in an ordered surviving set.
2. Select each of two child actions uniformly and independently from that set.
3. Apply its crossover and local search, then update the action's lifetime
   arithmetic mean using the resulting child penalty. Lower is better.
4. On source turn 30 and then every fifth turn, delete the surviving action
   with the largest lifetime mean. No deletion occurs before turn 30 or after
   only one action remains.
5. A tie retains the first current worst encountered, so the lowest surviving
   action index is deleted.
6. Insertion occurs after the adaptive update; the turn increments when the
   turn-by-turn line is written.

`memory_size=50` and `coeff_exploi_explo=1` are present in the shared adaptive
configuration but do not affect Deleter's lifetime-mean deletion rule.

This is source-faithful, not paper-faithful. Section 2.5 says that policy
updates use a queue of the last 50 negative-fitness rewards, and the six-step
paper pipeline performs insertion before policy update. The code gives
Deleter a positive-penalty lifetime mean, adds a 30-turn warm-up not stated in
the paper, and updates the helper before insertion. The old G5 `pass` label was
therefore withdrawn.

## Budget/provenance conflict

Section 3.1 states 20 independent GCP runs of one hour with two CPUs. In the
same official revision:

- `jobs_generator.py` sets `time_limit = 3600 * 3`;
- every inspected Deleter archive header records `time_limit=10800`;
- `xlsx_generator.py` has `data.time <= 3600` commented out;
- `one_job.py` can retry a failed target at a higher color count in a separate
  job, again with the configured per-attempt budget.

Despite its filename containing `1h`, the 64,960,102-byte archive is therefore
not a one-hour artifact. Applying the repository's unfiltered aggregation
reproduces all 31 published AHEAD+Deleter Table 2 rows. This identifies the
table's artifact provenance but does not reconcile it with the paper's stated
protocol.

An independent read-only inventory audit found exactly 1,143 root result CSVs
and 1,143 turn-by-turn CSVs.
The root set consists of 620 accepted legal files (20 × 31) plus 523 failed
lower-target attempts. Literal `restart` sentinels occur on 7,450 lines in 298
root files and zero turn-by-turn files, but no matching output path exists in
the frozen source. The formal root validator reports the 298/7,450 inventory;
the candidate separately hash-pins and parses the selected turn-by-turn
witness rather than claiming a full TBT-content gate. Its comment metadata
header is shifted by a missing `objective` value. These facts are evidence
that the archive was not emitted byte-for-byte by the pinned revision. The
result `time` is the best-found time stored in the final row, not terminal
process runtime.

The table pipeline rounds mean-best times to one decimal and converts the
positive result to an integer. For example, the exact `r250.5` archive mean is
`549.8` seconds while Table 2 shows `549`. The exact decimal remains evidence;
all 31 rows make `int(round(raw_mean, 1))` equal direct positive truncation.

## Seed and dimension hazards

The CLI seeds `0..19` are present, but OpenMP regions access the global
`std::mt19937` and `Solution::counter` without synchronization. A seed does not
guarantee a trajectory-identical native replay across thread schedules.

The label `r250.5` is not the solver dimension. Its original file has 250
vertices, repository metadata reports 246 after one reduction, and the actual
frozen GCP input `reduced_gcp/r250.5.col` has 235 vertices and 13,968 edges.
Archived solution vectors have length 235. Any native smoke must freeze the
235-variable reduced input by hash.

The source-backed smoke witness is `r250.5`, seed 15, target 66. Its legal
result is found at source turn 32/time 33. At turn 30 the selected pair IDs are
`[0,5]`, child penalties are `[2,2]`, post-update counts are
`[16,9,10,10,11,6]`, and operator 1 is deleted. This archived transition is
part of the shared Python/MATLAB fixture; it is not treated as evidence that
the pinned source can replay the entire trajectory.

## Build audit

The source requests C++17, gcc/g++ 11+ (paper: g++ 12.1), OpenMP, CMake 3.14+,
LibTorch CPU 1.13.0, cxxopts 2.2.1, fmt 9.0.0 and nlohmann/json 3.11.2. The CMake
file pins the latter packages, and the instance submodule is pinned. The
Dockerfile provides Ubuntu 22.04 build tools but does not itself install
LibTorch, so it is not a complete environment lock. A successful build of the
frozen source would establish executability only, not identity with the
archive-producing executable.

Native builds and downloads must occur in a disposable directory because the
upstream build script removes `build_release`. A native micro-run is a separate
verification gate; absence of that environment evidence cannot be converted
into a paper-level pass.

## Authenticated-byte custody review

A final adversarial review found that the first validator revision hashed the
archive path and then reopened it for parsing. Deterministic atomic-replacement
probes demonstrated that this could bind a pinned digest to bytes other than
those consumed by the parser. Amendment 004 supersedes every archive, witness,
hardware and H5 report from that revision.

The remediated path copies one retained archive descriptor into a private
authenticated snapshot, decompresses and parses only bytes derived from that
snapshot, and verifies the same file objects again after use. The selected
graph is read and reauthenticated through one retained descriptor. Hardware
workers inherit immutable `(member_name, bytes)` payloads and never open an
archive path; the pinned member-manifest digest, count and byte summary are
retained and compared across profiles. This closes the demonstrated input-path
race without changing a scientific target or clearing the mandatory
paper-level block.
