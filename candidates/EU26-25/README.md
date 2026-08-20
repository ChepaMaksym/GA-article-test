# EU26-25 - PyVRP X-n101-k25 OLD-first candidate

## Current status

`PREREGISTERED_OLD_ONLY / HYBRID_BLOCKED_BY_OLD`

This branch starts a new candidate cycle directly from the verified PR #8 base.
No numerical row, graph, thesis statement, implementation, or conclusion from
PR #19 is used as evidence.

## Reference study and immutable source

- Niels A. Wouda, Leon Lan, Wouter Kool,
  *PyVRP: a high-performance VRP solver package*.
- INFORMS Journal on Computing, 2024.
- Paper DOI: `10.1287/ijoc.2023.0055`.
- Computational artifact DOI: `10.1287/ijoc.2023.0055.cd`.
- Frozen research snapshot: `INFORMSJoC/2023.0055` commit
  `7ed6a24a0f4275da53c68e3db9ef5af197017111`.
- PyVRP release: `v0.5.0`; version commit
  `d4799a810a8cf7d16ea2c8871204bdfb3a896d06`.
- Source and artifact license: MIT.

## Applied benchmark

The frozen primary endpoint is CVRPLIB instance `X-n101-k25` from
`PyVRP/Instances` commit
`7474b068a8effa7f39448b241314b615c9271525`.

```text
instance Git blob: ad4539d0b70cd60178601d7b3515d08945fdb3ad
customers: 100
vehicle capacity: 206
best known solution / paper table value: 27591
paper runs: 10
paper mean: 27591.0
paper standard deviation: 0.0
```

The instance contains 100 customer decisions, so it exceeds the project
threshold of 15 without counting implementation parameters as physical model
dimensions.

## OLD adaptive mechanism

PyVRP 0.5.0 is a hybrid genetic search with adaptive feasibility penalties.
For a constraint penalty `omega`, feasible fraction `f`, target `xi=0.43`,
tolerance `delta=0.05`, increase factor `1.25`, and decrease factor `0.85`,
the released manager applies every 100 registrations:

```text
if f < xi - delta:
    omega_next = clip(1.25 * omega)
elif f > xi + delta:
    omega_next = clip(0.85 * omega)
else:
    omega_next = omega
```

This adaptive locus is explicitly a constraint-penalty controller. It is not
misrepresented as adaptive crossover or mutation.

The frozen paper configuration is copied byte-for-byte from
`configs/initial_submission_ijoc_cvrp.toml`. Its main GA values are population
25, generation size 40, 4 elites, repair probability 0.50, repair booster 12,
20,000 iterations without improvement before restart, and the published local
search operator set including SWAP*.

## Reproduction profile

The paper used a CPU-scaled runtime. That is retained as historical context but
is not portable across GitHub runners. The primary executable OLD gate is a
separately named iteration-normalised profile:

```text
profile: old_iteration_120k
seeds: 1..10
maximum iterations per seed: 120000
rounding: dimacs
instance format: vrplib
source: exact research snapshot / PyVRP 0.5.0
```

Instrumentation changes only `collect_statistics` from false to true. It adds
no random draw and does not change selection, crossover, local search,
penalties, repair, restart, or replacement.

The claim ceiling is therefore
`PASS_SOURCE_NATIVE_ITERATION_NORMALISED_ENDPOINT`, not literal historical CPU
runtime equivalence.

## OLD-first gates

HYBRID is forbidden until all of these pass:

1. paper, artifact, source, config, license and instance identities;
2. fixed-tape penalty update formula and boundaries;
3. source-native installation of the frozen artifact on Python 3.11;
4. 10/10 complete feasible seed rows;
5. 10/10 final costs equal 27591 within 120,000 iterations;
6. recomputed mean 27591.0 and population standard deviation 0.0;
7. exact seed and instance custody;
8. deterministic repeat and 1/2/4-worker batch equivalence;
9. portability smoke on Linux, macOS and Windows without promoting wall-clock
   time to a scientific endpoint.

The complete outcome-blind acceptance rule is in
`preregistration/PROTOCOL.md` and `preregistration/protocol.json`.

## Planned HYBRID after OLD PASS

After OLD passes, the instance, cost function, population, initial solutions,
seed ledger, local-search operators, penalty manager and evaluation/iteration
budget remain fixed. The only candidate intervention is dynamic repair
intensification controlled by the independently verified PR #8 reset
self-adjusting state:

```text
p_g = lambda_g / n
c_g = 1 / lambda_g
```

where `lambda` shrinks after strict improvement, grows after failure, and
resets after failure at the cap. `lambda` will control the probability of the
existing repair/intensification call; it will not alter route feasibility,
objective cost, crossover implementation or local-search operators.

Exploration must use a separate seed set. Only one frozen HYBRID variant may be
run on untouched confirmatory seeds paired with OLD.

## Claim boundary

At the present stage this branch claims only candidate selection,
preregistration and source/formula authentication. It does not claim OLD
reproduction, HYBRID improvement, fewer iterations, faster wall clock time,
scientific novelty, or a completed master thesis.
