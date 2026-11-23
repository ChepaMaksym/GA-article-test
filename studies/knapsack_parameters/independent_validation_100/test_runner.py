"""Regression checks for case scheduling, replay, and the benchmark boundary."""
from copy import deepcopy
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from studies.knapsack_parameters.iterative_validation_population13.pilot import check_accounting
from studies.knapsack_parameters.mutation_grid_100.observations import extract
from studies.knapsack_parameters.mutation_grid_100.validation.search import make_log
from studies.knapsack_parameters.mutation_grid_100.verification import verify_log
from studies.knapsack_parameters.population_validation_100.preparation import make_bank

from .benchmark import forecast, old_log
from .preparation import schedule_cases
from .runner import PROFILES, _checked_cases, authenticate_saved, identity, raw_prefix


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific tests run in GitHub Actions")
class ExecutionTests(unittest.TestCase):
    def test_paired_rectangular_schedule(self):
        rows = _checked_cases({"cases": schedule_cases()})
        self.assertEqual(len(rows), 1200)
        self.assertEqual(len({(r["task"], r["seed"]) for r in rows}), 300)
        self.assertEqual({(r["mu"], r["pc_percentage"], r["mutation_basis_points"]) for r in rows},
                         set(PROFILES))
        self.assertEqual(len({raw_prefix(r) for r in rows}), 1200)

    def test_duplicate_missing_pair_is_rejected(self):
        rows = schedule_cases()
        rows[-1] = rows[0].copy()
        with self.assertRaises(ValueError):
            _checked_cases({"cases": rows})

    def test_old_seed_and_wrong_task_index_are_rejected(self):
        for field, value in (("seed", 150001), ("task_index", 3), ("mu", 13), ("pc_percentage", True)):
            with self.subTest(field=field):
                rows = schedule_cases()
                rows[0][field] = value
                rows[0]["case_id"] = identity(rows[0])
                with self.assertRaises(ValueError):
                    _checked_cases({"cases": rows})

    def test_partial_generation_and_replayed_streams_for_every_profile(self):
        problem = {"n":100, "weights":[1]*100, "profits":[1]*100, "capacity":50}
        bank = make_bank(problem, 33, 160001, 160000)
        for profile in PROFILES:
            with self.subTest(profile=profile):
                mu = profile[0]
                # Exactly one full generation, then two further evaluated candidates.
                total = mu + mu - 1 + 2
                log = make_log(problem, bank, profile, 160001, 33, total)
                self.assertEqual(log["rng_initial"], bank["rng_states"])
                self.assertEqual(log["initial_masks"], bank["masks"][:mu])
                counts = check_accounting(log, mu, total)
                self.assertEqual((counts["completed_generations"], counts["terminal_partial_children"]), (1, 2))
                checked = verify_log(log)
                self.assertEqual(checked["verification_status"], "VERIFIED")
                self.assertEqual(checked["new_calls"], total-mu)
                observed = extract(log, total, 50, checkpoints=(mu, total))
                self.assertEqual(observed["final_best_profit"], checked["record_profit"])

    def test_rejects_optimum_and_mixed_generator_state(self):
        problem = {"n":100, "weights":[1]*100, "profits":[1]*100, "capacity":50}
        bank = make_bank(problem, 33, 160001, 160000)
        with self.assertRaises(ValueError):
            make_log(dict(problem, optimum=50), bank, PROFILES[0], 160001, 33, 35)
        corrupted = deepcopy(bank)
        corrupted["rng_states"].pop("selection")
        with self.assertRaises(ValueError):
            make_log(problem, corrupted, PROFILES[0], 160001, 33, 35)

    def test_determinism_and_corruption_of_operator_and_final_rng(self):
        problem = {"n":100, "weights":[1]*100, "profits":[1]*100, "capacity":50}
        bank = make_bank(problem, 33, 160001, 160000)
        log = make_log(problem, bank, (15,100,100), 160001, 33, 35)
        second = make_log(problem, bank, (15,100,100), 160001, 33, 35)
        self.assertEqual({k:v for k,v in log.items() if k != "timing_ns"},
                         {k:v for k,v in second.items() if k != "timing_ns"})
        bad_rng = deepcopy(log)
        bad_rng["rng_final"]["mutation"] = bad_rng["rng_final"]["branch"]
        with self.assertRaises(ValueError):
            verify_log(bad_rng)
        bad_operator = deepcopy(log)
        bad_operator["candidates"][0]["crossover"] = not bad_operator["candidates"][0]["crossover"]
        with self.assertRaises(ValueError):
            verify_log(bad_operator)

    def test_empty_and_incomplete_retained_evidence_is_rejected(self):
        case = schedule_cases()[0]
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                authenticate_saved(case, {}, {}, root, "1", "c"*40, 50)
            folder = root / "raw" / raw_prefix(case)
            folder.mkdir(parents=True)
            row = root / "compact" / "records" / (case["case_id"]+".json")
            row.parent.mkdir(parents=True)
            row.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                authenticate_saved(case, {}, {}, root, "1", "c"*40, 50)

    def test_old_benchmark_rejects_a_holdout_bank(self):
        problem = {"n":100, "weights":[1]*100, "profits":[1]*100, "capacity":50}
        bank = make_bank(problem, 33, 160001, 160000)
        with self.assertRaises(ValueError):
            old_log(problem, bank, PROFILES[0], 160001, 33, 100000)

    def test_forecast_requires_all_four_replayed_cases(self):
        rows = [{"case_seconds":30, "artifact_bytes":8*1024**2}]*4
        with self.assertRaises(ValueError):
            forecast(rows[:3])
        self.assertEqual(forecast(rows)["runner_minutes_with_reserve"], 1130)
        self.assertEqual(forecast(rows)["independent_runs_started"], 0)


if __name__ == "__main__":
    unittest.main()
