"""Emitters: detector surfaces -> legal dotted prediction masks.

Metric rule (exact): adding one unit dot with realised kernel credit k improves
DTI iff k > alpha*s (s = current DTI); removing dn dots with credit dS improves
iff dS < alpha*s*dn. Consequences: (1) mass that never best-covers a truth pixel
is pure alpha cost -> prune it; (2) dots closer than ~R to each other can be
mutually redundant -> dot-thin; (3) mass inside the catalogue mask earns nothing
-> keep emissions off-catalogue.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt

from .metric import kernel


def topk_mask(field: np.ndarray, n: int, support: np.ndarray) -> np.ndarray:
    """Exactly n highest-field pixels inside support (ties by raster index)."""
    f = np.asarray(field, dtype=np.float64).copy()
    m = np.asarray(support, bool)
    f[~m] = -np.inf
    flat = f.ravel()
    if n >= int(m.sum()):
        return m.copy()
    idx = np.argpartition(flat, -n)[-n:]
    out = np.zeros(flat.size, bool)
    out[idx] = True
    return out.reshape(f.shape)


def dot_thin_fieldfirst(support: np.ndarray, field: np.ndarray,
                        min_dist: float) -> np.ndarray:
    """Poisson-disk thinning visiting candidates in DESCENDING field order.

    Differs from the group's raster-order dot_thin: the layout is field-driven,
    so kept dots sit on the strongest detector pixels rather than on an
    arbitrary raster cascade. Deterministic (stable sort by (-field, index)).
    """
    ys, xs = np.nonzero(support)
    if ys.size == 0:
        return np.zeros(support.shape, bool)
    order = np.lexsort((xs * support.shape[0] + ys, -field[ys, xs].astype(np.float64)))
    ys, xs = ys[order], xs[order]
    r2 = min_dist * min_dist
    cell = max(1.0, float(min_dist))
    cells: dict = {}
    out = np.zeros(support.shape, bool)
    for y, x in zip(ys.tolist(), xs.tolist()):
        cy, cx = int(y // cell), int(x // cell)
        ok = True
        for gy in range(cy - 2, cy + 3):
            for gx in range(cx - 2, cx + 3):
                for (ky, kx) in cells.get((gy, gx), ()):
                    dy, dx = y - ky, x - kx
                    if dy * dy + dx * dx < r2 - 1e-9:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            out[y, x] = True
            cells.setdefault((cy, cx), []).append((y, x))
    return out


def dot_thin_matched(field: np.ndarray, n_target: int, support: np.ndarray,
                     min_dist: float = 2.8, iters: int = 14) -> np.ndarray:
    """Field-first thinning calibrated (support-quantile bisection) to ~n_target dots."""
    lo, hi = 0.0, 1.0
    best = None
    f = np.asarray(field, dtype=np.float64)
    m = np.asarray(support, bool)
    vals = f[m]
    if vals.size == 0:
        return np.zeros(field.shape, bool)
    for _ in range(iters):
        q = 0.5 * (lo + hi)
        tau = np.quantile(vals, 1.0 - q)
        sup = m & (f >= tau)
        dots = dot_thin_fieldfirst(sup, f, min_dist)
        n = int(dots.sum())
        if best is None or abs(n - n_target) < abs(best[0] - n_target):
            best = (n, dots)
        if n > n_target:
            hi = q
        else:
            lo = q
    return best[1]


def redundancy_prune(mask: np.ndarray, truth_proxy: np.ndarray,
                     keep_credit: float = 0.0) -> np.ndarray:
    """Delete dots that are the unique best cover of NO proxy-truth pixel.

    A dot is kept iff some proxy-truth pixel attains its maximum kernel credit
    from it (ties -> lowest raster index wins, deterministic). Dots with zero
    proxy credit are pure alpha cost under the proxy; `keep_credit` retains dots
    whose own detector credit exceeds it (safety against proxy incompleteness).
    """
    m = np.asarray(mask, bool).copy()
    t = np.asarray(truth_proxy, bool)
    if not m.any() or not t.any():
        return m
    ys, xs = np.nonzero(m)
    # credit each truth pixel can draw from the full set:
    dp_full = distance_transform_edt(~m)
    cred_full = kernel(dp_full[t])
    keep = np.zeros(m.shape, bool)
    # winner-take-all: attribute each credited truth pixel to its nearest dot.
    # NOTE: nearest-dot attribution is exact for binary dots because kernel
    # credit decreases monotonically with distance (ties broken by EDT order).
    idx = distance_transform_edt(~m, return_distances=False, return_indices=True)
    ty, tx = np.nonzero(t)
    c = kernel(dp_full[ty, tx])
    pos = c > 0
    wy = idx[0, ty[pos], tx[pos]]
    wx = idx[1, ty[pos], tx[pos]]
    keep[wy, wx] = True
    # `keep_credit` is applied by the caller as an explicit OR-mask (detector
    # corroboration retention); see scripts/run_pipeline.py experiment 2.
    return m & keep


def flank_select(mask: np.ndarray, dist_to_catalogue: np.ndarray,
                 keep_where: np.ndarray, radius_px: float) -> np.ndarray:
    """Selective flank prune: delete dots with d(cat)<=radius EXCEPT keep_where.

    Blanket B=3 pruning deletes credited dots too; this keeps flank dots that
    carry independent physical evidence (the lane-82 corroboration gate).
    """
    m = np.asarray(mask, bool).copy()
    flank = np.asarray(dist_to_catalogue) <= radius_px
    return m & ~(flank & ~np.asarray(keep_where, bool))
