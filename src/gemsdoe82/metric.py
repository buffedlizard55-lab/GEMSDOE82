"""Literal distance-weighted Tversky metric used by the GEMS challenge.

This is a compact, independently tested implementation of the equations on the
official DrivenData problem page.  It is deliberately shared by the holdout
and any local diagnostics; no alternative score is used for promotion.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

ALPHA = 0.2
BETA = 0.8
RADIUS_PX = 3.0  # 300 m at the competition's 100 m grid
PIXEL_M = 100.0
R_M = RADIUS_PX * PIXEL_M
EPS = 1e-12


def triangular_kernel(distance_px: np.ndarray | float) -> np.ndarray:
    return np.maximum(1.0 - np.asarray(distance_px, dtype=np.float64) / RADIUS_PX, 0.0)


def _validate(prediction: np.ndarray, truth: np.ndarray, valid: np.ndarray | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p = np.asarray(prediction, dtype=np.float64)
    g = np.asarray(truth, dtype=bool)
    if p.ndim != 2 or p.shape != g.shape:
        raise ValueError("prediction and truth must be matching 2-D arrays")
    v = np.ones(p.shape, dtype=bool) if valid is None else np.asarray(valid, dtype=bool)
    if v.shape != p.shape:
        raise ValueError("valid mask shape differs from prediction")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("predictions must be finite and in [0, 1]")
    return p, g, v


def _kernel_offsets() -> list[tuple[int, int, float]]:
    offsets: list[tuple[int, int, float]] = []
    radius = int(np.ceil(RADIUS_PX))
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            weight = float(triangular_kernel(np.hypot(dy, dx)))
            if weight > 0.0:
                offsets.append((dy, dx, weight))
    return offsets


KERNEL_OFFSETS = _kernel_offsets()


def dti_exact(prediction: np.ndarray, truth: np.ndarray, valid: np.ndarray | None = None) -> dict:
    """Compute the official soft DTI exactly.

    TP is a max over prediction cells around each truth cell, rather than a
    convolutional sum.  The explicit seven-by-seven offset loop below mirrors
    the published ``max_x p(x) k(d(x,g))`` equation and is fast enough for the
    100 m grid because it touches only the non-zero triangular kernel support.
    """
    p, g, v = _validate(prediction, truth, valid)
    p = np.where(v, p, 0.0)
    g = v & g
    n_truth = int(g.sum())
    if n_truth == 0:
        return {"tp": 0.0, "fp": float(p.sum()), "fn": 0.0, "n_truth": 0, "n_emitted": int((p > 0).sum()), "dti": 0.0}

    gy, gx = np.nonzero(g)
    tp_credit = np.zeros(len(gy), dtype=np.float64)
    height, width = p.shape
    for dy, dx, weight in KERNEL_OFFSETS:
        py = gy + dy
        px = gx + dx
        inside = (py >= 0) & (py < height) & (px >= 0) & (px < width)
        if np.any(inside):
            tp_credit[inside] = np.maximum(tp_credit[inside], p[py[inside], px[inside]] * weight)
    tp = float(tp_credit.sum())
    distance_to_truth = ndimage.distance_transform_edt(~g)
    fp = float((p * (1.0 - triangular_kernel(distance_to_truth))).sum())
    fn = float(n_truth - tp)
    denominator = tp + ALPHA * fp + BETA * fn + EPS
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "n_truth": n_truth,
        "n_emitted": int((p > 0).sum()),
        "dti": float(tp / denominator),
    }


def dti_from_terms(tp: float, fp: float, fn: float) -> float:
    return float(tp / (tp + ALPHA * fp + BETA * fn + EPS))


def brute_force(prediction: np.ndarray, truth: np.ndarray) -> dict:
    """Small-grid oracle used only in tests to guard distance-transform changes."""
    p, g, _ = _validate(prediction, truth, None)
    positives = np.argwhere(g)
    emitted = np.argwhere(p > 0)
    tp = 0.0
    for gy, gx in positives:
        if emitted.size:
            distances = np.sqrt(((emitted - np.array([gy, gx])) ** 2).sum(axis=1))
            tp += float(np.max(p[emitted[:, 0], emitted[:, 1]] * triangular_kernel(distances)))
    fp = 0.0
    for py, px in emitted:
        if positives.size:
            distances = np.sqrt(((positives - np.array([py, px])) ** 2).sum(axis=1))
            credit = float(np.max(triangular_kernel(distances)))
        else:
            credit = 0.0
        fp += float(p[py, px] * (1.0 - credit))
    fn = float(len(positives) - tp)
    return {"tp": tp, "fp": fp, "fn": fn, "dti": dti_from_terms(tp, fp, fn)}
