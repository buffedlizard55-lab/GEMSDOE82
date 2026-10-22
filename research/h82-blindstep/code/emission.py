"""DTI-aware emission: convert a belief surface to a sparse binary dot set.

Why sparse dots: DTI denominator rises by alpha=0.2 per unit mass wherever it lands, while a
truth pixel can be credited by ANY dot within 300 m (triangular kernel). Dense lines therefore
pay redundant mass; dots spaced ~2-3 px maximise credit per mass (the measured reason dotted
H19-5 at 44,090 px beat its 121,131-px parent, GEMSDOE32 claims ledger). Two rules:
- thin_topn: rank desc, accept if no accepted dot within `spacing` px (Chebyshev via visited mask).
- greedy_cover: lazy greedy max-cover of the Gaussian-smoothed belief over a candidate pool;
  each pick discounts neighbours within R=3 px by the triangular kernel (submodular coverage).
Catalogue hygiene (both): only emit where `allowed` (caller sets d(visible catalogue) > 2 px).
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter, distance_transform_edt

def allowed_mask(foot, catalogue_bool, buffer_px=2):
    d = distance_transform_edt(~catalogue_bool)
    return foot & (d > buffer_px), d

def thin_topn(surface, allowed, n, spacing=2):
    s = np.where(allowed, surface, -np.inf)
    flat = np.argpartition(s.ravel(), -min(400000, s.size))[-400000:]
    order = flat[np.argsort(s.ravel()[flat])[::-1]]
    H, W = surface.shape; taken = np.zeros((H, W), bool); blocked = np.zeros((H, W), bool)
    cnt = 0
    for f in order:
        if cnt >= n: break
        y, x = divmod(int(f), W)
        if blocked[y, x] or not np.isfinite(s[y, x]): continue
        taken[y, x] = True; cnt += 1
        y0, y1 = max(0, y - spacing), min(H, y + spacing + 1)
        x0, x1 = max(0, x - spacing), min(W, x + spacing + 1)
        blocked[y0:y1, x0:x1] = True
    return taken

def greedy_cover(surface, allowed, n, sigma=1.25, pool=250000, radius=3):
    belief = gaussian_filter(np.where(allowed, surface, 0).astype(np.float32), sigma, mode="nearest")
    b = np.where(allowed, belief, -np.inf); H, W = surface.shape
    k = min(pool, int(allowed.sum()))
    flat = np.argpartition(b.ravel(), -k)[-k:]
    ys, xs = np.divmod(flat, W); gain = b[ys, xs].astype(np.float64).copy()
    idx_of = -np.ones((H, W), np.int32); idx_of[ys, xs] = np.arange(k)
    # triangular kernel offsets
    offs = [(dy, dx, max(1 - np.hypot(dy, dx) / 3.0, 0.0))
            for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1)
            if max(1 - np.hypot(dy, dx) / 3.0, 0.0) > 0]
    cover = np.zeros((H, W), np.float32)  # best kernel cover of belief so far
    taken = np.zeros((H, W), bool); alive = np.ones(k, bool)
    for _ in range(n):
        j = int(np.argmax(np.where(alive, gain, -np.inf)))
        if not np.isfinite(gain[j]): break
        y, x = int(ys[j]), int(xs[j]); taken[y, x] = True; alive[j] = False
        for dy, dx, kw in offs:
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W:
                if kw > cover[ny, nx]:
                    cover[ny, nx] = kw
                    jj = idx_of[ny, nx]
                    if jj >= 0 and alive[jj]: gain[jj] = b[ny, nx] * (1.0 - kw)
    return taken
