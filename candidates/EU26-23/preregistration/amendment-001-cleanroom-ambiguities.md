# Amendment 001 - clean-room ambiguities frozen before implementation

Date: 2026-08-19

Parent preregistration commit: `415ae350513b4632bf0b54ffa01d70e273584b3c`

This amendment is outcome-blind. No EU26-23 optimizer, stochastic result, selected solution, final fitness or convergence trace existed when it was written.

## Why an amendment is required

The paper provides the algorithm order, formulas, operator descriptions, the exact public `singlecenter-63-n20` instance and a literal 30-trial mean for configuration 7. It does not publish the Visual Studio C++ source, original RNG seeds/states or a complete machine-readable run ledger. Three clean-room details therefore require explicit interpretation before code is written.

## A1 - initial drone-count rounding

The prose states that drone-node selection is repeated `initialDrone% * N` times, while Algorithm 4 contains a dimensionally inconsistent loop expression. For configuration 7, `8% * 20 = 1.6`.

Primary interpretation:

```text
num_initial_drone_nodes = floor(initial_drone_percent * num_nodes / 100)
```

Rationale: the paper implementation was C++, the loop bound is integral, and direct integer arithmetic is the minimal non-interpolating implementation. Therefore configuration 7 initializes exactly one drone-only node per candidate.

Sensitivity diagnostic, frozen but not eligible to replace the primary result:

```text
half_up(1.6) = 2 drone-only nodes
```

## A2 - initial memeplex distribution

The paper states that a mutated meme option is assigned a “new random value” but does not separately define initialization.

Primary interpretation: initialize every meme option independently and uniformly over the complete disclosed valid domain. This gives every operator and every probability lattice value nonzero support and matches the disclosed mutation transition.

Frozen domains:

```text
C   in {0,...,8}
CP  in {0,...,10}
CM  in {0,...,3}
DM  in {0,...,5}
TM  in {0,1}
TP  in {0,...,10}
TOM in {0,1,2}
TOP in {0,...,10}
```

`CP`, `TP` and `TOP` are interpreted as deciles, so value `8` means probability `0.8`, matching the paper’s explicit crossover example.

A deterministic midpoint memeplex may be used only as a diagnostic. It cannot produce `V8_OLD_NUMERIC=PASS`.

## A3 - innovation random-value semantics

The paper writes `r in [0,10]` and applies mutation when `r < innovationRate`.

Primary interpretation:

```text
r is a uniformly sampled integer in {0,...,10}
```

Thus innovation rate `7` mutates a particular meme option with probability `7/11`, and equality `r == 7` is a no-mutation boundary.

A continuous-uniform interpretation on `[0,10]` is retained only as a diagnostic because the meme probabilities themselves are represented as integer deciles in the paper.

## A4 - tie handling

Whenever the paper says “parent with the lowest fitness” or “two individuals with the lowest fitness” but exact fitness ties occur, EU26-23 uses a stable deterministic ordering:

1. lower makespan;
2. lexicographically smaller canonical tour IDs;
3. lexicographically smaller node-type vector;
4. lexicographically smaller memeplex;
5. earlier creation serial.

This prevents platform-dependent ordering and makes 1/2/4-worker comparisons meaningful. Tie handling is an engineering determinism rule, not an author-source claim.

## A5 - exact TSP replacement for Concorde

The paper uses Concorde to obtain an optimal TSP tour. EU26-23 uses exact Held-Karp dynamic programming for the 20-node Euclidean instance and independently verifies the returned cycle cost. Because both solve the same exact symmetric TSP, this is treated as a solver substitution, not an algorithmic change. The canonical cycle starts at the depot and chooses the lexicographically smaller orientation.

## A6 - scientific claim ceiling

Even if the numerical gate passes, the strongest OLD claim is:

```text
PASS_PAPER_PROFILE_AGGREGATE_REPRODUCTION
```

The following remain forbidden:

- `PASS_AUTHOR_SOURCE_REPLAY`;
- original-seed equivalence;
- byte-identical trajectory equivalence;
- historical Visual Studio environment equivalence;
- claiming that an ambiguity diagnostic is the primary paper profile.

If the primary interpretation fails the preregistered numerical gate, the candidate is rejected. Diagnostics may explain sensitivity but may not retroactively redefine OLD.
