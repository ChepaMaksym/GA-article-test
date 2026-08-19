# Amendment 002 - operator semantics frozen before implementation

Date: 2026-08-19

Parent ambiguity commit: `3872833cfa3f38bb18c3f1facac3372c10f59fae`

No EU26-23 optimizer or stochastic outcome existed when this amendment was written.

## Crossover event

One Bernoulli event is drawn per parent pair using the fitter parent’s `CP / 10` probability. On success, one operator produces both offspring. On failure, each offspring clones the corresponding parent chromosome. Both offspring inherit the fitter parent’s memeplex before meme innovation.

## Nine crossover variants

Node IDs are a depot-fixed permutation; node types are a parallel vector.

- `PMX_FULL`, `CX_FULL`, `OX_FULL`: permutation-preserving crossover; service type travels with the node ID supplied by the parent.
- `PMX_TOUR`, `CX_TOUR`, `OX_TOUR`: crossover only the customer permutation; service type is then inherited by node ID from the corresponding parent.
- `UX_TYPE`, `ONE_POINT_TYPE`, `TWO_POINT_TYPE`: operate only on customer service types while preserving each corresponding parent’s permutation.

This type-only interpretation for uniform/one-point/two-point avoids inventing an unreported duplicate-node repair. The depot is excluded from cut points and remains first and combined. Two-cut intervals are half-open `[left, right)`. Cycle crossover begins at the first customer locus.

## Mutation event counts

For each offspring:

1. draw one event with probability `TOP / 10`; on success apply exactly one tour operator;
2. draw one event with probability `TP / 10`; on success select one customer locus and apply one type operator appropriate to that node’s current type;
3. repair once after chromosome changes;
4. independently process all eight meme options for innovation.

No repeated-until-success loop is used.

## Tour operators

- `SWAP`: swap two distinct customer loci;
- `SLIDE`: remove the first sampled customer and insert it at the second sampled locus;
- `REVERSE`: reverse the inclusive customer block between two sampled loci.

Service types travel with node IDs.

## Type operators

Types are `COMBINED=1`, `DRONE=2`, `TRUCK_ONLY=3`.

Drone operators push a valid neighbour to truck-only, shift drone service left/right, or combine these actions. Combined-node operators convert the node to drone-only, optionally pushing left/right/both. Truck-only operators either extend the nearest unique drone segment across the selected node or end the segment by converting the node to combined. An impossible boundary action is a no-op before repair rather than a resampled action.

## Repair

The cycle is partitioned by combined nodes.

- A segment with more than one drone-only node is split by converting a midpoint customer between consecutive drone nodes to combined; when no interior midpoint exists, the later drone node becomes combined.
- A segment with no drone-only node may not contain truck-only nodes; they become combined.
- A segment with exactly one drone-only node may contain truck-only nodes.
- The depot is always combined.
- Repeat until legal.

Repair is idempotent and never changes node IDs or order.

## Makespan

For every combined-to-combined segment, the truck path visits all intermediate non-drone nodes in order. When a drone node exists, its flight is launch-combined to drone to rendezvous-combined. Segment time is truck time without a drone, otherwise `max(truck_time, drone_time)`. Fitness is the sum over all segments.

## Diagnostic-only alternatives

Per-offspring crossover events, probability domains `1..10`, continuous innovation, half-up initial-drone count and type inheritance by locus are sensitivity diagnostics only. They cannot replace the primary OLD profile or convert a failed primary campaign into PASS.
