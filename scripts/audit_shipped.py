"""Recheck archived candidate bytes and distinguish format from authorization.

This audit can establish only raster-format properties (range, NaN, grid, hash).
It must never claim organizer eligibility or authorize upload. Submission status
requires registry/submission_authorization.json with an independent selector
receipt bound to the exact candidate SHA-256.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems82 import grid as G
from gems82 import submission as SUB


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--downloads", default="docs/downloads")
    ap.add_argument("--out", default="evidence/ship_audit.json")
    args = ap.parse_args()
    ddir, dl = Path(args.data_dir), Path(args.downloads)
    foot = G.read_footprint(ddir / "sample_submission.tif")
    labels = G.read_labels(ddir / "labels.tif") & foot
    gate = json.loads(Path("evidence/gate.json").read_text())
    manifest = json.loads((dl / "submissions_manifest.json").read_text())
    slug = manifest["slug"]
    assert slug == gate["slug"], (slug, gate["slug"])
    authorization = json.loads(Path("registry/submission_authorization.json").read_text())
    report = {
        "slug": slug,
        "checks": {},
        "format_audit_passed": False,
        "submission_authorized": False,
        "authorization_status": authorization.get("status", "MISSING"),
    }

    for mode in ("zeros", "nan"):
        tif = dl / f"{slug}-{mode}.tif"
        assert tif.exists(), tif
        rec = SUB.audit_geotiff(tif, foot, labels, mode)  # raises unless 12/12
        disk = json.loads((dl / f"checks-{slug}-{mode}.tif.json").read_text())
        assert disk["sha256"] == rec["sha256"] == G.sha256(tif), mode
        assert disk["emitted_positive_pixels"] == rec["emitted_positive_pixels"], mode
        with rasterio.open(tif) as s:
            a = s.read(1)
        report["checks"][mode] = {
            "audit_12_of_12": True,
            "sha256": rec["sha256"], "dots": rec["emitted_positive_pixels"],
            "nan_inside_footprint": int(np.isnan(a[foot]).sum()),
            "min_in": rec["in_footprint_min"], "max_in": rec["in_footprint_max"],
            "grid_ok": G.check_grid(tif)["ok_grid"],
        }
        print(f"{mode}: 12/12 PASS dots={rec['emitted_positive_pixels']} "
              f"sha256={rec['sha256'][:16]}… grid_ok={report['checks'][mode]['grid_ok']}")

    zp = dl / f"{slug}-zeros.zip"
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        assert len(names) == 1 and names[0].endswith(".tif"), names
        assert z.read(names[0]) == (dl / f"{slug}-zeros.tif").read_bytes()
    report["checks"]["zip"] = {"single_tif": True, "byte_identical": True,
                               "sha256": G.sha256(zp)}
    for f in manifest["files"]:
        assert (dl / f).exists(), f
    raster_sha = report["checks"]["zeros"]["sha256"]
    authorized = (
        authorization.get("status") == "AUTHORIZED"
        and authorization.get("selected_for_submission") is True
        and bool(authorization.get("selector_receipt"))
        and authorization.get("authorized_sha256") == raster_sha
        and not authorization.get("duplicate_screen", {}).get("verdict", "").startswith("DUPLICATE")
    )
    report["format_audit_passed"] = all(
        report["checks"][mode]["audit_12_of_12"] for mode in ("zeros", "nan")
    )
    report["submission_authorized"] = authorized
    report["authorization_reason"] = authorization.get("reason")
    report["verdict"] = (
        "FORMAT AUDIT PASS; SELECTOR AUTHORIZATION VERIFIED"
        if report["format_audit_passed"] and authorized
        else "FORMAT AUDIT ONLY; NOT AUTHORIZED FOR SUBMISSION"
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))
    print(report["verdict"], "->", args.out)
    return 0 if report["format_audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
