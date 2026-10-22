"""Lane-82 experiment pipeline (EXACTLY 3 experiments + gate verdict).

Exp1 SELECTIVE SURGERY: base H33-2-B2 minus (a) d==3 flank dots with zero
     SGMC-MID credit and below-median corroboration, (b) ring d in {4,5,6} dots
     with zero SGMC-MID credit and bottom-quartile corroboration (cap 1500).
Exp2 REDUNDANCY PRUNE: Exp1 winner minus dots that are SGMC-FAR-creditless,
     below-median corroboration, AND have a kept base-neighbor within 2.0 px
     (cap 1000).
Exp3 CORROBORATED ADDITION: Exp2 winner plus up-to-1500 far-field (d2c>6)
     dots from top corroboration decile, >=2.8px apart and >=2.8px from kept
     dots, screened for SGMC-FAR credit/dot (gate R5).

Corroboration C = mean(h82_1, h82_4, h82_2) (antislope + conjugate-node +
radiometric-break), each robust-unit-normalised. h82_3 excluded (valley
aliasing), h82_5 excluded (halo, no lineament value; kept as documentation).

Writes work/exp{1,2,3}_*.npy + evidence/pipeline.json with the gate verdict.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems82 import emission as E
from gems82 import grid as G
from gems82 import holdout as H
from gems82.metric import dti_binary, kernel

TAU_LIVE = 0.2 * 0.2778  # 0.05556 live marginal bar at the base operating point


def jsafe(x):
    """JSON-safe float (Infinity/NaN -> None; strict parsers reject bare Infinity)."""
    if isinstance(x, float) and (x == float("inf") or x != x):
        return None
    return x


def mid_credit_per_dot(dots: np.ndarray, ctx: H.HoldoutContext) -> np.ndarray:
    """SGMC-MID kernel credit attributable to each dot (winner-take-all)."""
    m = np.asarray(dots, bool)
    cred = np.zeros(m.shape, np.float64)
    if not m.any():
        return cred
    dp = distance_transform_edt(~m)
    t = ctx.sgmc_mid & ctx.foot & ~ctx.labels
    c = kernel(dp[t])
    idx = distance_transform_edt(~m, return_distances=False, return_indices=True)
    ty, tx = np.nonzero(t)
    pos = c > 0
    # accumulate credit at winning dots (np.add.at for repeats)
    np.add.at(cred, (idx[0, ty[pos], tx[pos]], idx[1, ty[pos], tx[pos]]), c[pos])
    return cred


def far_credit_per_dot(dots: np.ndarray, ctx: H.HoldoutContext) -> np.ndarray:
    m = np.asarray(dots, bool)
    cred = np.zeros(m.shape, np.float64)
    if not m.any():
        return cred
    dp = distance_transform_edt(~m)
    t = ctx.sgmc_far & ctx.foot & ~ctx.labels
    c = kernel(dp[t])
    idx = distance_transform_edt(~m, return_distances=False, return_indices=True)
    ty, tx = np.nonzero(t)
    pos = c > 0
    np.add.at(cred, (idx[0, ty[pos], tx[pos]], idx[1, ty[pos], tx[pos]]), c[pos])
    return cred


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--surfaces", default="work/surfaces")
    ap.add_argument("--work", default="work")
    ap.add_argument("--out", default="evidence/pipeline.json")
    args = ap.parse_args()
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    print("loading context...", flush=True)
    ctx = H.load_holdout_context(args.data_dir)
    base = G.read_binary_mask(Path(args.data_dir) / "registry" / "h33-2-b2-37654-nan.tif")
    S1 = np.load(f"{args.surfaces}/h82_1_antislope.npy")
    S2 = np.load(f"{args.surfaces}/h82_2_radiometric.npy")
    S4 = np.load(f"{args.surfaces}/h82_4_conjugate.npy")

    def runit(a):
        v = np.clip(np.nan_to_num(a, nan=0.0), 0, None)
        vv = v[ctx.foot]
        hi = np.percentile(vv, 99.5)
        return np.clip(v / max(hi, 1e-9), 0, 1)
    C = (runit(S1) + runit(S2) + runit(S4)) / 3.0
    np.save(work / "corroboration_C.npy", C)
    Cb = C[base]
    med, q25 = float(np.median(Cb)), float(np.percentile(Cb, 25))
    print(f"base n={base.sum()} C-on-base median={med:.4f} q25={q25:.4f}", flush=True)

    d2c = ctx.d2c
    results = {"experiments": {}, "tau_live": TAU_LIVE}

    # ---------------- Exp1: selective surgery ----------------
    t0 = time.time()
    midcred = mid_credit_per_dot(base, ctx)
    flank = base & (d2c <= 3.0)          # d==3 ring (base already has d>2)
    ring = base & (d2c > 3.0) & (d2c <= 6.0)
    rm_flank = flank & (midcred == 0) & (C < med)
    ring_cand = ring & (midcred == 0) & (C < q25)
    # cap ring removals at 1500, lowest-C first
    ry, rx = np.nonzero(ring_cand)
    if ry.size > 1500:
        order = np.argsort(C[ry, rx], kind="stable")[:1500]
        keep = np.zeros_like(ring_cand)
        keep[ry[order], rx[order]] = True
        ring_cand = keep
    rm_ring = ring_cand
    exp1 = base & ~(rm_flank | rm_ring)
    np.save(work / "exp1_surgery.npy", exp1)
    dn1 = int((rm_flank | rm_ring).sum())
    cost1 = float(midcred[rm_flank | rm_ring].sum())  # ==0 by construction
    safety1 = float("inf") if cost1 == 0 else (TAU_LIVE * dn1 / cost1)
    r1 = H.evaluate_candidate(exp1, ctx, name="exp1-surgery")
    results["experiments"]["exp1"] = {
        "n": int(exp1.sum()), "removed_flank": int(rm_flank.sum()),
        "removed_ring": int(rm_ring.sum()), "mid_credit_cost": cost1,
        "live_safety": jsafe(safety1),
        "live_safety_note": "infinite (zero measured MID-credit cost)" if cost1 == 0 else "",
        "sec": round(time.time() - t0, 1),
        "holdout": {k: {kk: v[kk] for kk in ("pooled_dti", "tp", "fp", "n_truth", "quad_mean", "ci95_half", "per_quadrant") if kk in v} for k, v in r1.items() if k != "name"},
    }
    print(f"EXP1 n={exp1.sum()} rm_flank={rm_flank.sum()} rm_ring={rm_ring.sum()} "
          f"far={r1['sgmc_far']['pooled_dti']:.6f} mid={r1['sgmc_mid']['pooled_dti']:.6f} "
          f"raw={r1['sgmc_offcat']['pooled_dti']:.6f} safety={safety1:.2f}", flush=True)

    # ---------------- Exp2: redundancy prune on exp1 ----------------
    t0 = time.time()
    cur = exp1
    fcred = far_credit_per_dot(cur, ctx)
    yy, xx = np.nonzero(cur)
    tree = cKDTree(np.column_stack([yy, xx]).astype(float))
    # nearest kept-neighbor distance (k=2: self + nearest other)
    dists, _ = tree.query(np.column_stack([yy, xx]).astype(float), k=2)
    nnd = dists[:, 1]
    nnd_img = np.zeros(cur.shape, np.float32)
    nnd_img[yy, xx] = nnd
    cand2 = cur & (fcred == 0) & (C < med) & (nnd_img <= 2.0)
    cy, cx = np.nonzero(cand2)
    if cy.size > 1000:  # cap 1000, lowest-C first
        order = np.argsort(C[cy, cx], kind="stable")[:1000]
        keep = np.zeros_like(cand2)
        keep[cy[order], cx[order]] = True
        cand2 = keep
    exp2 = cur & ~cand2
    np.save(work / "exp2_redundant.npy", exp2)
    dn2 = int(cand2.sum())
    # conservative cost for safety: MID credit of removed dots
    midcred2 = mid_credit_per_dot(cur, ctx)
    cost2 = float(midcred2[cand2].sum())
    safety2 = float("inf") if cost2 == 0 else (TAU_LIVE * dn2 / cost2)
    r2 = H.evaluate_candidate(exp2, ctx, name="exp2-redundant")
    results["experiments"]["exp2"] = {
        "n": int(exp2.sum()), "removed": dn2, "mid_credit_cost": cost2,
        "live_safety": jsafe(safety2),
        "live_safety_note": "infinite (zero measured MID-credit cost)" if cost2 == 0 else "",
        "sec": round(time.time() - t0, 1),
        "holdout": {k: {kk: v[kk] for kk in ("pooled_dti", "tp", "fp", "n_truth", "quad_mean", "ci95_half", "per_quadrant") if kk in v} for k, v in r2.items() if k != "name"},
    }
    print(f"EXP2 n={exp2.sum()} removed={dn2} cost_mid={cost2:.2f} "
          f"far={r2['sgmc_far']['pooled_dti']:.6f} mid={r2['sgmc_mid']['pooled_dti']:.6f} "
          f"raw={r2['sgmc_offcat']['pooled_dti']:.6f} safety={safety2:.2f}", flush=True)

    # ---------------- Exp3: corroborated addition on exp2 ----------------
    t0 = time.time()
    cur = exp2
    dcur = distance_transform_edt(~cur)
    support = ctx.foot & ~ctx.labels & (ctx.d2c > 6.0) & (dcur >= 2.8)
    Cs = C.copy()
    Cs[~support] = -np.inf
    # top-decile of C within support, field-first thinned to <=1500
    vals = C[support]
    tau = float(np.quantile(vals, 0.90))
    candsup = support & (C >= tau)
    add = E.dot_thin_fieldfirst(candsup, C, 2.8)
    ay, ax = np.nonzero(add)
    if ay.size > 1500:
        order = np.argsort(-C[ay, ax], kind="stable")[:1500]
        keep = np.zeros_like(add)
        keep[ay[order], ax[order]] = True
        add = keep
    # screen: marginal SGMC-FAR credit/dot of the added set vs cur
    before = dti_binary(cur, ctx.sgmc_far, valid=ctx.foot, known=ctx.labels)
    trial = cur | add
    after = dti_binary(trial, ctx.sgmc_far, valid=ctx.foot, known=ctx.labels)
    dTP = after["tp"] - before["tp"]
    cpd = float(dTP / max(add.sum(), 1))
    bar_far = 0.2 * before["dti"]
    use_add = add if (cpd >= 2.0 * 0.05556 and add.sum() <= 1500) or (
        cpd >= 0.05556 and add.sum() <= 1000) else np.zeros_like(add)
    # note: gate R5 requires SGMC-FAR credit/dot >= 0.111 (2x live bar) for <=1500 dots
    if add.sum() > 1000 and cpd < 2.0 * 0.05556:
        # fall back to top-1000 by C and re-screen at 1x live bar
        ay, ax = np.nonzero(add)
        order = np.argsort(-C[ay, ax], kind="stable")[:1000]
        top1k = np.zeros_like(add)
        top1k[ay[order], ax[order]] = True
        aft1k = dti_binary(cur | top1k, ctx.sgmc_far, valid=ctx.foot, known=ctx.labels)
        cpd1k = float((aft1k["tp"] - before["tp"]) / 1000)
        use_add = top1k if cpd1k >= 0.05556 else np.zeros_like(add)
        cpd = cpd1k if cpd1k >= 0.05556 else cpd
    exp3 = cur | use_add
    np.save(work / "exp3_added.npy", exp3)
    np.save(work / "exp3_addmask.npy", use_add)
    r3 = H.evaluate_candidate(exp3, ctx, name="exp3-added")
    results["experiments"]["exp3"] = {
        "n": int(exp3.sum()), "added": int(use_add.sum()),
        "screen_credit_per_dot": cpd, "bar_far": bar_far,
        "sec": round(time.time() - t0, 1),
        "holdout": {k: {kk: v[kk] for kk in ("pooled_dti", "tp", "fp", "n_truth", "quad_mean", "ci95_half", "per_quadrant") if kk in v} for k, v in r3.items() if k != "name"},
    }
    print(f"EXP3 n={exp3.sum()} added={use_add.sum()} cpd={cpd:.4f} bar_far={bar_far:.4f} "
          f"far={r3['sgmc_far']['pooled_dti']:.6f} mid={r3['sgmc_mid']['pooled_dti']:.6f} "
          f"raw={r3['sgmc_offcat']['pooled_dti']:.6f}", flush=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=1, default=str))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
