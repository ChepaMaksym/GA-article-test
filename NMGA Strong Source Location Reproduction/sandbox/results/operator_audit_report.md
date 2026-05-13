# Article Operator Audit Report

Generated with profile `article_exact`. This checklist maps article-level requirements to local functions and tests.

| Article operator / claim | Local function | Verification status |
|---|---|---|
| Chromosome `[x,y,Q,H]` | `article_exact_spec`, optimizer population rows | Unit test checks spec chromosome and bounds |
| MGA fixed `Pc/Pm` | `nmga_options`, `run_evolutionary_optimizer` | Unit test checks `Pc=0.6`, `Pm=0.01` |
| NMGA Formula 7 `Pc=P1*(1-gen/maxgen)^b` | `nmga_adaptive_rates` | Unit test checks gens 1, SetMax, 500, 1000 |
| NMGA Formula 8 `Pm=P2*(1+gen/maxgen)^b` | `nmga_adaptive_rates` | Unit test checks gens 1, SetMax, 500, 1000 |
| AGP/EGP split | `article_gene_pool_split` | Unit test uses `article_operator_probe` split counts |
| AGP/EGP inheritance branch | `article_egp_crossover`, `breed_nmga` | Unit test checks deterministic child value |
| Nonuniform mutation amplitude decreases | `article_nonuniform_delta`, `mutate_nonuniform` | Unit test compares early vs late delta |
| Article SSE objective / reciprocal fitness detail | `source_objective` | Unit test checks `article_sse` against raw SSE |
| Bounds and population-size preservation | `run_evolutionary_optimizer` | Unit test checks bounds and history lengths |
| Table 1 protocol separated from sandbox stress cases | `run_article_exact_reproduction_impl` | This report and `article_exact_report.md` mark data provenance |

Remaining blocker: raw exact replication requires article_raw or digitized monitoring data, not currently available locally.
