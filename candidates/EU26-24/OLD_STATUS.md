# EU26-24 OLD result - rejected before HYBRID

Date: 2026-08-20

## Final decision

```text
OLD = REJECTED_OLD_REPRODUCTION
HYBRID = BLOCKED_NOT_CREATED
PR19 evidence used = false
```

The clean-room source-compatible OLD campaign was completed on the immutable
seed ledger `2001..2030`. No criterion was changed after pilot or confirmatory
rows were inspected.

## Formula and deterministic verification

The candidate passed source identity, Apache-2.0 provenance, objective and
constraint micro-oracles, the source-compatible paper/source divergence check,
24-bit decoding, the log-normal mutation fixed tape, 1/2/4-worker smoke
equivalence and an independent deterministic engineering oracle.

The independent oracle recovered:

```text
variables = [1, 0, 2, 2.1725518217, 8.0]
Phi = 21.7860501270
objectives = [91.0, 10454106.7458, 0.04375, 7135.0]
preferences = [42.8130, 37.7541, 97.3475, 14.9926]
```

This agrees with the published rounded Table 3/4 basin and confirms that the
application equations were implemented coherently.

## Confirmatory campaign

| Gate | Required | Observed | Result |
|---|---:|---:|---|
| Complete and feasible | >=24/30 | 30/30 | PASS |
| Vessel configuration `[1,0,2]` | >=24/30 | 30/30 | PASS |
| Anchor basin `2.15<=D<2.25`, `L>=7.95` | >=24/30 | 10/30 | **FAIL** |
| Median duration | `91 +/- 0.5` | 91.000000 | PASS |
| Median cost | `10.45E6 +/- 0.05E6` | 10460923.52 | PASS |
| Median fleet objective | `0.04375 +/- 0.005` | 0.04375000 | PASS |
| Median emissions | `7135 +/- 25` | 7135.00 | PASS |
| Preference medians | within 2 points | `[42.8130, 37.3962, 97.3475, 14.9926]` | PASS |

Additional campaign values:

```text
median Phi = 21.911316401845
median generations = 38.0
median logical NFE = 57000.0
campaign digest = 9e745f23e12f71f80f96938f0ebd8d2ae91dd48e7ba26dbdc3655b01b0209ebc
```

## Failure classification

This is a stochastic OLD endpoint-coverage failure, not a formula, feasibility,
runtime or data failure. The released log-normal controller consistently found
the correct vessel configuration and near-optimal feasible designs, but it did
not enter the narrow published anchor basin in the preregistered 80% of runs.

Because the OLD gate failed, the project rules prohibit:

- adding any executable PR #8 HYBRID for EU26-24;
- changing the basin tolerance or required coverage after seeing results;
- describing the deterministic oracle alone as stochastic OLD reproduction;
- using this candidate for a new master thesis;
- importing PR #19 evidence to rescue the candidate.

## Cleanup

No executable EU26-24 implementation was committed to the repository. Only the
preregistration, source manifest, compact confirmatory evidence and rejection
record remain. The next candidate must branch directly from the verified PR #8
base.
