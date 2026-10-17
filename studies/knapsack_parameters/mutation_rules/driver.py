"""CI-only unit validation, never a KPLIB experiment launcher."""
from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
from pathlib import Path
import unittest

from . import authority as a


def mathematical_receipt():
    """Independent high-precision domain check, not an empirical GA result."""
    with localcontext() as ctx:
        ctx.prec = 80
        n = Decimal(100)
        reliability = n ** 3
        # ln(e*n*R)=1+ln(n)+ln(R); do not drop the leading 1.
        threshold = n * (n / (n - 1)) ** 99 * (Decimal(1) + n.ln() + reliability.ln())
        a.require(threshold > 5000, "Registered bounded equivalence is false")
        return {"schema": "ga-mutation-rules-mathematical-receipt-v1", "protocol_id": a.PROTOCOL,
                "n": 100, "R": 1000000, "initial_r": 1, "initial_u": 0,
                "threshold_decimal": str(threshold), "budget": 5000,
                "full_generations": 172, "terminal_prefix_children": 12,
                "max_completed_generation_counter_without_success": 4988,
                "first_potential_complete_generation_without_success": int(threshold // 29) + 1,
                "first_potential_update_new_calls_without_success": 29 * (int(threshold // 29) + 1),
                "threshold_above_total_new_budget": True, "method": "Decimal, precision 80",
                "interpretation": "Transferred controller cannot activate in this bounded domain; no numerical article replication or KPLIB search was performed"}


def run_tests(output):
    provenance = a.check_preflight(output)
    output = Path(output)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    # The unchanged historical authority deliberately rejects a new module.
    # Reuse only pure core/reconstruction fixtures, never its phase contract tests.
    for module in ("studies.adaptive_parameters.mutation_only.test_mutation_only",
                   "studies.knapsack_parameters.mutation_population.tests.test_core",
                   "studies.knapsack_parameters.mutation_rules.tests.test_authority",
                   "studies.knapsack_parameters.mutation_rules.tests.test_controller",
                   "studies.knapsack_parameters.mutation_rules.tests.test_comparison"):
        suite.addTests(loader.loadTestsFromName(module))
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    proof = mathematical_receipt() if result.wasSuccessful() else None
    if proof is not None:
        a.write_json(output / "mathematical_receipt.json", proof)
    a.write_json(output / "tests_receipt.json", {**provenance, "tests_passed": result.wasSuccessful(),
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "scientific_search_performed": False,
        "mathematical_domain_verified": proof is not None,
        "admitted_new_published_controllers": 1})
    a.write_manifest(output)
    a.verify_manifest(output)
    print((output / "tests.txt").read_text(encoding="utf-8"))
    a.require(result.wasSuccessful() and result.testsRun > 0 and not result.skipped,
              "Independent CI checks did not all pass")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "tests"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "preflight":
        a.preflight(args.output)
    else:
        run_tests(args.output)


if __name__ == "__main__":
    main()
