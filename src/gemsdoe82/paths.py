"""Repository paths and competition-grid constants for GEMSDOE82.

The competition inputs are intentionally not committed.  ``data_dir`` first
checks ``GEMS_DATA_DIR`` and then the public-mirror cache created by
``scripts/fetch_public_mirror_cache.py``.  A separate environment variable makes
it possible to point the same code at the official DrivenData download without
changing the implementation.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEIGHT = 3730
WIDTH = 3292
SHAPE = (HEIGHT, WIDTH)
EPSG = 32611
PIXEL_M = 100.0
RADIUS_PX = 3.0


def data_dir() -> Path:
    configured = os.environ.get("GEMS_DATA_DIR")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates += [
        ROOT / ".cache" / "gems_data" / "core",
        ROOT / "data",
        ROOT / "data" / "raw",
    ]
    for candidate in candidates:
        if (candidate / "training_features.tif").exists() and (candidate / "sample_submission.tif").exists():
            return candidate
    # Return the first location so the error message points to a useful path.
    return candidates[0] if candidates else ROOT / "data"


def downloads_dir() -> Path:
    path = ROOT / "docs" / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def evidence_dir() -> Path:
    path = ROOT / "evidence"
    path.mkdir(parents=True, exist_ok=True)
    return path


def registry_dir() -> Path:
    path = ROOT / "registry"
    path.mkdir(parents=True, exist_ok=True)
    return path
