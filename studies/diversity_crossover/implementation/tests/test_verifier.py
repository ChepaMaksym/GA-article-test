"""CI-only independent replay and mathematical fixture tests."""

import copy
import itertools
import math
import unittest
from fractions import Fraction
from unittest.mock import patch

import numpy as np

from studies.diversity_crossover.implementation import engine, verifier


def journal(problem=None, method="baseline", pc=0.9, budget=23, masks=None, task=1):
    problem = problem or {"kind": "onemax", "n": 6}
    masks = masks or ["0" * problem["n"], "1" * problem["n"], "01" * (problem["n"] // 2)]
    scores = [verifier.independent_score(problem, mask) for mask in masks]
    records = []
    summary = engine.run_search(problem, masks, scores, method, engine.make_rngs(task, 0),
                                lambda row: records.append(copy.deepcopy(row)), budget=budget, pc=pc)
    return problem, records, summary


def locate(records, event):
    return next(row for row in records if row["event"] == event)


class IndependentScoringTests(unittest.TestCase):
    def test_knapsack_bit_order_and_feasibility(self):
        problem = {"kind": "knapsack", "n": 3, "weights": [6, 5, 5], "profits": [10, 8, 8], "capacity": 10}
        self.assertEqual(verifier.independent_score(problem, "100"),
                         {"key": [1, 10], "weight": 6, "value": 10, "feasible": True})
        self.assertEqual(verifier.independent_score(problem, "011")["value"], 16)
        self.assertEqual(verifier.independent_score(problem, "111")["key"], [0, -6])
        self.assertTrue(verifier.independent_score(problem, "000")["feasible"])

    def test_model_function_boundaries(self):
        self.assertEqual(verifier.independent_score({"kind": "flat", "n": 4}, "1111")["value"], 0)
        self.assertEqual(verifier.independent_score({"kind": "onemax", "n": 4}, "0111")["value"], 3)
        problem = {"kind": "jump", "n": 6, "k": 2}
        self.assertEqual(verifier.independent_score(problem, "111100")["value"], 6)
        self.assertEqual(verifier.independent_score(problem, "111110")["value"], 1)
        self.assertEqual(verifier.independent_score(problem, "111111")["value"], 8)

    def test_invalid_masks_and_inputs(self):
        for bad_mask in ("", "001", "00x0", "００００", [0, 0, 0, 0]):
            with self.subTest(mask=bad_mask), self.assertRaises(ValueError):
                verifier.independent_score({"kind": "onemax", "n": 4}, bad_mask)
        with self.assertRaises(ValueError):
            verifier.independent_score({"kind": "jump", "n": 4, "k": 4}, "0000")

    def test_unique_masks_and_pairwise_distance_are_distinct(self):
        masks = ["00", "00", "11"]
        scores = [verifier.independent_score({"kind": "flat", "n": 2}, mask) for mask in masks]
        metrics = verifier.independent_metrics(masks, scores)
        self.assertEqual(metrics["unique_fraction"], 2 / 3)
        self.assertEqual(metrics["diversity"], 2 / 3)
        upper_bound = 2 * math.floor(len(masks) ** 2 / 4) / (len(masks) * (len(masks) - 1))
        self.assertEqual(metrics["diversity"], upper_bound)
        for population in itertools.product(("00", "01", "10", "11"), repeat=3):
            pop = list(population)
            exact_pair_sum = sum(sum(a != b for a, b in zip(pop[i], pop[j]))
                                 for i in range(3) for j in range(i + 1, 3))
            actual = verifier.independent_metrics(pop, scores)["diversity"]
            self.assertEqual(actual, 2 * exact_pair_sum / (3 * 2 * 2))
            self.assertLessEqual(actual, upper_bound)

    def test_no_feasible_population_is_not_zero_quality(self):
        problem = {"kind": "knapsack", "n": 2, "weights": [5, 6], "profits": [8, 9], "capacity": 0}
        masks = ["10", "01"]
        result = verifier.independent_metrics(masks, [verifier.independent_score(problem, x) for x in masks])
        self.assertEqual(result["feasible_fraction"], 0)
        self.assertIsNone(result["mean_feasible_value"])

    def test_one_member_and_clone_population(self):
        score = verifier.independent_score({"kind": "flat", "n": 2}, "00")
        self.assertEqual(verifier.independent_metrics(["00"], [score])["diversity"], 0)
        metrics = verifier.independent_metrics(["00"] * 3, [score] * 3)
        self.assertEqual(metrics["unique_fraction"], 1 / 3)
        self.assertEqual(metrics["diversity"], 0)

    def test_crossover_counterexample_zero_versus_quarter(self):
        problem = {"kind": "knapsack", "n": 4, "weights": [2, 2, 1, 1], "profits": [2] * 4, "capacity": 2}
        probabilities = []
        for a, b in (("1000", "0100"), ("0010", "0001")):
            differing = [i for i in range(4) if a[i] != b[i]]
            self.assertEqual(len(differing), 2)
            good = 0
            weights, profits = [], []
            for flags in itertools.product((0, 1), repeat=len(differing)):
                child = list(a)
                for i, flag in zip(differing, flags):
                    child[i] = b[i] if flag else a[i]
                result = verifier.independent_score(problem, "".join(child))
                good += int(result["feasible"] and result["value"] > 2)
                weights.append(result["weight"])
                profits.append(result["value"])
            probabilities.append(Fraction(good, 2 ** len(differing)))
            parent_scores = [verifier.independent_score(problem, p) for p in (a, b)]
            self.assertEqual(Fraction(sum(weights), 4), Fraction(sum(s["weight"] for s in parent_scores), 2))
            self.assertEqual(Fraction(sum(profits), 4), Fraction(sum(s["value"] for s in parent_scores), 2))
        self.assertEqual(probabilities, [Fraction(0), Fraction(1, 4)])

    def test_neutral_flat_drift_exact_enumeration(self):
        # Published uniform-parent/neutral-replacement assumptions, not a
        # theoretical promise for directed mating or constrained knapsack.
        mu, n, chi = 2, 2, 1
        population = ["00", "11"]
        expected_sum = Fraction(0)
        possibilities = 0
        for first, second, cross, flips, replaced in itertools.product(
                range(mu), range(mu), itertools.product((0, 1), repeat=n),
                itertools.product((0, 1), repeat=n), range(mu)):
            pre = [population[first][i] if cross[i] else population[second][i] for i in range(n)]
            child = "".join(str(int(pre[i]) ^ flips[i]) for i in range(n))
            after = list(population)
            after[replaced] = child
            expected_sum += 2 * sum(a != b for a, b in zip(*after))
            possibilities += 1
        expected_sum /= possibilities
        original_sum = 4
        coefficient = Fraction(1) - Fraction(2, mu ** 2) - Fraction(4 * (mu - 1) * chi, mu ** 2 * n)
        predicted = coefficient * original_sum + 2 * chi * (mu - 1)
        self.assertEqual(expected_sum, predicted)


class JournalReplayTests(unittest.TestCase):
    def test_all_methods_and_objectives_replay(self):
        problems = ({"kind": "flat", "n": 6}, {"kind": "onemax", "n": 6},
                    {"kind": "jump", "n": 6, "k": 2},
                    {"kind": "knapsack", "n": 6, "weights": [1, 2, 3, 4, 5, 6],
                     "profits": [5, 4, 3, 2, 1, 6], "capacity": 10})
        for problem, method in itertools.product(problems, engine.METHODS):
            with self.subTest(kind=problem["kind"], method=method):
                _, records, summary = journal(problem=problem, method=method)
                checked = verifier.verify_journal(problem, iter(records))
                self.assertEqual(checked["status"], "VERIFIED")
                self.assertEqual(checked["summary"], summary)
                self.assertEqual(checked["verification_call_breakdown"]["initial"], 3)
                self.assertEqual(checked["verification_call_breakdown"]["final_candidates"], 23)
                self.assertEqual(checked["trace"][-1]["call"], 23)

    def test_partial_batch_preserves_record_but_not_replacement(self):
        problem, records, summary = journal(method="repeated", pc=1, budget=1,
                                            masks=["000000"] * 3)
        verified = verifier.verify_journal(problem, records)
        finished = locate(records, "finish_step")
        self.assertFalse(finished["completed"])
        self.assertFalse(finished["accepted"])
        self.assertIsNone(finished["selected_slot"])
        self.assertEqual(finished["population_hash"], summary["population_hash"])
        self.assertEqual(verified["summary"]["record"], locate(records, "candidate")["record"])
        self.assertEqual(verified["trace"][-1]["mean_feasible_value"], 0)

    def test_mutation_control_productivity_is_not_applicable(self):
        problem, records, _ = journal(pc=0)
        result = verifier.verify_journal(problem, records)
        self.assertEqual(result["productivity"]["conditional_status"], "NOT_APPLICABLE")
        self.assertIsNone(result["productivity"]["pre_mutation_better_fraction"])
        self.assertEqual(result["verification_call_breakdown"]["crossover_intermediates"], 0)

    def test_infeasible_parents_do_not_enter_conditional_denominator(self):
        problem = {"kind": "knapsack", "n": 6, "weights": [100] * 6, "profits": [1] * 6, "capacity": 0}
        _, records, _ = journal(problem=problem, pc=1, budget=1, masks=["111111"] * 3)
        result = verifier.verify_journal(problem, records)
        self.assertEqual(result["productivity"]["both_parents_feasible_candidates"], 0)
        self.assertEqual(result["productivity"]["conditional_status"], "NOT_APPLICABLE")

    def test_repeated_all_children_count_as_physical_calls(self):
        problem, records, _ = journal(method="repeated", pc=1, budget=8)
        result = verifier.verify_journal(problem, records)
        self.assertEqual(result["summary"]["new_calls"], 8)
        self.assertEqual(result["summary"]["completed_steps"], 2)
        self.assertEqual(result["verification_call_breakdown"]["crossover_intermediates"], 8)
        self.assertEqual(result["verification_calls"], 3 + 8 + 8)

    def test_replay_has_no_dependency_on_production_evaluation(self):
        problem, records, _ = journal()
        with patch.object(engine, "_score", side_effect=AssertionError("production evaluator forbidden")), \
             patch.object(engine, "_pick", side_effect=AssertionError("production selector forbidden")), \
             patch.object(engine, "metrics", side_effect=AssertionError("production metrics forbidden")):
            self.assertEqual(verifier.verify_journal(problem, records)["status"], "VERIFIED")

    def test_schema_and_operator_tampering_is_rejected(self):
        problem, original, _ = journal(method="directed", pc=1)
        mutations = (
            ("initial", "schema_version", 99),
            ("step", "step", 4), ("step", "calls_before", 7),
            ("step", "parent_indices", [999, 999]), ("step", "anchor_index", 999),
            ("step", "eligible_indices", []), ("step", "has_crossover", False),
            ("step", "planned_offspring", 4), ("step", "parent_distance", 999),
            ("candidate", "call", 2), ("candidate", "slot", 1),
            ("candidate", "mask", "xxxxxx"), ("candidate", "mutation_bits", [999]),
            ("candidate", "pre_mutation_mask", "xxxxxx"),
            ("candidate", "record", {}),
            ("finish_step", "completed", False), ("finish_step", "population_hash", "bad"),
            ("finish_step", "selected_slot", 999), ("finish_step", "replacement_index", 999),
            ("terminal", "summary", {}),
        )
        for event, field, value in mutations:
            with self.subTest(event=event, field=field):
                records = copy.deepcopy(original)
                locate(records, event)[field] = value
                with self.assertRaises(ValueError):
                    verifier.verify_journal(problem, records)

    def test_scores_rng_metrics_and_duplicate_tampering(self):
        problem, original, _ = journal(pc=1)
        for kind in ("score", "rng", "metrics", "duplicate", "initial_score"):
            records = copy.deepcopy(original)
            if kind == "score":
                locate(records, "candidate")["score"]["value"] += 1
            elif kind == "rng":
                locate(records, "step")["rng_before"]["mutation"]["state"]["state"] += 1
            elif kind == "metrics":
                locate(records, "finish_step")["metrics"]["diversity"] = 3
            elif kind == "initial_score":
                locate(records, "initial")["scores"][0]["value"] = 99
            else:
                row = locate(records, "candidate")
                row["duplicate"] = not row["duplicate"]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                verifier.verify_journal(problem, records)


    def test_truncated_unknown_and_duplicate_events_are_rejected(self):
        problem, original, _ = journal()
        examples = ([], original[:-1], original + [copy.deepcopy(original[-1])],
                    original[:2] + [{"event": "unknown"}] + original[2:],
                    [r for r in original if r["event"] != "checkpoint"],
                    original[:2] + [copy.deepcopy(original[1])] + original[2:])
        for records in examples:
            with self.subTest(length=len(records)), self.assertRaises(ValueError):
                verifier.verify_journal(problem, records)

    def test_problem_identity_is_bound(self):
        problem, records, _ = journal()
        wrong = dict(problem, kind="flat")
        with self.assertRaises(ValueError):
            verifier.verify_journal(wrong, records)

    def test_verification_guard_refuses_local_execution(self):
        problem, records, _ = journal()
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                verifier.verify_journal(problem, records)


class FrozenHeaderTests(unittest.TestCase):
    def fixture(self, method="baseline", pc=0.9):
        problem = {"kind": "flat", "n": 100}
        states = {}
        for channel, name in enumerate(verifier.CHANNELS):
            states[name] = np.random.PCG64(np.random.SeedSequence([70001, 0, 1, channel])).state
        initialization = np.random.Generator(np.random.PCG64())
        initialization.bit_generator.state = copy.deepcopy(states["initialization"])
        before = copy.deepcopy(initialization.bit_generator.state)
        masks = ["0" * 100]
        for _ in range(29):
            masks.append("".join("1" if bit else "0" for bit in initialization.random(100) < 0.5))
        after = copy.deepcopy(initialization.bit_generator.state)
        scores = [{"key": [1, 0], "weight": None, "value": 0, "feasible": True} for _ in masks]
        bank = {"schema_version": "diversity-pilot-bank-v1",
                "protocol_id": "GA-DIVERSITY-CROSSOVER-TECHNICAL-PILOT-V1",
                "task": "Flat", "task_index": 0, "start": "bank", "start_index": 1,
                "seed": 70001, "n": 100, "mu": 30,
                "problem": problem, "masks": masks, "scores": scores,
                "initialization_before": before, "initialization_after": after}
        states["initialization"] = copy.deepcopy(after)
        header = {"event": "initial", "schema_version": 1, "problem": problem,
                  "method": method, "population": copy.deepcopy(masks), "scores": copy.deepcopy(scores),
                  "params": {"mu": 30, "n": 100, "budget": 5000, "pc": float(pc),
                             "mutation_probability": 0.01, "repeated_offspring": 4},
                  "initial_record": {"mask": masks[0], "score": scores[0], "call": 0},
                  "rng_start": states}
        return problem, bank, header

    def test_registered_headers_bind_all_methods_and_control(self):
        for method, pc in (("baseline", 0.9), ("directed", 0.9),
                           ("repeated", 0.9), ("baseline", 0)):
            with self.subTest(method=method, pc=pc):
                problem, bank, header = self.fixture(method=method, pc=pc)
                result = verifier.verify_frozen_header(problem, header, bank, method, pc)
                self.assertEqual(result["status"], "VERIFIED_FROZEN_HEADER")
                self.assertEqual(result["objective_evaluations"], 0)

    def test_changed_initial_states_rejected_for_each_channel(self):
        problem, bank, original = self.fixture()
        for channel in verifier.CHANNELS:
            header = copy.deepcopy(original)
            header["rng_start"][channel]["state"]["state"] += 1
            with self.subTest(channel=channel), self.assertRaises(ValueError):
                verifier.verify_frozen_header(problem, header, bank, "baseline", 0.9)

    def test_original_seed_state_not_substituted_for_prepared_initialization(self):
        problem, bank, header = self.fixture()
        header["rng_start"]["initialization"] = bank["initialization_before"]
        with self.assertRaises(ValueError):
            verifier.verify_frozen_header(problem, header, bank, "baseline", 0.9)

    def test_bank_and_header_identifiers_and_parameters_are_bound(self):
        problem, original_bank, original_header = self.fixture()
        for field, value in (("seed", 70002), ("task_index", 1), ("start_index", 0),
                             ("task", "OneMax"), ("start", "cloned"), ("mu", 29),
                             ("n", 99), ("protocol_id", "other"), ("schema_version", "other")):
            bank = copy.deepcopy(original_bank)
            bank[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verifier.verify_frozen_header(problem, original_header, bank, "baseline", 0.9)
        for field, value in (("mu", 29), ("n", 99), ("budget", 4999), ("pc", 0),
                             ("mutation_probability", 0.03), ("repeated_offspring", 1)):
            header = copy.deepcopy(original_header)
            header["params"][field] = value
            with self.subTest(parameter=field), self.assertRaises(ValueError):
                verifier.verify_frozen_header(problem, header, original_bank, "baseline", 0.9)

    def test_population_scores_objective_method_and_record_are_bound(self):
        problem, bank, original = self.fixture()
        for change in ("mask", "score", "problem", "method", "record"):
            header = copy.deepcopy(original)
            if change == "mask":
                header["population"][0] = "1" + "0" * 99
            elif change == "score":
                header["scores"][0]["value"] = 1
            elif change == "problem":
                header["problem"]["kind"] = "onemax"
            elif change == "method":
                header["method"] = "directed"
            else:
                header["initial_record"]["call"] = 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                verifier.verify_frozen_header(problem, header, bank, "baseline", 0.9)

    def test_frozen_binding_uses_no_production_functions_or_objective_queries(self):
        problem, bank, header = self.fixture()
        with patch.object(engine, "make_rngs", side_effect=AssertionError("producer RNG forbidden")), \
             patch.object(engine, "evaluate", side_effect=AssertionError("producer evaluator forbidden")), \
             patch.object(verifier, "independent_score", side_effect=AssertionError("extra objective query forbidden")):
            result = verifier.verify_frozen_header(problem, header, bank, "baseline", 0.9)
        self.assertEqual(result["objective_evaluations"], 0)

    def test_unknown_budget_pc_and_initialization_seed_are_rejected(self):
        problem, bank, header = self.fixture()
        for budget, pc in ((4999, 0.9), (5000, 0.5)):
            with self.subTest(budget=budget, pc=pc), self.assertRaises(ValueError):
                verifier.verify_frozen_header(problem, header, bank, "baseline", pc, budget=budget)
        bad = copy.deepcopy(bank)
        bad["initialization_before"]["state"]["state"] += 1
        with self.assertRaises(ValueError):
            verifier.verify_frozen_header(problem, header, bad, "baseline", 0.9)

    def test_public_verification_helpers_reject_local_execution(self):
        problem, bank, header = self.fixture()
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}):
            for call in (lambda: verifier.verify_frozen_header(problem, header, bank, "baseline", 0.9),
                         lambda: verifier.independent_score(problem, "0" * 100),
                         lambda: verifier.independent_metrics(bank["masks"], bank["scores"])):
                with self.assertRaises(ValueError):
                    call()

if __name__ == "__main__":
    unittest.main()
