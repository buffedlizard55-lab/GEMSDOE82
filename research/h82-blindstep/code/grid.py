"""Competition grid, portal-safe writer, independent validator.

Grid measured from the restored rasters (sha256-pinned, registry/data_manifest.json):
EPSG:32611, 100 m, 3730x3292, transform (100,0,243350, 0,-100,4508550).
Portal error 'Predicted values must be in range [0, 1]' has two causes measured by the
group (GEMSDOE32): (1) the -3.4e38 float sentinel written through, (2) a nodata tag carrying
that sentinel. Primary download here is therefore ALL-FINITE ('zeros' outside footprint,
nodata=None, every one of 12,279,160 cells in [0,1]); a NaN-outside twin (competition's own
sample format) ships alongside. Validator re-reads bytes from disk; no in-memory trust.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np
import rasterio

H, W = 3730, 3292
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
SENTINEL = -3.4028234663852886e38
BAND_NAMES = ["mag_anom","rtp","tmi_hg","geod_2ndinv","iso_grav_anom_slope","tc",
 "geod_shearrate","geod_dilaterate","tmi_vg","deq_n100a15","iso_grav_anom_vg","det_elev",
 "iso_grav_anom","tmi","depth_to_base_surf","ieq_n100a15","cond_surf","iso_grav_anom_hg",
 "det_elev_slope"]

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()

def load_template(sample_path):
    with rasterio.open(sample_path) as s:
        assert (s.height, s.width) == (H, W), (s.height, s.width)
        assert s.crs.to_epsg() == 32611, s.crs
        assert tuple(float(v) for v in s.transform)[:6] == TRANSFORM, tuple(s.transform)
        foot = np.isfinite(s.read(1))
        profile = dict(driver="GTiff", dtype="float32", count=1, crs=s.crs,
                       transform=s.transform, width=W, height=H)
    return foot, profile

def load_labels(labels_path, foot):
    with rasterio.open(labels_path) as s:
        a = s.read(1)
    return (a == 1) & foot

def read_band(features_path, idx):
    """One band as float32 with sentinel/non-finite -> NaN (never written to a submission)."""
    with rasterio.open(features_path) as s:
        a = s.read(idx).astype(np.float32)
    a[(~np.isfinite(a)) | (a < -1e38)] = np.nan
    return a

def write_submission(mask01, foot, profile, out_path, outside="zeros"):
    m = np.asarray(mask01, dtype=np.float32)
    assert m.shape == (H, W)
    vals = m[foot]
    assert np.isfinite(vals).all() and (vals >= 0).all() and (vals <= 1).all(), "in-footprint range"
    if outside == "zeros":
        arr = np.where(foot, m, np.float32(0.0)).astype(np.float32)
        prof = {**profile, "nodata": None, "compress": "deflate", "predictor": 3,
                "zlevel": 9, "tiled": True, "blockxsize": 256, "blockysize": 256}
    elif outside == "nan":
        arr = np.where(foot, m, np.float32(np.nan)).astype(np.float32)
        prof = {**profile, "nodata": float("nan"), "compress": "deflate", "predictor": 3,
                "zlevel": 9, "tiled": True, "blockxsize": 256, "blockysize": 256}
    else: raise ValueError(outside)
    out_path = Path(out_path); out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **prof) as d: d.write(arr, 1)
    return out_path

def validate(path, foot, labels=None, mode="zeros"):
    """Independent re-read audit. Raises on any failure; returns receipt dict."""
    with rasterio.open(path) as s:
        arr = s.read(1); meta = dict(count=s.count, dtype=s.dtypes[0], crs=str(s.crs),
            height=s.height, width=s.width, transform=tuple(float(v) for v in s.transform)[:6],
            nodata=(None if s.nodata is None else float(s.nodata)))
    fin_in = arr[foot]; out = arr[~foot]; nfoot = int(foot.sum())
    checks = {
        "single_band": meta["count"] == 1,
        "dtype_float32": meta["dtype"] == "float32",
        "shape_3730x3292": (meta["height"], meta["width"]) == (H, W),
        "crs_epsg32611": "32611" in meta["crs"],
        "transform_match": meta["transform"] == TRANSFORM,
        "no_nan_inside_footprint": int(np.isnan(fin_in).sum()) == 0,
        "no_inf_inside_footprint": int(np.isinf(fin_in).sum()) == 0,
        "no_sentinel_inside_footprint": int((fin_in < -1e30).sum()) == 0,
        "all_finite_inside_footprint": int(np.isfinite(fin_in).sum()) == nfoot,
        "range_0_1_inside_footprint": bool(np.isfinite(fin_in).all() and (fin_in >= 0).all() and (fin_in <= 1).all()),
        "nodata_safe": bool((meta["nodata"] is None) or np.isnan(meta["nodata"])),
        "outside_compliant": bool((out == 0).all()) if mode == "zeros" else bool(np.isnan(out).all()),
    }
    if mode == "zeros":
        checks["full_grid_all_finite_0_1"] = bool(np.isfinite(arr).all() and (arr >= 0).all() and (arr <= 1).all())
    if labels is not None:
        checks["zero_on_catalogue"] = bool(int(((arr > 0) & labels).sum()) == 0)
    ok = all(checks.values())
    receipt = dict(file=Path(path).name, sha256=sha256_file(path), bytes=Path(path).stat().st_size,
        mode=mode, meta=meta, footprint_px=nfoot, positive_px=int(((arr > 0) & foot).sum()),
        mass=float(np.nansum(arr[foot])), min_in=float(np.nanmin(fin_in)), max_in=float(np.nanmax(fin_in)),
        checks=checks, all_passed=bool(ok))
    if not ok: raise ValueError(f"VALIDATOR FAIL {path}: {[k for k,v in checks.items() if not v]}")
    return receipt
