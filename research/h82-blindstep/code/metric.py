"""Official distance-weighted Tversky index (DTI), clean-room from the problem page.

Source (verbatim formulas): https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
  k(d) = max(1 - d/R, 0), R = 300 m = 3 px at 100 m.
  TP_w = sum_{g in G} max_{x: d(x,g)<=R} p(x) k(d(x,g))
  FP_w = sum_{x: p(x)>0} p(x) [1 - max_{g in G} k(d(x,g))]
  FN_w = sum_{g in G} [1 - max_{x: d(x,g)<=R} p(x) k(d(x,g))] = |G| - TP_w
  DTI = TP_w / (TP_w + alpha FP_w + beta FN_w + eps), alpha=0.2, beta=0.8.
Worked example on that page: TP=3.00 FP=1.89 FN=2.00 -> 0.60 (tested in tests/test_metric.py).
Algebra: DTI = T / (0.2*(T + S - M) + 0.8*|G|) with S=sum p, M=sum p*max_g k.
Marginal bar: adding unit mass with realised kernel credit k raises DTI iff k > alpha*DTI
(denominator rises by exactly alpha regardless of placement).
Known-fault handling: caller passes `known` (visible catalogue) masked pixel-exactly
(excluded from both truth and prediction scoring), per the parallel-run protocol.
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA, BETA, R_PX, EPS = 0.2, 0.8, 3.0, 1e-12

def kernel(d, radius=R_PX):
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)

def _offsets(radius=R_PX):
    r = int(np.ceil(radius)); out = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            k = float(kernel(np.hypot(dy, dx), radius))
            if k > 0: out.append((dy, dx, k))
    return out
_OFFS = _offsets()

def components(pred, truth, valid=None, known=None):
    """Exact TP_w/FP_w/FN_w for soft or binary p in [0,1]. Returns credit maps too."""
    pred = np.asarray(pred); truth = np.asarray(truth)
    if pred.ndim != 2 or pred.shape != truth.shape: raise ValueError("shape mismatch")
    valid = np.ones(pred.shape, bool) if valid is None else np.asarray(valid, bool)
    known = np.zeros(pred.shape, bool) if known is None else np.asarray(known, bool)
    active = valid & ~known
    vals = pred[active]
    if not np.isfinite(vals).all() or (vals < 0).any() or (vals > 1).any():
        raise ValueError("predictions in scored domain must be finite and in [0,1]")
    p = np.where(active, pred, 0.0).astype(np.float64)
    g = active & (truth > 0)
    n = int(g.sum())
    # credit per truth pixel: max_x p(x) k(d(x,g))
    credit_map = np.zeros(p.shape)
    if n:
        yy, xx = np.nonzero(g); credit = np.zeros(n)
        H, W = p.shape
        for dy, dx, k in _OFFS:
            ny, nx = yy + dy, xx + dx
            ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
            credit[ok] = np.maximum(credit[ok], p[ny[ok], nx[ok]] * k)
        credit_map[g] = credit
        tp = float(credit.sum())
        d = distance_transform_edt(~g)
        fp_map = p * (1.0 - kernel(d))
        fp = float(fp_map.sum()); m = float((p * kernel(d)).sum())
    else:
        tp, fp, m, fp_map = 0.0, float(p.sum()), 0.0, p.copy()
    fn = float(n) - tp
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, S=float(p.sum()), M=m,
                dti=dti_from(tp, fp, fn), credit_map=credit_map, fp_map=fp_map, truth_mask=g)

def dti_from(tp, fp, fn, alpha=ALPHA, beta=BETA):
    return float(tp / (tp + alpha * fp + beta * fn + EPS))

def marginal_bar(current_dti, alpha=ALPHA):
    return alpha * current_dti

def bruteforce(pred, truth, alpha=ALPHA, beta=BETA, radius=R_PX):
    """Literal O(|G|*|P|) transcription for unit tests only."""
    pred = np.asarray(pred, float); gs = np.argwhere(np.asarray(truth) > 0); xs = np.argwhere(pred > 0)
    tp = fn = fp = 0.0
    for g in gs:
        best = max([pred[tuple(x)] * max(1 - float(np.hypot(*(x - g))) / radius, 0.0)
                    for x in xs if float(np.hypot(*(x - g))) <= radius] + [0.0])
        tp += best; fn += 1 - best
    for x in xs:
        kmax = max([max(1 - float(np.hypot(*(x - g))) / radius, 0.0) for g in gs] + [0.0])
        fp += pred[tuple(x)] * (1 - kmax)
    return dict(tp=tp, fp=fp, fn=fn, dti=dti_from(tp, fp, fn, alpha, beta))
