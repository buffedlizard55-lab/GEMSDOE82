"""Competition grid geometry, footprint, raster IO.

Grid facts are measured from the competition rasters themselves (owner mirrors of
DrivenData files, sha256-pinned in registry/data_manifest.json), never invented:

    EPSG:32611 (UTM 11N), 100 m pixels, width 3292 x height 3730,
    origin (243350, 4508550), footprint 5,167,373 px (finite pixels of
    sample_submission.tif), labels: 60,988 fault px.

Provenance: geometry cross-checked against GEMSDOE32 src/gems32/grid.py and
re-measured here in evidence/grid_receipt.json.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

HEIGHT = 3730
WIDTH = 3292
TOTAL_PIXELS = HEIGHT * WIDTH  # 12,279,160
FOOTPRINT_PIXELS = 5_167_373
LABEL_FAULT_PIXELS = 60_988
CRS = "EPSG:32611"
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
RES_M = 100.0

NODATA_F32 = np.float32(-3.4028234663852886e38)


def read_footprint(sample_submission_path: str | Path) -> np.ndarray:
    """Boolean footprint = finite pixels of the sample submission raster."""
    with rasterio.open(sample_submission_path) as s:
        a = s.read(1)
    return np.isfinite(a)


def read_labels(labels_path: str | Path) -> np.ndarray:
    """Catalogue raster -> boolean (>=1 is a mapped fault; 0 no-fault; -1 outside)."""
    with rasterio.open(labels_path) as s:
        a = s.read(1)
    return a >= 1


def read_binary_mask(path: str | Path, threshold: float = 0.5) -> np.ndarray:
    """Any submission-like raster -> boolean positive mask (finite & > threshold)."""
    with rasterio.open(path) as s:
        a = s.read(1)
    return np.isfinite(a) & (a > threshold)


def grid_meta_from_template(template_path: str | Path) -> dict:
    with rasterio.open(template_path) as s:
        return dict(
            driver="GTiff", dtype="float32", count=1, crs=s.crs,
            transform=s.transform, width=s.width, height=s.height,
        )


def check_grid(path: str | Path) -> dict:
    """Verify a raster matches the competition grid; returns receipt dict."""
    with rasterio.open(path) as s:
        t = tuple(s.transform)[:6]
        ok = (
            s.height == HEIGHT and s.width == WIDTH
            and str(s.crs) == CRS
            and all(abs(a - b) < 1e-6 for a, b in zip(t, TRANSFORM))
            and s.count == 1 and s.dtypes[0] == "float32"
        )
        return dict(
            path=str(path), height=s.height, width=s.width, crs=str(s.crs),
            transform=list(t), count=s.count, dtype=s.dtypes[0],
            nodata=None if s.nodata is None or (isinstance(s.nodata, float) and np.isnan(s.nodata)) else float(s.nodata),
            nodata_repr=str(s.nodata), ok_grid=bool(ok),
        )


def sha256(path: str | Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
