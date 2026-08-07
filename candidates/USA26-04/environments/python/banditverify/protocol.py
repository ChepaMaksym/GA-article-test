"""Fail-closed validation of the frozen protocol and absence declarations."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import subprocess
from typing import Any

from .canonical import canonical_json, sha256_file
from .provenance import repository_root
from .security import require_exact_keys, strict_json_load


CANDIDATE = Path(__file__).resolve().parents[3]

SOURCE_FIELDS = (
    "source_id",
    "kind",
    "url",
    "revision_or_path",
    "accessed_utc",
    "bytes",
    "sha256",
    "license_status",
)
EXPECTED_SOURCE_ROWS = {
    "NSF_FULL_TEXT": {
        "source_id": "NSF_FULL_TEXT",
        "kind": "legal_full_text",
        "url": "https://par.nsf.gov/servlets/purl/10568003",
        "revision_or_path": "NSF-PAR record 10568003",
        "accessed_utc": "2026-08-07",
        "bytes": "3765486",
        "sha256": "808fa86ff865d7228959c39d6793c8d4e18d965ea37269d340371f9ff8a1effb",
        "license_status": "ACM permission notice; no code license",
    },
    "ARXIV_PDF": {
        "source_id": "ARXIV_PDF",
        "kind": "author_manuscript",
        "url": "https://arxiv.org/pdf/2406.15976v1",
        "revision_or_path": "arXiv:2406.15976v1",
        "accessed_utc": "2026-08-07",
        "bytes": "3554426",
        "sha256": "74f07de64535fdf3e3a058a196ee95ec30c8dd8b6d94e39eaa8e0fb7d4002543",
        "license_status": "arXiv nonexclusive distribution license",
    },
    "ARXIV_SOURCE": {
        "source_id": "ARXIV_SOURCE",
        "kind": "source_archive",
        "url": "https://arxiv.org/e-print/2406.15976v1",
        "revision_or_path": "arXiv:2406.15976v1",
        "accessed_utc": "2026-08-07",
        "bytes": "4741270",
        "sha256": "d64694271e3f57a409ad7be419db835cb1dc90d572392dd64a15d871cc8db017",
        "license_status": "arXiv nonexclusive distribution license",
    },
    "ARXIV_MAIN_TEX": {
        "source_id": "ARXIV_MAIN_TEX",
        "kind": "source_archive_member",
        "url": "https://arxiv.org/e-print/2406.15976v1",
        "revision_or_path": "AdaMAD-v2.tex",
        "accessed_utc": "2026-08-07",
        "bytes": "66195",
        "sha256": "1fb58c7a7c6a080e27ffb23f0c78d4baacee761b071fe74398c90458516dc638",
        "license_status": "arXiv nonexclusive distribution license",
    },
    "AUTHOR_FORK_REPO": {
        "source_id": "AUTHOR_FORK_REPO",
        "kind": "author-named_repository",
        "url": "https://github.com/andrewni2002/propeller",
        "revision_or_path": "commit 19cd3291bdc85cc51ad8ae2d442726e5e141841e; tree 9d4a59e74f8ac1987323ef5ca87dea00ee5eff39",
        "accessed_utc": "2026-08-07",
        "bytes": "",
        "sha256": "",
        "license_status": "EPL-2.0 OR GPL-2.0-or-later WITH Classpath-exception-2.0",
    },
    "AUTHOR_FORK_LICENSE": {
        "source_id": "AUTHOR_FORK_LICENSE",
        "kind": "repository_member",
        "url": "https://github.com/andrewni2002/propeller/blob/19cd3291bdc85cc51ad8ae2d442726e5e141841e/LICENSE",
        "revision_or_path": "19cd329:LICENSE",
        "accessed_utc": "2026-08-07",
        "bytes": "14199",
        "sha256": "721c2da257578bace3332b14d8ea06643d7d26753e7ef25a837b4e904edc0bf5",
        "license_status": "EPL-2.0 OR GPL-2.0-or-later WITH Classpath-exception-2.0",
    },
    "PROPELLER_UPSTREAM": {
        "source_id": "PROPELLER_UPSTREAM",
        "kind": "related_upstream_repository",
        "url": "https://github.com/lspector/propeller",
        "revision_or_path": "commit 847341e4d8dd632b9aef961cfdc170ebd23b8bd8; tree 2054bcbb16bdcac6774fcdc9b87b2f668d8c2214",
        "accessed_utc": "2026-08-07",
        "bytes": "",
        "sha256": "",
        "license_status": "EPL-2.0 OR GPL-2.0-or-later WITH Classpath-exception-2.0; temporal comparator only",
    },
}
EXPECTED_BANDIT_TEXT = {
    "Ackley": "10.1",
    "Griewank": "4.69e-3",
    "Rastrigin": "3686",
    "Rosenbrock": "105",
    "Sphere": "5.56e-8",
    "Linear": "-2.91e46",
}
REQUIRED_ABSENCES = {
    "paper_specific_controller_code": False,
    "paper_pinned_code_revision": False,
    "continuous_mutation_transition": False,
    "controller_initial_values": False,
    "controller_initial_momenta": False,
    "controller_initial_histories": False,
    "empty_or_partial_history_rule": False,
    "argmax_tie_break": False,
    "upper_boundary_rule": False,
    "rng_family": False,
    "rng_stream_partition": False,
    "seed_ledger": False,
    "raw_per_run_results": False,
    "numeric_confidence_intervals": False,
    "environment_lock": False,
}
EXPECTED_BINDING = {
    "freeze_commit": "c76c7ebf26777c52f2ff9a78482d894534dfb94b",
    "publication_remap": {
        "prepublication_local_commit": "a8322b17dcd8e6f722b6d70390f24262f5bcbff2",
        "published_remote_commit": "c76c7ebf26777c52f2ff9a78482d894534dfb94b",
        "shared_tree": "f836090953f8b70374495c78f57dc009e455316a",
        "shared_parent": "eeac926e15107503377cbe09cdc8e830a6607fa5",
        "mapping_scope": "PROVENANCE_ONLY_NO_SCOPE_OR_TARGET_CHANGES",
    },
    "sources_csv_git_blob": "4a223488cbc08f4f5bbb0ee3bc4f469164a6af9d",
    "sources_csv_sha256": "023b7b309617b221fcd9687b7c31adc02e989ef5d2b6802e6cafcc28f4b05949",
    "protocol_json_git_blob": "4ef5afcf68a8ec6dd984e457d2d49db852a635a1",
    "protocol_json_frozen_sha256": "1cdb56c4280a2363e3b0c36eb25fea5901c751cc6bcd58f0faf4652a4cefa492",
    "table1_csv_git_blob": "67333e19a7e440e6aa4e9837d238d3463d326e61",
    "table1_csv_sha256": "727bbbaa4d5e475178067c8af329f2d1e4330aab95682582cf0d034b36e483cb",
}
EXPECTED_PRIMARY = {
    "method": "Bandit",
    "function": "rastrigin",
    "dimension": 100,
    "initial_sd": 10.0,
    "non_elite_population": 100,
    "elite_population": 1,
    "selection": "truncation",
    "truncation_size": 10,
    "generations": 1000,
    "reported_runs": 50,
    "reported_mean_text": "3686",
    "rounding_interval_descriptive_only": [3685.5, 3686.5],
    "executable_target": False,
}
EXPECTED_REWARD_SEMANTICS = {
    "P1": "mean(parent_error - child_error)",
    "P2": "mean(log1p(parent_error) - log1p(child_error))",
    "P3": "mean(log1p(child_error) - log1p(parent_error))",
}
EXPECTED_CONTROLLER_CONSTANTS = {
    "ensemble_bandits": 5,
    "tile_codings_per_bandit": 20,
    "history_length": 100,
    "learning_rate_log10_uniform": [-4.0, -3.0],
    "momentum": 0.9,
    "epsilon_start": 1.0,
    "epsilon_end": 0.01,
    "epsilon_anneal_generations": 5,
    "function_min_sampling_noise_tiles": 7,
    "log_sigma_range": [-100.0, 100.0],
    "base_tile_width": 0.03,
    "tile_widths": [0.18, 0.21, 0.24, 0.27, 0.30, 0.33, 0.36, 0.39],
    "tile_offsets": [0.0, 0.03, 0.06, 0.09, 0.12, 0.15],
}
EXPECTED_HARDWARE = {
    "timing_repeats": 5,
    "required_roles": ["work_4core", "work_8core", "github_actions_4core"],
    "thread_limit": 1,
}


def _typed_equal(actual: Any, expected: Any, context: str) -> None:
    if canonical_json(actual) != canonical_json(expected):
        raise AssertionError(f"{context} changed or has a type mismatch")


def _validate_git_binding() -> None:
    repository = repository_root(CANDIDATE)
    remap = EXPECTED_BINDING["publication_remap"]
    freeze_twins = (
        remap["prepublication_local_commit"],
        remap["published_remote_commit"],
    )
    bindings = (
        (
            "candidates/USA26-04/source_manifest/sources.csv",
            EXPECTED_BINDING["sources_csv_git_blob"],
            EXPECTED_BINDING["sources_csv_sha256"],
        ),
        (
            "candidates/USA26-04/config/protocol.json",
            EXPECTED_BINDING["protocol_json_git_blob"],
            EXPECTED_BINDING["protocol_json_frozen_sha256"],
        ),
        (
            "candidates/USA26-04/fixtures/published_table1_descriptive.csv",
            EXPECTED_BINDING["table1_csv_git_blob"],
            EXPECTED_BINDING["table1_csv_sha256"],
        ),
    )
    resolved_twins: list[str] = []
    ancestor_twins: list[str] = []
    for freeze in freeze_twins:
        try:
            resolved = subprocess.check_output(
                ["git", "rev-parse", f"{freeze}^{{commit}}"],
                cwd=repository,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except subprocess.CalledProcessError:
            continue
        if resolved != freeze:
            raise AssertionError("a preregistration freeze twin did not resolve exactly")
        resolved_twins.append(freeze)

        tree = subprocess.check_output(
            ["git", "show", "-s", "--format=%T", freeze],
            cwd=repository,
            text=True,
        ).strip()
        parent = subprocess.check_output(
            ["git", "show", "-s", "--format=%P", freeze],
            cwd=repository,
            text=True,
        ).strip()
        if tree != remap["shared_tree"] or parent != remap["shared_parent"]:
            raise AssertionError("publication-remap freeze twins are not exact tree/parent twins")

        for path, expected_blob, expected_sha in bindings:
            blob = subprocess.check_output(
                ["git", "rev-parse", f"{freeze}:{path}"],
                cwd=repository,
                text=True,
            ).strip()
            content = subprocess.check_output(
                ["git", "show", f"{freeze}:{path}"], cwd=repository
            )
            if blob != expected_blob or hashlib.sha256(content).hexdigest() != expected_sha:
                raise AssertionError(f"frozen Git object binding changed for {path}")

        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", freeze, "HEAD"],
            cwd=repository,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if ancestry.returncode == 0:
            ancestor_twins.append(freeze)
        elif ancestry.returncode != 1:
            raise AssertionError("could not establish preregistration freeze ancestry")

    if not resolved_twins:
        raise AssertionError("both preregistration freeze twins are unavailable")
    if len(ancestor_twins) != 1:
        raise AssertionError(
            "exactly one publication-remap freeze twin must be an ancestor of HEAD"
        )
    if ancestor_twins[0] != EXPECTED_BINDING["freeze_commit"]:
        raise AssertionError("published remote preregistration freeze is not the HEAD ancestor")


def validate_protocol(candidate: Path = CANDIDATE) -> dict[str, Any]:
    protocol = strict_json_load(candidate / "config" / "protocol.json")
    require_exact_keys(
        protocol,
        {
            "candidate_id",
            "frozen_date",
            "protocol_id",
            "scope",
            "overall_status",
            "published_result_status",
            "registry_status",
            "pass_full_forbidden",
            "table1_execution_forbidden",
            "full_ga_forbidden",
            "preregistration_binding",
            "primary_descriptive_cell",
            "reward_semantics",
            "controller_constants_reported",
            "required_absences",
            "hardware",
        },
        "protocol",
    )
    required_top = {
        "candidate_id": "USA26-04",
        "frozen_date": "2026-08-07",
        "protocol_id": "USA26-04-FORMULA-PORTABILITY-v1",
        "scope": "FORMULA_AND_AMBIGUITY_VALIDATION_ONLY",
        "overall_status": "BLOCKED_G5_G9",
        "published_result_status": "INCONCLUSIVE_PUBLISHED_RESULT",
        "registry_status": "conditional_noneligible",
        "pass_full_forbidden": True,
        "table1_execution_forbidden": True,
        "full_ga_forbidden": True,
    }
    for key, expected in required_top.items():
        _typed_equal(protocol.get(key), expected, f"protocol.{key}")
    _typed_equal(
        protocol.get("preregistration_binding"), EXPECTED_BINDING, "preregistration binding"
    )
    _typed_equal(protocol.get("primary_descriptive_cell"), EXPECTED_PRIMARY, "primary cell")
    _typed_equal(
        protocol.get("reward_semantics"), EXPECTED_REWARD_SEMANTICS, "reward semantics"
    )
    _typed_equal(
        protocol.get("controller_constants_reported"),
        EXPECTED_CONTROLLER_CONSTANTS,
        "controller constants",
    )
    _typed_equal(protocol.get("required_absences"), REQUIRED_ABSENCES, "absence manifest")
    _typed_equal(protocol.get("hardware"), EXPECTED_HARDWARE, "hardware contract")
    _validate_git_binding()

    sources_path = candidate / "source_manifest" / "sources.csv"
    if sha256_file(sources_path) != EXPECTED_BINDING["sources_csv_sha256"]:
        raise AssertionError("sources.csv no longer matches its frozen byte identity")
    with sources_path.open(
        encoding="utf-8", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise AssertionError("sources.csv field order/schema changed")
        source_rows = list(reader)
    source_ids = [row.get("source_id") for row in source_rows]
    if len(source_ids) != len(set(source_ids)):
        raise AssertionError("sources.csv contains duplicate source IDs")
    if set(source_ids) != set(EXPECTED_SOURCE_ROWS):
        raise AssertionError("sources.csv exact source ID set changed")
    for row in source_rows:
        if row != EXPECTED_SOURCE_ROWS[row["source_id"]]:
            raise AssertionError(f"source identity field changed for {row['source_id']}")

    with (candidate / "fixtures" / "published_table1_descriptive.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        table = list(csv.DictReader(handle))
    table_path = candidate / "fixtures" / "published_table1_descriptive.csv"
    if sha256_file(table_path) != EXPECTED_BINDING["table1_csv_sha256"]:
        raise AssertionError("Table 1 CSV no longer matches its frozen byte identity")
    if len(table) != 6 or {row["problem"] for row in table} != set(EXPECTED_BANDIT_TEXT):
        raise AssertionError("Table 1 descriptive rows changed")
    for row in table:
        if row["bandit_text"] != EXPECTED_BANDIT_TEXT[row["problem"]]:
            raise AssertionError(f"Table 1 text changed for {row['problem']}")
        if row["executable_target"].lower() != "false":
            raise AssertionError("a descriptive Table 1 value became executable")
    primary_rows = [row for row in table if row["role"] == "primary_descriptive_only"]
    if len(primary_rows) != 1 or primary_rows[0]["problem"] != "Rastrigin":
        raise AssertionError("the primary descriptive cell changed")

    return {
        "protocol_id": protocol["protocol_id"],
        "scope": protocol["scope"],
        "paper_level_status": protocol["overall_status"],
        "published_result_status": protocol["published_result_status"],
        "registry_status": protocol["registry_status"],
        "source_identity_count": len(EXPECTED_SOURCE_ROWS),
        "absence_count": len(REQUIRED_ABSENCES),
        "descriptive_target_count": len(table),
        "executable_target_count": 0,
    }
