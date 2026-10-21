"""Verify sha256 pins + grid geometry of fetched data files."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems82 import grid as G

PINS = {
    # file (relative to data dir) -> (sha256, bytes)
    "labels.tif": ("7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093", 425830),
    "sample_submission.tif": ("2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc", 1599597),
    "existing_faults.tif": ("7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093", 425830),
    "external/derived_sgmc_faults_100m_u8.tif": ("643cbe992ef4ba37588fb469163ed8291e3ceb23d6c1f78a3cfaa462430c2da0", 198602),
    "external/lidar_scarp_features_u8.tif": ("d580bb8bdcdb941e32fefb8b38044bc5bf04e199bf2e83498c3576e6fc465568", 36943606),
    "external/geodawn_rad_u8.tif": ("c22420f75999030d7cc65c9e31e50d232ea6158423bca051613a18a8b20ba682", 26612970),
    "external/geodawn_extensions_u8.tif": ("a35a9c6d2a14786f4dab85481ee59769213072f5dab5b2535ea82ae4d9bb7d9b", 27132925),
    "external/gdr_wellspring_in_footprint.csv": ("122718e65bdf55aab0ee12ad20d80062f0deb1de957225a61ad880dd5dc196ea", 2146771),
    "registry/d28-44090-nan.tif": ("91eae1ca42ec845eaa8c2ba32da49806e24751743459b8a10017c479bbe639b8", 1603424),
    "registry/h33-2-b2-37654-nan.tif": ("baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd", 355443),
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()
    d = Path(args.data_dir)
    results = {}
    ok = True
    for rel, (pin, nbytes) in PINS.items():
        p = d / rel
        if not p.exists():
            results[rel] = {"status": "MISSING"}
            ok = False
            continue
        h, n = sha256(p), p.stat().st_size
        passed = (h == pin and n == nbytes)
        ok = ok and passed
        results[rel] = {"status": "PASS" if passed else "FAIL", "sha256": h, "bytes": n,
                        "expected_sha256": pin, "expected_bytes": nbytes}
        print(("PASS " if passed else "FAIL ") + f"{rel}  {h[:16]}…  {n} B")
    # grid geometry on the core grids
    for rel in ("labels.tif", "sample_submission.tif"):
        p = d / rel
        if p.exists():
            import rasterio
            with rasterio.open(p) as s:
                print(f"grid {rel}: {s.height}x{s.width} {s.crs} res={s.res} dtype={s.dtypes[0]}")
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(results, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
