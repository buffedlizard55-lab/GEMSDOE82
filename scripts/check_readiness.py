#!/usr/bin/env python3
"""Report whether the checkout has the minimum assets needed for holdout/submission.

This is a diagnostic only. It does not download data, modify predictions, create a
GeoTIFF, or replace the canonical shared evaluator or writer.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]

INPUTS: dict[str, tuple[str, ...]] = {
    "features": ("training_features.tif", "gems-geodawn-numerical-features.tif"),
    "labels": ("labels.tif", "existing_faults.tif"),
    "sample_grid": ("sample_submission.tif", "example_submission.tif"),
    "dem_links": ("1m_DEM_links.csv", "digital_elevation_model_links.json"),
}

SHARED_TOOLS: dict[str, tuple[str, ...]] = {
    "evaluate_holdout.py": (
        "evaluate_holdout.py",
        "scripts/evaluate_holdout.py",
        "vendor/gems57/evaluate_holdout.py",
    ),
    "submission_writer.py": (
        "submission_writer.py",
        "scripts/submission_writer.py",
        "vendor/gems57/submission_writer.py",
    ),
}


def _find_first(root: Path, paths: Iterable[str]) -> str | None:
    for relative in paths:
        candidate = root / relative
        if candidate.is_file() and candidate.stat().st_size > 0:
            return relative
    return None


def inspect_root(root: Path = ROOT, feature_cache_path: str | None = None) -> dict[str, object]:
    inputs: dict[str, dict[str, object]] = {}
    for logical_name, accepted_names in INPUTS.items():
        path = _find_first(root, (f"data/{name}" for name in accepted_names))
        inputs[logical_name] = {
            "status": "present" if path else "missing",
            "path": path,
            "accepted_names": list(accepted_names),
        }

    tools: dict[str, dict[str, object]] = {}
    for tool, accepted_paths in SHARED_TOOLS.items():
        path = _find_first(root, accepted_paths)
        tools[tool] = {"status": "present" if path else "missing", "path": path}

    # The canonical template's cache path/format is not specified here. Accept only
    # an explicit CLI/test value or environment variable; never guess a private cache.
    cache_reference = feature_cache_path or os.environ.get("GEMS_FEATURE_CACHE_PATH")
    cache_path: Path | None = None
    if cache_reference:
        candidate = Path(cache_reference).expanduser()
        cache_path = candidate if candidate.is_absolute() else root / candidate
    cache_present = cache_path is not None and cache_path.is_file() and cache_path.stat().st_size > 0
    cache_display_path = None
    if cache_present and cache_path is not None:
        try:
            cache_display_path = cache_path.relative_to(root).as_posix()
        except ValueError:
            cache_display_path = str(cache_path)
    cache = {
        "status": "present" if cache_present else "missing_or_unspecified",
        "path": cache_display_path,
        "explicit_path_supplied": bool(cache_reference),
    }

    registry_dir = root / "registry" / "rasters"
    registry_rasters = sorted(
        path.relative_to(root).as_posix()
        for path in registry_dir.rglob("*.tif")
        if path.is_file()
    ) if registry_dir.is_dir() else []

    holdout_assets_present = (
        inputs["features"]["status"] == "present"
        and inputs["labels"]["status"] == "present"
        and tools["evaluate_holdout.py"]["status"] == "present"
        and cache["status"] == "present"
    )
    candidate_stage_assets_present = holdout_assets_present and bool(registry_rasters)
    writer_assets_present = (
        candidate_stage_assets_present
        and inputs["sample_grid"]["status"] == "present"
        and tools["submission_writer.py"]["status"] == "present"
    )

    return {
        "checkout": root.name,
        "inputs": inputs,
        "shared_tools": tools,
        "cached_feature_stack": cache,
        "registry_rasters": {
            "status": "present" if registry_rasters else "missing",
            "paths": registry_rasters,
        },
        "holdout_assets_present": bool(holdout_assets_present),
        "candidate_stage_assets_present": bool(candidate_stage_assets_present),
        "writer_assets_present": bool(writer_assets_present),
        "submit_ready": False,
        "note": "Asset presence is not scientific or portal validation and never authorizes a submission. This diagnostic does not create or validate a TIFF.",
    }


def main() -> int:
    report = inspect_root()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["writer_assets_present"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
