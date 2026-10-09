"""Bounded, CI-only acquisition and provenance audit; no optimizer is executed.

The source snapshots remain byte-identical to the pinned repositories.  Counts
describe retained artifacts, not a numerical reproduction of the paper.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import urllib.request

from studies.knapsack_parameters.lambda_study.contract import (
    AUTHOR_REPO, AUTHOR_SHA, INPUT_REPO, INPUT_SHA, MODULE_ROOT, PROTOCOL_ID,
    authenticate, read_json, require,
    sha256_bytes, write_file_manifest, write_json,
)

ISG_SIZES = (16, 25, 36, 49, 64, 81, 100)
CENSOR_LIMIT = 2_100_000_000
MAX_DOWNLOAD = 128 * 1024 * 1024
MAX_EXTRACTED = 128 * 1024 * 1024
PAPER_URL = "https://mhevia.com/assets/pdf/journal_oplclga.pdf"


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _safe_relative(name: str) -> PurePosixPath:
    require(bool(name) and "\\" not in name
            and not any(re.match(r"^[A-Za-z]:", part) for part in name.split("/")),
            "unsafe archive/tree path")
    path = PurePosixPath(name)
    require(not path.is_absolute() and all(part not in (".", "..")
            for part in name.split("/")), "archive/tree path escapes root")
    return path


def extract_snapshot(archive: bytes, target: Path, expected_prefix: str) -> None:
    """Extract regular files only, validating the entire archive before writes."""
    require(not target.exists(), "snapshot target already exists")
    planned = []
    seen = set()
    total = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
        for member in source.getmembers():
            name = member.name.rstrip("/") if member.isdir() else member.name
            parts = _safe_relative(name).parts
            require(parts[0] == expected_prefix, "unexpected tarball root")
            require(member.isdir() or member.isfile(), "links/special tar members forbidden")
            if len(parts) == 1:
                require(member.isdir(), "archive root must be a directory")
                continue
            relative = PurePosixPath(*parts[1:]).as_posix()
            require(relative not in seen, "duplicate archive member")
            seen.add(relative)
            total += member.size
            require(0 <= member.size <= MAX_DOWNLOAD and total <= MAX_EXTRACTED,
                    "archive extraction exceeds bounded size")
            planned.append((member, relative))
        target.mkdir(parents=True)
        for member, relative in planned:
            destination = target.joinpath(*PurePosixPath(relative).parts)
            require(destination.resolve().is_relative_to(target.resolve()),
                    "archive extraction escapes target")
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                stream = source.extractfile(member)
                require(stream is not None, "unreadable archive member")
                data = stream.read(member.size + 1)
                require(len(data) == member.size, "truncated archive member")
                destination.write_bytes(data)
                destination.chmod(0o755 if member.mode & 0o111 else 0o644)


def verify_snapshot(root: Path, tree: dict, repository: str, revision: str) -> list[dict]:
    require(tree.get("truncated") is False, "GitHub tree is truncated")
    expected = {}
    for item in tree.get("tree", []):
        if item.get("type") == "tree":
            continue
        require(item.get("type") == "blob" and item.get("mode") in ("100644", "100755"),
                "unsupported Git tree object")
        relative = _safe_relative(item["path"]).as_posix()
        require(relative not in expected, "duplicate Git tree path")
        expected[relative] = item
    actual = {path.relative_to(root).as_posix(): path for path in root.rglob("*") if path.is_file()}
    require(set(actual) == set(expected), "archive files differ from pinned Git tree")
    manifest = []
    for relative in sorted(actual):
        data = actual[relative].read_bytes()
        entry = expected[relative]
        require(len(data) == entry["size"], f"Git blob byte length mismatch: {relative}")
        require(git_blob_sha(data) == entry["sha"], f"Git blob mismatch: {relative}")
        manifest.append({"repository": repository, "revision": revision,
                         "path": relative, "bytes": len(data),
                         "git_mode": entry["mode"],
                         "git_blob_sha1": entry["sha"], "sha256": sha256_bytes(data)})
    return manifest


def validate_source_identity(repository: str, revision: str, key: str) -> None:
    expected = {"author": (AUTHOR_REPO, AUTHOR_SHA), "inputs": (INPUT_REPO, INPUT_SHA)}
    require(key in expected and (repository, revision) == expected[key],
            "source identity differs from registered revision")


def _download(url: str, *, github_api: bool = False) -> tuple[bytes, dict]:
    require(os.environ.get("GITHUB_ACTIONS") == "true", "acquisition is GitHub Actions only")
    require(url.startswith("https://"), "HTTPS acquisition required")
    headers = {"User-Agent": "ga-knapsack-bounded-source-audit/1"}
    if github_api:
        require(url.startswith("https://api.github.com/"), "unexpected GitHub API URL")
        headers["Accept"] = "application/vnd.github+json"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        data = response.read(MAX_DOWNLOAD + 1)
        require(len(data) <= MAX_DOWNLOAD, "download exceeds bounded size")
        metadata = {"requested_url": url, "final_url": response.geturl(),
                    "bytes": len(data), "sha256": sha256_bytes(data),
                    "content_type": response.headers.get("Content-Type"),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified")}
    return data, metadata


def acquire_repository(output: Path, key: str, repository: str, revision: str) -> dict:
    validate_source_identity(repository, revision, key)
    api = "https://api.github.com/repos/" + repository
    commit_bytes, commit_metadata = _download(api + "/git/commits/" + revision, github_api=True)
    commit = json.loads(commit_bytes)
    require(commit.get("sha") == revision, "GitHub returned a different commit")
    tree_sha = commit["tree"]["sha"]
    tree_bytes, tree_metadata = _download(api + "/git/trees/" + tree_sha + "?recursive=1", github_api=True)
    tree = json.loads(tree_bytes)
    require(tree.get("sha") == tree_sha, "GitHub returned a different tree")
    archive_url = "https://codeload.github.com/" + repository + "/tar.gz/" + revision
    archive, archive_metadata = _download(archive_url)
    source_dir = output / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / (key + "-commit.json")).write_bytes(commit_bytes)
    (source_dir / (key + "-tree.json")).write_bytes(tree_bytes)
    archive_path = source_dir / (key + "-" + revision + ".tar.gz")
    archive_path.write_bytes(archive)
    target = source_dir / key
    extract_snapshot(archive, target, repository.split("/")[1] + "-" + revision)
    manifest = verify_snapshot(target, tree, repository, revision)
    return {"repository": repository, "revision": revision, "tree_sha": tree_sha,
            "archive": archive_metadata, "commit_api": commit_metadata,
            "tree_api": tree_metadata, "files": manifest, "verified": True}


def validate_ising_bytes(data: bytes, n: int) -> dict:
    """Independent integer-energy check; no optimization or optimum search."""
    require(n in ISG_SIZES, "unregistered Ising size")
    try:
        lines = data.decode("ascii").splitlines()
        require(len(lines) >= 2, "truncated Ising header")
        header = lines[0].split()
        require(len(header) == 2, "invalid Ising header")
        minimum = int(header[0])
        witness = header[1]
        require(len(witness) == n and set(witness) <= {"0", "1"}, "invalid Ising witness")
        require(len(lines[1].split()) == 1, "invalid edge-count line")
        edge_count = int(lines[1])
        require(edge_count == 2 * n and len(lines) == edge_count + 2,
                "missing/truncated/extra Ising edges")
        edges = []
        seen = set()
        side = math.isqrt(n)
        require(side * side == n, "Ising grid is not square")
        for line in lines[2:]:
            fields = line.split()
            require(len(fields) == 3, "invalid Ising edge")
            a, b, coupling = map(int, fields)
            require(0 <= a < n and 0 <= b < n and a != b and coupling in (-1, 1),
                    "invalid Ising endpoint/coupling")
            pair = tuple(sorted((a, b)))
            require(pair not in seen, "duplicate Ising edge")
            seen.add(pair)
            edges.append((a, b, coupling))
        expected_edges = set()
        for a in range(n):
            expected_edges.add(tuple(sorted((a, a // side * side + (a % side + 1) % side))))
            expected_edges.add(tuple(sorted((a, (a + side) % n))))
        require(seen == expected_edges, "Ising topology differs from periodic square grid")
        signs = [1 if bit == "1" else -1 for bit in witness]
        energy = -sum(signs[a] * coupling * signs[b] for a, b, coupling in edges)
        require(energy == minimum, "Ising witness disagrees with energy metadata")
        return {"n": n, "minimum_energy_metadata": minimum, "witness_energy": energy,
                "edge_count": edge_count, "format_verified": True, "witness_verified": True,
                "optimality_independently_proven": False}
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid Ising numeric/ASCII format") from exc


def audit_ising(root: Path, sizes=ISG_SIZES, instance_ids=range(200)) -> dict:
    records, errors = [], []
    for n in sizes:
        for instance_id in instance_ids:
            relative = f"problem_files/IsingSpinGlass_pm_{n}_{instance_id}.txt"
            try:
                data = (root / relative).read_bytes()
                record = validate_ising_bytes(data, n)
                record.update({"path": relative, "instance_id": instance_id,
                               "analyzed": 100 <= instance_id <= 199,
                               "bytes": len(data), "sha256": sha256_bytes(data),
                               "git_blob_sha1": git_blob_sha(data)})
                records.append(record)
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append({"path": relative, "error": str(exc)})
    expected = len(sizes) * len(instance_ids)
    return {"expected_files": expected, "verified_files": len(records),
            "analyzed_verified_files": sum(row["analyzed"] for row in records),
            "prior_verified_files": sum(not row["analyzed"] for row in records),
            "complete": len(records) == expected and not errors,
            "records": records, "errors": errors,
            "witness_scope": "checks attained metadata energy; does not prove global minimality"}


def parse_cpp_config(text: str) -> dict[str, str]:
    """Match token-pair parsing and last-value-wins, with # line comments."""
    tokens = []
    for line in text.splitlines():
        for token in line.split():
            if token.startswith("#"):
                break
            tokens.append(token)
    require(len(tokens) % 2 == 0, "truncated C++ configuration token pair")
    return dict(zip(tokens[::2], tokens[1::2]))


