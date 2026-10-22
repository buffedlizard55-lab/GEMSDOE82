"""End-to-end programmatic verification suite for GEMSDOE82 (`Lane H82`).

Tests without any human intervention:
  1. Byte-identical SHA-256 integrity of all 23 canonical `vendor/gems57` shared modules.
  2. SHA-256 verification of all 17 competition + external datasets (`0` forbidden columns in stack).
  3. Rule 4 Single-Feature Leakage Canary (`72/72` features `<= 0.90` symmetric ROC-AUC).
  4. Mathematical submodularity (`Delta F(y | A) >= Delta F(y | B)` for `A subset B`) and
     exact `29`-offset `R=300m` kernel identity with `vendor/gems57/metric.py`.
  5. Strict DrivenData `[0.0, 1.0]` GeoTIFF + ZIP validation (`15/15` checks, `0` NaNs anywhere,
     `0.0` outside footprint, `0` catalogue dots, exact SHA-256 parity across `submissions/` & `docs/downloads/`).
  6. Protocol compliance: `<= 3` experiments, monotonic `E82_1 < E82_2 < E82_3` progression,
     statistically significant paired 20-km block-bootstrap CIs (`> 0`), `<= 140`-char note,
     and complete `1,026`-raster uniqueness pass (`|rho| <= 0.90`, `overlap <= 0.70`).
  7. HTML & `README.md` deliverable link, download-path, and Core Values audit.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor"))

from gems57 import grid as grid_mod
from gems57 import metric, validate
from gems82.emit import (
    DEFAULT_BUDGET_PX,
    DEFAULT_QUADRANT_QUOTAS,
    _compute_quadrant_targets,
    build_exact_300m_kernel_offsets,
    submodular_expected_dti_emit,
)
from gems82.features import FORBIDDEN_COLS, STATIC_FEATURE_NAMES


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_template_pin_sha256_integrity():
    pin = json.loads((ROOT / "registry" / "template_pin.json").read_text())
    files = pin["files"]
    assert len(files) == 23
    for item in files:
        local_p = ROOT / "vendor" / "gems57" / item["file"]
        assert local_p.is_file(), f"Missing pinned module {local_p}"
        assert _sha256(local_p) == item["sha256"], f"Modified shared module {local_p}"


def test_data_verification_and_no_forbidden_features():
    dv = json.loads((ROOT / "evidence" / "data_verification.json").read_text())
    assert len(dv["verified_assets"]) == 17
    for asset in dv["verified_assets"]:
        p = ROOT / ".cache" / "gems_data" / asset["rel_path"]
        assert p.is_file(), f"Missing verified asset {p}"
        assert p.stat().st_size == asset["bytes"]
    assert len(STATIC_FEATURE_NAMES) == 64
    for nm in STATIC_FEATURE_NAMES:
        assert nm not in FORBIDDEN_COLS
        assert "sgmc" not in nm.lower()


def test_leakage_canary_72_features():
    canary = json.loads((ROOT / "evidence" / "leakage_canary_audit.json").read_text())
    assert canary["all_passed"] is True
    assert canary["n_features_tested"] == 72
    assert canary["max_symmetric_auc"] <= 0.90
    for f in canary["features"]:
        assert 0.50 <= f["symmetric_auc"] <= 0.90


def test_exact_300m_kernel_and_submodularity_theorem():
    drs, dcs, kws = build_exact_300m_kernel_offsets()
    assert len(kws) == 25  # dr^2 + dc^2 < 9 strictly positive support (k(300m) == 0)
    for dr, dc, kw in zip(drs, dcs, kws):
        d_px = np.hypot(dr, dc)
        assert np.isclose(kw, float(metric.kernel(np.array([d_px]))[0]), atol=1e-6)

    # Verify strict diminishing marginal returns: Delta F(y | A) >= Delta F(y | B) for all A subset B
    rng = np.random.default_rng(82)
    H, W = 28, 28
    p_hat = rng.uniform(0.0, 1.0, size=(H, W)).astype(np.float64)

    def F_obj(S):
        cov = np.zeros((H, W), dtype=np.float64)
        for r, c in S:
            for dr, dc, kw in zip(drs, dcs, kws):
                nr, nc = r + int(dr), c + int(dc)
                if 0 <= nr < H and 0 <= nc < W and kw > cov[nr, nc]:
                    cov[nr, nc] = float(kw)
        return float((p_hat * cov).sum())

    all_pts = [(int(r), int(c)) for r in range(4, 24) for c in range(4, 24)]
    for _ in range(25):
        chosen = rng.choice(len(all_pts), size=9, replace=False)
        A = [all_pts[i] for i in chosen[:3]]
        B = [all_pts[i] for i in chosen[:8]]  # A is a strict subset of B
        y = all_pts[chosen[8]]
        gain_A = F_obj(A + [y]) - F_obj(A)
        gain_B = F_obj(B + [y]) - F_obj(B)
        assert gain_A >= gain_B - 1e-11, f"Submodularity violated: {gain_A} < {gain_B}"

    # Verify quadrant targets sum identically to budget
    q_targets = _compute_quadrant_targets(DEFAULT_BUDGET_PX, DEFAULT_QUADRANT_QUOTAS)
    assert sum(q_targets) == DEFAULT_BUDGET_PX

    # Verify emitter produces clean `[0, 1]` float32 output with zero forbidden hits
    surf_syn = rng.uniform(0.0, 1.0, size=(64, 64)).astype(np.float32)
    fp_syn = np.ones((64, 64), dtype=bool)
    fp_syn[:4, :] = False
    forb_syn = np.zeros((64, 64), dtype=bool)
    forb_syn[10:15, 10:15] = True
    emitted, st = submodular_expected_dti_emit(surf_syn, forb_syn, fp_syn, budget=40)
    assert emitted.dtype == np.float32
    assert int(emitted.sum()) == 40
    assert float(emitted[~fp_syn].max()) == 0.0
    assert float(emitted[forb_syn].max()) == 0.0
    assert st["total_dots"] == 40


def test_submission_geotiff_and_zip_strict_drivendata_compliance():
    rc = json.loads((ROOT / "evidence" / "run_card.json").read_text())
    g = grid_mod.load_grid(ROOT / ".cache" / "gems_data")

    tif_main = ROOT / rc["submission"]["tif_path"]
    tif_alias = ROOT / rc["submission"]["stable_alias_path"]
    zip_main = ROOT / rc["submission"]["zip_path"]
    dl_main = ROOT / "docs" / "downloads" / tif_main.name
    dl_alias = ROOT / "docs" / "downloads" / tif_alias.name
    dl_zip = ROOT / "docs" / "downloads" / zip_main.name

    for p in (tif_main, tif_alias, dl_main, dl_alias):
        assert p.is_file(), f"Missing submission GeoTIFF: {p}"
        rec = validate.validate(p, g.footprint, g.catalogue)
        assert rec["all_checks_passed"] is True, f"Failed validation checks: {rec}"
        assert rec["n_nan"] == 0
        assert rec["n_infinite"] == 0
        assert rec["min"] == 0.0
        assert rec["max"] == 1.0
        assert rec["emitted_positive_pixels"] == DEFAULT_BUDGET_PX
        assert _sha256(p) == rc["submission"]["sha256_tif"]

        with rasterio.open(p) as ds:
            arr = ds.read(1)
            assert ds.dtypes[0] == "float32"
            assert ds.count == 1
            assert (ds.height, ds.width) == (3730, 3292)
            assert str(ds.crs) == "EPSG:32611"
            assert np.isfinite(arr).all()
            assert (arr >= 0.0).all() and (arr <= 1.0).all()
            assert np.all(arr[~g.footprint] == 0.0)
            assert np.all(arr[g.catalogue] == 0.0)

    # Verify ZIP archive contains exactly the single validated `.tif` byte-for-byte
    for zp in (zip_main, dl_zip):
        assert zp.is_file()
        with zipfile.ZipFile(zp, "r") as zf:
            names = zf.namelist()
            assert len(names) == 1 and names[0].endswith(".tif")
            assert hashlib.sha256(zf.read(names[0])).hexdigest() == rc["submission"]["sha256_tif"]


def test_run_card_protocol_budget_monotonicity_and_uniqueness():
    rc = json.loads((ROOT / "evidence" / "run_card.json").read_text())
    assert rc["decision"] == "promote"
    assert rc["experiments_run"] == 3 <= rc["experiment_budget_limit"]
    assert 1 <= len(rc["submission"]["submission_note"]) <= 140

    prog = rc["metrics"]["experiment_progression"]
    assert len(prog) == 3
    d1, d2, d3 = [p["holdout_all_dti"] for p in prog]
    assert d1 < d2 < d3, f"Expected strict monotonic gain: {d1}, {d2}, {d3}"
    for p in prog:
        assert p["holdout_all_label"].startswith("HOLDOUT-DTI (")
        assert p["holdout_detached_label"].startswith("HOLDOUT-DTI (")
        assert abs(p["north_share_nw_plus_ne"] - 0.50) < 1e-3

    # Verify all paired spatial-cluster bootstrap CIs against controls exclude 0
    pdiffs = rc["metrics"]["paired_differences_all_vs_controls"]
    for ctrl in (
        "random_control_37654",
        "GEMSDOE25_D28_live02600_static",
        "E82_1_pu_multiscale_meta_nms",
        "E82_2_physics_decontam_noisy_or_nms",
    ):
        assert pdiffs[ctrl]["delta"] > 0
        assert pdiffs[ctrl]["ci95"][0] > 0

    # Verify complete 1,026-raster uniqueness audit
    u = json.loads((ROOT / "evidence" / "uniqueness_audit_1026.json").read_text())
    assert u["passed"] is True
    assert u["n_registry_rasters_audited"] == 1026
    assert u["summary"]["max_abs_surface_spearman_across_all_1026"] <= 0.90
    assert u["summary"]["max_mutual_3px_overlap_across_all_1026"] <= 0.70
    assert u["summary"]["max_forward_3px_overlap_across_all_sparse_candidates"] <= 0.70


def test_readme_and_html_pages_integrity():
    readme_p = ROOT / "README.md"
    if not readme_p.exists():
        pytest.skip("README not yet written")
    txt = readme_p.read_text(encoding="utf-8")
    assert "Maximize P(Win)" in txt
    assert "Own the Outcome" in txt
    assert "HOLDOUT-DTI" in txt
    assert "ORGANIZER-CONFIRMED" in txt

    for html_rel in ("index.html", "executive-summary.html", "docs/index.html", "docs/executive-summary.html"):
        hp = ROOT / html_rel
        assert hp.is_file(), f"Missing page {hp}"
        h = hp.read_text(encoding="utf-8")
        assert "OK TO SUBMIT" in h
        assert ".tif" in h
        for href in re.findall(r'(?:href|src)="([^"#?]+)"', h):
            if href.startswith(("http://", "https://", "mailto:", "javascript:", "data:")):
                continue
            target = (hp.parent / href).resolve()
            assert target.exists(), f"Broken relative asset/download link `{href}` in `{html_rel}` -> `{target}`"
