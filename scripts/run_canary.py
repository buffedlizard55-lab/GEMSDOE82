"""LEAKAGE CANARY: test each lane-82 surface alone before trusting any result.

For each surface: AUC vs (a) SGMC off-catalogue truth, (b) full catalogue.
AUC > 0.90 on EITHER = leakage until proven otherwise (label-free surfaces
must not separate faults nearly perfectly; the catalogue itself would).

Also reports: mutual Spearman rho between surfaces (|rho| > 0.95 = redundant),
and the fraction of each surface's top-1% mass within 3 px of the catalogue
(flank-loading diagnostic).

Writes evidence/canary.json. Exit code 1 if any canary trips.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems82 import features as F
from gems82 import grid as G


def auc_mw(score: np.ndarray, pos: np.ndarray) -> float:
    """Mann-Whitney AUC of score for boolean pos (both flattened, finite only)."""
    s = np.asarray(score, dtype=np.float64).ravel()
    p = np.asarray(pos, bool).ravel()
    fin = np.isfinite(s)
    s, p = s[fin], p[fin]
    n1 = int(p.sum())
    n0 = int((~p).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(s) + 1)
    # average-rank ties correction via pandas-free method
    _, first, counts = np.unique(s[order], return_index=True, return_counts=True)
    for f, c in zip(first.tolist(), counts.tolist()):
        if c > 1:
            ranks[order[f:f + c]] = f + (c + 1) / 2.0
    u = ranks[p].sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n0))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    from scipy.stats import rankdata
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    fin = np.isfinite(a) & np.isfinite(b)
    a, b = a[fin], b[fin]
    if a.std() == 0 or b.std() == 0:
        return 0.0
    ra = rankdata(a) - (len(a) + 1) / 2
    rb = rankdata(b) - (len(b) + 1) / 2
    return float((ra * rb).sum() / np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default="evidence/canary.json")
    ap.add_argument("--stride", type=int, default=2,
                    help="strided sampling for AUC speed (2 = every 2nd pixel)")
    args = ap.parse_args()
    ddir = Path(args.data_dir)
    foot = G.read_footprint(ddir / "sample_submission.tif")
    labels = G.read_labels(ddir / "labels.tif") & foot
    import rasterio
    with rasterio.open(ddir / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgm = ds.read(1) > 0
    near = binary_dilation(labels, iterations=3)
    sgmc_off = sgm & ~labels & ~near & foot

    lidar = F.read_lidar(ddir / "external")
    rad = F.read_rad(ddir / "external")
    ext = F.read_ext(ddir / "external")
    surfaces = {
        "h82_1_antislope_lineament": F.h82_1_antislope_lineament(lidar, foot),
        "h82_2_radiometric_break": F.h82_2_radiometric_break(rad, ext, foot),
        "h82_3_valley_deflection": F.h82_3_valley_deflection(lidar, foot),
        "h82_4_conjugate_intersection": F.h82_4_conjugate_intersection(lidar, foot),
        "h82_5_thermal_upflow_prior": F.h82_5_thermal_upflow_prior(ddir, foot),
    }
    st = args.stride
    sl = (slice(None, None, st), slice(None, None, st))
    foot_s = foot[sl]
    lab_s = labels[sl]
    sgmc_s = sgmc_off[sl]
    near_s = near[sl]
    report = {"stride": st, "surfaces": {}, "pairwise_rho": {}, "tripped": False}
    names = list(surfaces)
    for name, s in surfaces.items():
        v = s[sl]
        auc_cat = auc_mw(np.where(foot_s, v, np.nan), lab_s & foot_s)
        auc_sgmc = auc_mw(np.where(foot_s, v, np.nan), sgmc_s & foot_s)
        finite = np.isfinite(np.where(foot_s, v, np.nan))
        top = np.zeros_like(finite)
        vals = v[foot_s & np.isfinite(v)]
        if vals.size:
            tau = np.quantile(vals, 0.99)
            top = foot_s & np.isfinite(v) & (v >= tau)
        flank = float((top & near_s).sum() / max(top.sum(), 1))
        trip = bool(max(auc_cat, auc_sgmc) > 0.90)
        report["tripped"] = report["tripped"] or trip
        report["surfaces"][name] = {
            "auc_vs_catalogue": auc_cat, "auc_vs_sgmc_offcat": auc_sgmc,
            "top1pct_flank3px_frac": flank, "leak_trip": trip,
            "finite_frac": float(np.isfinite(v[foot_s]).sum() / max(foot_s.sum(), 1)),
        }
        print(f"{name}: AUC(cat)={auc_cat:.4f} AUC(sgmc-off)={auc_sgmc:.4f} "
              f"flank={flank:.3f} {'TRIP' if trip else 'ok'}")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            r = spearman(np.where(foot_s, surfaces[names[i]][sl], np.nan),
                         np.where(foot_s, surfaces[names[j]][sl], np.nan))
            report["pairwise_rho"][f"{names[i]}__{names[j]}"] = r
            print(f"rho({names[i]}, {names[j]}) = {r:.4f}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))
    print("tripped:", report["tripped"], "->", args.out)
    return 1 if report["tripped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