def cpp_seed_identity(config: dict) -> dict:
    seed = int(config["seed"])
    return {"recorded_signed_seed": seed,
            "actual_seed_available": seed != -1,
            "mt19937_seed_uint32": seed % (1 << 32) if seed != -1 else None,
            "semantics": "one mt19937 per batch; signed int seeds convert to unsigned engine seed"}


def parse_python_log(text: str) -> dict:
    header = {}
    for line in text.splitlines():
        if line.startswith("Final results:"):
            break
        for part in line.split("\t"):
            if ":" in part:
                key, value = part.split(":", 1)
                header[key.strip()] = value.strip()
    require(all(key in header for key in ("Seed", "Problem", "Size", "Runs", "Algorithm")),
            "Python log configuration incomplete")
    seed, declared = int(header["Seed"]), int(header["Runs"])
    rows = []
    pattern = re.compile(r"^Final results:\s+Run:\s+(\d+)\s+Gens:\s+(\d+)\s+Evals:\s+(\d+).*Solved:\s+(True|False)\s*$")
    for line in text.splitlines():
        if not line.startswith("Final results:"):
            continue
        match = pattern.match(line)
        require(match is not None, "malformed Python final-result row")
        run, generations, evaluations = map(int, match.groups()[:3])
        rows.append({"run": run, "actual_python_seed": seed + run,
                     "actual_numpy_seed": seed + run,
                     "generations": generations, "evaluations": evaluations,
                     "recorded_solved": match.group(4) == "True"})
    require([row["run"] for row in rows] == list(range(1, declared + 1)),
            "Python log run IDs/count differ from declared runs")
    require(all(0 <= row["actual_numpy_seed"] < 1 << 32 for row in rows),
            "Python log seed outside numpy legacy seed range")
    return {"configuration": header, "base_seed": seed, "declared_runs": declared,
            "retained_runs": len(rows), "actual_seed_rule": "base seed + one-based run, both random and numpy",
            "runs": rows, "seed_provenance": "recorded configuration plus pinned master.py reseeding; no saved RNG state"}


