# Frozen prospective configuration

`experiment_matrix.csv` is a **five-function subset**, not the complete
paper experiment matrix. It contains Ackley, Griewank, Rastrigin,
Rosenbrock, and Sphere as requested for the clean-room scaffold; the
paper's unbounded Linear function and all neuroevolution tasks are
intentionally omitted.

Every one of the 40 matrix rows is paired with all 40 rows of
`seed_ledger.csv`, producing 1600 prospective run IDs. No full-matrix run
has been executed. The dimension-dependent budgets come from Appendix A
and conflict with the audited driver's fixed 1000-generation budget; this
is recorded rather than treated as a resolved published protocol.

The values \(K=10\), \(\eta_x=0.5\), and \(\eta_\sigma=0.5\) are the
defaults in the audited author artifact (`paper_meta.py` and
`optim.run_evolution_ours`). They are frozen here as an artifact-backed
interpretation, not presented as unambiguous camera-ready prose.
