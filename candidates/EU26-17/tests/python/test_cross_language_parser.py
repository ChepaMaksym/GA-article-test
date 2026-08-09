from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


CANDIDATE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE_ROOT / "environments" / "python"))

from eu2617.validation import _parse_octave_tsv  # noqa: E402


class CrossLanguageParserTests(unittest.TestCase):
    def test_independent_ledger_parser_requires_every_frozen_case(self) -> None:
        fixture = json.loads(
            (CANDIDATE_ROOT / "fixtures" / "transition_cases.json").read_text(
                encoding="utf-8"
            )
        )
        lines = ["name\tgdm\tmutation_rate\tcrossover_rate\tbranch"]
        for case in fixture["cases"]:
            expected = case["expected"]
            lines.append(
                "\t".join(
                    (
                        case["name"],
                        format(expected["gdm"], ".17g"),
                        format(expected["mutation_rate"], ".17g"),
                        format(expected["crossover_rate"], ".17g"),
                        expected["branch"],
                    )
                )
            )
        with tempfile.TemporaryDirectory(prefix="eu2617-ledger-") as directory:
            path = Path(directory) / "octave.tsv"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            report = _parse_octave_tsv(path, fixture)
        self.assertEqual(report["status"], "PASS_CROSS_LANGUAGE")
        self.assertEqual(report["case_count"], len(fixture["cases"]))

        with tempfile.TemporaryDirectory(prefix="eu2617-ledger-") as directory:
            path = Path(directory) / "missing-case.tsv"
            path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "case set"):
                _parse_octave_tsv(path, fixture)


if __name__ == "__main__":
    unittest.main()
