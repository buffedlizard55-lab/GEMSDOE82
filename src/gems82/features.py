"""Lane-82 label-free detector surfaces.

All surfaces are computed ONLY from the external rasters (USGS 3DEP 1 m LiDAR
scarp stack, USGS GeoDAWN radiometrics, GDR 1391 point tables). NO surface reads
labels.tif / existing_faults.tif / any scored submission, so each is safe to
evaluate on a spatial holdout without retrospective leakage. (Verified by the
leakage canary in scripts/run_canary.py: AUC > 0.90 vs any truth = leakage.)

External band orders (from data/external/*.json sidecars):
  lidar_scarp_features_u8.tif : ex_max, ex_mean, step_max, lapneg_max,
      lappos_max, downface_max, upface_max, cross_max, relief, coh100,
      strike, valid   (quantisation q = 1 + round(254*t(clip(x/xmax,0,1))))
  geodawn_rad_u8.tif          : K, Th, U, TC
  geodawn_extensions_u8.tif   : ThK, UK, UTh, TMI_up150
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter, maximum_filter

LIDAR_BANDS = ["ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max",
               "downface_max", "upface_max", "cross_max", "relief", "coh100",
               "strike", "valid"]
LIDAR_XMAX = {"ex_max": 1.5, "ex_mean": 0.3, "step_max": 1.0, "lapneg_max": 0.05,
              "lappos_max": 0.05, "downface_max": 1.0, "upface_max": 1.0,
              "cross_max": 1.0, "relief": 300.0, "coh100": 1.0, "strike": 180.0,
              "valid": 1.0}
LIDAR_SQRT = {"ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max",
              "downface_max", "upface_max", "cross_max", "relief"}
RAD_BANDS = ["K", "Th", "U", "TC"]
EXT_BANDS = ["ThK", "UK", "UTh", "TMI_up150"]


def dequant_lidar(q: np.ndarray, band: str) -> np.ndarray:
    """Invert q = 1 + round(254*t(clip(x/xmax,0,1))); q==0 means no-lidar.

    Returns physical units where the band documents them (m/m, 1/m, m, deg),
    NaN where q == 0.
    """
    q = np.asarray(q, dtype=np.float64)
    out = np.full(q.shape, np.nan)
    m = q > 0
    t = (q[m] - 1.0) / 254.0
    if band in LIDAR_SQRT:
        t = t ** 2
    out[m] = np.clip(t, 0.0, 1.0) * LIDAR_XMAX[band]
    return out.astype(np.float32)


def read_lidar(external_dir: str | Path) -> dict[str, np.ndarray]:
    d = Path(external_dir)
    out = {}
    with rasterio.open(d / "lidar_scarp_features_u8.tif") as ds:
        for i, name in enumerate(LIDAR_BANDS, start=1):
            out[name] = dequant_lidar(ds.read(i), name)
    return out


def read_rad(external_dir: str | Path) -> dict[str, np.ndarray]:
    """Radiometrics as 0..1 (uint8 / 255); 0 (nodata) -> NaN."""
    d = Path(external_dir)
    out = {}
    with rasterio.open(d / "geodawn_rad_u8.tif") as ds:
        for i, name in enumerate(RAD_BANDS, start=1):
            q = ds.read(i).astype(np.float32)
            out[name] = np.where(q > 0, q / 255.0, np.nan).astype(np.float32)
    return out


def read_ext(external_dir: str | Path) -> dict[str, np.ndarray]:
    d = Path(external_dir)
    out = {}
    with rasterio.open(d / "geodawn_extensions_u8.tif") as ds:
        for i, name in enumerate(EXT_BANDS, start=1):
            q = ds.read(i).astype(np.float32)
            out[name] = np.where(q > 0, q / 255.0, np.nan).astype(np.float32)
    return out


def robust_unit(a: np.ndarray, foot: np.ndarray, pct: float = 99.5,
                clip: float = 6.0) -> np.ndarray:
    """Robust footprint-normalised non-negative score in [0, 1]."""
    out = np.zeros(a.shape, dtype=np.float32)
    v = np.asarray(foot, bool) & np.isfinite(a)
    if not v.any():
        return out
    vals = a[v].astype(np.float64)
    med = float(np.median(vals))
    q25, q75 = np.percentile(vals, [25.0, 75.0])
    scale = max(float(q75 - q25) / 1.349, 1e-9)
    z = (a.astype(np.float64) - med) / scale
    hi = float(np.percentile(z[v], pct))
    hi = max(hi, 1e-6)
    out[v] = np.clip(z[v] / hi, 0.0, clip) / clip
    return out


def _fill(a: np.ndarray, foot: np.ndarray, sigma: float | None = 1.0) -> np.ndarray:
    v = np.asarray(foot, bool) & np.isfinite(a)
    med = float(np.median(a[v])) if v.any() else 0.0
    f = np.where(v, a, med).astype(np.float32)
    return gaussian_filter(f, sigma, mode="nearest") if sigma else f


def grad_mag(a: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    gx = gaussian_filter(a, sigma, order=(0, 1), mode="nearest")
    gy = gaussian_filter(a, sigma, order=(1, 0), mode="nearest")
    return np.hypot(gx, gy).astype(np.float32)


def nms_ridge(a: np.ndarray, foot: np.ndarray, radius: int = 1) -> np.ndarray:
    """4-direction non-maximum-suppressed crest strength (Hilditch-style max)."""
    f = _fill(a, foot, sigma=None)
    best = np.zeros_like(f)
    shifts = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for dy, dx in shifts:
        p1 = np.roll(np.roll(f, dy, 0), dx, 1)
        p2 = np.roll(np.roll(f, -dy, 0), -dx, 1)
        crest = np.minimum(f - p1, f - p2)
        np.maximum(best, crest, out=best)
    return np.where(foot, np.maximum(best, 0.0), 0.0).astype(np.float32)


def orientation_coherence_vote(strike_deg: np.ndarray, coh: np.ndarray,
                               foot: np.ndarray, window: int = 5) -> np.ndarray:
    """Doubled-angle resultant length of strike over a window, gated by coh.

    Returns R in [0,1]: 1 where neighbouring pixels agree on one strike AND the
    local fabric is coherent; ~0 for isotropic/noisy fabric. Label-free.
    """
    th = np.deg2rad(np.where(np.isfinite(strike_deg), strike_deg, 0.0)) * 2.0
    c = np.where(np.isfinite(coh), np.clip(coh, 0, 1), 0.0)
    u = np.cos(th) * c
    v = np.sin(th) * c
    k = 2 * (window // 2) + 1
    su = maximum_filter(u, size=k, mode="nearest")  # dilate support, not the mean
    # use uniform (mean) resultant for agreement:
    from scipy.ndimage import uniform_filter
    mu = uniform_filter(u, size=k, mode="nearest")
    mv = uniform_filter(v, size=k, mode="nearest")
    mc = uniform_filter(c, size=k, mode="nearest")
    R = np.hypot(mu, mv) / np.maximum(mc, 1e-9)
    return np.where(np.asarray(foot, bool), np.clip(R, 0, 1), 0.0).astype(np.float32)


# ----------------------------------------------------------------------------------
# Lane H82-2 hypothesis surfaces (display IDs H82-2.1 .. H82-2.5; code names
# h82_1 .. h82_5 predate the H82-1-blindstep lane — see docs/lanes.html).
# Each returns float32 in [0,1]-ish.
# ----------------------------------------------------------------------------------

def h82_1_antislope_lineament(lidar: dict, foot: np.ndarray) -> np.ndarray:
    """H82-2.1 (PRIMARY): antislope (uphill-facing) scarp lineaments.

    upface_max = max 10 m-scale step gradient AGAINST the regional slope, i.e.
    scarps that face uphill. A fluvial bank or terrace riser always faces
    downhill; an uphill-facing step is a fault scarp, a sackung/landslide
    headscarp, or a resistant bed — far more fault-specific than generic
    slope-excess. Surface = NMS crest of upface x strike-agreement vote x
    lidar-valid, with channel-bank suppression (low cross_max quotient).
    """
    up = lidar["upface_max"]
    cross = lidar["cross_max"]
    strike = lidar["strike"]
    coh = lidar["coh100"]
    valid = lidar["valid"]
    crest = nms_ridge(np.nan_to_num(up, nan=0.0), foot)
    agree = orientation_coherence_vote(strike, coh, foot, window=5)
    up_u = robust_unit(np.nan_to_num(up, nan=0.0), foot)
    cross_u = robust_unit(np.nan_to_num(cross, nan=0.0), foot)
    bank_suppress = 1.0 - 0.6 * cross_u  # channel banks have high cross_max
    s = robust_unit(crest, foot) * (0.35 + 0.65 * agree) * (0.35 + 0.65 * up_u)
    s = s * bank_suppress
    s = np.where(np.isfinite(valid) & (valid > 0), s, 0.0)
    return np.where(foot, s, 0.0).astype(np.float32)


def h82_2_radiometric_break(rad: dict, ext: dict, foot: np.ndarray) -> np.ndarray:
    """H82-2.2: airborne radiometric ratio breaks (K-enrichment / U-mobility edges).

    Hydrothermal alteration along a fault resets K (enrichment in argillic caps)
    and mobilises U; the RATIO edges (Th/K, U/Th) mark alteration fronts even
    where absolute counts are low. Surface = max gradient magnitude over the
    six ratio/count fields, NMS-crided. Catches blind faults with clay caps but
    no scarp. Mimic: lithologic contacts (addressed by requiring lineament
    straightness via H82-2.1 agreement in the fusion, not here).
    """
    fields = [rad["K"], rad["Th"], rad["U"], ext["ThK"], ext["UK"], ext["UTh"]]
    gm = np.zeros(foot.shape, np.float32)
    for f in fields:
        g = grad_mag(_fill(f, foot, sigma=1.0), sigma=1.0)
        gm = np.maximum(gm, robust_unit(g, foot))
    crest = nms_ridge(gm, foot)
    return np.where(foot, robust_unit(crest, foot), 0.0).astype(np.float32)


def h82_3_valley_deflection(lidar: dict, foot: np.ndarray) -> np.ndarray:
    """H82-2.3: deflected-drainage lineaments (valley-floor kink detector).

    Faults offset and align channels; the signature is a straight valley reach
    that kinks: high relief-gradient coherence along a line. Proxy from 100 m
    aggregates: NMS valley skeleton on -relief-gradient... here implemented as
    crest of lappos (base concavity = valley floor) weighted by relief and
    strike agreement. Catches range-front step faults buried under fans (no
    scarp preserved at 1 m because the fan surface is young).
    Mimic: axial playas / meander cutoffs (excluded by straightness vote).
    """
    lap = lidar["lappos_max"]
    relief = lidar["relief"]
    agree = orientation_coherence_vote(lidar["strike"], lidar["coh100"], foot, window=7)
    crest = nms_ridge(np.nan_to_num(lap, nan=0.0), foot)
    s = robust_unit(crest, foot) * (0.3 + 0.7 * agree)
    s = s * (0.5 + 0.5 * robust_unit(np.nan_to_num(relief, nan=0.0), foot))
    valid = lidar["valid"]
    return np.where(foot & np.isfinite(valid) & (valid > 0), s, 0.0).astype(np.float32)


def h82_4_conjugate_intersection(lidar: dict, foot: np.ndarray) -> np.ndarray:
    """H82-2.4: conjugate / intersection-node density (dilatational jog proxy).

    Geothermal upflow concentrates at fault intersections and stepovers (Faulds
    & Hinz 2015). Label-free proxy: pixels where TWO distinct strikes coexist
    within 5 px (low resultant R but high coherence on both sides), i.e. local
    strike variance hotspots on the scarp fabric. Catches relay ramps between
    mapped segments — the canonical 'fault missing from the catalogue'.
    Mimic: dendritic drainage junctions (suppressed by requiring scarp relief).
    """
    strike = np.deg2rad(np.where(np.isfinite(lidar["strike"]), lidar["strike"], 0.0)) * 2.0
    coh = np.where(np.isfinite(lidar["coh100"]), lidar["coh100"], 0.0)
    from scipy.ndimage import uniform_filter
    u = np.cos(strike) * coh
    v = np.sin(strike) * coh
    mu = uniform_filter(u, size=5, mode="nearest")
    mv = uniform_filter(v, size=5, mode="nearest")
    mc = uniform_filter(coh, size=5, mode="nearest")
    R = np.hypot(mu, mv) / np.maximum(mc, 1e-9)
    disagree = (1.0 - R) * np.clip(mc * 2.0, 0, 1)  # high fabric energy, no single strike
    relief_u = robust_unit(np.nan_to_num(lidar["relief"], nan=0.0), foot)
    s = np.clip(disagree, 0, 1) * (0.4 + 0.6 * relief_u)
    valid = lidar["valid"]
    s = np.where(np.isfinite(valid) & (valid > 0), s, 0.0)
    return np.where(foot, s, 0.0).astype(np.float32)


def h82_5_thermal_upflow_prior(data_dir: str | Path, foot: np.ndarray,
                               length_px: float = 20.0) -> np.ndarray:
    """H82-2.5: GDR measured-geothermometer upflow halo (IDW of T_reservoir max).

    Per-spring max of quartz/chalcedony/cation geothermometers (measured spring
    chemistry, GDR 1391, CC BY 4.0); IDW surface w = 1/(1+(d/L)^2), L=20 px.
    A >150 C reservoir needs a deep permeable conduit — a fault — which needs
    no surface scarp. Catches blind conduits under cover. Mimic: lateral
    outflow plumes (down-weighted by taking the max estimator, which disagrees
    under mixing, and by short L). Label-free (dist_known_fault_px NEVER used).
    """
    import pandas as pd
    p = Path(data_dir) / "external" / "gdr_wellspring_in_footprint.csv"
    out = np.zeros(foot.shape, np.float32)
    if not p.exists():
        return out
    df = pd.read_csv(p)
    need = {"row", "col", "geothermquartz_c", "geothermchalc_c", "geothermcat_c", "temp_c"}
    if not need.issubset(df.columns):
        return out
    t = df[["geothermquartz_c", "geothermchalc_c", "geothermcat_c"]].apply(pd.to_numeric, errors="coerce")
    tmax = t.max(axis=1)
    ok = np.isfinite(tmax.to_numpy()) & np.isfinite(df["row"].to_numpy()) & np.isfinite(df["col"].to_numpy())
    if not ok.any():
        return out
    rr = df["row"].to_numpy()[ok].astype(int)
    cc = df["col"].to_numpy()[ok].astype(int)
    vv = np.clip(tmax.to_numpy()[ok].astype(float), 0, 350) / 350.0
    H, W = foot.shape
    sel = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
    rr, cc, vv = rr[sel], cc[sel], vv[sel]
    if rr.size == 0:
        return out
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([rr, cc]).astype(float))
    yy, xx = np.mgrid[0:H, 0:W]
    grid_pts = np.column_stack([yy.ravel(), xx.ravel()]).astype(float)
    acc = np.zeros(grid_pts.shape[0])
    wsum = np.zeros(grid_pts.shape[0])
    k = min(8, rr.size)
    step = 400_000
    for s0 in range(0, grid_pts.shape[0], step):
        d, idx = tree.query(grid_pts[s0:s0 + step], k=k)
        d = np.atleast_2d(d)
        idx = np.atleast_2d(idx)
        w = 1.0 / (1.0 + (d / length_px) ** 2)
        acc[s0:s0 + step] = (w * vv[idx]).sum(axis=1)
        wsum[s0:s0 + step] = w.sum(axis=1)
    out = (acc / np.maximum(wsum, 1e-12)).reshape(H, W).astype(np.float32)
    out = gaussian_filter(out, sigma=3.0)
    return np.where(foot, np.clip(out, 0, 1), 0.0).astype(np.float32)


def h82_6_magnetic_tilt(ext: dict, foot: np.ndarray) -> np.ndarray:
    """H82-2.6: GeoDAWN TMI_up150 horizontal-gradient + Laplace-tilt edge ridges.

    Upward-continued (150 m) total magnetic intensity covers 99.94% of the
    competition footprint (including the 24.63% of the footprint and 45.8% of
    the NE quadrant where 1 m 3DEP LiDAR has valid==0). By Laplace's equation in
    source-free space above the magnetic basement, d2M/dz2 = -(d2M/dx2 + d2M/dy2).
    Combining the NMS crest of the horizontal gradient ||grad_h M|| (Blakely &
    Simpson 1986) with the NMS crest of the harmonic tilt-angle gradient
    ||grad arctan(V2 / ||grad_h M||)|| (Miller & Singh 1994; Verduzco et al.
    2004) locates concealed intrabasin and basement-step fault contacts beneath
    alluvial cover. Mimic: unfaulted plutonic/volcanic contacts and dikes.
    """
    raw = ext["TMI_up150"]
    tmi = _fill(raw, foot, sigma=1.5)
    gx = gaussian_filter(tmi, 1.5, order=(0, 1), mode="nearest")
    gy = gaussian_filter(tmi, 1.5, order=(1, 0), mode="nearest")
    hgrad = np.hypot(gx, gy).astype(np.float32)
    lap_h = -(gaussian_filter(tmi, 1.5, order=(0, 2), mode="nearest") +
              gaussian_filter(tmi, 1.5, order=(2, 0), mode="nearest"))
    tilt = np.arctan2(lap_h, np.maximum(hgrad, 1e-6)).astype(np.float32)
    tilt_grad = grad_mag(tilt, sigma=1.0)
    s = (0.6 * robust_unit(nms_ridge(hgrad, foot), foot) +
         0.4 * robust_unit(nms_ridge(tilt_grad, foot), foot))
    valid_tmi = np.asarray(foot, bool) & np.isfinite(raw)
    return np.where(valid_tmi, robust_unit(s, foot), 0.0).astype(np.float32)


def _stratum_unit(a: np.ndarray, mask: np.ndarray, pct: float = 99.5) -> np.ndarray:
    v = np.clip(np.nan_to_num(a, nan=0.0), 0.0, None)
    m = np.asarray(mask, bool)
    if not m.any():
        return np.zeros(a.shape, dtype=np.float32)
    hi = float(np.percentile(v[m], pct))
    return np.clip(v / max(hi, 1e-9), 0.0, 1.0).astype(np.float32)


def _quantile_rank(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    from scipy.stats import rankdata
    out = np.zeros(a.shape, dtype=np.float32)
    m = np.asarray(mask, bool) & np.isfinite(a)
    if not m.any():
        return out
    vals = a[m]
    out[m] = ((rankdata(vals, method="average") - 0.5) / float(vals.size)).astype(np.float32)
    return out


def coverage_aware_corroboration(
    s1_antislope: np.ndarray,
    s2_rad: np.ndarray,
    s3_valley: np.ndarray,
    s4_conj: np.ndarray,
    s5_thermal: np.ndarray,
    s6_mag: np.ndarray,
    valid_lidar: np.ndarray,
    foot: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Coverage-aware multi-physics corroboration (C_cov, C_add).

    Fixes the H82-2 missing-LiDAR coverage confound (IR-82-LIDAR-01): 1 m LiDAR
    covers 75.37% of the footprint (valid_lidar==False on 24.63% of footprint
    and 45.8% of NE quadrant). Averaging zero-filled LiDAR surfaces with
    full-coverage GeoDAWN surfaces caused 52.1% of H82-2's dot removals to fall
    in valid_lidar==0 regions purely due to missing LiDAR survey tiles.

    Returns:
      * C_cov : stratum-quantile-normalised score in [0, 1] with identical
                Uniform(0, 1) marginal distribution on both valid_lidar and
                no_lidar strata (used for unbiased carrier retention).
      * C_add : coverage-aware physical corroboration amplitude in [0, 1] (used
                for field-first Poisson-disk placement of novel far-field dots).
    """
    foot_b = np.asarray(foot, bool)
    vl = np.asarray(valid_lidar, bool) & foot_b
    nl = foot_b & ~vl

    u1 = _stratum_unit(s1_antislope, vl)
    u3 = _stratum_unit(s3_valley, vl)
    u4 = _stratum_unit(s4_conj, vl)
    u2 = _stratum_unit(s2_rad, foot_b)
    u5 = _stratum_unit(s5_thermal, foot_b)
    u6 = _stratum_unit(s6_mag, foot_b)

    c_lidar = (0.45 * u1 + 0.25 * u4 + 0.12 * u3 + 0.09 * u2 + 0.09 * u6).astype(np.float32)
    c_nolidar = (0.45 * u6 + 0.40 * u2 + 0.15 * u5).astype(np.float32)

    c_cov = np.zeros(foot_b.shape, dtype=np.float32)
    c_cov[vl] = _quantile_rank(c_lidar, vl)[vl]
    c_cov[nl] = _quantile_rank(c_nolidar, nl)[nl]

    c_add = np.where(
        vl,
        0.50 * u1 + 0.25 * u4 + 0.15 * u3 + 0.05 * u2 + 0.05 * u6,
        0.25 * (0.55 * u6 + 0.45 * u2),
    ).astype(np.float32)
    c_add = np.where(foot_b, c_add, 0.0).astype(np.float32)
    return c_cov, c_add


def fuse(surfaces: dict[str, np.ndarray], foot: np.ndarray,
         weights: dict[str, float] | None = None) -> np.ndarray:
    """Weighted-mean fusion of [0,1] surfaces (default: equal weights)."""
    weights = weights or {k: 1.0 for k in surfaces}
    tot = sum(weights.values()) or 1.0
    out = np.zeros(foot.shape, np.float32)
    for k, s in surfaces.items():
        out += weights.get(k, 0.0) * np.clip(np.nan_to_num(s, nan=0.0), 0, 1)
    out /= tot
    return np.where(foot, out, 0.0).astype(np.float32)
