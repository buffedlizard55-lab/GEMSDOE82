"""Submission writer/auditor on synthetic grids (no data files needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from gems82 import grid as G
from gems82 import submission as SUB


@pytest.fixture()
def tiny_template(tmp_path):
    # Build a downsized stand-in by monkeypatching grid constants is risky;
    # instead test the audit invariants on a real-shaped in-memory array via
    # direct audit of crafted arrays. Here: verify audit rejects bad inputs.
    return tmp_path


def _write(path, arr, foot_shape=(3730, 3292), nodata=None):
    meta = dict(driver="GTiff", dtype="float32", count=1, crs="EPSG:32611",
                transform=(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0),
                width=foot_shape[1], height=foot_shape[0], nodata=nodata)
    with rasterio.open(path, "w", **meta) as dst:
        dst.write(arr.astype(np.float32), 1)


def test_audit_rejects_nan_inside(tmp_path):
    foot = np.zeros((3730, 3292), bool)
    foot[100:200, 100:200] = True
    # monkeypatch footprint count by padding foot to the true size
    rng = np.random.default_rng(0)
    idx = rng.choice(foot.size, G.FOOTPRINT_PIXELS, replace=False)
    foot = np.zeros((3730, 3292), bool)
    foot.ravel()[idx] = True
    labels = np.zeros_like(foot)
    arr = np.zeros((3730, 3292), np.float32)
    bad = np.flatnonzero(foot)[0]
    arr.ravel()[bad] = np.nan
    p = tmp_path / "bad.tif"
    _write(p, arr)
    with pytest.raises(ValueError):
        SUB.audit_geotiff(p, foot, labels, "zeros")


def test_audit_rejects_out_of_range(tmp_path):
    foot = np.zeros((3730, 3292), bool)
    rng = np.random.default_rng(1)
    foot.ravel()[rng.choice(foot.size, G.FOOTPRINT_PIXELS, replace=False)] = True
    labels = np.zeros_like(foot)
    arr = np.zeros((3730, 3292), np.float32)
    arr.ravel()[np.flatnonzero(foot)[0]] = 1.5
    p = tmp_path / "bad.tif"
    _write(p, arr)
    with pytest.raises(ValueError):
        SUB.audit_geotiff(p, foot, labels, "zeros")


def test_audit_accepts_clean_pair(tmp_path):
    foot = np.zeros((3730, 3292), bool)
    rng = np.random.default_rng(2)
    foot.ravel()[rng.choice(foot.size, G.FOOTPRINT_PIXELS, replace=False)] = True
    labels = np.zeros_like(foot)
    dots = np.zeros((3730, 3292), bool)
    dots.ravel()[rng.choice(np.flatnonzero(foot), 1000, replace=False)] = True
    z = tmp_path / "tmpl.tif"
    _write(z, np.where(foot, 0, np.nan).astype(np.float32), nodata=np.nan)
    for mode in ("zeros", "nan"):
        p = tmp_path / f"good-{mode}.tif"
        SUB.write_mask(dots, foot, z, p, outside=mode)
        rec = SUB.audit_geotiff(p, foot, labels, mode)
        assert rec["all_checks_passed"] and rec["emitted_positive_pixels"] == 1000


def test_shipped_h82_3_geotiff_pair_in_ci():
    import json
    root = Path(__file__).resolve().parents[1]
    gate = json.loads((root / "evidence" / "gate.json").read_text())
    assert gate["verdict"] == "PROMOTED"
    assert all(gate["rules"].values())
    z_rec = gate["receipts"]["zeros"]
    n_rec = gate["receipts"]["nan"]
    z_path = root / "docs" / "downloads" / z_rec["filename"]
    n_path = root / "docs" / "downloads" / n_rec["filename"]
    assert SUB.sha256_file(z_path) == z_rec["sha256"] == gate["raster_sha256_zeros"]
    assert SUB.sha256_file(n_path) == n_rec["sha256"]
    with rasterio.open(z_path) as sz, rasterio.open(n_path) as sn:
        az = sz.read(1)
        an = sn.read(1)
        assert sz.shape == sn.shape == (G.HEIGHT, G.WIDTH)
        assert str(sz.crs) == str(sn.crs) == G.CRS
        assert tuple(sz.transform)[:6] == G.TRANSFORM
        assert int(np.isfinite(az).sum()) == G.TOTAL_PIXELS
        assert float(az.min()) >= 0.0 and float(az.max()) <= 1.0
        assert int(np.isfinite(an).sum()) == G.FOOTPRINT_PIXELS
        fin_n = an[np.isfinite(an)]
        assert float(fin_n.min()) >= 0.0 and float(fin_n.max()) <= 1.0
        assert int((az > 0).sum()) == 35000
        assert np.array_equal(az > 0, np.isfinite(an) & (an > 0))
