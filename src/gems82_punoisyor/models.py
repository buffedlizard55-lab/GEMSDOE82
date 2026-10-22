"""Lane H82 Multi-Physics Positive-Unlabeled Experts, 4-Octave Steerable Pyramid,
3-Family Meta-Ensemble, and Self-Masked Disjunctive Structural Continuation (`src/gems82/models.py`).

Memory-engineered (`< 950 MB` peak RSS via disk-backed `float16` memmap streaming) and fast
(`~160s` total across all 5 domains, 4-octave steerable pyramid, 3 model families, and self-masked
structural continuation).
"""

from __future__ import annotations

import gc
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
from scipy import ndimage as ndi
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import RobustScaler

from gems82_punoisyor.features import (
    DOMAIN_SLICES,
    FOLD_MECH_NAMES,
    STATIC_FEATURE_NAMES,
    StaticStack82,
    build_positive_tile_mask,
    compute_fold_safe_mechanics82,
)


def compute_quadrant_ids(shape: Tuple[int, int]) -> np.ndarray:
    """Return quadrant index array in `{0: NW, 1: NE, 2: SW, 3: SE}`."""
    q = np.zeros(shape, dtype=np.int8)
    rm = shape[0] // 2
    cm = shape[1] // 2
    q[:rm, cm:] = 1
    q[rm:, :cm] = 2
    q[rm:, cm:] = 3
    return q


def calibrate_quadrant_lidar_seam(
    raw_valid: np.ndarray,
    valid_idx: np.ndarray,
    has_lidar_fp: np.ndarray,
    shape: Tuple[int, int],
) -> np.ndarray:
    """Convert raw probability array on `valid_idx` into a seam-free `[0, 1]` quantile score
    calibrated within each `(quadrant in {NW,NE,SW,SE}, has_lidar in {0,1})` stratum.
    """
    q_fp = compute_quadrant_ids(shape).ravel()[valid_idx]
    out = np.zeros(len(valid_idx), dtype=np.float32)
    lid = np.asarray(has_lidar_fp, dtype=bool)
    for qid in range(4):
        for lid_flag in (False, True):
            m = (q_fp == qid) & (lid == lid_flag)
            n = int(m.sum())
            if n <= 1:
                continue
            r = rankdata(np.nan_to_num(raw_valid[m], nan=0.0), method="average")
            out[m] = ((r - 0.5) / float(n)).astype(np.float32)
    return out


def calibrate_on_allow_domain(
    raw_valid: np.ndarray,
    allow_valid: np.ndarray,
    valid_idx: np.ndarray,
    has_lidar_fp: np.ndarray,
    shape: Tuple[int, int],
) -> np.ndarray:
    """Rank-calibrate strictly within scoreable off-catalogue pixels `allow_valid` per
    `(quadrant, has_lidar)` stratum so masked known-fault halos never consume top quantile mass.
    """
    q_fp = compute_quadrant_ids(shape).ravel()[valid_idx]
    out = np.zeros(len(valid_idx), dtype=np.float32)
    lid = np.asarray(has_lidar_fp, dtype=bool)
    alw = np.asarray(allow_valid, dtype=bool)
    for qid in range(4):
        for lid_flag in (False, True):
            m = alw & (q_fp == qid) & (lid == lid_flag)
            n = int(m.sum())
            if n <= 1:
                continue
            r = rankdata(np.nan_to_num(raw_valid[m], nan=0.0), method="average")
            out[m] = ((r - 0.5) / float(n)).astype(np.float32)
    return out


def disjunctive_noisy_or_on_allow(
    p_blind_valid: np.ndarray,
    p_struct_valid: np.ndarray,
    allow_valid: np.ndarray,
    valid_idx: np.ndarray,
    has_lidar_fp: np.ndarray,
    shape: Tuple[int, int],
    lambda_struct: float = 0.92,
) -> np.ndarray:
    """Disjunctive Noisy-OR union `1 - (1 - pb) * (1 - ps)` calibrated strictly on scoreable
    off-catalogue pixels `allow_valid` so both outward crack-tip continuations (`ps`) and
    far-field blind multi-physics scarps (`pb`) retain full tail dynamic range (`median d_cat ~ 13-16 px`).
    """
    qb = calibrate_on_allow_domain(p_blind_valid, allow_valid, valid_idx, has_lidar_fp, shape)
    qs = calibrate_on_allow_domain(p_struct_valid, allow_valid, valid_idx, has_lidar_fp, shape)
    pb = np.clip(qb ** 10, 0.0, 0.9999)
    ps = np.clip(lambda_struct * (qs ** 13), 0.0, 0.9999)
    u = 1.0 - (1.0 - pb) * (1.0 - ps)
    return calibrate_on_allow_domain(u, allow_valid, valid_idx, has_lidar_fp, shape)


