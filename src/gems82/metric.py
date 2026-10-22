"""Exact official DTI metric (distance-weighted Tversky index).

Official specification: problem page
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
triangular kernel k(d) = max(1 - d/R, 0), R = 300 m = 3 px at 100 m resolution,
alpha = 0.2 (false positives), beta = 0.8 (false negatives).

Known-fault masking: scored domain excludes known catalogue pixels (organizer
clarification, DrivenData community thread 11516, as recorded by GEMSDOE32).

Formulation used here (equivalent to the published equations):

    TP_w = sum_{g in G} max_{x: d(x,g)<=R} p(x) * k(d(x,g))
    FP_w = sum_{x: p(x)>0} p(x) * [1 - max_{g in G} k(d(x,g))]
    FN_w = |G| - TP_w
    DTI  = TP_w / (TP_w + alpha*FP_w + beta*FN_w)
         = TP_w / (alpha*(TP_w + FP_w) + beta*|G|)

Math cross-checked against GEMSDOE32 src/gems32/metric.py and against the
literal O(|G|*|P|) transcription in dti_bruteforce (tests/test_metric.py).
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA: float = 0.2
BETA: float = 0.8
RADIUS_PX: float = 3.0  # 300 m at 100 m resolution
EPS: float = 1e-12


def kernel(d, radius: float = RADIUS_PX) -> np.ndarray:
    """Triangular kernel k(d) = max(1 - d/R, 0); d and R in pixels."""
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def _prepare(pred, truth, valid, known):
    pred = np.asarray(pred)
    truth = np.asarray(truth)
    if pred.ndim != 2 or pred.shape != truth.shape:
        raise ValueError("prediction and truth must be equal-shaped 2-D grids")
    valid = np.ones(pred.shape, bool) if valid is None else np.asarray(valid, bool)
    known = np.zeros(pred.shape, bool) if known is None else np.asarray(known, bool)
    if valid.shape != pred.shape or known.shape != pred.shape:
        raise ValueError("mask grid mismatch")
    active = valid & ~known
    vals = np.asarray(pred, dtype=np.float64)[active]
    if vals.size and (not np.isfinite(vals).all() or (vals < 0).any() or (vals > 1).any()):
        raise ValueError("predictions inside the scored domain must be finite and in [0, 1]")
    p = np.where(active & np.isfinite(pred), pred, 0.0).astype(np.float64)
    g = active & (np.asarray(truth) > 0)
    return p, g, active


def dti_exact(pred, truth, valid=None, known=None,
              alpha: float = ALPHA, beta: float = BETA) -> dict:
    """Exact DTI for arbitrary soft or binary predictions in [0, 1]."""
    p, g, _ = _prepare(pred, truth, valid, known)
    n = int(g.sum())
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0, dti=0.0, coverage=0.0)
    dp = distance_transform_edt(~(p > 0)) if (p > 0).any() else np.full(p.shape, 1e9)
    # soft-credit path: for each truth pixel, max over kernel offsets of p*k
    H, W = p.shape
    yy, xx = np.nonzero(g)
    r = int(np.ceil(RADIUS_PX))
    credit = np.zeros(n, dtype=np.float64)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            k = float(kernel(np.hypot(dy, dx)))
            if k <= 0.0:
                continue
            ny, nx = yy + dy, xx + dx
            ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
            credit[ok] = np.maximum(credit[ok], p[ny[ok], nx[ok]] * k)
    tp = float(credit.sum())
    fn = float(n) - tp
    dg = distance_transform_edt(~g)
    fp = float((p * (1.0 - kernel(dg))).sum())
    dti = tp / (tp + alpha * fp + beta * fn + EPS)
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, dti=float(dti), coverage=tp / n)


def dti_binary(pred_bool, truth, valid=None, known=None,
               alpha: float = ALPHA, beta: float = BETA) -> dict:
    """Fast exact DTI for binary {0,1} predictions via distance transforms."""
    pred_bool = np.asarray(pred_bool, bool)
    truth = np.asarray(truth, bool)
    valid_ = np.ones(pred_bool.shape, bool) if valid is None else np.asarray(valid, bool)
    known_ = np.zeros(pred_bool.shape, bool) if known is None else np.asarray(known, bool)
    active = valid_ & ~known_
    p = pred_bool & active
    g = truth & active
    n = int(g.sum())
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0, dti=0.0, coverage=0.0)
    if not p.any():
        return dict(tp=0.0, fp=0.0, fn=float(n), n_truth=n, dti=0.0, coverage=0.0)
    dp = distance_transform_edt(~p)
    tp = float(kernel(dp[g]).sum())
    fn = float(n) - tp
    dg = distance_transform_edt(~g)
    fp = float((1.0 - kernel(dg[p])).sum())
    dti = tp / (tp + alpha * fp + beta * fn + EPS)
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, dti=float(dti), coverage=tp / n)


def dti_bruteforce(pred, truth, alpha: float = ALPHA, beta: float = BETA,
                   radius: float = RADIUS_PX) -> dict:
    """Literal O(|G|*|P|) transcription of the published equations (test oracle)."""
    pred = np.asarray(pred, float)
    truth = np.asarray(truth, bool)
    gs = np.argwhere(truth)
    xs = np.argwhere(pred > 0)
    tp = fn = 0.0
    for g in gs:
        best = 0.0
        for x in xs:
            d = float(np.hypot(*(x - g)))
            if d <= radius:
                best = max(best, pred[tuple(x)] * max(1.0 - d / radius, 0.0))
        tp += best
        fn += 1.0 - best
    fp = 0.0
    for x in xs:
        kmax = 0.0
        for g in gs:
            kmax = max(kmax, max(1.0 - float(np.hypot(*(x - g))) / radius, 0.0))
        fp += pred[tuple(x)] * (1.0 - kmax)
    return dict(tp=tp, fp=fp, fn=fn,
                dti=float(tp / (tp + alpha * fp + beta * fn + EPS)))


def marginal_inclusion_threshold(current_dti: float, alpha: float = ALPHA) -> float:
    """Minimum marginal kernel credit k for an added unit dot to improve DTI.

    DTI = T / (alpha*(T+F) + beta*K); adding unit mass with realised kernel
    weight k gives dT = k, dF = 1-k, so dD = alpha exactly, and
    dDTI > 0 <=> k > alpha*DTI. (Derivation verified by brute force in
    tests/test_metric.py; corrects the alpha*s/(1-alpha*s) form that appeared
    in earlier group notes.)
    """
    return alpha * current_dti


def removal_gain(tp: float, denom: float, dn: int, ds_credit: float,
                 alpha: float = ALPHA) -> float:
    """New DTI after removing dn dots carrying ds_credit weighted credit.

    new_DTI = (T - dS) / (D - alpha*dn). Gain iff dS/dn < alpha*DTI_current.
    """
    return (tp - ds_credit) / (denom - alpha * dn + EPS)
