"""Parallel-run duplicate guard: rank-correlation + 3 px dot overlap vs registry.

Rule (from the brief): if our raster's rank-correlation with any registry raster
exceeds 0.90, or more than 70% of our dots fall within 3 px of one registry
raster's dots, we have drifted into another lane: log it as a duplicate and STOP.

Both checks run on the final dots (binary masks). Rank-correlation here is the
Spearman correlation of the two flattened binary fields (equivalent to Pearson
on ranks; ties handled by scipy rankdata average method on a strided sample for
speed, exact on the full grid for the final verdict).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.stats import rankdata

RHO_LIMIT = 0.90
OVERLAP_LIMIT = 0.70


def spearman_binary(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, bool).ravel().astype(np.float64)
    b = np.asarray(b, bool).ravel().astype(np.float64)
    if a.std() == 0 or b.std() == 0:
        return 0.0
    ra = rankdata(a)
    rb = rankdata(b)
    ra -= ra.mean()
    rb -= rb.mean()
    denom = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / denom) if denom else 0.0


def overlap_within_3px(dots: np.ndarray, ref_dots: np.ndarray) -> float:
    """Fraction of `dots` within 3 px (Euclidean) of any `ref_dots` pixel."""
    dots = np.asarray(dots, bool)
    ref_dots = np.asarray(ref_dots, bool)
    if not dots.any():
        return 0.0
    if not ref_dots.any():
        return 0.0
    d = distance_transform_edt(~ref_dots)
    return float((d[dots] <= 3.0).mean())


def check_vs_registry(dots: np.ndarray, registry: dict[str, np.ndarray]) -> dict:
    """Returns per-ref {spearman_rho, overlap_3px} + duplicate verdict."""
    dots = np.asarray(dots, bool)
    per_ref = {}
    dup = False
    for name, ref in registry.items():
        ref = np.asarray(ref, bool)
        assert ref.shape == dots.shape, (name, ref.shape, dots.shape)
        rho = spearman_binary(dots, ref)
        ov = overlap_within_3px(dots, ref)
        is_dup = bool(rho > RHO_LIMIT or ov > OVERLAP_LIMIT)
        dup = dup or is_dup
        per_ref[name] = dict(spearman_rho=rho, overlap_3px=ov, duplicate=is_dup)
    return dict(per_ref=per_ref, duplicate=bool(dup),
                rho_limit=RHO_LIMIT, overlap_limit=OVERLAP_LIMIT,
                n_dots=int(dots.sum()))


def lane_independence_pass(surface_checks: dict, final_dot_check: dict,
                           registry_count: int, expected_registry_count: int) -> bool:
    """Fail closed unless surface AND complete final-mask screens are clean."""
    return bool(
        registry_count == expected_registry_count
        and not any(v.get("duplicate", False) for v in surface_checks.values())
        and not final_dot_check.get("duplicate", False)
    )
