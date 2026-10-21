"""Spatially blocked hide-and-recover evaluator for GEMSDOE82.

Protocol
--------
* whole connected catalogue components are withheld inside four spatial
  quadrants; no component is split across a fold;
* a 3-pixel collar around the withheld components is removed from the
  catalogue-derived *feature context*; the candidate surface is then allowed
  to score the hidden component and its surrounding pixels;
* every visible catalogue pixel is masked pixel-exactly in the scored domain;
* DTI terms are pooled across 200-pixel (20 km) spatial blocks before the ratio
  and the 95% interval is a paired spatial-block bootstrap;
* the only evaluator is ``gemsdoe82-pooled-hide-v1`` and its score is a
  HOLDOUT-DTI, never a leaderboard score.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy import ndimage

from . import metric

VERSION = "gemsdoe82-pooled-hide-v1"
BUFFER_PX = 3
DOMAIN_EROSION_PX = 12
BLOCK_SIDE_PX = 200
FOLD_NAMES = ("NW", "NE", "SW", "SE")


@dataclass(frozen=True)
class Fold:
    name: str
    hidden: np.ndarray
    visible: np.ndarray
    feature_visible: np.ndarray
    active: np.ndarray
    truth: np.ndarray
    withheld_components: int


def _quadrants(footprint: np.ndarray) -> dict[str, np.ndarray]:
    rows, cols = np.nonzero(footprint)
    mid_y, mid_x = float(np.median(rows)), float(np.median(cols))
    yy, xx = np.indices(footprint.shape)
    return {
        "NW": footprint & (yy <= mid_y) & (xx <= mid_x),
        "NE": footprint & (yy <= mid_y) & (xx > mid_x),
        "SW": footprint & (yy > mid_y) & (xx <= mid_x),
        "SE": footprint & (yy > mid_y) & (xx > mid_x),
    }


def _choose_components(component_labels: np.ndarray, eligible: np.ndarray, fraction: float, seed: int) -> tuple[np.ndarray, int]:
    ids = np.unique(component_labels[eligible])
    ids = ids[ids > 0]
    if len(ids) == 0:
        return np.zeros(component_labels.shape, dtype=bool), 0
    sizes = np.bincount(component_labels.ravel())
    rng = np.random.default_rng(seed)
    order = rng.permutation(ids)
    target = max(1, int(round(float(sizes[ids].sum()) * fraction)))
    chosen: list[int] = []
    count = 0
    for component_id in order:
        chosen.append(int(component_id))
        count += int(sizes[component_id])
        if count >= target:
            break
    hidden = np.isin(component_labels, np.asarray(chosen, dtype=component_labels.dtype)) & eligible
    return hidden, len(chosen)


def build_folds(catalogue: np.ndarray, footprint: np.ndarray, *, seed: int = 8201, fraction: float = 0.20, buffer_px: int = BUFFER_PX) -> list[Fold]:
    """Construct deterministic whole-component spatial folds."""
    cat = np.asarray(catalogue, dtype=bool) & np.asarray(footprint, dtype=bool)
    fp = np.asarray(footprint, dtype=bool)
    if cat.shape != fp.shape:
        raise ValueError("catalogue/footprint shape mismatch")
    # The supplied raster is a pixelized trace.  Eight-connectivity is the least
    # destructive whole-segment approximation available without vector geometry.
    labels, _ = ndimage.label(cat, structure=np.ones((3, 3), dtype=bool))
    quadrants = _quadrants(fp)
    folds: list[Fold] = []
    for index, name in enumerate(FOLD_NAMES):
        quadrant = quadrants[name]
        interior = ndimage.binary_erosion(quadrant, iterations=DOMAIN_EROSION_PX, border_value=0)
        # Keep a component whole only when all its pixels are in this fold's
        # interior.  Components crossing a quadrant boundary remain visible.
        component_ids = np.unique(labels[quadrant & (labels > 0)])
        eligible = np.zeros(cat.shape, dtype=bool)
        for component_id in component_ids:
            pixels = labels == component_id
            if np.any(pixels) and np.all(interior[pixels]):
                eligible |= pixels
        hidden, n_components = _choose_components(labels, eligible, fraction, seed + index)
        visible = cat & ~hidden
        hidden_buffer = ndimage.binary_dilation(hidden, iterations=int(buffer_px), structure=np.ones((3, 3), dtype=bool))
        feature_visible = visible & ~hidden_buffer
        active = fp & quadrant & ~visible
        truth = hidden & active
        if int(truth.sum()) == 0:
            raise RuntimeError(f"{name} fold has no withheld positives; input catalogue cannot support protocol")
        folds.append(Fold(name, hidden, visible, feature_visible, active, truth, n_components))
    return folds


def emit_top(surface: np.ndarray, allowed: np.ndarray, budget: int) -> np.ndarray:
    """Emit binary unit-mass pixels at the highest surface values."""
    s = np.asarray(surface, dtype=np.float32)
    domain = np.asarray(allowed, dtype=bool)
    if s.shape != domain.shape:
        raise ValueError("surface/allowed shape mismatch")
    if not np.isfinite(s).all() or (s < 0).any() or (s > 1).any():
        raise ValueError("surface must be finite in [0,1]")
    ids = np.flatnonzero(domain)
    if len(ids) == 0:
        raise ValueError("empty emission domain")
    n = min(int(budget), len(ids))
    values = s.ravel()[ids]
    # Stable tie-breaking makes the artifact reproducible without a random
    # choice among equal quantized values.
    order = np.argsort(-values, kind="stable")[:n]
    result = np.zeros(s.shape, dtype=np.float32)
    result.ravel()[ids[order]] = 1.0
    return result


def _block_terms(prediction: np.ndarray, truth: np.ndarray, active: np.ndarray, block_side: int = BLOCK_SIDE_PX) -> dict[tuple[int, int], np.ndarray]:
    """Return [TP, FP, FN, truth_count] by physical global spatial block."""
    p = np.asarray(prediction, dtype=np.float64)
    g = np.asarray(truth, dtype=bool) & np.asarray(active, dtype=bool)
    v = np.asarray(active, dtype=bool)
    if p.shape != g.shape or p.shape != v.shape:
        raise ValueError("block-term shape mismatch")
    p = np.where(v, p, 0.0)
    gy, gx = np.nonzero(g)
    credit = np.zeros(len(gy), dtype=np.float64)
    height, width = p.shape
    for dy, dx, weight in metric.KERNEL_OFFSETS:
        py, px = gy + dy, gx + dx
        inside = (py >= 0) & (py < height) & (px >= 0) & (px < width)
        if np.any(inside):
            credit[inside] = np.maximum(credit[inside], p[py[inside], px[inside]] * weight)
    distance_to_truth = ndimage.distance_transform_edt(~g)
    fp_field = p * (1.0 - metric.triangular_kernel(distance_to_truth))
    result: dict[tuple[int, int], np.ndarray] = {}
    for y, x, tp_credit in zip(gy, gx, credit):
        key = (int(y // block_side), int(x // block_side))
        term = result.setdefault(key, np.zeros(4, dtype=np.float64))
        term[0] += tp_credit
        term[2] += 1.0 - tp_credit
        term[3] += 1.0
    py, px = np.nonzero(p > 0)
    for y, x in zip(py, px):
        key = (int(y // block_side), int(x // block_side))
        term = result.setdefault(key, np.zeros(4, dtype=np.float64))
        term[1] += fp_field[y, x]
    return result


def _pool_blocks(block_maps: Iterable[dict[tuple[int, int], np.ndarray]]) -> np.ndarray:
    merged: dict[tuple[int, int], np.ndarray] = {}
    for block_map in block_maps:
        for key, term in block_map.items():
            merged.setdefault(key, np.zeros(4, dtype=np.float64))[:] += term
    if not merged:
        raise ValueError("no nonempty spatial blocks")
    return np.stack([merged[k] for k in sorted(merged)], axis=0)


def _summary(terms: np.ndarray, *, seed: int, draws: int) -> dict:
    total = terms.sum(axis=0)
    dti = metric.dti_from_terms(float(total[0]), float(total[1]), float(total[2]))
    rng = np.random.default_rng(seed)
    n_blocks = len(terms)
    picks = rng.integers(0, n_blocks, size=(draws, n_blocks))
    boot_terms = terms[picks].sum(axis=1)
    boot_scores = boot_terms[:, 0] / (boot_terms[:, 0] + metric.ALPHA * boot_terms[:, 1] + metric.BETA * boot_terms[:, 2] + metric.EPS)
    return {
        "evidence_class": "HOLDOUT-DTI",
        "evaluator_version": VERSION,
        "dti": float(dti),
        "ci95": [float(x) for x in np.quantile(boot_scores, [0.025, 0.975])],
        "withheld_positive_pixels": int(round(total[3])),
        "spatial_blocks": int(n_blocks),
        "bootstrap_draws": int(draws),
        "bootstrap_seed": int(seed),
        "tpw": float(total[0]),
        "fpw": float(total[1]),
        "fnw": float(total[2]),
    }


def rank_auc(values_positive: np.ndarray, values_negative: np.ndarray) -> float:
    """Tie-aware Mann–Whitney AUC without a scikit-learn dependency."""
    pos = np.asarray(values_positive, dtype=np.float64)
    neg = np.asarray(values_negative, dtype=np.float64)
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    combined = np.concatenate([pos, neg])
    order = np.argsort(combined, kind="mergesort")
    sorted_values = combined[order]
    ranks = np.empty(len(combined), dtype=np.float64)
    start = 0
    while start < len(sorted_values):
        end = start + 1
        while end < len(sorted_values) and sorted_values[end] == sorted_values[start]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2.0 + 1.0
        start = end
    u = ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2.0
    return float(u / (len(pos) * len(neg)))


def canary_report(features: dict[str, np.ndarray], folds: list[Fold], *, seed: int = 8202, max_negative: int = 100_000) -> dict:
    rng = np.random.default_rng(seed)
    report: dict[str, dict] = {}
    for name, field in features.items():
        positives: list[np.ndarray] = []
        negatives: list[np.ndarray] = []
        for fold in folds:
            active = fold.active
            pos = np.asarray(field)[fold.truth]
            neg_ids = np.flatnonzero(active & ~fold.truth)
            if len(neg_ids) > max_negative:
                neg_ids = rng.choice(neg_ids, max_negative, replace=False)
            positives.append(np.asarray(field)[fold.truth])
            negatives.append(np.asarray(field).ravel()[neg_ids])
        auc = rank_auc(np.concatenate(positives), np.concatenate(negatives))
        report[name] = {
            "evidence_class": "LEAKAGE-CANARY",
            "auc": None if not np.isfinite(auc) else float(auc),
            "suspicious": bool(np.isfinite(auc) and max(auc, 1.0 - auc) > 0.90),
            "withheld_positive_pixels": int(sum(len(x) for x in positives)),
            "negative_sample_pixels": int(sum(len(x) for x in negatives)),
        }
    return report


def evaluate_surface(surface: np.ndarray, folds: list[Fold], *, budget: int = 37_654, buffer_px: int = BUFFER_PX, seed: int = 8203, draws: int = 2000) -> dict:
    """Evaluate one surface against all four folds and pool before scoring."""
    fold_terms: list[dict[tuple[int, int], np.ndarray]] = []
    per_fold: dict[str, dict] = {}
    predictions: dict[str, np.ndarray] = {}
    for fold in folds:
        # The only catalogue-derived operation is the visible-fault exclusion;
        # the withheld pixels never enter this mask.
        away_from_visible = ndimage.distance_transform_edt(~fold.visible) > float(buffer_px)
        allowed = fold.active & away_from_visible
        prediction = emit_top(surface, allowed, budget)
        predictions[fold.name] = prediction
        per_fold[fold.name] = metric.dti_exact(prediction, fold.truth, valid=fold.active)
        fold_terms.append(_block_terms(prediction, fold.truth, fold.active))
    pooled = _summary(_pool_blocks(fold_terms), seed=seed, draws=draws)
    return {
        "evidence_class": "HOLDOUT-DTI",
        "evaluator_version": VERSION,
        "alpha": metric.ALPHA,
        "beta": metric.BETA,
        "triangular_radius_m": metric.R_M,
        "budget": int(budget),
        "buffer_px": int(buffer_px),
        "per_fold": per_fold,
        "pooled": pooled,
        "predictions": predictions,
    }


def implementation_hash() -> str:
    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()
