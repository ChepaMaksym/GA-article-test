"""Authenticate and audit the frozen Zenodo source archive."""

from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from pathlib import PurePosixPath
from typing import Any

from .contract import exact, require
from .errors import VerificationError


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and "\x00" not in name
        and "\\" not in name
        and not path.is_absolute()
        and all(part not in ("", ".", "..") for part in name.rstrip("/").split("/"))
        and not (path.parts and ":" in path.parts[0])
    )


def verify_code_archive(data: bytes, contract: dict[str, Any]) -> dict[str, Any]:
    stage = "A2_CODE"
    cfg = contract["zenodo_files"]["repelling_code.zip"]
    exact(len(data), cfg["bytes"], stage, "archive bytes")
    exact(hashlib.md5(data, usedforsecurity=False).hexdigest(), cfg["md5"], stage, "archive MD5")
    exact(hashlib.sha256(data).hexdigest(), cfg["sha256"], stage, "archive SHA-256")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data), mode="r")
        bad = archive.testzip()
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise VerificationError(stage, f"invalid code ZIP: {exc}") from exc
    require(bad is None, stage, f"code ZIP CRC failure at {bad!r}")
    infos = archive.infolist()
    exact(len(infos), cfg["entry_count"], stage, "entry count")
    exact(sum(info.file_size for info in infos), cfg["total_uncompressed_bytes"], stage, "total uncompressed bytes")
    names = [info.filename for info in infos]
    exact(len(names), len(set(names)), stage, "unique member count")
    for info in infos:
        require(_safe_name(info.filename), stage, f"unsafe member name {info.filename!r}")
        require((info.flag_bits & 0x1) == 0, stage, f"encrypted member {info.filename!r}")
        require(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), stage, f"unsupported member method {info.filename!r}")
        mode = (info.external_attr >> 16) & 0xFFFF
        require(stat.S_IFMT(mode) != stat.S_IFLNK, stage, f"symbolic link {info.filename!r}")

    member_bytes: dict[str, bytes] = {}
    for expected in contract["required_code_members"]:
        path = expected["path"]
        try:
            payload = archive.read(path)
        except KeyError as exc:
            raise VerificationError(stage, f"missing pinned source member {path!r}") from exc
        exact(len(payload), expected["bytes"], stage, f"{path} bytes")
        exact(hashlib.sha256(payload).hexdigest(), expected["sha256"], stage, f"{path} SHA-256")
        member_bytes[path] = payload

    license_text = member_bytes["repelling_code/LICENSE"].decode("utf-8")
    require("MIT License" in license_text and "Permission is hereby granted" in license_text, stage, "embedded MIT license text missing")
    requirements = member_bytes["repelling_code/requirements.txt"].decode("ascii").splitlines()
    exact(
        requirements,
        contract["source_snapshot"]["runtime_requirements"],
        stage,
        "lower-bound requirements",
    )
    setup = member_bytes["repelling_code/setup.py"].decode("utf-8")
    for token in ("__version__ = \"1.0.6\"", "-O3", "-fno-math-errno", "-march=native", "cxx_std=17"):
        require(token in setup, stage, f"setup token {token!r} missing")
    collect = member_bytes["repelling_code/repelling/collect_data.py"].decode("utf-8")
    for token in (
        "for instance in range(1, args.n_instances + 1):",
        "for run in range(args.n_runs):",
        "c_cmaes.utils.set_seed(42 * run)",
        "budget=problem.meta_data.n_variables * args.budget",
        "target=problem.optimum.y + 1e-8",
    ):
        require(token in collect, stage, f"driver token {token!r} missing")
    restart = member_bytes["repelling_code/src/restart.cpp"].decode("utf-8")
    for token in ("lambda_large = lambda_init * 2", "budget_small = remaining_budget / 2", "lambda_large *= 2", "std::pow(dist(rng::GENERATOR), 2)"):
        require(token in restart, stage, f"BIPOP token {token!r} missing")
    repelling = member_bytes["repelling_code/src/repelling.cpp"].decode("utf-8")
    for token in ("std::pow(shrinkage, attempts) * radius", "p.settings.volume / (p.settings.sigma0 * coverage * p.stats.solutions.size())", "std::tgamma(n / 2.0 + 1.0)", "if (max_f < y)"):
        require(token in repelling, stage, f"repelling token {token!r} missing")
    mutation = member_bytes["repelling_code/src/mutation.cpp"].decode("utf-8")
    require("sigma *= std::exp((cs / damps) * ((adaptation->ps.norm() / adaptation->chiN) - 1))" in mutation, stage, "CSA formula missing")
    common = member_bytes["repelling_code/src/common.cpp"].decode("utf-8")
    require("GENERATOR.seed(seed)" in common and "srand(seed)" in common, stage, "dual seed semantics missing")

    eigen_path = "repelling_code/external/Eigen/src/Core/util/Macros.h"
    extension = contract["source_snapshot"]["embedded_extension"]
    extension_path = "repelling_code/" + extension
    require(eigen_path in names, stage, "bundled Eigen macros missing")
    require(extension_path in names, stage, "bundled CPython extension missing")
    macros = archive.read(eigen_path).decode("ascii", errors="strict")
    for token in (
        "#define EIGEN_WORLD_VERSION 3",
        "#define EIGEN_MAJOR_VERSION 4",
        "#define EIGEN_MINOR_VERSION 0",
    ):
        require(token in macros, stage, f"Eigen version token {token!r} missing")

    archive.close()
    return {
        "status": "PASS_CODE_ARCHIVE_IDENTITY",
        "bytes": len(data),
        "md5": hashlib.md5(data, usedforsecurity=False).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "entries": len(infos),
        "total_uncompressed_bytes": sum(info.file_size for info in infos),
        "duplicates": 0,
        "encrypted_members": 0,
        "embedded_license": "MIT",
        "modcma_version": contract["source_snapshot"]["modcma_version"],
        "eigen_version": contract["source_snapshot"]["eigen_version"],
        "git_revision": None,
        "source_native_status": contract["source_native_status"],
    }
