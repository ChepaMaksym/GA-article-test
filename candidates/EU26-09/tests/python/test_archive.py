from __future__ import annotations

import unittest

from eu2609.archive import ArtifactError, parse_artifact

from test_support import CONTRACT, raw_payload, replace_once


class ArtifactHappyPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = raw_payload()
        cls.result = parse_artifact(cls.payload, CONTRACT)

    def test_run_count(self) -> None:
        self.assertEqual(len(self.result.runs), 500)

    def test_run_ids_are_contiguous(self) -> None:
        self.assertEqual(tuple(row.run_id for row in self.result.runs), tuple(range(1, 501)))

    def test_all_runs_solved(self) -> None:
        self.assertTrue(all(row.solved for row in self.result.runs))

    def test_exact_totals(self) -> None:
        self.assertEqual(dict(self.result.totals), CONTRACT["endpoint"]["raw_totals"])

    def test_exact_means(self) -> None:
        self.assertEqual(dict(self.result.means), CONTRACT["endpoint"]["raw_means"])

    def test_raw_container_shape(self) -> None:
        self.assertEqual(self.result.bytes_count, 48918)
        self.assertEqual(self.result.lf_count, 522)
        self.assertFalse(self.payload.endswith(b"\n"))

    def test_first_and_last_seed_derivation(self) -> None:
        endpoint = CONTRACT["endpoint"]
        self.assertEqual(endpoint["base_seed"] + self.result.runs[0].run_id, 885480222)
        self.assertEqual(endpoint["base_seed"] + self.result.runs[-1].run_id, 885480721)

    def test_generated_mode_accepts_same_payload(self) -> None:
        generated = parse_artifact(
            self.payload,
            CONTRACT,
            require_frozen_container=False,
            require_frozen_endpoint=False,
        )
        self.assertEqual(generated.runs, self.result.runs)


class ArtifactMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = raw_payload()

    def assertRejected(self, payload: bytes, *, frozen_container: bool = False) -> None:  # noqa: N802
        with self.assertRaises(ArtifactError):
            parse_artifact(
                payload,
                CONTRACT,
                require_frozen_container=frozen_container,
                require_frozen_endpoint=False,
            )

    def test_rejects_non_utf8(self) -> None:
        marker = "λ".encode("utf-8")
        self.assertRejected(self.payload.replace(marker, b"\xff\xff", 1))

    def test_rejects_cr(self) -> None:
        self.assertRejected(self.payload.replace(b"\n", b"\r", 1))

    def test_rejects_nul(self) -> None:
        self.assertRejected(replace_once(self.payload, b"OneMax", b"One\x00ax"))

    def test_rejects_seed_metadata_change(self) -> None:
        self.assertRejected(replace_once(self.payload, b"Seed: 885480221", b"Seed: 885480220"))

    def test_rejects_problem_metadata_change(self) -> None:
        self.assertRejected(replace_once(self.payload, b"Problem: OneMax", b"Problem: OneMox"))

    def test_rejects_separator_change(self) -> None:
        self.assertRejected(self.payload.replace(b"-", b"=", 1))

    def test_rejects_missing_run(self) -> None:
        lines = self.payload.split(b"\n")
        self.assertEqual(len(lines), 523)
        self.assertRejected(b"\n".join(lines[:18] + lines[19:]))

    def test_rejects_duplicate_run_id(self) -> None:
        self.assertRejected(replace_once(self.payload, b"Run: 2    Gens:", b"Run: 1    Gens:"))

    def test_rejects_noncanonical_run_id(self) -> None:
        self.assertRejected(replace_once(self.payload, b"Run: 1    Gens:", b"Run: 01    Gens:"))

    def test_rejects_unsolved_run(self) -> None:
        self.assertRejected(self.payload.replace(b"Solved: True", b"Solved: False", 1))

    def test_rejects_odd_evaluation_count(self) -> None:
        self.assertRejected(self.payload.replace(b"Evals: 1042", b"Evals: 1043", 1))

    def test_rejects_evaluation_accounting_lower_bound(self) -> None:
        self.assertRejected(self.payload.replace(b"Gens: 217", b"Gens: 700", 1))

    def test_rejects_lambda_probability_mismatch(self) -> None:
        self.assertRejected(
            self.payload.replace("λ: 17 p:".encode(), "λ: 18 p:".encode(), 1)
        )

    def test_rejects_zero_probability(self) -> None:
        old = b"0.17085937499999793"
        self.assertRejected(replace_once(self.payload, old, b"0.00000000000000000"))

    def test_rejects_nonfinite_probability_syntax(self) -> None:
        old = b"0.17085937499999793"
        self.assertRejected(replace_once(self.payload, old, b"nan"))

    def test_rejects_footer_value_change(self) -> None:
        self.assertRejected(replace_once(self.payload, b"196.336", b"196.337"))

    def test_rejects_footer_label_change(self) -> None:
        self.assertRejected(replace_once(self.payload, b"Average lambda:", b"Average Lambda:"))

    def test_rejects_footer_reordering(self) -> None:
        old = b"Average fitness:100.0\nAverage lambda:9.892"
        new = b"Average lambda:9.892\nAverage fitness:100.0"
        self.assertRejected(replace_once(self.payload, old, new))

    def test_rejects_row_tab_spacing(self) -> None:
        self.assertRejected(replace_once(self.payload, b"Run: 1    Gens:", b"Run: 1\t   Gens:"))

    def test_frozen_container_rejects_terminal_lf(self) -> None:
        self.assertRejected(self.payload + b"\n", frozen_container=True)

    def test_frozen_container_rejects_byte_change(self) -> None:
        mutated = replace_once(self.payload, b"OneMax", b"OneMox")
        self.assertRejected(mutated, frozen_container=True)

    def test_rejects_payload_that_is_not_bytes(self) -> None:
        with self.assertRaises(ArtifactError):
            parse_artifact("not bytes", CONTRACT)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
