"""H82-1 lane surface: blind (buried) fault facies-juxtaposition step.

Hypothesis: the USGS/INGENIOUS Quaternary catalogue is surface-rupture biased: a fault with
no scarp (buried under alluvium) is systematically unmapped, yet it still juxtaposes basement
facies, so it appears as a coincident STEP in independent potential fields (isostatic gravity
band 13, reduced-to-pole magnetics band 2, depth-to-conductive-base band 15) with a shared
strike and LOW topographic expression (det_elev_slope band 19). Signature = geometric mean of
three robust-normalised gradient-magnitude step responses x cross-field gradient-direction
agreement x soft anti-scarp gate. Label-free: never reads labels/catalogue (holdout-safe).
Named non-fault mimic: buried lithologic contact / intrusive margin / paleo-shoreline with no
fault offset produces the same coincident potential-field step.
Control surface (same steps, gate inverted to REQUIRE slope) tests the anti-scarp claim.
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter
from . import grid

def _fill(a, foot):
    v = foot & np.isfinite(a)
    med = float(np.median(a[v])) if v.any() else 0.0
    return np.where(v, a, med).astype(np.float32)

def robust_unit(a, foot, pct=99.5):
    out = np.zeros(a.shape, np.float32); v = foot & np.isfinite(a)
    if not v.any(): return out
    vals = a[v]; med = float(np.median(vals))
    q25, q75 = np.percentile(vals, [25, 75]); scale = max(float(q75 - q25) / 1.349, 1e-12)
    z = (a - med) / scale; hi = max(float(np.percentile(z[v], pct)), 1e-9)
    out[v] = np.clip(z[v] / hi, 0, 1).astype(np.float32)
    return out

def _step(features_path, idx, foot, sigma=2.0):
    a = gaussian_filter(_fill(grid.read_band(features_path, idx), foot), sigma, mode="nearest")
    gy, gx = np.gradient(a)
    return robust_unit(np.hypot(gx, gy), foot), gx.astype(np.float32), gy.astype(np.float32)

def build_surfaces(features_path, foot):
    """Returns dict of float32 surfaces in [0,1] on footprint (0 outside)."""
    g_step, ggx, ggy = _step(features_path, 13, foot)      # iso_grav_anom
    r_step, rgx, rgy = _step(features_path, 2, foot)       # rtp
    d_step, _, _ = _step(features_path, 15, foot)          # depth_to_base_surf
    c_step, _, _ = _step(features_path, 17, foot)          # cond_surf (canary / audit only)
    slope = robust_unit(_fill(grid.read_band(features_path, 19), foot), foot)  # det_elev_slope
    gn = np.hypot(ggx, ggy) + 1e-12; rn = np.hypot(rgx, rgy) + 1e-12
    agree = np.abs(ggx * rgx + ggy * rgy) / (gn * rn)      # |cos| of gradient dirs (strike-shared)
    agree = np.where(foot, agree, 0).astype(np.float32)
    core = (np.maximum(g_step, 0) * np.maximum(r_step, 0) * np.maximum(d_step, 0)) ** (1/3)
    gate_blind = (0.15 + 0.85 * (1.0 - slope)).astype(np.float32)   # favour NO scarp, floor 0.15
    gate_scarp = (0.15 + 0.85 * slope).astype(np.float32)
    w_agree = (0.5 + 0.5 * agree).astype(np.float32)
    s_blind = np.where(foot, core * w_agree * gate_blind, 0).astype(np.float32)
    s_scarp = np.where(foot, core * w_agree * gate_scarp, 0).astype(np.float32)
    return dict(grav_step=g_step, rtp_step=r_step, depth_step=d_step, cond_step=c_step,
                strike_agree=agree, slope_unit=slope, core_geomean=np.where(foot, core, 0).astype(np.float32),
                s_blind=s_blind, s_scarp_control=s_scarp)