def parse_cpp_dat(text: str) -> list[tuple[float, int]]:
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split()
        require(len(fields) == 2, "malformed C++ dat row")
        fitness, evaluations = float(fields[0]), int(fields[1])
        require(math.isfinite(fitness) and evaluations >= 0, "invalid C++ dat value")
        rows.append((fitness, evaluations))
    return rows


def catalog_results(author: Path) -> dict:
    python_logs, cpp_batches, planned_configs, errors = [], [], [], []
    for path in sorted((author / "Raw").rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(author).as_posix()
        try:
            entry = parse_python_log(path.read_text(encoding="utf-8"))
            entry["path"] = relative
            python_logs.append(entry)
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append({"path": relative, "error": str(exc)})
    results = author / "Goldman-modified" / "results"
    for path in sorted((author / "Goldman-modified" / "config").glob("*.cfg")):
        try:
            config = parse_cpp_config(path.read_text(encoding="utf-8"))
            declared_limit = int(config["eval_limit"]) if "eval_limit" in config else None
            planned_configs.append({"path": path.relative_to(author).as_posix(),
                                    "configuration": config,
                                    "declared_eval_limit": declared_limit,
                                    "declared_eval_limit_exceeds_int32": declared_limit is not None
                                    and not -(1 << 31) <= declared_limit < (1 << 31),
                                    "status": "configuration source, not evidence of executed settings"})
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append({"path": path.relative_to(author).as_posix(), "error": str(exc)})
    for path in sorted(results.glob("*.cfg")):
        relative = path.relative_to(author).as_posix()
        try:
            config = parse_cpp_config(path.read_text(encoding="utf-8"))
            dat = path.with_suffix(".dat")
            require(dat.is_file(), "recorded C++ config has no matching dat")
            rows = parse_cpp_dat(dat.read_text(encoding="utf-8"))
            declared = int(config["runs"])
            require(len(rows) == declared, "recorded C++ dat count differs from cfg runs")
            part_match = re.search(r"_(\d+)\.cfg$", path.name)
            part = part_match.group(1) if part_match else "0"
            is_ising = config.get("problem") == "IsingSpinGlass"
            # Exact static read_results.py mapping: exp_num begins at 100 for
            # ISG part 2, otherwise 0; first 100 are discarded for ISG.
            exp_start = 100 if is_ising and part == "2" else 0
            analyzed = [(index, row) for index, row in enumerate(rows, exp_start + 1)
                        if not is_ising or index > 100]
            declared_limit = int(config["eval_limit"])
            entry = {"path": relative, "dat_path": dat.relative_to(author).as_posix(),
                     "configuration": config, "seed_identity": cpp_seed_identity(config),
                     "declared_runs": declared, "retained_rows": len(rows),
                     "part": part, "analysis_rows": len(analyzed),
                     "discarded_rows": len(rows) - len(analyzed),
                     "analysis_experiment_numbers": [index for index, _ in analyzed],
                     "analysis_suppressed_until_following_part": part == "1",
                     "declared_eval_limit": declared_limit,
                     "declared_eval_limit_exceeds_int32": not -(1 << 31) <= declared_limit < (1 << 31),
                     "effective_eval_limit": None,
                     "effective_limit_status": "unverified compiler/runtime atoi(int), then size_t; do not assume declared value",
                     "censored_rows": sum(fitness != 1.0 or evaluations >= CENSOR_LIMIT
                                          for _, (fitness, evaluations) in analyzed),
                     "censor_limit": CENSOR_LIMIT,
                     "censor_rule": "fitness != 1 OR evaluations >= 2100000000 -> replace by 2100000000",
                     "instance_ids_from_config": [int(config.get("problem_seed", "0")) + run
                                                   for run in range(declared)],
                     "retained_run_rows": [{"zero_based_run": run,
                                            "instance_id": int(config.get("problem_seed", "0")) + run,
                                            "fitness": fitness, "best_attainment_evaluations": evaluations}
                                           for run, (fitness, evaluations) in enumerate(rows)],
                     "reported_evaluations_by_run": [evaluations for _, evaluations in rows],
                     "evaluation_scope": "dat stores record.best().second, not necessarily total evaluations consumed",
                     "shared_rng_batch": True}
            cpp_batches.append(entry)
        except (OSError, KeyError, ValueError, RuntimeError) as exc:
            errors.append({"path": relative, "error": str(exc)})
    paired_dat = {entry["dat_path"] for entry in cpp_batches}
    orphan_dat = [path.relative_to(author).as_posix() for path in sorted(results.glob("*.dat"))
                  if path.relative_to(author).as_posix() not in paired_dat]
    # Small coverage grid binds every retained log/config to its dimensions.
    grid = []
    for entry in python_logs:
        cfg = entry["configuration"]
        grid.append({"language": "Python", "source": entry["path"],
                     "problem": cfg["Problem"], "n": cfg["Size"], "k": cfg.get("k"),
                     "extra": cfg.get("Extra"), "algorithm": cfg["Algorithm"],
                     "lambda_argument": cfg.get("Initial offspring population size"),
                     "runs": entry["retained_runs"], "recorded_seed": entry["base_seed"],
                     "numeric_reproduction": "NOT_EXECUTED"})
    for entry in cpp_batches:
        cfg = entry["configuration"]
        grid.append({"language": "C++", "source": entry["path"],
                     "problem": cfg.get("problem"), "n": cfg.get("length"),
                     "k": cfg.get("k"), "algorithm": cfg.get("optimizer"),
                     "part": entry["part"], "runs": entry["retained_rows"],
                     "analyzed_rows": entry["analysis_rows"], "recorded_seed": cfg.get("seed"),
                     "numeric_reproduction": "NOT_EXECUTED"})
    return {"python_logs": python_logs, "cpp_batches": cpp_batches,
            "planned_cpp_configurations": planned_configs, "coverage_grid": grid,
            "python_log_count": len(python_logs), "cpp_batch_count": len(cpp_batches),
            "errors": errors, "unpaired_dat": orphan_dat,
            "analysis_scope": "integrity/configuration/count/censor classification only; no means/medians/quantiles recomputed"}


def source_semantics(author: Path) -> list[dict]:
    """Source-anchored discrepancies, keeping comments separate from behavior."""
    specifications = [
        ("rounding_python", "Python-code/utils/journalalgorithms.py", "round(self.offspring_size)",
         "Python round uses ties-to-even; printed nearest rounding and prospective half-up are distinct profiles."),
        ("python_final_pool", "Python-code/utils/journalalgorithms.py", "# offspring = []",
         "Mutation offspring remain in the final selection pool alongside crossover offspring in the SA class."),
        ("python_reset", "Python-code/utils/journalalgorithms.py", "elif self.offspring_size == self.offspring_size_max:",
         "Python reset occurs on failure at lambda_max; C++ reset timing must be treated separately."),
        ("python_seed", "Python-code/master.py", "np.random.seed(configuration.seed+run)",
         "Both Python random and numpy receive base seed plus one-based run."),
        ("cpp_rounding", "Goldman-modified/src/LambdaLambda.cpp", "round(lambda)",
         "C++ round uses halfway away from zero; positive lambda therefore rounds half-up."),
        ("cpp_factor", "Goldman-modified/src/LambdaLambda.cpp", "lambda *= 1.1067;",
         "Rounded growth factor 1.1067 differs from exact 1.5^(1/4)."),
        ("cpp_best_duplicate", "Goldman-modified/src/LambdaLambda.cpp", "if (best_offspring_fitness == next_fitness)",
         "Separate improvement and equality if blocks add a newly best mutant twice; crossover does the same, biasing tie selection."),
        ("cpp_reset", "Goldman-modified/src/LambdaLambdaReset.cpp", "if (lambda == length)",
         "Reset to 1 occurs before success/failure update; failure can immediately multiply it. Comments alone are not executable semantics."),
        ("cpp_limit", "Goldman-modified/src/Experiments.cpp", 'size_t limit = config.get<int>("eval_limit");',
         "eval_limit is read as int then converted to size_t; out-of-range declarations are not verified actual limits."),
        ("cpp_atoi", "Goldman-modified/src/Configuration.cpp", 'return atoi(get<string>(key).c_str());',
         "atoi has no checked overflow handling; record environment/runtime before interpreting large declared limits."),
        ("cpp_batch_rng", "Goldman-modified/src/Experiments.cpp", "single_run(rand, config, problem, solver, run)",
         "One shared RNG advances through all batch runs. Preserve prior 100 runs and original stopping semantics for exact replay; censor at 2.1B only in analysis."),
        ("cpp_analysis", "Goldman-modified/read_results.py", "max_eval = 2100000000",
         "Analysis discards ISG first 100, handles split part 2, and caps unsolved/at-or-above-limit outcomes; this is not a run stopping rule."),
        ("hardcoded_graphs", "Graphs/graphs.py", "y1 = [373204.462",
         "Graphs contain hardcoded values. Plot generation does not by itself demonstrate a chain from raw runs to every published cell."),
        ("landscape", "Graphs/parameter_landscape.py", "data_path = 'Landscape_experiments'",
         "Landscape script refers to a separate experiment directory; coverage and numerical reconstruction remain unresolved."),
    ]
    findings = []
    for identifier, relative, anchor, interpretation in specifications:
        text = (author / relative).read_text(encoding="utf-8")
        lines = [index for index, line in enumerate(text.splitlines(), 1) if anchor in line]
        findings.append({"id": identifier, "path": relative, "anchor": anchor,
                         "line_numbers": lines, "anchor_found": bool(lines),
                         "interpretation": interpretation,
                         "evidence_kind": "static source inspection; paper comparison requires manual source interpretation"})
    return findings


def paper_coverage(catalog: dict, author: Path) -> list[dict]:
    groups = [
        ("Jump", ("Jump",), "main n/k sweeps and algorithm variants"),
        ("OneMax", ("OneMax",), "n sweeps and lambda maxima/reset variants"),
        ("NearestPeak", ("NearestPeak",), "all extra peak specifications"),
        ("WeightedNearestPeak", ("WeightedNearestPeak",), "all weighted extra peak specifications"),
        ("Partition", ("MakespanScheduling", "Partition"), "paper/source naming mapping and instance generation"),
        ("Ising Spin Glass", ("IsingSpinGlass",), "seven sizes, all eight solvers; prior and analyzed fixtures distinct"),
        ("MAX-3SAT", ("MAXSAT", "MaxSat"), "all sizes, solvers and any split batches"),
        ("empirical parameter landscape", (), "Graphs/Landscape_experiments: processed grid cells need mapping to Raw batches and seeds"),
        ("additional Jump in paper text", ("Jump",), "independent manual mapping from textual experiment to retained log/config"),
    ]
    grid = catalog.get("coverage_grid", [])
    return [{"paper_experiment": name, "source_problem_names": list(names),
             "source_grid_rows": [i for i, row in enumerate(grid) if row["problem"] in names],
             "required_scope": scope, "paper_mapping_status": "MANUAL_MAPPING_INCOMPLETE",
             "published_values_gate": "NOT_REPRODUCED", "full_execution_authorized": False,
             "landscape_directory_present": (author / "Graphs/Landscape_experiments").is_dir()
             if name == "empirical parameter landscape" else None}
            for name, names, scope in groups]


def landscape_catalog(author: Path) -> list[dict]:
    """Identify processed copies without pretending they contain raw seed headers."""
    rows = []
    for path in sorted((author / "Graphs/Landscape_experiments").glob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        counterpart = author / "processed-results" / path.name
        counts = re.findall(r"Number of runs:\s*(\d+)", data.decode("utf-8"))
        rows.append({"path": path.relative_to(author).as_posix(), "sha256": sha256_bytes(data),
                     "bytes": len(data), "recorded_run_count_headers": [int(value) for value in counts],
                     "processed_counterpart": counterpart.relative_to(author).as_posix(),
                     "processed_counterpart_bytes_identical": counterpart.is_file()
                     and counterpart.read_bytes() == data,
                     "raw_seed_mapping": "UNRESOLVED; do not count this copy as a separate campaign"})
    return rows


def _preserve_licenses(output: Path) -> list[dict]:
    items = [("author", "LICENSE", "author-GPL-3.0-LICENSE"),
             ("author", "Goldman-modified/LICENSE.txt", "Goldman-modified-BSD-LICENSE.txt"),
             ("inputs", "LICENSE.txt", "P3-BSD-LICENSE.txt")]
    records = []
    for key, relative, name in items:
        source = output / "source" / key / relative
        require(source.is_file(), "required upstream license unavailable")
        data = source.read_bytes()
        require(b"GNU GENERAL PUBLIC LICENSE" in data if key == "author" and relative == "LICENSE"
                else b"Redistribution and use" in data, "unexpected upstream license text")
        target = output / "licenses" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        records.append({"repository_key": key, "source_path": relative,
                        "retained_path": target.relative_to(output).as_posix(),
                        "bytes": len(data), "sha256": sha256_bytes(data)})
    return records


def _critical_pack(output: Path, ising: dict) -> dict:
    path = output / "critical-ising-inputs.tar.gz"
    with tarfile.open(path, "w:gz") as pack:
        for row in ising["records"]:
            data = (output / "source" / "inputs" / row["path"]).read_bytes()
            member = tarfile.TarInfo(row["path"])
            member.size = len(data)
            member.mtime = 0
            pack.addfile(member, io.BytesIO(data))
        license_data = (output / "source" / "inputs" / "LICENSE.txt").read_bytes()
        member = tarfile.TarInfo("LICENSE.txt")
        member.size = len(license_data)
        member.mtime = 0
        pack.addfile(member, io.BytesIO(license_data))
    return {"path": path.name, "bytes": path.stat().st_size,
            "sha256": sha256_bytes(path.read_bytes()), "input_files": len(ising["records"]),
            "retention_note": "archive is evidence; CI expiry must be checked before any cleanup"}


def retain_source_observations(output: Path, catalog: dict) -> None:
    """Compress copied log observations, preserving the report as metadata."""
    ledger = {
        "schema_version": "ga-lambda-retained-source-observations-v1",
        "scope": "copied upstream observations, not new algorithm runs or reconstructed statistics",
        "python_runs": {log["path"]: log["runs"] for log in catalog["python_logs"]},
        "cpp_run_rows": {batch["path"]: batch["retained_run_rows"] for batch in catalog["cpp_batches"]},
    }
    path = output / "source-observations.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(ledger, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    catalog["source_observations"] = {"path": path.name, "bytes": path.stat().st_size,
                                      "sha256": sha256_bytes(path.read_bytes()),
                                      "scope": ledger["scope"]}
    for log in catalog["python_logs"]:
        rows = log.pop("runs")
        log["reported_evaluations_by_run"] = [row["evaluations"] for row in rows]
        log["recorded_generations_by_run"] = [row["generations"] for row in rows]
        log["actual_seed_first"] = log["base_seed"] + 1
        log["actual_seed_last"] = log["base_seed"] + log["declared_runs"]
        log["evaluation_scope"] = "author algorithm-reported counter; zero-mutation generations may charge unevaluated offspring"
    for batch in catalog["cpp_batches"]:
        batch.pop("retained_run_rows")


def write_compact_bundle(output: Path, report: dict) -> None:
    """Portable evidence without upstream colon-bearing paths or full PDF/code."""
    compact = output / "compact"
    compact.mkdir(exist_ok=True)
    reduced = dict(report)
    reduced["full_evidence_reference"] = {
        "path": "audit-report.json", "identity": report["identity"],
        "bytes": (output / "audit-report.json").stat().st_size,
        "sha256": sha256_bytes((output / "audit-report.json").read_bytes()),
        "retention": "full CI source artifact; verify artifact expiry before cleanup",
    }
    reduced["repositories"] = {
        key: {field: value for field, value in repository.items() if field != "files"}
        | {"verified_file_count": len(repository["files"]), "file_inventory": "source_manifest.json"}
        for key, repository in report["repositories"].items()
    }
    if "results_catalog" in report:
        catalog = dict(report["results_catalog"])
        catalog["python_logs"] = [
            {key: value for key, value in log.items()
             if key not in ("runs", "reported_evaluations_by_run", "recorded_generations_by_run")}
            | {"actual_seed_first": log["base_seed"] + 1,
               "actual_seed_last": log["base_seed"] + log["declared_runs"],
               "run_rows_retention": "full CI artifact hash-bound by full_evidence_reference"}
            for log in catalog["python_logs"]
        ]
        catalog["cpp_batches"] = [
            {key: value for key, value in batch.items()
             if key not in ("retained_run_rows", "reported_evaluations_by_run")}
            for batch in catalog["cpp_batches"]
        ]
        reduced["results_catalog"] = catalog
    write_json(compact / "audit-report.json", reduced)
    write_json(output / "source_identity.json", {
        "schema_version": "ga-lambda-source-identity-v1", "identity": report["identity"],
        "availability": report["availability"],
        "repositories": {key: {"repository": value["repository"], "revision": value["revision"],
                                "tree_sha": value["tree_sha"], "archive": value["archive"]}
                         for key, value in report["repositories"].items()},
        "paper": report.get("paper"), "full_reproduction_authorized": False,
    })
    for name in ("source_manifest.json", "source_identity.json", "SOURCE_AUDIT_UK.md", "critical-ising-inputs.tar.gz"):
        source = output / name
        if source.is_file():
            shutil.copyfile(source, compact / name)
    for path in sorted((output / "licenses").glob("*")):
        if path.is_file():
            (compact / "licenses").mkdir(exist_ok=True)
            shutil.copyfile(path, compact / "licenses" / path.name)
    write_file_manifest(compact)


def write_source_packet(output: Path) -> dict:
    """Wrap the verified full evidence in a portable, hash-bound TAR packet.

    GitHub's artifact ZIP cannot represent upstream colon-bearing filenames.
    The packet keeps those names and file bytes unchanged within the TAR; only
    its portable transport directory is uploaded.  Compact/transport products
    are deliberately absent from the full manifest to avoid checksum cycles.
    """
    output = Path(output)
    manifest = write_file_manifest(output, exclude_prefixes=("compact", "transport"))
    transport = output / "transport"
    transport.mkdir(exist_ok=True)
    packet = transport / "full-source.tar.gz"
    rows = sorted(manifest["files"], key=lambda row: row["path"])
    seen = set()
    planned = []
    total = 0
    for row in rows:
        relative = _safe_relative(row["path"]).as_posix()
        require(relative not in seen, "duplicate full-evidence manifest path")
        require(relative != "file_manifest.json"
                and relative.split("/", 1)[0] not in ("compact", "transport"),
                "full-evidence manifest includes derived transport/compact files")
        seen.add(relative)
        path = output.joinpath(*PurePosixPath(relative).parts)
        require(path.resolve().is_relative_to(output.resolve()) and path.is_file()
                and not path.is_symlink(), "invalid full-evidence source file")
        data = path.read_bytes()
        require(len(data) == row["bytes"] and sha256_bytes(data) == row["sha256"],
                "full-evidence file differs from declared manifest")
        total += len(data)
        require(total <= MAX_EXTRACTED, "full-evidence packet exceeds extraction bound")
        planned.append((relative, path, data))
    manifest_path = output / "file_manifest.json"
    manifest_data = manifest_path.read_bytes()
    require(total + len(manifest_data) <= MAX_EXTRACTED,
            "full-evidence manifest exceeds extraction bound")
    planned.append(("file_manifest.json", manifest_path, manifest_data))
    with packet.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                root = tarfile.TarInfo("bundle")
                root.type = tarfile.DIRTYPE
                root.mode = 0o755
                root.mtime = 0
                archive.addfile(root)
                for relative, path, data in sorted(planned, key=lambda item: item[0]):
                    member = tarfile.TarInfo("bundle/" + relative)
                    member.size = len(data)
                    member.mode = path.stat().st_mode & 0o777
                    member.mtime = 0
                    archive.addfile(member, io.BytesIO(data))
    reference = {
        "path": packet.name, "sha256": sha256_bytes(packet.read_bytes()),
        "bytes": packet.stat().st_size, "prefix": "bundle",
        "full_file_manifest_sha256": sha256_bytes(manifest_data),
    }
    report = read_json(output / "audit-report.json")
    write_json(transport / "source_packet_manifest.json", {
        "schema_version": "ga-lambda-source-packet-v1", "identity": report["identity"],
        "source_manifest_sha256": sha256_bytes((output / "source_manifest.json").read_bytes()),
        "audit_report_sha256": sha256_bytes((output / "audit-report.json").read_bytes()),
        "full_file_manifest_sha256": reference["full_file_manifest_sha256"],
        "source_packet_reference": reference,
    })
    write_file_manifest(transport)
    compact = output / "compact"
    reduced = read_json(compact / "audit-report.json")
    reduced["source_packet_reference"] = reference
    write_json(compact / "audit-report.json", reduced)
    write_file_manifest(compact)
    return reference


def audit_sources(output_root: Path, identity: dict) -> dict:
    require(os.environ.get("GITHUB_ACTIONS") == "true", "source audit executes only in GitHub Actions")
    protocol = read_json(MODULE_ROOT / "protocol.json")
    require(protocol["protocol_id"] == PROTOCOL_ID, "protocol identity mismatch")
    require(protocol["authorized_now"]["full_reproduction"] is False, "bounded audit cannot authorize full execution")
    output_root.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": "ga-knapsack-lambda-source-audit-v1", "identity": identity,
              "status": "BOUNDED_SOURCE_AUDIT", "scientific_reproduction": "NOT_EXECUTED",
              "full_admission": "BLOCKED", "repositories": {}, "acquisition_errors": [],
              "availability": {"author_sources_verified": False, "input_sources_verified": False,
                               "ising_all_verified": False, "paper_acquired": False,
                               "licenses_preserved": False, "bounded_pilot": False}}
    for key, repository, revision in (("author", AUTHOR_REPO, AUTHOR_SHA), ("inputs", INPUT_REPO, INPUT_SHA)):
        try:
            report["repositories"][key] = acquire_repository(output_root, key, repository, revision)
            report["availability"][key + "_sources_verified" if key == "author" else "input_sources_verified"] = True
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            report["acquisition_errors"].append({"repository_key": key, "error": str(exc)})
    source = output_root / "source"
    source.mkdir(exist_ok=True)
    try:
        pdf, metadata = _download(PAPER_URL)
        require(pdf.startswith(b"%PDF-"), "paper URL did not return a PDF")
        (source / "paper.pdf").write_bytes(pdf)
        metadata.update({"doi": protocol["paper"]["doi"], "content_pinned_before_acquisition": False,
                         "claim_scope": "fixed URL acquired and hash recorded; PDF hash was not preregistered",
                         "affiliation_check": "manual citation from paper p.1; no automated PDF parser"})
        report["paper"] = metadata
        report["availability"]["paper_acquired"] = True
    except (OSError, ValueError, RuntimeError) as exc:
        report["acquisition_errors"].append({"repository_key": "paper", "error": str(exc)})
    if report["availability"]["author_sources_verified"]:
        author = source / "author"
        report["results_catalog"] = catalog_results(author)
        retain_source_observations(output_root, report["results_catalog"])
        report["source_semantics"] = source_semantics(author)
        report["paper_coverage"] = paper_coverage(report["results_catalog"], author)
        report["landscape_catalog"] = landscape_catalog(author)
        report["availability"]["bounded_pilot"] = True
    if report["availability"]["input_sources_verified"]:
        report["ising"] = audit_ising(source / "inputs")
        report["availability"]["ising_all_verified"] = report["ising"]["complete"]
        if report["ising"]["complete"]:
            report["critical_input_pack"] = _critical_pack(output_root, report["ising"])
    if all(report["availability"][key] for key in ("author_sources_verified", "input_sources_verified")):
        try:
            report["licenses"] = _preserve_licenses(output_root)
            report["availability"]["licenses_preserved"] = True
        except (OSError, ValueError, RuntimeError) as exc:
            report["acquisition_errors"].append({"repository_key": "licenses", "error": str(exc)})
        original = source / "inputs" / "src" / "Evaluation.cpp"
        modified = source / "author" / "Goldman-modified" / "src" / "Evaluation.cpp"
        report["goldman_evaluator_bytes_identical"] = original.read_bytes() == modified.read_bytes()
    report["unresolved_full_reproduction_gaps"] = [
        "full execution and resources are not authorized by this protocol",
        "paper-to-config/seed/input/raw-statistic mapping is not yet complete for every experiment",
        "printed algorithm and Python/C++ source semantics require explicit separate profiles",
        "original compiler/standard-library RNG environment is not established",
        "large declared C++ limits pass through atoi(int); actual historical limit is unverified",
        "exact C++ batch RNG requires prior runs and original stopping semantics, not analysis censoring",
        "hardcoded plot values and processed Graphs/Landscape_experiments need exact raw-batch/seed mapping",
        "no independently proven optimum preprocessing provenance for supplied Ising energy metadata",
        "retained inputs, licenses and CI artifact expiry require retention review before cleanup",
    ]
    report["input_license_provenance"] = {
        "repository_license": "P3 LICENSE.txt BSD two-clause retained byte-for-byte",
        "source_chain": "paper names Goldman-Punch fixtures; author README links brianwgoldman/P3",
        "file_specific_license_or_preprocessing_details": "not independently established; repository license is not a separate fixture-specific statement",
    }
    manifests = {key: value["files"] for key, value in report["repositories"].items()}
    write_json(output_root / "source_manifest.json", {"identity": identity, "repositories": manifests})
    write_json(output_root / "audit-report.json", report)
    text = (
        "# Обмежений аудит джерел λ\n\n"
        f"Статус: `{report['status']}`. Числове відтворення: `NOT_EXECUTED`; повний допуск: `BLOCKED`.\n\n"
        "Одержання та перевірки виконуються лише у GitHub Actions. Для успішно перевірених джерел "
        "маніфест звіряє кожний файл із Git blob SHA-1 за фіксованим commit і записує SHA-256 та довжину. "
        "Збережені ліцензії та помилки одержання перелічено в audit-report.json.\n\n"
        f"Доступність: `{json.dumps(report['availability'], ensure_ascii=False)}`.\n\n"
        "Очікувано 1400 файлів ISG для n∈{16,25,36,49,64,81,100}, індексів 0–199; "
        f"перевірено {report.get('ising', {}).get('verified_files', 0)}, з них аналізованих "
        f"{report.get('ising', {}).get('analyzed_verified_files', 0)} із 700 індексів 100–199. "
        "Для успішних записів перевірено формат, топологію та енергію записаного свідка; "
        "глобальна мінімальність незалежно не доведена.\n\n"
        "Python-журнали містять base seed; фактичний seed кожного run дорівнює base+run для random і numpy. "
        "C++ cfg/dat зберігають batch seed, кількість рядків, split parts, відкидання перших 100 ISG і "
        "аналізове цензурування на 2 100 000 000. Цензурування не є правилом зупинки replay. "
        "Один RNG проходить попередні run; їх пропуск або рання зупинка змінюють наступний стан.\n\n"
        "`source_semantics` фіксує Python ties-to-even, C++ half-up, повний пул мутантів Python, "
        "1.1067 у C++, reset, подвійне додавання нового найкращого на нічиїх і hardcoded graphs. "
        "eval_limit читається через atoi(int), потім size_t: запис 100 млрд не підтверджує фактичний ліміт.\n\n"
        "Повний каталог конфігурацій і seed: `audit-report.json`; checksums: `source_manifest.json` "
        "та `file_manifest.json`. Paper coverage відокремлено від числової реплікації. PDF SHA-256 "
        "зафіксовано після одержання з реєстрованої URL; PDF не комітиться.\n\n"
        "## Невирішені умови повної серії\n\n"
        + "\n".join("- " + gap for gap in report["unresolved_full_reproduction_gaps"]) + "\n"
    )
    (output_root / "SOURCE_AUDIT_UK.md").write_text(text, encoding="utf-8")
    write_compact_bundle(output_root, report)
    write_source_packet(output_root)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    identity = authenticate(args.expected_sha)
    report = audit_sources(args.output, identity)
    print(json.dumps({"status": report["status"], "availability": report["availability"],
                      "full_admission": report["full_admission"]}, sort_keys=True))
    for key in ("author_sources_verified", "input_sources_verified", "ising_all_verified",
                "paper_acquired", "licenses_preserved"):
        require(report["availability"][key], f"required bounded source acquisition/verification failed: {key}")


if __name__ == "__main__":
    main()
