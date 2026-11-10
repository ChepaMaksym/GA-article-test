# Programming checks

`test_validation.py` contains synthetic 100-item fixtures. It does not execute the nine registered full pilot runs or any main-series run. The full 100000-evaluation accounting is checked arithmetically; generated toy journals use only 80, 96, 100 or 117 total evaluations.

The tests require the actual GitHub Actions environment through `common.require_ci()` in `setUpClass`. They never set `GITHUB_ACTIONS=true` themselves and must not be executed locally by spoofing CI.

Expected public wrapper contracts:

```python
preparation.score(problem, mask) -> {"weight": int, "profit": int, "feasible": bool}
preparation.make_bank(problem, task_index, seed, preparation_seed) -> {
    "masks": [str] * 30,
    "scores": [dict] * 30,
    "rng_states": {six_channel_names: PCG64_state},
    # Additional recorded preparation metadata is allowed.
}
preparation.validate_source(raw_bytes, source_entry) -> problem
pilot.make_log(problem, bank, mu, seed, task_index, total=100000) -> log
```

`source_entry` includes `source_path`, `bytes` and `git_blob_sha1`. The synthetic source path names a `n00100` file; a `n00500` source, changed bytes or a changed blob identity must be rejected. Scientific source files remain bound to the pinned corpus manifest by the preparation driver, not by the toy fixture.

Checks cover shared initial prefixes, independent known scores, six initial random states, determinism, unchanged inputs, fixed probabilities, exact evaluation accounting, complete and incomplete generations, independent replay, corrupted masks/populations/random states, feasibility, duplicate initial individuals, ties, elitism and exclusion of OPT from the search interface.

The threshold test supplies a clearly marked synthetic observation history. It checks an initializing prefix, exact equality at 93% OPT, a final-evaluation achievement and retained nonachievement. This fixture is not a complete operator journal and is never described as a verified research run.

Intended command, after the separate resource authorization:

```text
python -m unittest studies.knapsack_parameters.population_validation_100.test_validation -v
```

No tests have been executed while preparing these files.
