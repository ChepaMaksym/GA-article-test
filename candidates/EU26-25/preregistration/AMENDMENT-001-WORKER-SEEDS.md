# Amendment 001 - distinct worker/load seed set

Date: 2026-08-20

This amendment is committed before any EU26-25 optimizer row exists.

`PROTOCOL.md` originally said that worker/load equivalence would use the two
portability smoke seeds. To exercise four concurrent workers without duplicate
scientific rows, P3 is now frozen as:

```text
worker/load seeds: 911, 912, 913, 914
maximum iterations: 2000 per seed
worker counts: 1, 2, 4
```

P2 remains unchanged:

```text
portability seeds: 901, 902
operating systems: Ubuntu, macOS, Windows
maximum iterations: 2000 per seed
```

The OLD endpoint seeds `1..10`, 120000-iteration budget, BKS, formulas,
acceptance rule, HYBRID prohibition and confirmatory HYBRID seed ledger are
unchanged. This amendment exists only to create a meaningful four-worker load
profile.
