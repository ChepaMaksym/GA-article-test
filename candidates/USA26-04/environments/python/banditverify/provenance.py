"""Git/source identity helpers shared by profile producer and comparator."""

from __future__ import annotations

from pathlib import Path
import subprocess

from .canonical import sha256_file


SOURCE_SCOPE = (
    "candidates/USA26-04",
    ".github/workflows/usa26-04-validation.yml",
    "registry/cohort_2026_12",
    "AGENTS.md",
    "RESEARCH_STATUS.md",
    "registry/README.md",
    "registry/attempt_outcomes.md",
    "failure_logs/README.md",
    "verification/README.md",
)


def repository_root(start: Path) -> Path:
    return Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=start, text=True
        ).strip()
    ).resolve()


def git_head(repository: Path) -> str:
    result = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    if len(result) != 40 or any(character not in "0123456789abcdef" for character in result):
        raise RuntimeError("Git HEAD is not a full lowercase SHA-1")
    return result


def source_paths(repository: Path) -> list[Path]:
    tracked = subprocess.check_output(
        ["git", "ls-files", "--", *SOURCE_SCOPE], cwd=repository, text=True
    ).splitlines()
    paths = [repository / item for item in tracked if "/results/" not in item]
    if not paths:
        raise RuntimeError("no tracked USA26-04 source files were found")
    return sorted(paths)


def source_hashes(repository: Path, paths: list[Path] | None = None) -> dict[str, str]:
    selected = source_paths(repository) if paths is None else paths
    result = {
        str(path.relative_to(repository)): sha256_file(path)
        for path in selected
    }
    if not result:
        raise RuntimeError("source hash map cannot be empty")
    return result


def source_git_state(repository: Path) -> list[str]:
    output = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            *SOURCE_SCOPE,
        ],
        cwd=repository,
        text=True,
    )
    return sorted(line for line in output.splitlines() if line.strip())


def matlab_source_hashes(candidate: Path) -> dict[str, str]:
    directory = candidate / "environments" / "matlab"
    paths = sorted(directory.glob("*.m"))
    if not paths:
        raise RuntimeError("no independent MATLAB/Octave sources found")
    return {path.name: sha256_file(path) for path in paths}
