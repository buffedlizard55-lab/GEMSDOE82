"""Spatially-blocked holdout evaluation (hide-and-recover).

Protocol (per the parallel-run brief):
  * withhold WHOLE fault segments (connected components) with a buffer collar,
  * derive every catalogue-based feature only from the visible faults,
  * mask visible faults pixel-exactly from the scored domain,
  * score pooled DTI (alpha=0.2, beta=0.8, 300 m triangular kernel).

Three instruments (truths), reported separately, never blended into one number:

  1. SGMC-FAR (PRIMARY for emission decisions): truth = USGS State Geologic
     Map Compilation fault pixels with Euclidean d(catalogue) > 6 px (600 m),
     inside the footprint, catalogue masked pixel-exactly. The 6 px moat is
     principled (twice the kernel radius: flank dots at d<=3 are structurally
     incapable of earning credit) and validated: it reproduces BOTH known live
     orderings (D2.8 < R1-SOLO < H33-2-B2) with the TP-neutral mechanism the
     live record implies (evidence/moat_sweep.json). Pooled + per-quadrant DTI
     with 95% CI. Licensed for flank surgery (d<=3) and far-field (d>6)
     additions; BLIND to the d in {4,5,6} ring by construction.
  2. SGMC-MID (secondary): same but moat > 3 px Euclidean (minimal exclusion
     that still reproduces both live orderings). Keeps the ring visible, so
     ring surgery is measurable; no-loss gate only.
  3. SGMC-RAW (secondary): SGMC truth > 300 m (Chebyshev) from the catalogue.
     Reproduces D2.8 < R1 but NOT the B=2 step (phantom near-flank credit);
     kept as the conservative instrument. No-loss gate only.
  4. CAT-HIDDEN (diagnostic): whole-component hide-and-recover on the visible
     catalogue itself (4 quadrants x 2 draws, 15 px collar, 12 px domain
     erosion, 20% of test-quadrant component mass hidden). MEASURED to be
     anti-monotone vs live on emission questions (0.0967 -> 0.0305 -> 0.0045
     across the chain the live record ranks ascending), so it is reported as a
     diagnostic, never as a gate or a projection.

Leakage note on catalogue-distance features: lane-82 detectors are label-free
(they never read labels.tif). Catalogue distance is used ONLY to REMOVE mass
(flank pruning) or to REQUIRE off-catalogue placement — the conservative
direction on CAT-HIDDEN (it can only hide credit from the instrument, never
manufacture it). SGMC-OFFCAT truth never touches the catalogue at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, distance_transform_edt, label

from . import grid as G
from .metric import ALPHA, BETA, EPS, dti_binary, kernel

FOLD_NAMES = ("NW", "NE", "SW", "SE")
COLLAR_PX = 15
DOMAIN_ERODE = 12
HIDE_FRAC = 0.20
DRAWS = (20, 21)


def quadrant_ids(footprint: np.ndarray) -> np.ndarray:
    """Quadrant 0..3 (NW, NE, SW, SE) split at median row/col of the footprint."""
    footprint = np.asarray(footprint, bool)
    yy, xx = np.nonzero(footprint)
    ym, xm = int(np.median(yy)), int(np.median(xx))
    H, W = footprint.shape
    gy, gx = np.ogrid[:H, :W]
    q = np.full((H, W), -1, np.int8)
    q[(gy < ym) & (gx < xm) & footprint] = 0
    q[(gy < ym) & (gx >= xm) & footprint] = 1
    q[(gy >= ym) & (gx < xm) & footprint] = 2
    q[(gy >= ym) & (gx >= xm) & footprint] = 3
    return q


MOAT_FAR_PX = 6.0   # primary instrument exclusion radius (Euclidean px)
MOAT_MID_PX = 3.0   # secondary instrument exclusion radius (Euclidean px)


@dataclass
class HoldoutContext:
    foot: np.ndarray
    labels: np.ndarray
    sgmc_off: np.ndarray      # raw: SGMC & ~dilate3(labels) & foot
    sgmc_mid: np.ndarray      # SGMC & d2c>3 (Euclidean) & foot
    sgmc_far: np.ndarray      # SGMC & d2c>6 (Euclidean) & foot
    d2c: np.ndarray           # Euclidean distance-to-catalogue (px)
    quad: np.ndarray
    # CAT-HIDDEN cells: list of (key, active, truth) full-grid boolean arrays
    cells: list
    n_sgmc_truth: int


def _pick_components(rng, comp_size, ids, target_px):
    if ids.size == 0:
        return ids
    perm = rng.permutation(ids)
    cum = np.cumsum(comp_size[perm])
    k = int(np.searchsorted(cum, target_px)) + 1
    return perm[: min(k, perm.size)]


def load_holdout_context(data_dir: str | Path) -> HoldoutContext:
    ddir = Path(data_dir)
    foot = G.read_footprint(ddir / "sample_submission.tif")
    labels = G.read_labels(ddir / "labels.tif") & foot
    import rasterio
    with rasterio.open(ddir / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgm = ds.read(1) > 0
    near = binary_dilation(labels, iterations=3)
    sgmc_off = sgm & ~labels & ~near & foot
    d2c = distance_transform_edt(~labels)
    sgmc_mid = sgm & (d2c > MOAT_MID_PX) & foot
    sgmc_far = sgm & (d2c > MOAT_FAR_PX) & foot

    quad = quadrant_ids(foot)
    comp, n_comp = label(labels, structure=np.ones((3, 3), int))
    comp_size = np.bincount(comp.ravel(), minlength=n_comp + 1)
    all_ids = np.arange(1, n_comp + 1)

    cells = []
    for seed in DRAWS:
        for fold in range(4):
            rng = np.random.default_rng(10_000 * (seed + 1) + fold)
            q = quad == fold
            collar = binary_dilation(q, structure=np.ones((3, 3), bool), iterations=COLLAR_PX) & foot
            domain = binary_erosion(q, iterations=DOMAIN_ERODE)
            touch_collar = np.isin(all_ids, np.unique(comp[collar & labels]))
            in_test = np.isin(all_ids, np.unique(comp[q & labels]))
            test_ids = all_ids[in_test]
            train_ids = all_ids[~touch_collar]
            hid_test = _pick_components(rng, comp_size, test_ids, HIDE_FRAC * float((labels & q).sum()))
            hid_train = _pick_components(rng, comp_size, train_ids, HIDE_FRAC * float(comp_size[train_ids].sum()))
            hidden_full = np.isin(comp, hid_test)
            hidden_train = np.isin(comp, hid_train)
            visible = labels & ~hidden_full & ~hidden_train
            active = domain & ~visible  # visible faults masked pixel-exactly
            truth = hidden_full & domain & active
            cells.append(dict(key=f"draw{seed}_fold{fold}", active=active, truth=truth,
                              n_truth=int(truth.sum())))

    return HoldoutContext(foot=foot, labels=labels, sgmc_off=sgmc_off,
                          sgmc_mid=sgmc_mid, sgmc_far=sgmc_far, d2c=d2c,
                          quad=quad, cells=cells, n_sgmc_truth=int(sgmc_off.sum()))


def _ci95(vals: np.ndarray) -> tuple[float, float]:
    vals = np.asarray(vals, float)
    if vals.size < 2:
        return float(vals[0]) if vals.size else 0.0, 0.0
    se = float(vals.std(ddof=1) / np.sqrt(vals.size))
    return float(vals.mean()), 1.96 * se


def _sgmc_frame(mask: np.ndarray, ctx: HoldoutContext, truth: np.ndarray) -> dict:
    m = np.asarray(mask, bool) & ctx.foot
    pooled = dti_binary(m, truth, valid=ctx.foot, known=ctx.labels)
    per_quad = {}
    for f in range(4):
        q = ctx.quad == f
        r = dti_binary(m & q, truth & q, valid=ctx.foot & q, known=ctx.labels & q)
        per_quad[FOLD_NAMES[f]] = r["dti"]
    mean, half = _ci95(np.array(list(per_quad.values())))
    return dict(pooled_dti=pooled["dti"], tp=pooled["tp"], fp=pooled["fp"],
                fn=pooled["fn"], n_truth=pooled["n_truth"],
                per_quadrant=per_quad, quad_mean=mean, ci95_half=half,
                n_emitted=int(m.sum()), n_on_catalogue=int((m & ctx.labels).sum()))


def evaluate_sgmc_offcat(mask: np.ndarray, ctx: HoldoutContext) -> dict:
    """Raw SGMC frame (secondary): SGMC truth > 300 m Chebyshev from catalogue."""
    return _sgmc_frame(mask, ctx, ctx.sgmc_off)


def evaluate_sgmc_mid(mask: np.ndarray, ctx: HoldoutContext) -> dict:
    """Mid SGMC frame (secondary): SGMC truth with d2c > 3 px Euclidean."""
    return _sgmc_frame(mask, ctx, ctx.sgmc_mid)


def evaluate_sgmc_far(mask: np.ndarray, ctx: HoldoutContext) -> dict:
    """PRIMARY instrument: pooled + per-quadrant DTI vs SGMC far truth (moat>6)."""
    return _sgmc_frame(mask, ctx, ctx.sgmc_far)


def evaluate_cat_hidden(mask: np.ndarray, ctx: HoldoutContext) -> dict:
    """Secondary diagnostic: whole-segment hide-and-recover on the catalogue."""
    m = np.asarray(mask, bool) & ctx.foot
    per_cell = {}
    for cell in ctx.cells:
        p = m & cell["active"]
        r = dti_binary(p, cell["truth"], valid=cell["active"],
                       known=np.zeros_like(cell["active"]))
        per_cell[cell["key"]] = r["dti"]
    vals = np.array(list(per_cell.values()))
    mean, half = _ci95(vals)
    # pooled counts via summed tp/fp/fn for an exact pooled DTI
    tp = fp = fn = 0.0
    nt = 0
    for cell in ctx.cells:
        p = m & cell["active"]
        t = cell["truth"]
        n = int(t.sum())
        nt += n
        if n == 0 or not p.any():
            fn += float(n)
            fp += float(p.sum())
            continue
        dp = distance_transform_edt(~p)
        tp_c = float(kernel(dp[t]).sum())
        tp += tp_c
        fn += float(n) - tp_c
        dg = distance_transform_edt(~t)
        fp += float((1.0 - kernel(dg[p])).sum())
    pooled = tp / (tp + ALPHA * fp + BETA * fn + EPS)
    return dict(pooled_dti=float(pooled), tp=tp, fp=fp, fn=fn, n_truth=nt,
                per_cell=per_cell, cell_mean=mean, ci95_half=half,
                n_emitted=int(m.sum()))


def evaluate_candidate(mask: np.ndarray, ctx: HoldoutContext, name: str = "candidate") -> dict:
    """All instruments + metadata. Numbers are HOLDOUT-DTI, never scores."""
    return dict(name=name,
                sgmc_far=evaluate_sgmc_far(mask, ctx),
                sgmc_mid=evaluate_sgmc_mid(mask, ctx),
                sgmc_offcat=evaluate_sgmc_offcat(mask, ctx),
                cat_hidden=evaluate_cat_hidden(mask, ctx))
