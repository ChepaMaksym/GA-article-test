# Test and CI audit - reconstructed preconfirmatory state

The source tree includes exact Split/brute-force checks, permutation closure,
OLD roulette controls, lambda transitions and reset delay, deterministic paired
initial populations, and worker invariance.

The current-head GitHub matrix must run Linux, macOS and Windows with Python
3.11/3.12/3.13 and 1/2/4 workers. Scientific status remains pending until the
matrix completes after the source-tree corrective commit.
