# USA26-09 OLD rejection

Date: 2026-08-20

```text
OLD = FAIL_METHOD_AND_ENDPOINT_EQUIVALENCE
HYBRID = BLOCKED_NOT_AUTHORIZED
```

## Decisive failure

The published Set-I cell `N=50`, `m=10`, `HGA-avg=1.82` is a rounded mean over
100 independently generated uniform instances and ten HGA executions per
instance. The reconstructed OLD used one fixed instance and a 30-seed median.
The comparison therefore changes both the instance distribution and the
statistic.

The fixed instance's deterministic nearest-neighbor order already gives
`1.8288547696784496`, making the proposed anchor gate non-diagnostic of HGA.

## Algorithm mismatch

The clean-room runner does not reproduce the complete paper HGA. Missing or
materially changed components include:

- `mu=10`, `lambda=20` variable population control;
- diversity-power sorting and survivor policy;
- tournament size 2;
- Similar Tour Crossover;
- intersection removal and enrichment;
- adaptive education repeated 100/1000 times;
- nearest-city restriction;
- diversification after 1000 non-improving generations;
- stop after 2500 generations without improvement or cutoff time.

No tolerance or seed change can repair these structural mismatches. The fresh
`3001..3030` campaign is cancelled and may not be described as OLD evidence.
