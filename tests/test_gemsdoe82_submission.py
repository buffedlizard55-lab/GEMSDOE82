"""Comprehensive Pass 1 / Pass 2 / Pass 3 verification suite for GEMSDOE82 (Lane H82-CSAM)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor"))

from gems57 import evaluate_holdout as EH, gates, validate as V  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_pass1_template_pins_and_prompt_archive() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "First, put this prompt into the repo README.md" in readme
    assert "OK TO DOWNLOAD AND SUBMIT" in readme
    assert "0.2778" in readme and "0.4413" in readme and "0.3195" in readme

    pins = json.loads((ROOT / "registry" / "template_pin.json").read_text())
    for rel, expected_sha in pins.get("files", {}).items():
        p = ROOT / "vendor" / "gems57" / rel
        assert p.is_file(), f"Missing pinned template file: {rel}"
        assert _sha256(p) == expected_sha, f"SHA-256 mismatch on {rel}"


def test_pass1_h33_byte_forensics_and_three_experiments() -> None:
    f_h33 = json.loads((ROOT / "evidence" / "h33_byte_forensics.json").read_text())
    assert f_h33["forensic_D28_to_H33"]["formula_matches_bit_for_bit"] is True
    assert f_h33["forensic_D28_to_H33"]["removed_dots"] == 6436
    assert f_h33["forensic_D28_to_H33"]["added_dots"] == 0

    exp1 = json.loads((ROOT / "evidence" / "h82_exp1_canary_and_ablation.json").read_text())
    assert exp1["evidence_class"] == "HOLDOUT-DTI"
    assert exp1["evaluator_version"] == EH.VERSION
    assert exp1["leakage_canary"]["n_channels_tested"] == 114
    assert exp1["leakage_canary"]["all_passed"] is True
    assert exp1["leakage_canary"]["max_symmetric_auc"] <= 0.90

    exp2 = json.loads((ROOT / "evidence" / "h82_exp2_dual_holdout.json").read_text())
    assert exp2["evidence_class"] == "HOLDOUT-DTI"
    assert exp2["total_withheld_positive_pixels"] == 22663
    p_scores = exp2["pooled_dual_seed"]["scores"]
    assert p_scores["H82_CSAM_41200_uncapped"]["dti"] > p_scores["H33_fold_fair"]["dti"] + 0.06
    assert exp2["pooled_dual_seed"]["paired_differences"]["H33_fold_fair"]["ci95"][0] > 0.05

    exp3 = json.loads((ROOT / "evidence" / "h82_exp3_uniqueness_and_validation.json").read_text())
    assert exp3["n_prior_rasters_scanned"] >= 186
    assert exp3["pre_placement_surface"]["max_spearman_rho"] <= 0.90
    assert exp3["pre_placement_surface"]["max_top41200_3px_overlap"] <= 0.70
    assert exp3["final_dots_41200"]["max_spearman_rho"] <= 0.90
    assert exp3["final_dots_41200"]["max_3px_overlap"] <= 0.70
    assert exp3["final_dots_37654_parity"]["max_spearman_rho"] <= 0.90
    assert exp3["final_dots_37654_parity"]["max_3px_overlap"] <= 0.70


def test_pass2_geotiff_validation_and_downloads() -> None:
    rc = json.loads((ROOT / "run_card.json").read_text())
    assert rc["verdict"] == "promote"
    assert rc["experiments_executed"] == 3
    assert 1 <= len(rc["submission"]["submission_name"]) <= 140
    assert 1 <= len(rc["submission"]["submission_note"]) <= 140

    sample_path = ROOT / "data" / "bridge" / "sample_submission.tif"
    cat_path = ROOT / "data" / "bridge" / "existing_faults.tif"
    with rasterio.open(sample_path) as ds_s:
        foot = np.isfinite(ds_s.read(1))
    with rasterio.open(cat_path) as ds_c:
        cat = ds_c.read(1) > 0

    for rel_tif, expected_dots, expected_sha in [
        ("submissions/gems82-h82-csam-dinkelbach-41200-20261021-zeros.tif", 41200, rc["submission"]["raster_sha256"]),
        ("docs/downloads/gems82-h82-csam-dinkelbach-41200-20261021-zeros.tif", 41200, rc["submission"]["raster_sha256"]),
        ("downloads/gems82-h82-csam-dinkelbach-41200-20261021-zeros.tif", 41200, rc["submission"]["raster_sha256"]),
        ("submissions/gems82-h82-csam-dinkelbach-37654-20261021-zeros.tif", 37654, rc["submission"]["companion_parity_37654"]["raster_sha256"]),
        ("docs/downloads/gems82-h82-csam-dinkelbach-37654-20261021-zeros.tif", 37654, rc["submission"]["companion_parity_37654"]["raster_sha256"]),
        ("downloads/gems82-h82-csam-dinkelbach-37654-20261021-zeros.tif", 37654, rc["submission"]["companion_parity_37654"]["raster_sha256"]),
    ]:
        p = ROOT / rel_tif
        assert p.is_file(), f"Missing submission TIF: {rel_tif}"
        assert _sha256(p) == expected_sha
        rep = gates.format_report(p, sample_path, footprint=foot)
        assert rep["ok"] is True, f"Format report failed for {rel_tif}: {rep['problems']}"
        val = V.validate(p, foot, cat)
        V.assert_submittable(val)
        assert val["emitted_positive_pixels"] == expected_dots
        assert val["on_catalogue_positive_pixels"] == 0
        assert val["n_nan"] == 0 and val["n_infinite"] == 0


def test_pass3_html_pages_and_local_links() -> None:
    for page_rel in ("index.html", "executive-summary.html", "docs/index.html", "docs/executive-summary.html"):
        page_path = ROOT / page_rel
        assert page_path.is_file(), f"Missing HTML page: {page_rel}"
        html = page_path.read_text()
        assert "OK TO DOWNLOAD AND SUBMIT" in html
        assert "ORGANIZER-CONFIRMED" in html and "HOLDOUT-DTI" in html
        base_dir = page_path.parent
        for attr in re.findall(r'(?:href|src)="([^"]+)"', html):
            if attr.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = (base_dir / attr.split("#")[0]).resolve()
            assert target.exists(), f"Broken link '{attr}' in {page_rel} -> {target}"
