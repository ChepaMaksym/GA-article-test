# EU26-27 AGSEMO OLD test plan

1. Formula unit tests.
2. Benchmark objective/Pareto-front oracle tests.
3. Seed determinism tests.
4. Negative controls for invalid parameters.
5. Linux/macOS/Windows CI.
6. Worker replay on 1/2/4 workers.
7. 100-run frozen-seed campaign only after CI pass.
8. Compare mean/variance and endpoint distribution with published values.
9. Generate convergence and mutation-strength plots only from the frozen campaign.
10. HYBRID design is written after OLD verification, not before.

Current status: implementation committed; CI verification pending.