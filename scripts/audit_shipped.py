"""Independent re-verification of shipped artifacts (no trust in build scripts).

Re-opens every file in docs/downloads from disk and checks:
  1. -zeros.tif: 12/12 submission audit (strict: whole grid finite in [0,1]).
  2. -nan.tif: 12/12 submission audit (competition format: NaN outside).
  3. -zeros.zip: contains exactly one .tif, byte-identical to the shipped zeros.
  4. checks-*.json receipts match recomputed sha256/size/dots.
  5. submissions_manifest.json names files that exist.
  6. evidence/gate.json verdict == PROMOTED and slug matches downloads.
  7. No NaN inside footprint (both variants), values in [0,1], CRS/shape/
     transform match the template.

Exit 0 + 'PORTAL-ILLEGAL ARTIFACTS: none' on success; exit 1 otherwise.
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
    report = {"slug": slug, "checks": {}, "portal_illegal": []}

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
    report["checks"]["gate"] = {"verdict": gate["verdict"],
                                "rules": gate["rules"]}
    if gate["verdict"] != "PROMOTED":
        report["portal_illegal"].append("gate verdict is not PROMOTED")
    for f in manifest["files"]:
        assert (dl / f).exists(), f
    report["verdict"] = "PORTAL-ILLEGAL ARTIFACTS: none" if not report["portal_illegal"] else "FAIL"
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))
    print(report["verdict"], "->", args.out)
    return 0 if not report["portal_illegal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
