#!/usr/bin/env python3
"""Autonomous SHA-256 verified competition & public geoscience data preparation for GEMSDOE82.

Resolves the data-placement blocker with zero manual input by restoring SHA-256-pinned
archives into `.cache/data` and `data/raw` (both git-ignored so repository snapshots remain
small and clean) and verifying every cryptographic SHA-256 pin bit-for-bit.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))

from gems57 import grid as G  # noqa: E402

CORE_PINS = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "existing_faults.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}

SIBLING_REPOS = ("GEMSDOE73", "GEMSDOE74", "GEMSDOE75", "GEMSDOE76", "GEMSDOE77")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def link_or_copy(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.exists():
            return
        dst.unlink(missing_ok=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.symlink_to(src.resolve())


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "restore_h77_step_data.py")], check=True)
    cache_data = ROOT / ".cache" / "data"
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    link_or_copy(cache_data / "training_features.tif", raw_dir / "training_features.tif")
    link_or_copy(cache_data / "existing_faults.tif", raw_dir / "existing_faults.tif")
    link_or_copy(cache_data / "existing_faults.tif", raw_dir / "labels.tif")
    link_or_copy(cache_data / "sample_submission.tif", raw_dir / "sample_submission.tif")
    link_or_copy(cache_data / "data" / "external", raw_dir / "external")

    lidar_json = raw_dir / "external" / "lidar_scarp_features.json"
    if not lidar_json.exists():
        with lidar_json.open("wb") as out:
            subprocess.run(
                [
                    "gh",
                    "api",
                    "repos/buffedlizard55-lab/GEMSDOE24/contents/data/external/lidar_scarp_features.json",
                    "-H",
                    "Accept: application/vnd.github.raw",
                ],
                stdout=out,
                check=True,
            )

    audit_dir = raw_dir / "external" / "audit_sources"
    audit_dir.mkdir(parents=True, exist_ok=True)
    for af in ("acquisition_block_id_100m.tif", "blm_closed_claim_distance_m.tif", "tiger_road_distance_m.tif"):
        ap = audit_dir / af
        if not ap.exists():
            with ap.open("wb") as out:
                subprocess.run(
                    [
                        "gh",
                        "api",
                        f"repos/buffedlizard55-lab/GEMSDOE24/contents/data/external/audit_sources/{af}",
                        "-H",
                        "Accept: application/vnd.github.raw",
                    ],
                    stdout=out,
                    check=True,
                )

    subprocess.run([sys.executable, str(ROOT / "scripts" / "restore_data.py")], check=True)

    # Restore pinned witnesses and sibling rasters
    reg_dir = ROOT / ".cache" / "registry"
    sib_dir = ROOT / ".cache" / "siblings"
    reg_dir.mkdir(parents=True, exist_ok=True)
    sib_dir.mkdir(parents=True, exist_ok=True)

    pins = json.loads((ROOT / "registry" / "witness_sources.json").read_text())
    for key, meta in pins.items():
        path = reg_dir / ("dense_witness.tif" if key == "dense_witness" else "h33.tif")
        if not path.exists() or sha256_file(path) != meta["sha256"]:
            with path.open("wb") as out:
                subprocess.run(
                    [
                        "gh",
                        "api",
                        f"repos/{meta['repo']}/contents/{meta['path']}?ref={meta['ref']}",
                        "-H",
                        "Accept: application/vnd.github.raw",
                    ],
                    stdout=out,
                    check=True,
                )
        assert sha256_file(path) == meta["sha256"], f"Witness SHA-256 mismatch on {key}"

    if len(list(sib_dir.glob("*.tif"))) < 50:
        for repo in SIBLING_REPOS:
            url = f"https://codeload.github.com/buffedlizard55-lab/{repo}/tar.gz/main"
            req = urllib.request.Request(url, headers={"User-Agent": "gemsdoe82-prepare"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                with tarfile.open(fileobj=resp, mode="r|gz") as tf:
                    for m in tf:
                        if not m.isfile():
                            continue
                        rel = m.name.split("/", 1)[1] if "/" in m.name else m.name
                        low = rel.lower()
                        if not low.endswith(".tif"):
                            continue
                        if any(
                            k in low
                            for k in (
                                "existing_faults",
                                "sample_submission",
                                "example_submission",
                                "labels.tif",
                                "training_features",
                                "data/external",
                                "data/raw",
                                "data/official",
                                "data/bridge",
                            )
                        ):
                            continue
                        dst = sib_dir / f"{repo}__{Path(rel).name}"
                        if not dst.exists():
                            dst.write_bytes(tf.extractfile(m).read())

    core_verified = {}
    for k, exp in CORE_PINS.items():
        got = sha256_file(raw_dir / k)
        assert got == exp, f"SHA-256 mismatch on {k}: {got} != {exp}"
        core_verified[k] = {"sha256": got, "bytes": (raw_dir / k).stat().st_size, "ok": True}

    grid = G.load_grid(raw_dir)
    manifest = {
        "schema": "gemsdoe82-prepared-manifest-v1",
        "evidence_class": "DATA-MEASUREMENT",
        "shape": list(grid.shape),
        "crs": str(grid.crs),
        "transform": list(tuple(grid.transform)[:6]),
        "footprint_pixels": int(grid.footprint.sum()),
        "catalogue_pixels": int(grid.catalogue.sum()),
        "core_files": core_verified,
        "archive_registry_rasters": len(list((cache_data / "registry" / "rasters").glob("*.tif"))),
        "sibling_rasters": len(list(sib_dir.glob("*.tif"))),
        "scored_reference_rasters": len(list((raw_dir / "scored").glob("*.tif"))),
        "training_labels_note": "existing_faults.tif / labels.tif is the mapped fault catalogue, NOT unpublished organizer test truth",
    }
    (ROOT / "data" / "prepared_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "evidence" / "data_receipt.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
