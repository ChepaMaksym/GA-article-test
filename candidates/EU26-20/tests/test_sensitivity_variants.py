#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import random
import sys
import unittest
from unittest import mock

import numpy as np

OLD_DIR = Path(__file__).resolve().parents[1] / "old"
sys.path.insert(0, str(OLD_DIR))
SPEC = importlib.util.spec_from_file_location(
    "eu26_20_sensitivity_variants", OLD_DIR / "sensitivity_variants.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load sensitivity variants")
SENS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SENS
SPEC.loader.exec_module(SENS)
BASE = SENS.base


class SensitivityVariantTests(unittest.TestCase):
    def test_variant_registry_is_exactly_preregistered(self) -> None:
        self.assertEqual(
            set(SENS.VARIANTS),
            {
                "legacy_mt19937_rng",
                "source_rounding",
                "source_stop19",
                "numeric_identifier_geometry",
                "source_like_bundle",
            },
        )

    def test_source_rounding_is_material_at_initial_rates(self) -> None:
        self.assertEqual(SENS.source_round_counts(10, 0.9, 0.4), (8, 4))
        self.assertEqual(BASE.paper_offspring_counts(10, 0.9, 0.4), (10, 4))

    def test_legacy_adapter_is_repeatable(self) -> None:
        first = SENS.LegacyRandomAdapter(7)
        second = SENS.LegacyRandomAdapter(7)
        self.assertEqual(first.integers(1, 11), second.integers(1, 11))
        np.testing.assert_array_equal(
            first.choice(tuple(range(20)), 5, False),
            second.choice(tuple(range(20)), 5, False),
        )

    def test_numeric_geometry_uses_identifiers(self) -> None:
        x = np.array([[0, 100, 0], [1, 100, 1], [2, 100, 2]], dtype=float)
        feature_geometry = BASE.FeatureGeometry(x, [0, 1, 2])
        numeric_geometry = SENS.NumericIdentifierGeometry(x, [0, 1, 2])
        self.assertEqual(feature_geometry.solution_distance([0], [2]), 0.0)
        self.assertEqual(numeric_geometry.solution_distance([0], [2]), 2.0)

    def test_patch_context_restores_primary_globals(self) -> None:
        originals = (
            BASE.np.random.default_rng,
            BASE.FeatureGeometry,
            BASE.paper_offspring_counts,
            BASE.generate_diverse_candidates,
        )
        with SENS.patched_variant(SENS.VARIANTS["source_like_bundle"]):
            self.assertIs(BASE.FeatureGeometry, SENS.NumericIdentifierGeometry)
            self.assertIs(BASE.paper_offspring_counts, SENS.source_round_counts)
            self.assertIs(
                BASE.generate_diverse_candidates,
                SENS.legacy_generate_diverse_candidates,
            )
            adapter = BASE.np.random.default_rng(1)
            self.assertIsInstance(adapter, SENS.LegacyRandomAdapter)
        restored = (
            BASE.np.random.default_rng,
            BASE.FeatureGeometry,
            BASE.paper_offspring_counts,
            BASE.generate_diverse_candidates,
        )
        self.assertEqual(restored, originals)

    def test_run_variant_is_never_primary_eligible(self) -> None:
        fake = {
            "schema": "eu26-20-colon-paper-old-v1",
            "profile": "paper_cleanroom_feature_geometry",
            "offspring_rounding": "paper_ceil",
            "geometry": "feature_vectors_euclidean",
            "features": [1, 2],
            "subset_length": 2,
            "best_accuracy": 0.9,
            "trace": [],
        }
        with mock.patch.object(BASE, "run_paper_profile", return_value=fake) as runner:
            result = SENS.run_variant(
                np.zeros((10, 5)),
                np.array([1] * 5 + [2] * 5),
                [0, 1, 2, 3, 4],
                1,
                "source_stop19",
            )
        self.assertFalse(result["primary_gate_eligible"])
        self.assertEqual(result["profile"], "old_sensitivity_only")
        self.assertEqual(result["variant"], "source_stop19")
        config = runner.call_args.args[4]
        self.assertEqual(config.stop_after, 19)


if __name__ == "__main__":
    unittest.main()
