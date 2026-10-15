"""Independent CI-only checks for figures made from already frozen evidence.

No search, exact solver, bootstrap or plotting is invoked by these tests.  The
small temporary mirrors below exercise rejection paths; production source pins
are never edited.  Run this module only in the authorized Actions workflow.
"""

from __future__ import annotations

from contextlib import contextmanager
import csv
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from studies.diversity_crossover.simple_figures import build


REPO_ROOT = Path(__file__).resolve().parents[3]


class CIOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Simple-figure checks may execute only in GitHub Actions")


def read_json(root: Path, relative: str) -> dict:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str, value: dict) -> None:
    (root / relative).write_text(json.dumps(value, ensure_ascii=False, indent=2),
                                 encoding="utf-8")


@contextmanager
def mirror_inputs():
    """Copy the five source files; never mutate the retained Git evidence."""
    with tempfile.TemporaryDirectory(prefix="simple-figure-source-") as name:
        root = Path(name)
        for relative in build.INPUT_SHA256:
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise AssertionError("An input pin must be repository-relative")
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / relative_path, target)
        yield root


def load_with_test_pins(root: Path, *changed: str) -> dict:
    """Reach semantic guards after deliberate fixture-only changes.

    Fresh hashes apply only inside this mock context.  Re-signing a test fixture
    must not be mistaken for authorization to change historical source inputs.
    """
    pins = dict(build.INPUT_SHA256)
    for relative in changed:
        pins[relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    with patch.object(build, "INPUT_SHA256", pins):
        return build.load_inputs(root)


def rewrite_neighbor_fixture(root: Path, rows: list[dict]) -> None:
    path = root / build.NEIGHBORS_REL
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "neighbor_index", "distance", "flip_i", "flip_j", "weight", "profit",
            "feasible", "reason", "comparison"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    case = read_json(root, build.CASE_REL)
    case["neighbors_file"]["bytes"] = path.stat().st_size
    case["neighbors_file"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(root, build.CASE_REL, case)


class FrozenInputTests(CIOnlyTests):
    def test_source_pins_and_fixed_case_metadata(self):
        required = {build.CASE_REL, build.NEIGHBORS_REL, build.ANALYSIS_REL,
                    build.MAIN_RESULTS_REL, build.DATA_REL}
        self.assertEqual(set(build.INPUT_SHA256), required)
        for relative, expected in build.INPUT_SHA256.items():
            with self.subTest(source=relative):
                self.assertEqual(hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest(),
                                 expected)
        case = read_json(REPO_ROOT, build.CASE_REL)
        self.assertEqual(case["instance_id"], "UC-s000")
        self.assertEqual(case["status"], "ADMITTED_STRICT_LOCAL")
        self.assertEqual(case["provenance"]["run_id"], 37637475385)
        self.assertEqual(case["provenance"]["run_attempt"], 1)
        self.assertEqual(case["certificate"]["center"]["profit"], 46510)
        self.assertEqual(case["exact"]["confirmed_optimum"], 46537)

    def test_real_inputs_match_independent_neighbor_reconstruction(self):
        result = build.load_inputs(REPO_ROOT)
        case = read_json(REPO_ROOT, build.CASE_REL)
        tokens = (REPO_ROOT / build.DATA_REL).read_text(encoding="utf-8").split()
        n, capacity = int(tokens[0]), int(tokens[1])
        self.assertEqual((n, capacity, len(tokens)), (100, 22545, 202))
        profits, weights = list(map(int, tokens[2::2])), list(map(int, tokens[3::2]))
        center = case["certificate"]["center"]
        witness = case["exact"]["capacity"]

        def score(mask):
            self.assertEqual(len(mask), n)
            self.assertLessEqual(set(mask), {"0", "1"})
            return (sum(profits[i] for i in range(n) if mask[i] == "1"),
                    sum(weights[i] for i in range(n) if mask[i] == "1"))

        self.assertEqual(score(center["mask"]), (46510, 22487))
        self.assertEqual(score(witness["witness_mask"]), (46537, 22519))
        self.assertLessEqual(22519, capacity)
        self.assertEqual(sum(a != b for a, b in zip(center["mask"], witness["witness_mask"])), 3)
        expected_flips = {(i,) for i in range(n)} | set(itertools.combinations(range(n), 2))
        found, indices = set(), set()
        max_gain = {"1": None, "2": None}
        counts = {1: 0, 2: 0, "feasible": 0, "invalid": 0}
        with (REPO_ROOT / build.NEIGHBORS_REL).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                distance = int(row["distance"])
                flips = ((int(row["flip_i"]),) if distance == 1 else
                         (int(row["flip_i"]), int(row["flip_j"])))
                self.assertIn(distance, (1, 2))
                self.assertIn(flips, expected_flips)
                self.assertNotIn(flips, found)
                self.assertNotIn(int(row["neighbor_index"]), indices)
                found.add(flips)
                indices.add(int(row["neighbor_index"]))
                bits = list(center["mask"])
                for index in flips:
                    bits[index] = "0" if bits[index] == "1" else "1"
                profit, weight = score("".join(bits))
                feasible = weight <= capacity
                self.assertEqual((int(row["profit"]), int(row["weight"])), (profit, weight))
                self.assertEqual(row["feasible"], "1" if feasible else "0")
                self.assertEqual(row["reason"], "FEASIBLE" if feasible else "CAPACITY_EXCEEDED")
                self.assertEqual(row["comparison"], "WORSE" if feasible else "INVALID")
                counts[distance] += 1
                counts["feasible" if feasible else "invalid"] += 1
                if feasible:
                    gain = profit - center["profit"]
                    previous = max_gain[str(distance)]
                    max_gain[str(distance)] = gain if previous is None else max(previous, gain)
        self.assertEqual(found, expected_flips)
        self.assertEqual(indices, set(range(1, 5051)))
        self.assertEqual(counts, {1: 100, 2: 4950, "feasible": 2670, "invalid": 2380})
        self.assertTrue(all(gain < 0 for gain in max_gain.values()))
        locality = result["locality"]
        self.assertEqual(locality["max_gain_by_distance"], max_gain)
        self.assertEqual((locality["witness_gain"], locality["witness_distance"],
                          locality["n"], locality["neighbors"]), (27, 3, 100, 5050))

    def test_saved_outcomes_keep_methods_and_tasks_separate(self):
        rows = build.load_inputs(REPO_ROOT)["outcomes"]
        expected = {
            ("Jump4", "baseline"): (8, 30), ("Jump4", "directed"): (30, 30),
            ("Jump8", "baseline"): (0, 30), ("Jump8", "directed"): (0, 30),
            ("KPLIB-local", "baseline"): (0, 420),
            ("KPLIB-local", "directed"): (0, 420),
        }
        actual = {(row["task"], row["method"]): (row["successes"], row["runs"]) for row in rows}
        self.assertEqual(len(rows), len(expected))
        self.assertEqual(actual, expected)

    def test_changed_source_bytes_rejected_before_semantics(self):
        for relative in build.INPUT_SHA256:
            with self.subTest(source=relative), mirror_inputs() as root:
                path = root / relative
                path.write_bytes(path.read_bytes() + b"\n")
                with self.assertRaises(ValueError):
                    build.load_inputs(root)

    def test_missing_pinned_source_is_not_substituted(self):
        with mirror_inputs() as root:
            (root / build.DATA_REL).unlink()
            with self.assertRaises((ValueError, FileNotFoundError)):
                build.load_inputs(root)

    def test_wrong_case_identity_or_certificate_rejected_after_test_repinning(self):
        mutations = (
            lambda value: value.update(instance_id="UC-s001"),
            lambda value: value.update(status="GLOBAL_CENTER"),
            lambda value: value["provenance"].update(run_id=37637475386),
            lambda value: value["certificate"].update(strict=False),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index), mirror_inputs() as root:
                case = read_json(root, build.CASE_REL)
                mutate(case)
                write_json(root, build.CASE_REL, case)
                with self.assertRaises(ValueError):
                    load_with_test_pins(root, build.CASE_REL)

    def test_wrong_witness_cannot_prove_nonglobality(self):
        with mirror_inputs() as root:
            case = read_json(root, build.CASE_REL)
            case["exact"]["capacity"]["witness_mask"] = case["certificate"]["center"]["mask"]
            write_json(root, build.CASE_REL, case)
            with self.assertRaises(ValueError):
                load_with_test_pins(root, build.CASE_REL)

    def test_incomplete_and_duplicate_neighborhoods_rejected(self):
        for mode in ("missing", "duplicate"):
            with self.subTest(mode=mode), mirror_inputs() as root:
                with (root / build.NEIGHBORS_REL).open(encoding="utf-8", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                if mode == "missing":
                    rows.pop()
                else:
                    rows[-1] = dict(rows[0])
                rewrite_neighbor_fixture(root, rows)
                with self.assertRaises(ValueError):
                    load_with_test_pins(root, build.NEIGHBORS_REL, build.CASE_REL)

    def test_corrupt_neighbor_weight_is_not_only_plotted(self):
        with mirror_inputs() as root:
            with (root / build.NEIGHBORS_REL).open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[0]["weight"] = str(int(rows[0]["weight"]) + 1)
            rewrite_neighbor_fixture(root, rows)
            with self.assertRaises(ValueError):
                load_with_test_pins(root, build.NEIGHBORS_REL, build.CASE_REL)

    def test_incomplete_or_adaptive_main_metadata_rejected(self):
        changes = ({"status": "INCOMPLETE_MAIN"}, {"complete_runs": 6303},
                   {"completed_search_calls": 31519999}, {"adaptive_parameters": True})
        for change in changes:
            with self.subTest(change=change), mirror_inputs() as root:
                analysis = read_json(root, build.ANALYSIS_REL)
                analysis.update(change)
                write_json(root, build.ANALYSIS_REL, analysis)
                with self.assertRaises(ValueError):
                    load_with_test_pins(root, build.ANALYSIS_REL)

    def test_duplicate_and_changed_outcome_group_rejected(self):
        for mode in ("duplicate", "successes", "runs"):
            with self.subTest(mode=mode), mirror_inputs() as root:
                analysis = read_json(root, build.ANALYSIS_REL)
                group = next(row for row in analysis["descriptive_groups"]
                             if row["task"] == "Jump4" and row["start"] == "cloned"
                             and row["method"] == "baseline" and row["series"] == "main")
                if mode == "duplicate":
                    analysis["descriptive_groups"].append(dict(group))
                elif mode == "successes":
                    group["escapes"] = 9
                else:
                    group["runs"] = 29
                write_json(root, build.ANALYSIS_REL, analysis)
                with self.assertRaises(ValueError):
                    load_with_test_pins(root, build.ANALYSIS_REL)


class MathematicalIllustrationTests(CIOnlyTests):
    def test_mutation_probability_matches_independent_exact_target_formula(self):
        with localcontext() as context:
            context.prec = 60
            for text in ("0.005", "0.01", "0.03", "0.1"):
                probability = Decimal(text)
                expected = probability ** 3 * (1 - probability) ** 97
                actual = build.mutation_probability(float(text), n=100, r=3)
                with self.subTest(p=text):
                    self.assertTrue(math.isclose(actual, float(expected), rel_tol=1e-12, abs_tol=0.0))

    def test_mutation_endpoints_and_single_target_peak(self):
        self.assertEqual(build.mutation_probability(0, n=100, r=3), 0)
        self.assertEqual(build.mutation_probability(1, n=100, r=3), 0)
        self.assertEqual(build.mutation_probability(0, n=3, r=0), 1)
        self.assertEqual(build.mutation_probability(1, n=3, r=3), 1)
        self.assertGreater(build.mutation_probability(.03), build.mutation_probability(.01))
        self.assertGreater(build.mutation_probability(.03), build.mutation_probability(.05))

    def test_invalid_mutation_domains_rejected(self):
        for probability, n, r in ((-.01, 100, 3), (1.01, 100, 3),
                                  (float("nan"), 100, 3), (float("inf"), 100, 3),
                                  (.01, 0, 0), (.01, 3, -1), (.01, 3, 4)):
            with self.subTest(p=probability, n=n, r=r), self.assertRaises(ValueError):
                build.mutation_probability(probability, n=n, r=r)

    def test_lambda_illustration_is_an_independently_reconstructed_schedule(self):
        rows = build.lambda_example()
        self.assertEqual([row["generation"] for row in rows], list(range(6)))
        self.assertEqual(rows[0]["event"], "початок")
        self.assertEqual(rows[0]["lambda"], 10)
        self.assertEqual([row["event"] for row in rows[1:]],
                         ["без поліпшення"] * 4 + ["строге поліпшення"])
        with localcontext() as context:
            context.prec = 60
            factor = Decimal("1.5")
            growth = factor.sqrt().sqrt()
            expected = Decimal(10)
            for row in rows[1:]:
                expected = (max(Decimal(1), expected / factor)
                            if row["event"] == "строге поліпшення"
                            else min(Decimal(40), expected * growth))
                self.assertTrue(math.isclose(row["lambda"], float(expected), rel_tol=1e-12, abs_tol=1e-12))
        self.assertAlmostEqual(rows[4]["lambda"], 15, places=12)
        self.assertAlmostEqual(rows[5]["lambda"], 10, places=12)

    def test_toy_crossover_uses_exact_probabilities_not_simulation(self):
        probabilities = build.toy_crossover_probabilities()
        self.assertEqual(probabilities, [Fraction(0), Fraction(1, 4)])
        self.assertTrue(all(type(value) is Fraction for value in probabilities))
        weights, profits, capacity = (2, 2, 1, 1), (2, 2, 2, 2), 2
        independently_enumerated = []
        for first, second in (("1000", "0100"), ("0010", "0001")):
            variable = [i for i in range(4) if first[i] != second[i]]
            successes = 0
            for choices in itertools.product((0, 1), repeat=len(variable)):
                bits = list(first)
                for index, take_second in zip(variable, choices):
                    bits[index] = second[index] if take_second else first[index]
                weight = sum(weights[i] for i in range(4) if bits[i] == "1")
                profit = sum(profits[i] for i in range(4) if bits[i] == "1")
                successes += int(weight <= capacity and profit > 2)
            independently_enumerated.append(Fraction(successes, 2 ** len(variable)))
        self.assertEqual(probabilities, independently_enumerated)


if __name__ == "__main__":
    unittest.main()