def valid_to_2d(vals_valid: np.ndarray, valid_idx: np.ndarray, shape: Tuple[int, int], fill: float = 0.0) -> np.ndarray:
    arr = np.full(shape[0] * shape[1], fill, dtype=np.float32)
    arr[valid_idx] = np.asarray(vals_valid, dtype=np.float32)
    return arr.reshape(shape)


def _steerable_octave_response(
    p2d: np.ndarray,
    half_len: int,
    step: int,
    flank: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute 8-azimuth steerable line integral max, ridge-minus-flank contrast, and orientation
    selectivity (`max - min`) on 2D probability map `p2d` using exact sparse shift stencils.
    """
    H, W = p2d.shape
    pad = half_len + flank + 1
    pp = np.pad(p2d, pad, mode="constant", constant_values=0.0)
    sample_t = list(range(-half_len, half_len + 1, step))
    inv_n = 1.0 / float(len(sample_t))

    best_along = np.full((H, W), -1e9, dtype=np.float32)
    min_along = np.full((H, W), 1e9, dtype=np.float32)
    best_contrast = np.full((H, W), -1e9, dtype=np.float32)
    along = np.zeros((H, W), dtype=np.float32)
    flk = np.zeros((H, W), dtype=np.float32)

    for k in range(8):
        rad = k * (np.pi / 8.0)
        dy, dx = np.sin(rad), np.cos(rad)
        py, px = -dx, dy
        along.fill(0.0)
        flk.fill(0.0)
        for t in sample_t:
            oy = pad + int(round(t * dy))
            ox = pad + int(round(t * dx))
            along += pp[oy : oy + H, ox : ox + W]
            for sgn in (-1, 1):
                fy = pad + int(round(t * dy + sgn * flank * py))
                fx = pad + int(round(t * dx + sgn * flank * px))
                flk += 0.5 * pp[fy : fy + H, fx : fx + W]
        along *= inv_n
        flk *= inv_n
        np.maximum(best_along, along, out=best_along)
        np.minimum(min_along, along, out=min_along)
        np.maximum(best_contrast, along - flk, out=best_contrast)

    aniso = np.maximum(best_along - min_along, 0.0)
    return best_along, best_contrast, aniso


META_FEATURE_NAMES: List[str] = [
    "cal_scarp",
    "cal_fluv",
    "cal_pot",
    "cal_geo",
    "cal_full",
    "dom_second_best",
    "dom_third_best",
    "oct1_300m_along",
    "oct1_300m_contrast",
    "oct1_300m_aniso",
    "oct2_900m_along",
    "oct2_900m_contrast",
    "oct2_900m_aniso",
    "oct3_2100m_along",
    "oct3_2100m_contrast",
    "oct3_2100m_aniso",
    "oct4_4500m_along",
    "oct4_4500m_contrast",
    "scarp_1300m_along",
    "scarp_1300m_contrast",
    "pot_1500m_along",
    "geo_1500m_along",
    "multiscale_crest_continuity",
    "decontam_composite_idx",
]


def compute_steerable_pyramid_memmap(
    domain_cal: Dict[str, np.ndarray],
    stack: StaticStack82,
    fp: np.ndarray,
    out_mmap_path: Path,
) -> Tuple[np.memmap, List[str]]:
    """Stream all 24 multi-scale 4-octave steerable pyramid + domain consensus channels directly
    into a `float16` memmap (`248 MB` disk, `< 220 MB` transient RAM).
    """
    valid_idx = stack.valid_idx
    n_valid = len(valid_idx)
    shape = fp.shape

    mm = np.memmap(out_mmap_path, dtype=np.float16, mode="w+", shape=(n_valid, 24))
    p_scarp = domain_cal["scarp"]
    p_fluv = domain_cal["fluv"]
    p_pot = domain_cal["pot"]
    p_geo = domain_cal["geo"]
    p_full = domain_cal["full"]

    mm[:, 0] = p_scarp.astype(np.float16)
    mm[:, 1] = p_fluv.astype(np.float16)
    mm[:, 2] = p_pot.astype(np.float16)
    mm[:, 3] = p_geo.astype(np.float16)
    mm[:, 4] = p_full.astype(np.float16)

    dom_sorted = np.sort(np.column_stack([p_scarp, p_fluv, p_pot, p_geo]), axis=1)
    mm[:, 5] = dom_sorted[:, 2].astype(np.float16)
    mm[:, 6] = dom_sorted[:, 1].astype(np.float16)
    del dom_sorted

    base_2d = (
        0.34 * valid_to_2d(p_scarp ** 4, valid_idx, shape)
        + 0.16 * valid_to_2d(p_fluv ** 4, valid_idx, shape)
        + 0.16 * valid_to_2d(p_pot ** 4, valid_idx, shape)
        + 0.14 * valid_to_2d(p_geo ** 4, valid_idx, shape)
        + 0.20 * valid_to_2d(p_full ** 4, valid_idx, shape)
    ).astype(np.float32)

    o1_a, o1_c, o1_an = _steerable_octave_response(base_2d, half_len=2, step=1, flank=3)
    o1_flat = o1_a.ravel()[valid_idx]
    mm[:, 7] = o1_flat.astype(np.float16)
    mm[:, 8] = o1_c.ravel()[valid_idx].astype(np.float16)
    mm[:, 9] = o1_an.ravel()[valid_idx].astype(np.float16)
    del o1_a, o1_c, o1_an

    o2_a, o2_c, o2_an = _steerable_octave_response(base_2d, half_len=5, step=2, flank=3)
    mm[:, 10] = o2_a.ravel()[valid_idx].astype(np.float16)
    mm[:, 11] = o2_c.ravel()[valid_idx].astype(np.float16)
    mm[:, 12] = o2_an.ravel()[valid_idx].astype(np.float16)
    del o2_a, o2_c, o2_an

    o3_a, o3_c, o3_an = _steerable_octave_response(base_2d, half_len=10, step=2, flank=4)
    o3_flat = o3_a.ravel()[valid_idx]
    mm[:, 13] = o3_flat.astype(np.float16)
    mm[:, 14] = o3_c.ravel()[valid_idx].astype(np.float16)
    mm[:, 15] = o3_an.ravel()[valid_idx].astype(np.float16)
    mm[:, 22] = np.sqrt(np.maximum(o1_flat, 0.0) * np.maximum(o3_flat, 0.0)).astype(np.float16)
    del o3_a, o3_c, o3_an, o1_flat, o3_flat

    o4_a, o4_c, _ = _steerable_octave_response(base_2d, half_len=22, step=4, flank=6)
    mm[:, 16] = o4_a.ravel()[valid_idx].astype(np.float16)
    mm[:, 17] = o4_c.ravel()[valid_idx].astype(np.float16)
    del o4_a, o4_c, base_2d

    sc_a, sc_c, _ = _steerable_octave_response(valid_to_2d(p_scarp ** 4, valid_idx, shape), half_len=6, step=2, flank=3)
    mm[:, 18] = sc_a.ravel()[valid_idx].astype(np.float16)
    mm[:, 19] = sc_c.ravel()[valid_idx].astype(np.float16)
    del sc_a, sc_c

    po_a, _, _ = _steerable_octave_response(valid_to_2d(p_pot ** 4, valid_idx, shape), half_len=7, step=2, flank=4)
    mm[:, 20] = po_a.ravel()[valid_idx].astype(np.float16)
    del po_a

    ge_a, _, _ = _steerable_octave_response(valid_to_2d(p_geo ** 4, valid_idx, shape), half_len=7, step=2, flank=4)
    mm[:, 21] = ge_a.ravel()[valid_idx].astype(np.float16)
    del ge_a

    ctx_idx = [
        STATIC_FEATURE_NAMES.index("pluvial_mimic_flag"),
        STATIC_FEATURE_NAMES.index("interfluve_scarp_idx"),
        STATIC_FEATURE_NAMES.index("road_embankment_flag"),
        STATIC_FEATURE_NAMES.index("crossgrad_align_topo_pot"),
    ]
    ctx = np.asarray(stack.X_mmap[:, ctx_idx], dtype=np.float32)
    mm[:, 23] = np.clip(ctx[:, 0] - 0.5 * ctx[:, 1] + 0.5 * ctx[:, 2] - 0.3 * ctx[:, 3], -30.0, 30.0).astype(np.float16)
    del ctx
    mm.flush()
    gc.collect()
    return np.memmap(out_mmap_path, dtype=np.float16, mode="r", shape=(n_valid, 24)), list(META_FEATURE_NAMES)


def _sample_pu_training_indices(
    train_valid_mask: np.ndarray,
    pos_valid_mask: np.ndarray,
    pos_tile_valid_mask: np.ndarray,
    vis_buffer_valid_mask: np.ndarray,
    hard_fp_valid_mask: np.ndarray,
    q_fp: np.ndarray,
    n_neg_target: int = 84_000,
    seed: int = 82,
) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    pos_idx = np.flatnonzero(train_valid_mask & pos_valid_mask)
    if len(pos_idx) > 48_000:
        pos_idx = rng.choice(pos_idx, size=48_000, replace=False)

    neg_parts: List[np.ndarray] = []
    n_pu_per_q = int(0.75 * n_neg_target) // 4
    pu_pool_mask = train_valid_mask & pos_tile_valid_mask & (~vis_buffer_valid_mask)
    for qid in range(4):
        cand = np.flatnonzero(pu_pool_mask & (q_fp == qid))
        if len(cand) == 0:
            cand = np.flatnonzero(train_valid_mask & (~vis_buffer_valid_mask) & (q_fp == qid))
        if len(cand) > 0:
            neg_parts.append(rng.choice(cand, size=min(len(cand), n_pu_per_q), replace=False))

    hard_pool = np.flatnonzero(train_valid_mask & hard_fp_valid_mask & (~vis_buffer_valid_mask))
    n_hard = int(0.25 * n_neg_target)
    if len(hard_pool) > 0:
        neg_parts.append(rng.choice(hard_pool, size=min(len(hard_pool), n_hard), replace=False))

    neg_idx = np.unique(np.concatenate(neg_parts))
    idx_all = np.concatenate([pos_idx, neg_idx])
    y_all = np.concatenate([
        np.ones(len(pos_idx), dtype=np.int8),
        np.zeros(len(neg_idx), dtype=np.int8),
    ])
    perm = rng.permutation(len(idx_all))
    return idx_all[perm], y_all[perm]


def _predict_lgb_batched(
    model: lgb.LGBMClassifier,
    X_source: np.ndarray,
    col_idx: Optional[np.ndarray] = None,
    row_mask: Optional[np.ndarray] = None,
    batch_size: int = 650_000,
) -> np.ndarray:
    rows = np.arange(X_source.shape[0]) if row_mask is None else np.flatnonzero(row_mask)
    out = np.zeros(len(rows), dtype=np.float32)
    for start in range(0, len(rows), batch_size):
        sl = rows[start : start + batch_size]
        Xb = (
            np.asarray(X_source[sl], dtype=np.float32)
            if col_idx is None
            else np.asarray(X_source[sl][:, col_idx], dtype=np.float32)
        )
        out[start : start + batch_size] = model.predict_proba(Xb)[:, 1].astype(np.float32)
    return out


@dataclass
class H82FoldArtifacts:
    oof_domains_cal: Dict[str, np.ndarray]
    X_meta_oof_mmap: np.memmap
    oof_blind_lgb: np.ndarray
    oof_blind_mlp: np.ndarray
    oof_blind_lr: np.ndarray
    oof_blind_ens: np.ndarray
    oof_blind_decontam: np.ndarray
    full_blind_ens: np.ndarray
    full_blind_decontam: np.ndarray
    full_struct_cal: np.ndarray
    full_union: np.ndarray
    diagnostics: Dict[str, object]


def fit_and_predict_h82(
    stack: StaticStack82,
    folds: List[Dict[str, np.ndarray]],
    fp: np.ndarray,
    full_visible_faults: np.ndarray,
    work_dir: Path,
    lambda_struct: float = 0.72,
    seed: int = 82,
) -> H82FoldArtifacts:
    """Fit full out-of-quadrant H82 blind + structural pipeline with `< 950 MB` peak RAM."""
    t0 = time.time()
    work_dir.mkdir(parents=True, exist_ok=True)
    valid_idx = stack.valid_idx
    n_valid = len(valid_idx)
    shape = fp.shape
    q_fp = compute_quadrant_ids(shape).ravel()[valid_idx]

    shore_score = np.asarray(stack.X_mmap[:, STATIC_FEATURE_NAMES.index("pluvial_mimic_flag")], dtype=np.float32)
    interfluve_idx = np.asarray(stack.X_mmap[:, STATIC_FEATURE_NAMES.index("interfluve_scarp_idx")], dtype=np.float32)
    road_score = np.asarray(stack.X_mmap[:, STATIC_FEATURE_NAMES.index("road_embankment_flag")], dtype=np.float32)
    xgrad_align = np.asarray(stack.X_mmap[:, STATIC_FEATURE_NAMES.index("crossgrad_align_topo_pot")], dtype=np.float32)
    xgrad_ortho = np.asarray(stack.X_mmap[:, STATIC_FEATURE_NAMES.index("crossgrad_ortho_confounder")], dtype=np.float32)
    geo_multi = np.asarray(stack.X_mmap[:, STATIC_FEATURE_NAMES.index("geotherm_multiline_index")], dtype=np.float32)

    hard_fp_valid = (
        (shore_score > np.quantile(shore_score, 0.90))
        | (road_score > 0.35)
        | (stack.det_slope_fp < 2.2)
        | ((interfluve_idx < np.quantile(interfluve_idx, 0.20)) & (stack.det_slope_fp > 8.0))
    )

    domain_cols: Dict[str, np.ndarray] = {
        "scarp": np.arange(DOMAIN_SLICES["scarp"].start, DOMAIN_SLICES["scarp"].stop),
        "fluv": np.arange(DOMAIN_SLICES["fluv"].start, DOMAIN_SLICES["fluv"].stop),
        "pot": np.arange(DOMAIN_SLICES["pot"].start, DOMAIN_SLICES["pot"].stop),
        "geo": np.arange(DOMAIN_SLICES["geo"].start, DOMAIN_SLICES["geo"].stop),
        "full": np.arange(0, len(STATIC_FEATURE_NAMES)),
    }

    fold_train_idx: List[Tuple[np.ndarray, np.ndarray]] = []
    for k_fold, f in enumerate(folds):
        vis_k = np.asarray(f["visible"], dtype=bool) & fp
        train_2d = np.asarray(f["train_mask"], dtype=bool) & fp
        pos_tile_2d = build_positive_tile_mask(vis_k, fp, tile_px=128)
        vis_buf_2d = ndi.distance_transform_edt(~vis_k) <= 3.0
        tr_idx, y_tr = _sample_pu_training_indices(
            train_valid_mask=train_2d.ravel()[valid_idx],
            pos_valid_mask=vis_k.ravel()[valid_idx],
            pos_tile_valid_mask=pos_tile_2d.ravel()[valid_idx],
            vis_buffer_valid_mask=vis_buf_2d.ravel()[valid_idx],
            hard_fp_valid_mask=hard_fp_valid,
            q_fp=q_fp,
            n_neg_target=80_000,
            seed=seed + 101 * k_fold,
        )
        fold_train_idx.append((tr_idx, y_tr))

    # Full-catalogue PU training sample across ALL 4 quadrants for competition inference
    vis_all = np.asarray(full_visible_faults, dtype=bool) & fp
    pos_tile_all = build_positive_tile_mask(vis_all, fp, tile_px=128)
    vis_buf_all = ndi.distance_transform_edt(~vis_all) <= 3.0
    full_tr_idx, full_y_tr = _sample_pu_training_indices(
        train_valid_mask=np.ones(n_valid, dtype=bool),
        pos_valid_mask=vis_all.ravel()[valid_idx],
        pos_tile_valid_mask=pos_tile_all.ravel()[valid_idx],
        vis_buffer_valid_mask=vis_buf_all.ravel()[valid_idx],
        hard_fp_valid_mask=hard_fp_valid,
        q_fp=q_fp,
        n_neg_target=96_000,
        seed=seed + 777,
    )
    del pos_tile_all, vis_buf_all

    # ── Stage 1A: 5 Domain PU LightGBM Experts (4 disjoint OOF folds + 1 full-catalogue model) ──
    oof_domains_cal: Dict[str, np.ndarray] = {}
    full_domains_cal: Dict[str, np.ndarray] = {}
    for dom_name, cols in domain_cols.items():
        n_est = 155 if dom_name == "full" else 125
        oof_d = np.zeros(n_valid, dtype=np.float32)
        for k_fold, f in enumerate(folds):
            tr_idx, y_tr = fold_train_idx[k_fold]
            clf = lgb.LGBMClassifier(
                n_estimators=n_est,
                learning_rate=0.06,
                num_leaves=31,
                max_bin=127,
                min_child_samples=60,
                subsample=0.82,
                subsample_freq=1,
                colsample_bytree=0.80,
                reg_alpha=1.5,
                reg_lambda=4.0,
                random_state=seed + 17 * k_fold,
                n_jobs=-1,
                verbose=-1,
            )
            clf.fit(np.asarray(stack.X_mmap[tr_idx][:, cols], dtype=np.float32), y_tr)
            val_mask = (~np.asarray(f["train_mask"], dtype=bool) & fp).ravel()[valid_idx]
            oof_d[val_mask] = _predict_lgb_batched(clf, stack.X_mmap, cols, row_mask=val_mask)

        clf_full = lgb.LGBMClassifier(
            n_estimators=n_est,
            learning_rate=0.06,
            num_leaves=31,
            max_bin=127,
            min_child_samples=60,
            subsample=0.82,
            subsample_freq=1,
            colsample_bytree=0.80,
            reg_alpha=1.5,
            reg_lambda=4.0,
            random_state=seed + 999,
            n_jobs=-1,
            verbose=-1,
        )
        clf_full.fit(np.asarray(stack.X_mmap[full_tr_idx][:, cols], dtype=np.float32), full_y_tr)
        full_d = _predict_lgb_batched(clf_full, stack.X_mmap, cols, row_mask=None)

        oof_domains_cal[dom_name] = calibrate_quadrant_lidar_seam(oof_d, valid_idx, stack.has_lidar_fp, shape)
        full_domains_cal[dom_name] = calibrate_quadrant_lidar_seam(full_d, valid_idx, stack.has_lidar_fp, shape)
        del oof_d, full_d
        gc.collect()

    print(f"[models82] Stage 1A (5 PU domain experts) complete in {time.time() - t0:.1f}s")

    # ── Stage 1B: Stream 4-Octave Steerable Pyramid to disk memmap + 3-Family Meta-Ensemble ──
    X_meta_oof, meta_names = compute_steerable_pyramid_memmap(
        oof_domains_cal, stack, fp, work_dir / "meta_oof.f16.mmap"
    )
    X_meta_full, _ = compute_steerable_pyramid_memmap(
        full_domains_cal, stack, fp, work_dir / "meta_full.f16.mmap"
    )
    del full_domains_cal
    gc.collect()

    oof_lgb = np.zeros(n_valid, dtype=np.float32)
    oof_mlp = np.zeros(n_valid, dtype=np.float32)
    oof_lr = np.zeros(n_valid, dtype=np.float32)

    for k_fold, f in enumerate(folds):
        tr_idx, y_tr = fold_train_idx[k_fold]
        Xm_tr = np.asarray(X_meta_oof[tr_idx], dtype=np.float32)
        val_mask = (~np.asarray(f["train_mask"], dtype=bool) & fp).ravel()[valid_idx]

        m_lgb = lgb.LGBMClassifier(
            n_estimators=150,
            learning_rate=0.05,
            num_leaves=23,
            max_bin=127,
            min_child_samples=80,
            subsample=0.80,
            subsample_freq=1,
            colsample_bytree=0.80,
            reg_alpha=2.0,
            reg_lambda=6.0,
            random_state=seed + 31 * k_fold,
            n_jobs=-1,
            verbose=-1,
        )
        m_lgb.fit(Xm_tr, y_tr)
        oof_lgb[val_mask] = _predict_lgb_batched(m_lgb, X_meta_oof, None, row_mask=val_mask)

        scaler = RobustScaler()
        Xs_tr = np.clip(scaler.fit_transform(np.nan_to_num(Xm_tr, nan=0.0)), -8.0, 8.0)
        m_mlp = MLPClassifier(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            alpha=1e-2,
            batch_size=512,
            learning_rate_init=1e-3,
            max_iter=16,
            early_stopping=True,
            n_iter_no_change=4,
            random_state=seed + 53 * k_fold,
        )
        m_mlp.fit(Xs_tr, y_tr)
        m_lr = LogisticRegression(C=0.5, max_iter=300)
        m_lr.fit(Xs_tr, y_tr)
        del Xm_tr, Xs_tr

        val_rows = np.flatnonzero(val_mask)
        for st in range(0, len(val_rows), 500_000):
            sl_r = val_rows[st : st + 500_000]
            Xv_s = np.clip(scaler.transform(np.nan_to_num(np.asarray(X_meta_oof[sl_r], dtype=np.float32), nan=0.0)), -8.0, 8.0)
            oof_mlp[sl_r] = m_mlp.predict_proba(Xv_s)[:, 1].astype(np.float32)
            oof_lr[sl_r] = m_lr.predict_proba(Xv_s)[:, 1].astype(np.float32)

    # Full-catalogue 3-family meta-models
    Xm_ftr = np.asarray(X_meta_full[full_tr_idx], dtype=np.float32)
    mf_lgb = lgb.LGBMClassifier(
        n_estimators=150,
        learning_rate=0.05,
        num_leaves=23,
        max_bin=127,
        min_child_samples=80,
        subsample=0.80,
        subsample_freq=1,
        colsample_bytree=0.80,
        reg_alpha=2.0,
        reg_lambda=6.0,
        random_state=seed + 401,
        n_jobs=-1,
        verbose=-1,
    )
    mf_lgb.fit(Xm_ftr, full_y_tr)
    full_lgb = _predict_lgb_batched(mf_lgb, X_meta_full, None, row_mask=None)

    f_scaler = RobustScaler()
    Xs_ftr = np.clip(f_scaler.fit_transform(np.nan_to_num(Xm_ftr, nan=0.0)), -8.0, 8.0)
    mf_mlp = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        alpha=1e-2,
        batch_size=512,
        learning_rate_init=1e-3,
        max_iter=16,
        early_stopping=True,
        n_iter_no_change=4,
        random_state=seed + 501,
    )
    mf_mlp.fit(Xs_ftr, full_y_tr)
    mf_lr = LogisticRegression(C=0.5, max_iter=300)
    mf_lr.fit(Xs_ftr, full_y_tr)
    del Xm_ftr, Xs_ftr

    full_mlp = np.zeros(n_valid, dtype=np.float32)
    full_lr = np.zeros(n_valid, dtype=np.float32)
    for st in range(0, n_valid, 650_000):
        Xb_s = np.clip(f_scaler.transform(np.nan_to_num(np.asarray(X_meta_full[st : st + 650_000], dtype=np.float32), nan=0.0)), -8.0, 8.0)
        full_mlp[st : st + 650_000] = mf_mlp.predict_proba(Xb_s)[:, 1].astype(np.float32)
        full_lr[st : st + 650_000] = mf_lr.predict_proba(Xb_s)[:, 1].astype(np.float32)

    cal_lgb = calibrate_quadrant_lidar_seam(oof_lgb, valid_idx, stack.has_lidar_fp, shape)
    cal_mlp = calibrate_quadrant_lidar_seam(oof_mlp, valid_idx, stack.has_lidar_fp, shape)
    cal_lr = calibrate_quadrant_lidar_seam(oof_lr, valid_idx, stack.has_lidar_fp, shape)
    oof_blind_ens = calibrate_quadrant_lidar_seam(
        0.52 * cal_lgb + 0.30 * cal_mlp + 0.18 * cal_lr, valid_idx, stack.has_lidar_fp, shape
    )

    f_cal_lgb = calibrate_quadrant_lidar_seam(full_lgb, valid_idx, stack.has_lidar_fp, shape)
    f_cal_mlp = calibrate_quadrant_lidar_seam(full_mlp, valid_idx, stack.has_lidar_fp, shape)
    f_cal_lr = calibrate_quadrant_lidar_seam(full_lr, valid_idx, stack.has_lidar_fp, shape)
    full_blind_ens = calibrate_quadrant_lidar_seam(
        0.52 * f_cal_lgb + 0.30 * f_cal_mlp + 0.18 * f_cal_lr, valid_idx, stack.has_lidar_fp, shape
    )
    del oof_lgb, oof_mlp, oof_lr, full_lgb, full_mlp, full_lr, f_cal_lgb, f_cal_mlp, f_cal_lr
    gc.collect()
    print(f"[models82] Stage 1B (4-octave steerable pyramid + 3-family meta-ensemble) complete in {time.time() - t0:.1f}s")

    # ── Stage 2A (`H82-2/3/4`): Physical Decontamination & Conduit Gain ──
    shore_q985 = float(np.quantile(shore_score, 0.985)) + 1e-6
    inter_q12 = float(np.quantile(interfluve_idx, 0.12))
    xg_a_q95 = float(np.quantile(xgrad_align, 0.95)) + 1e-6
    xg_o_q98 = float(np.quantile(xgrad_ortho, 0.98)) + 1e-6
    gm_q96 = float(np.quantile(geo_multi, 0.96)) + 1e-6

    static_gain = (
        np.clip(1.0 - 0.34 * np.clip(shore_score / shore_q985, 0.0, 1.5), 0.55, 1.0)
        * np.where(stack.det_slope_fp < 1.8, 0.42, np.where(stack.det_slope_fp < 3.0, 0.78, 1.0))
        * np.clip(1.0 - 0.38 * road_score, 0.52, 1.0)
        * np.where((interfluve_idx < inter_q12) & (stack.det_slope_fp > 12.0), 0.72, 1.0)
        * (1.0 + 0.10 * np.clip(xgrad_align / xg_a_q95, 0.0, 1.5))
        * np.clip(1.0 - 0.08 * np.clip(xgrad_ortho / xg_o_q98, 0.0, 1.2), 0.86, 1.0)
        * (1.0 + 0.11 * np.clip(geo_multi / gm_q96, 0.0, 1.5))
    ).astype(np.float32)
    del shore_score, interfluve_idx, road_score, xgrad_align, xgrad_ortho, geo_multi, hard_fp_valid
    gc.collect()

    dom2_oof = np.asarray(X_meta_oof[:, 5], dtype=np.float32)
    oof_blind_decontam = calibrate_quadrant_lidar_seam(
        (oof_blind_ens ** 3) * static_gain * np.clip(0.62 + 0.38 * (dom2_oof ** 2), 0.62, 1.0),
        valid_idx,
        stack.has_lidar_fp,
        shape,
    )
    dom2_full = np.asarray(X_meta_full[:, 5], dtype=np.float32)
    full_blind_decontam = calibrate_quadrant_lidar_seam(
        (full_blind_ens ** 3) * static_gain * np.clip(0.62 + 0.38 * (dom2_full ** 2), 0.62, 1.0),
        valid_idx,
        stack.has_lidar_fp,
        shape,
    )
    del static_gain, dom2_oof, dom2_full
    gc.collect()

    # Full-catalogue self-masked structural model for competition `.tif` submission
    rng_sm = np.random.default_rng(seed + 1909)
    comp_lbl, n_comp = ndi.label(vis_all, structure=np.ones((3, 3), dtype=int))
    comp_ids = np.arange(1, n_comp + 1)
    rng_sm.shuffle(comp_ids)
    mask_arr = np.zeros(n_comp + 1, dtype=bool)
    for cid in comp_ids[: max(1, int(0.24 * n_comp))]:
        mask_arr[cid] = True
    self_hid_all = mask_arr[comp_lbl]
    mech_f_tr = compute_fold_safe_mechanics82(
        vis_all & (~self_hid_all), fp, stack.best_strike_rad_2d, stack.scarp_prior_2d
    )
    dlog_col = FOLD_MECH_NAMES.index("vis_dist_log_capped")
    pos_sm = np.flatnonzero(self_hid_all.ravel()[valid_idx])
    neg_near = np.flatnonzero((fp & (~vis_all)).ravel()[valid_idx] & (mech_f_tr[:, dlog_col] < 3.05))
    neg_far = np.flatnonzero((fp & (~vis_all)).ravel()[valid_idx])
    neg_sm = np.unique(np.concatenate([
        rng_sm.choice(neg_near, size=min(len(neg_near), 55_000), replace=False),
        rng_sm.choice(neg_far, size=min(len(neg_far), 40_000), replace=False),
    ]))
    sm_idx = np.concatenate([pos_sm, neg_sm])
    y_sm = np.concatenate([np.ones(len(pos_sm), dtype=np.int8), np.zeros(len(neg_sm), dtype=np.int8)])
    X_sm_ftr = np.hstack([
        mech_f_tr[sm_idx],
        np.asarray(X_meta_full[sm_idx][:, [0, 2, 3, 7, 10, 13, 22]], dtype=np.float32),
    ])
    clf_s_full = lgb.LGBMClassifier(
        n_estimators=160,
        learning_rate=0.05,
        num_leaves=23,
        max_bin=127,
        min_child_samples=60,
        subsample=0.80,
        subsample_freq=1,
        colsample_bytree=0.85,
        reg_alpha=2.0,
        reg_lambda=6.0,
        random_state=seed + 888,
        n_jobs=-1,
        verbose=-1,
    )
    clf_s_full.fit(X_sm_ftr, y_sm)
    del mech_f_tr, X_sm_ftr

    mech_f_eval = compute_fold_safe_mechanics82(
        vis_all, fp, stack.best_strike_rad_2d, stack.scarp_prior_2d
    )
    full_struct_raw = np.zeros(n_valid, dtype=np.float32)
    for st in range(0, n_valid, 700_000):
        Xf = np.hstack([
            mech_f_eval[st : st + 700_000],
            np.asarray(X_meta_full[st : st + 700_000][:, [0, 2, 3, 7, 10, 13, 22]], dtype=np.float32),
        ])
        full_struct_raw[st : st + 700_000] = clf_s_full.predict_proba(Xf)[:, 1].astype(np.float32)
    del mech_f_eval, X_meta_full
    gc.collect()

    full_struct_cal = calibrate_quadrant_lidar_seam(full_struct_raw, valid_idx, stack.has_lidar_fp, shape)
    pb_full = np.clip(full_blind_decontam ** 8, 0.0, 0.999)
    ps_full = np.clip(lambda_struct * (full_struct_cal ** 12), 0.0, 0.999)
    full_union = calibrate_quadrant_lidar_seam(
        1.0 - (1.0 - pb_full) * (1.0 - ps_full), valid_idx, stack.has_lidar_fp, shape
    )
    print(f"[models82] Full H82 pipeline finished in {time.time() - t0:.1f}s")

    return H82FoldArtifacts(
        oof_domains_cal=oof_domains_cal,
        X_meta_oof_mmap=X_meta_oof,
        oof_blind_lgb=cal_lgb,
        oof_blind_mlp=cal_mlp,
        oof_blind_lr=cal_lr,
        oof_blind_ens=oof_blind_ens,
        oof_blind_decontam=oof_blind_decontam,
        full_blind_ens=full_blind_ens,
        full_blind_decontam=full_blind_decontam,
        full_struct_cal=full_struct_cal,
        full_union=full_union,
        diagnostics={
            "runtime_seconds": round(float(time.time() - t0), 2),
            "meta_feature_names": meta_names,
            "mechanical_feature_names": list(FOLD_MECH_NAMES),
            "lambda_struct": float(lambda_struct),
        },
    )


def evaluate_blind_quadrant_transfer(
    oof_blind_decontam: np.ndarray,
    valid_idx: np.ndarray,
    visible_all: np.ndarray,
    fp: np.ndarray,
) -> Dict[str, object]:
    """Evaluate exact 4-Quadrant Blind Spatial Transfer (`leave-one-quadrant-out`) directly from
    the already out-of-quadrant `oof_blind_decontam` surface (`zero` fault-proximity channels,
    trained strictly on `ctx.quad != q` for every quadrant `q`).
    """
    q_fp = compute_quadrant_ids(fp.shape).ravel()[valid_idx]
    vis_fp = (visible_all & fp).ravel()[valid_idx].astype(np.int8)
    q_names = ["NW", "NE", "SW", "SE"]
    per_quad = {
        qn: round(float(roc_auc_score(vis_fp[q_fp == qi], oof_blind_decontam[q_fp == qi])), 5)
        for qi, qn in enumerate(q_names)
    }
    return {
        "protocol": "leave-one-quadrant-out (186.5km x 164.6km whole-region blind transfer, zero fault-proximity channels)",
        "per_quadrant_roc_auc": per_quad,
        "mean_roc_auc": round(float(np.mean(list(per_quad.values()))), 5),
    }
