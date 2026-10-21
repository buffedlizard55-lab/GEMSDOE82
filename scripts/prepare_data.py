#!/usr/bin/env python3
"""Validate competition inputs and write a small auditable manifest.

The script never changes source rasters.  It treats values below -1e30 in the
feature stack as sentinels, and defines the scoring footprint from finite cells
of ``sample_submission.tif``.  Use ``GEMS_DATA_DIR`` to point at the official
DrivenData download or the public-mirror cache.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gemsdoe82.paths import EPSG, HEIGHT, WIDTH, data_dir  # noqa: E402

EXPECTED_BANDS = [
    "mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc",
    "geod_shearrate", "geod_dilaterate", "tmi_vg", "deq_n100a15", "iso_grav_anom_vg",
    "det_elev", "iso_grav_anom", "tmi", "depth_to_base_surf", "ieq_n100a15",
    "cond_surf", "iso_grav_anom_hg", "det_elev_slope",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    root = data_dir()
    required = [root / name for name in ("training_features.tif", "labels.tif", "existing_faults.tif", "sample_submission.tif")]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing inputs: " + ", ".join(missing) + ". Run scripts/fetch_public_mirror_cache.py or use official data.")
    with rasterio.open(root / "sample_submission.tif") as sample:
        footprint = np.isfinite(sample.read(1, masked=False))
        shape = sample.shape
        transform = list(sample.transform)[:6]
        crs = sample.crs
        if shape != (HEIGHT, WIDTH) or crs is None or crs.to_epsg() != EPSG:
            raise ValueError(f"sample grid mismatch: shape={shape}, crs={crs}")
    with rasterio.open(root / "existing_faults.tif") as faults, rasterio.open(root / "labels.tif") as labels:
        fault_array = faults.read(1, masked=False)
        label_array = labels.read(1, masked=False)
        if faults.shape != shape or labels.shape != shape:
            raise ValueError("fault/label shape mismatch")
        if not np.array_equal(fault_array, label_array):
            raise ValueError("existing_faults.tif and labels.tif differ; use labels.tif for the organizer source")
        catalogue = (fault_array == 1) & footprint
    band_stats = []
    with rasterio.open(root / "training_features.tif") as features:
        if features.shape != shape or features.count != len(EXPECTED_BANDS):
            raise ValueError(f"feature stack mismatch: {features.shape}, {features.count} bands")
        names = [features.tags(i).get("band_name", f"band_{i}") for i in range(1, features.count + 1)]
        if names != EXPECTED_BANDS:
            raise ValueError(f"band order mismatch: {names}")
        for index, name in enumerate(names, 1):
            array = features.read(index).astype(np.float32, copy=False)
            sentinel = (~np.isfinite(array)) | (array < -1e30)
            finite_inside = footprint & ~sentinel
            values = array[finite_inside]
            if values.size == 0:
                raise ValueError(f"band {name} has no valid cells inside footprint")
            band_stats.append({
                "index": index,
                "name": name,
                "finite_inside": int(values.size),
                "sentinel_inside": int((footprint & sentinel).sum()),
                "min": float(values.min()),
                "p02": float(np.percentile(values, 2)),
                "median": float(np.median(values)),
                "p98": float(np.percentile(values, 98)),
                "max": float(values.max()),
            })
    manifest = {
        "evidence_class": "DATA-MEASUREMENT",
        "prepared_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "official DrivenData download if GEMS_DATA_DIR points there; otherwise pinned public GitHub mirror",
        "data_dir": str(root.relative_to(ROOT)) if root.is_relative_to(ROOT) else "external GEMS_DATA_DIR",
        "grid": {"shape": list(shape), "crs": str(crs), "epsg": crs.to_epsg(), "transform": transform, "footprint_pixels": int(footprint.sum())},
        "catalogue_pixels": int(catalogue.sum()),
        "files": {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in required},
        "bands": band_stats,
        "irregularities": [
            "The competition data tab redirects to login in the current environment; public-mirror provenance is therefore not organizer-authenticated.",
            "Feature nodata sentinels are excluded from feature calculations; submission writer emits zeros outside the finite sample footprint to avoid the portal range error.",
        ],
    }
    out = ROOT / "registry" / "data_manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
