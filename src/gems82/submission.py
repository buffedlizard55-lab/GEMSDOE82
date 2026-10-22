"""DrivenData GeoTIFF submission writer + 12-point validator audit.

Fixes the portal error "Predicted values must be in range [0, 1]" structurally:
  * every in-footprint pixel is finite and clipped to [0, 1] (no NaN / inf /
    -3.4e38 sentinels inside the footprint, ever);
  * two variants are shipped for every candidate:
      -zeros.tif : 0.0 outside the footprint, nodata=None  -> the WHOLE grid
                   satisfies 0<=v<=1 (strict-validator-proof);
      -nan.tif   : NaN outside the footprint, nodata=NaN   -> the competition's
                   own sample-submission format.
  * CRS / shape / geotransform are copied pixel-exactly from the template
    (sample_submission.tif); dtype float32, single band.

audit_geotiff() re-opens the bytes from disk and enforces 12 checks; it RAISES
on any failure, so a shipped receipt with all_checks_passed=true is a proof of
portal-format compliance, not a claim.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

from .grid import (CRS, FOOTPRINT_PIXELS, HEIGHT, TRANSFORM, WIDTH,
                   grid_meta_from_template, sha256)

EXPECTED_TOTAL = HEIGHT * WIDTH


def sha256_file(path: Path) -> str:
    return sha256(path)


def write_mask(mask: np.ndarray, foot: np.ndarray, template_tif: Path,
               out_path: Path, outside: str = "zeros") -> Path:
    """Write a boolean/float mask as a legal submission GeoTIFF."""
    assert outside in ("zeros", "nan")
    m = np.asarray(mask, dtype=np.float32)
    assert m.shape == (HEIGHT, WIDTH), (m.shape, (HEIGHT, WIDTH))
    foot = np.asarray(foot, bool)
    assert foot.sum() == FOOTPRINT_PIXELS, f"footprint {foot.sum()} != {FOOTPRINT_PIXELS}"
    vals = m[foot]
    if not np.isfinite(vals).all():
        bad = int((~np.isfinite(vals)).sum())
        raise ValueError(f"{bad} non-finite values inside the footprint")
    if (vals < 0).any() or (vals > 1).any():
        raise ValueError("values outside [0, 1] inside the footprint")
    out = np.where(foot, np.clip(m, 0.0, 1.0),
                   np.float32(0.0) if outside == "zeros" else np.float32(np.nan))
    meta = grid_meta_from_template(template_tif)
    meta["nodata"] = None if outside == "zeros" else np.nan
    meta["compress"] = "deflate"
    meta["tiled"] = True
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(out.astype(np.float32), 1)
    return out_path


def audit_geotiff(tif_path: Path, foot: np.ndarray, labels: np.ndarray,
                  mode: str) -> dict:
    """Strict 12-point DrivenData submission validator audit. Raises on failure."""
    assert mode in ("zeros", "nan")
    with rasterio.open(tif_path) as src:
        arr = src.read(1)
        crs_str = str(src.crs)
        transform_tuple = tuple(round(float(x), 4) for x in src.transform)[:6]
        dtypes = src.dtypes
        count = src.count
        height, width = src.height, src.width
        nodata_val = src.nodata
    in_foot = arr[foot]
    out_foot = arr[~foot]
    in_finite = int(np.isfinite(in_foot).sum())
    in_nan = int(np.isnan(in_foot).sum())
    in_inf = int(np.isinf(in_foot).sum())
    in_sentinel = int((in_foot < -1e30).sum())
    in_min = float(np.nanmin(in_foot))
    in_max = float(np.nanmax(in_foot))
    in_01 = bool(in_finite == FOOTPRINT_PIXELS
                 and np.all((in_foot >= 0.0) & (in_foot <= 1.0)))
    if mode == "zeros":
        full_01 = bool(int(np.isfinite(arr).sum()) == EXPECTED_TOTAL
                       and np.all((arr >= 0.0) & (arr <= 1.0)))
        out_ok = bool(np.all(out_foot == 0.0))
    else:
        full_01 = in_01
        out_ok = bool(np.all(np.isnan(out_foot)))
    emitted = int((in_foot > 0.5).sum())
    on_cat = int(((arr > 0.5) & labels).sum())
    checks = {
        "single_band": count == 1,
        "dtype_float32": dtypes[0] == "float32",
        "dimensions_3730x3292": (height == HEIGHT and width == WIDTH),
        "crs_epsg_32611": "32611" in crs_str,
        "in_footprint_all_finite": in_finite == FOOTPRINT_PIXELS,
        "in_footprint_zero_nan": in_nan == 0,
        "in_footprint_zero_inf": in_inf == 0,
        "in_footprint_zero_sentinel": in_sentinel == 0,
        "in_footprint_range_0_1": in_01,
        "outside_footprint_compliant": out_ok,
        "zero_on_catalogue_leakage": on_cat == 0,
        "validator_range_0_1_guaranteed": full_01,
    }
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        raise ValueError(f"Submission audit failed for {tif_path.name}: {failed}")
    h = hashlib.sha256()
    with tif_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {
        "filename": tif_path.name,
        "size_bytes": tif_path.stat().st_size,
        "sha256": h.hexdigest(),
        "mode": mode,
        "crs": crs_str,
        "transform": list(transform_tuple),
        "shape": [height, width],
        "dtype": dtypes[0],
        "nodata": None if nodata_val is None or (isinstance(nodata_val, float) and np.isnan(nodata_val)) else float(nodata_val),
        "nodata_repr": str(nodata_val),
        "emitted_positive_pixels": emitted,
        "footprint_fraction": round(emitted / float(FOOTPRINT_PIXELS), 6),
        "on_catalogue_positive_pixels": on_cat,
        "in_footprint_finite_pixels": in_finite,
        "in_footprint_min": in_min,
        "in_footprint_max": in_max,
        "full_grid_finite_pixels": int(np.isfinite(arr).sum()),
        "checks": checks,
        "all_checks_passed": True,
    }


def write_submission_pair(mask: np.ndarray, foot: np.ndarray, labels: np.ndarray,
                          template_tif: Path, out_dir: Path, slug: str) -> dict:
    """Write + audit both -zeros.tif and -nan.tif variants. Returns receipt."""
    out_dir = Path(out_dir)
    receipts = {}
    for mode, suffix in (("zeros", "zeros"), ("nan", "nan")):
        p = out_dir / f"{slug}-{suffix}.tif"
        write_mask(mask, foot, template_tif, p, outside=mode)
        receipts[mode] = audit_geotiff(p, foot, labels, mode)
    return receipts
