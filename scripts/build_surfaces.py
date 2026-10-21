"""Build + cache the five lane-82 label-free surfaces as work/surfaces/*.npy."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems82 import features as F
from gems82 import grid as G


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out-dir", default="work/surfaces")
    args = ap.parse_args()
    ddir = Path(args.data_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    foot = G.read_footprint(ddir / "sample_submission.tif")
    t0 = time.time()
    lidar = F.read_lidar(ddir / "external")
    rad = F.read_rad(ddir / "external")
    ext = F.read_ext(ddir / "external")
    print(f"reads done in {time.time()-t0:.1f}s", flush=True)
    builders = {
        "h82_1_antislope": lambda: F.h82_1_antislope_lineament(lidar, foot),
        "h82_2_radiometric": lambda: F.h82_2_radiometric_break(rad, ext, foot),
        "h82_3_valley": lambda: F.h82_3_valley_deflection(lidar, foot),
        "h82_4_conjugate": lambda: F.h82_4_conjugate_intersection(lidar, foot),
        "h82_5_thermal": lambda: F.h82_5_thermal_upflow_prior(ddir, foot),
    }
    meta = {}
    for name, fn in builders.items():
        t1 = time.time()
        s = fn()
        np.save(out / f"{name}.npy", s)
        meta[name] = {"min": float(s.min()), "max": float(s.max()),
                      "mean": float(s[foot].mean()), "sec": round(time.time() - t1, 1)}
        print(f"{name}: min={s.min():.4f} max={s.max():.4f} mean_in={s[foot].mean():.4f} "
              f"({time.time()-t1:.1f}s)", flush=True)
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
