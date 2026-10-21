"""Lane-drift gate (protocol §1): vs every registry raster, surface Spearman |rho| <= 0.90
AND dot overlap within 3 px <= 70% (both directions reported). FAIL = duplicate, stop."""
from __future__ import annotations
import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt
from scipy.stats import spearmanr

def read_raster(path):
    with rasterio.open(path) as s: return s.read(1)

def dot_overlap(mine_bool, other_bool):
    def frac(a, b):
        if a.sum() == 0: return 0.0
        d = distance_transform_edt(~b)
        return float((d[a] <= 3).mean())
    return frac(mine_bool, other_bool), frac(other_bool, mine_bool)

def surface_rho(mine_surface, other_arr, foot, sample=200000, seed=82):
    rng = np.random.default_rng(seed)
    idx = np.argwhere(foot & np.isfinite(other_arr))
    if len(idx) > sample: idx = idx[rng.choice(len(idx), sample, replace=False)]
    a = mine_surface[idx[:, 0], idx[:, 1]]; b = other_arr[idx[:, 0], idx[:, 1]]
    return float(spearmanr(a, b).statistic)

def check(mine_surface, mine_dots, registry_paths, foot):
    rows = []; ok = True
    for p in registry_paths:
        arr = read_raster(p); other_dots = np.isfinite(arr) & (arr > 0)
        fwd, rev = dot_overlap(mine_dots, other_dots)
        rho = surface_rho(mine_surface, arr, foot)
        bad = (abs(rho) > 0.90) or (fwd > 0.70)
        ok &= not bad
        rows.append(dict(raster=str(p), spearman_rho=rho, my_dots_within3px=fwd,
                         their_dots_within3px=rev, duplicate=bool(bad)))
    return dict(unique=bool(ok), comparisons=rows)
