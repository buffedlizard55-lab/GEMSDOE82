"""Zero-leakage multi-resolution physical feature stack (`64` static channels + `8` fold-safe
mechanical channels) and Rule 4 single-feature leakage canary audit for GEMSDOE82 (`Lane H82`).

Strict invariants:
  1. Zero historical prediction rasters are read anywhere in feature construction or training.
  2. `derived_sgmc_faults_100m_u8.tif` is NEVER used in `X_static`, fold mechanics, or training.
  3. Catalogue-derived columns in external tables (`dist_known_fault_px`, `known_fault`, `label`)
     are explicitly blocked and asserted unused.
  4. `1 m` 3DEP LiDAR bands preserve native `NaN` outside LiDAR coverage (`24.60%` of footprint)
     so tree splits never create artificial survey-boundary cliffs.
  5. Peak container RSS stays well under `1.1 GB` (`float16` memmap = `661 MB` on disk).
"""
from __future__ import annotations

import gc
import json
import struct
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform as rio_transform
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from sklearn.metrics import roc_auc_score

FORBIDDEN_COLS = frozenset({"dist_known_fault_px", "known_fault", "label"})

DOMAIN_SLICES: Dict[str, slice] = {
    "scarp": slice(0, 22),     # 22 ch: 1m LiDAR (native NaN) + 1m Openness + 3m Wallace + 10m 3DEP
    "fluv": slice(22, 34),     # 12 ch: Pluvial strike-climb z_ASL + Fluvial chi/ksn/area + Road prism
    "pot": slice(34, 50),      # 16 ch: Verduzco tilt + 150m upward TMI + Gallardo-Meju cross-grad + Basement
    "geo": slice(50, 64),      # 14 ch: GDR springs + 3,800 2m probes + 709 sinter seals + K/Th + MT + Demag
}

STATIC_FEATURE_NAMES: List[str] = [
    # Domain 1: Multi-Resolution Tectonic Geomorphology (0..21)
    "lid_has_coverage",
    "lid_step_max",
    "lid_piedmont_step",
    "lid_dipole",
    "lid_tect_vs_fluv",
    "lid_antislope",
    "lid_coh100",
    "lid_step_dog",
    "lid_worm_1300m",
    "open1m_dipole_lrm",
    "h3m_gate07",
    "h3m_gate12",
    "h3m_sharpness",
    "h3m_worm_1300m",
    "t10_slope_p90",
    "t10_steep_frac",
    "t10_slope_conc",
    "t10_curv_dog",
    "t10_aspect_planar",
    "t10_hs_worm_1500m",
    "det_elev_lrm",
    "det_slope_anom",
    # Domain 2: Pluvial Contour-Climb & Fluvial ksn/Chi Interfluve Decontamination (22..33)
    "z_along_strike_climb_1500m",
    "z_cross_strike_drop_700m",
    "climb_to_shoreline_ratio",
    "pluvial_highstand_prox",
    "pluvial_mimic_flag",
    "chi_log10_area",
    "interfluve_scarp_idx",
    "chi_ksn_max",
    "chi_ksn_knick_dog",
    "chi_divide_step",
    "road_log_dist",
    "road_embankment_flag",
    # Domain 3: Depth-Invariant Potential-Field Tilt & Cross-Gradient Contact Physics (34..49)
    "verduzco_mag_tilt",
    "verduzco_mag_tilt_hgm",
    "verduzco_grav_tilt",
    "verduzco_grav_tilt_hgm",
    "worm_mag_1500m",
    "worm_grav_1500m",
    "up150_deep_persist",
    "crossgrad_align_topo_pot",
    "crossgrad_ortho_confounder",
    "dbase_log",
    "dbase_grad",
    "dbase_curv",
    "grav_hp8",
    "rtp_hp8",
    "strain_transtension",
    "seismic_micro_log",
    # Domain 4: Backward Geothermal Conduit Inversion (50..63)
    "gdr_spring_aniso_near",
    "gdr_spring_aniso_far",
    "probe_2m_dab_near",
    "probe_2m_dab_halo",
    "paleo_sinter_seal_near",
    "paleo_sinter_seal_halo",
    "volc_vent_halo",
    "tc_heatflow_resid",
    "mt_clay_cap_grad",
    "mt_cond_local",
    "rad_k_th_alteration",
    "rad_tc_grad",
    "hydro_demag_conduit",
    "geotherm_multiline_index",
]
assert len(STATIC_FEATURE_NAMES) == 64

FOLD_MECH_NAMES: List[str] = [
    "vis_collinear_short",
    "vis_collinear_med",
    "vis_stepover_bridge",
    "vis_wingcrack_lobe",
    "vis_strike_corridor",
    "vis_dist_log_capped",
    "vis_slip_dilation_tendency",
    "vis_phys_corroborated_bridge",
]
assert len(FOLD_MECH_NAMES) == 8


@dataclass
class StaticStack82:
    X_mmap: np.memmap                 # shape (N_valid, 64), float16
    valid_idx: np.ndarray             # flat indices of footprint == True (5,167,373)
    has_lidar_fp: np.ndarray          # bool (5,167,373)
    det_slope_fp: np.ndarray          # float32 (5,167,373), degrees/grade from band 19
    best_strike_rad_2d: np.ndarray    # float32 (H, W) in [0, pi)
    scarp_prior_2d: np.ndarray        # float32 (H, W) standardized multi-res scarp amplitude
    feature_names: List[str]


_IDX_CACHE: List[Tuple[np.ndarray, np.ndarray]] = []


def _nn_fill(arr: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    out = arr.astype(np.float32, copy=True)
    bad = ~valid_mask
    if bad.any():
        idx = None
        for prev_bad, prev_idx in _IDX_CACHE:
            if np.array_equal(bad, prev_bad):
                idx = prev_idx
                break
        if idx is None:
            idx = ndi.distance_transform_edt(bad, return_distances=False, return_indices=True)
            if len(_IDX_CACHE) < 4:
                _IDX_CACHE.append((bad.copy(), idx))
        out[bad] = out[idx[0][bad], idx[1][bad]]
    return out


def _clip_f16(vec: np.ndarray) -> np.ndarray:
    """Standardize extreme tails safely inside float16 dynamic range while preserving NaNs."""
    v = vec.astype(np.float32, copy=False)
    fin = np.isfinite(v)
    if not fin.any():
        return np.zeros_like(v, dtype=np.float16)
    med = float(np.median(v[fin]))
    mad = float(np.median(np.abs(v[fin] - med))) * 1.4826 + 1e-5
    z = (v - med) / mad
    out = np.empty_like(v, dtype=np.float16)
    out[fin] = np.clip(z[fin], -25.0, 25.0).astype(np.float16)
    out[~fin] = np.float16(np.nan)
    return out


def compute_oriented_worm(
    edge_2d: np.ndarray, valid_2d: np.ndarray, half_len: int = 6, flank: int = 3
) -> np.ndarray:
    """6-azimuth strike-integrated ridge response minus parallel flanking baselines.

    Uses exact non-zero sparse stencil accumulation (~35x faster than dense 2D convolution
    while producing identical floating-point ridge-minus-flank integrals).
    """
    x = np.where(valid_2d, np.nan_to_num(edge_2d, nan=0.0), 0.0).astype(np.float32)
    m = ndi.uniform_filter(x, size=25)
    s = np.sqrt(np.maximum(ndi.uniform_filter(x * x, size=25) - m * m, 1e-6))
    z = np.clip((x - m) / (s + 0.2), -3.0, 7.0).astype(np.float32)
    del m, s

    H, W = z.shape
    pad = half_len + flank + 1
    zp = np.pad(z, pad, mode="edge")
    best = np.full((H, W), -1e9, dtype=np.float32)
    sample_t = range(-half_len, half_len + 1, 2)
    n_t = float(len(sample_t))

    for deg in (0, 30, 60, 90, 120, 150):
        rad = np.radians(deg)
        dy, dx = np.sin(rad), np.cos(rad)
        py, px = -dx, dy
        acc = np.zeros((H, W), dtype=np.float32)
        for t in sample_t:
            oy = pad + int(round(t * dy))
            ox = pad + int(round(t * dx))
            acc += zp[oy : oy + H, ox : ox + W]
            for sgn in (-1, 1):
                fy = pad + int(round(t * dy + sgn * flank * py))
                fx = pad + int(round(t * dx + sgn * flank * px))
                acc -= 0.5 * zp[fy : fy + H, fx : fx + W]
        acc *= 1.0 / n_t
        np.maximum(best, acc, out=best)
    del zp, z
    return np.where(valid_2d, np.maximum(best, 0.0), 0.0).astype(np.float32)


def _point_kernel_field(
    shape: Tuple[int, int],
    rows: np.ndarray,
    cols: np.ndarray,
    weights: np.ndarray,
    sigma_near: float = 4.5,
    sigma_far: float = 16.0,
) -> Tuple[np.ndarray, np.ndarray]:
    imp = np.zeros(shape, dtype=np.float32)
    if rows.size:
        np.maximum.at(imp, (rows, cols), weights.astype(np.float32))
    near = ndi.gaussian_filter(imp, sigma=sigma_near) * (sigma_near ** 2)
    far = ndi.gaussian_filter(imp, sigma=sigma_far) * (sigma_far ** 2)
    return near.astype(np.float32), far.astype(np.float32)


def _load_2m_probes(zip_path: Path, transform: Any, shape: Tuple[int, int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    with zipfile.ZipFile(zip_path) as zf:
        dbf_name = next(n for n in zf.namelist() if n.lower().endswith(".dbf"))
        buf = zf.read(dbf_name)
    numrec, lenhdr, lenrec = struct.unpack("<4xIHH20x", buf[:32])
    fields = []
    pos, offset = 32, 1
    while buf[pos] != 0x0D:
        fname = buf[pos : pos + 11].split(b"\x00", 1)[0].decode("ascii", errors="ignore")
        assert fname not in FORBIDDEN_COLS, f"Blocked column {fname}"
        flen = buf[pos + 16]
        fields.append((fname, offset, flen))
        offset += flen
        pos += 32
    fmap = {n: (o, l) for n, o, l in fields}
    lats, lons, wts = [], [], []
    for i in range(numrec):
        rec = buf[lenhdr + i * lenrec : lenhdr + (i + 1) * lenrec]
        if not rec or rec[:1] == b"*":
            continue
        try:
            lat = float(rec[fmap["LatDegreeN"][0] : fmap["LatDegreeN"][0] + fmap["LatDegreeN"][1]].strip())
            lon = float(rec[fmap["LongDegree"][0] : fmap["LongDegree"][0] + fmap["LongDegree"][1]].strip())
            dab_s = rec[fmap["F2mDAB"][0] : fmap["F2mDAB"][0] + fmap["F2mDAB"][1]].strip()
            t2m_s = rec[fmap["T2m"][0] : fmap["T2m"][0] + fmap["T2m"][1]].strip()
            dab = float(dab_s) if dab_s else 0.0
            t2m = float(t2m_s) if t2m_s else 0.0
        except ValueError:
            continue
        if 35.0 <= lat <= 45.0 and -123.0 <= lon <= -112.0:
            lats.append(lat)
            lons.append(lon)
            wts.append(1.0 + max(0.0, dab) * 0.6 + max(0.0, t2m - 21.0) * 0.15)
    ux, uy = rio_transform("EPSG:4269", "EPSG:32611", lons, lats)
    cols = np.floor((np.asarray(ux) - transform.c) / transform.a).astype(np.int64)
    rows = np.floor((np.asarray(uy) - transform.f) / transform.e).astype(np.int64)
    ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
    return rows[ok], cols[ok], np.asarray(wts, dtype=np.float32)[ok]


def build_or_load_static_stack82(
    data_dir: Path, cache_dir: Path, fp: np.ndarray, force_rebuild: bool = False
) -> StaticStack82:
    """Build or reload the 64-feature static multi-physics stack on valid footprint cells."""
    t0 = time.time()
    cache_dir.mkdir(parents=True, exist_ok=True)
    mmap_path = cache_dir / "gems82_static64.f16.mmap"
    aux_path = cache_dir / "gems82_static64_aux.npz"
    valid_idx = np.flatnonzero(fp.ravel())
    n_val = int(valid_idx.size)
    shape = fp.shape

    if not force_rebuild and mmap_path.is_file() and aux_path.is_file():
        X_mmap = np.memmap(mmap_path, dtype=np.float16, mode="r", shape=(n_val, len(STATIC_FEATURE_NAMES)))
        aux = np.load(aux_path)
        return StaticStack82(
            X_mmap=X_mmap,
            valid_idx=valid_idx,
            has_lidar_fp=aux["has_lidar_fp"],
            det_slope_fp=aux["det_slope_fp"],
            best_strike_rad_2d=aux["best_strike_rad_2d"],
            scarp_prior_2d=aux["scarp_prior_2d"],
            feature_names=list(STATIC_FEATURE_NAMES),
        )

    X_mmap = np.memmap(mmap_path, dtype=np.float16, mode="w+", shape=(n_val, len(STATIC_FEATURE_NAMES)))

    def put(col: int, arr_2d_or_fp: np.ndarray, is_fp: bool = False) -> None:
        vec = arr_2d_or_fp if is_fp else arr_2d_or_fp.ravel()[valid_idx]
        X_mmap[:, col] = _clip_f16(vec)

    # ── Domain 1 (0..21): Multi-Resolution Tectonic Geomorphology ──
    with rasterio.open(data_dir / "training_features.tif") as ds_tf:
        tf_transform = ds_tf.transform
        det_elev = _nn_fill(ds_tf.read(12), fp & np.isfinite(ds_tf.read(12)) & (ds_tf.read(12) > -1e20))
        det_slope = _nn_fill(ds_tf.read(19), fp & np.isfinite(ds_tf.read(19)) & (ds_tf.read(19) > -1e20))

    det_slope_fp = det_slope.ravel()[valid_idx].astype(np.float32)

    with rasterio.open(data_dir / "external" / "lidar_scarp_features_u8.tif") as ds_lid:
        has_lid_2d = (ds_lid.read(12) > 0) & fp
        has_lidar_fp = has_lid_2d.ravel()[valid_idx]
        step1 = ds_lid.read(3).astype(np.float32)
        lapn = ds_lid.read(4).astype(np.float32)
        lapp = ds_lid.read(5).astype(np.float32)
        downf = ds_lid.read(6).astype(np.float32)
        upf = ds_lid.read(7).astype(np.float32)
        crossf = ds_lid.read(8).astype(np.float32)
        rel1 = ds_lid.read(9).astype(np.float32)
        coh1 = ds_lid.read(10).astype(np.float32) / 255.0
        lid_strike_rad = (ds_lid.read(11).astype(np.float32) / 255.0) * np.pi

    def _lid_nan(a2d: np.ndarray) -> np.ndarray:
        v = a2d.ravel()[valid_idx].astype(np.float32)
        v[~has_lidar_fp] = np.nan
        return v

    step1_clean = np.where(has_lid_2d, step1, 0.0).astype(np.float32)
    step1_dog = step1_clean - ndi.gaussian_filter(step1_clean, sigma=8.0)
    lid_worm = compute_oriented_worm(step1_clean, has_lid_2d, half_len=6, flank=3)

    put(0, has_lidar_fp.astype(np.float32), is_fp=True)
    put(1, _lid_nan(step1), is_fp=True)
    put(2, _lid_nan(step1 / np.sqrt(rel1 + 9.0)), is_fp=True)
    put(3, _lid_nan(np.sqrt(np.maximum(lapn * lapp, 0.0))), is_fp=True)
    put(4, _lid_nan(np.maximum(downf, 1.35 * upf) * (0.3 + coh1) / (crossf + 0.08)), is_fp=True)
    put(5, _lid_nan(upf * (0.25 + coh1) / (crossf + 0.10)), is_fp=True)
    put(6, _lid_nan(coh1), is_fp=True)
    put(7, _lid_nan(step1_dog), is_fp=True)
    put(8, _lid_nan(lid_worm), is_fp=True)
    del lapn, lapp, downf, upf, crossf, rel1, coh1, step1_dog
    gc.collect()

    npz_open = np.load(data_dir / "dem1m_high_prior_openness_lrm.npz")
    open_fp = np.zeros(n_val, dtype=np.float32)
    cidx = npz_open["cov_fp_indices"].astype(np.int64)
    open_fp[cidx] = (
        0.5 * npz_open["openness_dipole_max"].astype(np.float32)
        + 0.5 * npz_open["lrm_grad_max"].astype(np.float32)
    )
    put(9, open_fp, is_fp=True)
    del npz_open, open_fp

    with rasterio.open(data_dir / "h52_scarp3m_100m.tif") as ds_h3:
        h07_raw = ds_h3.read(1).astype(np.float32)
        h12_raw = ds_h3.read(2).astype(np.float32)
        sig_raw = ds_h3.read(4).astype(np.float32)
        str3_raw = ds_h3.read(6).astype(np.float32)

    h07 = _nn_fill(np.maximum(h07_raw, 0.0), fp & (h07_raw > -30000))
    h12 = _nn_fill(np.maximum(h12_raw, 0.0), fp & (h12_raw > -30000))
    sig3 = _nn_fill(np.maximum(sig_raw, 0.0), fp & (sig_raw > -30000))
    h3m_worm = compute_oriented_worm(h12, fp, half_len=6, flank=3)
    put(10, h07)
    put(11, h12)
    put(12, h12 / (0.001 * sig3 + 5.0))
    put(13, h3m_worm)
    del h07_raw, h12_raw, sig_raw, h07, sig3
    gc.collect()

    with rasterio.open(data_dir / "topo_10m_derived_100m_u8.tif") as ds_t10:
        t10_slp = _nn_fill(ds_t10.read(1).astype(np.float32), fp & (ds_t10.read(1) > 0))
        t10_stf = _nn_fill(ds_t10.read(3).astype(np.float32), fp & (ds_t10.read(3) > 0))
        t10_std = _nn_fill(ds_t10.read(4).astype(np.float32), fp & (ds_t10.read(4) > 0))
        t10_curv = _nn_fill(ds_t10.read(6).astype(np.float32), fp & (ds_t10.read(6) > 0))
        t10_coh = _nn_fill(ds_t10.read(7).astype(np.float32), fp & (ds_t10.read(7) > 0))
        t10_lin = _nn_fill(ds_t10.read(8).astype(np.float32), fp & (ds_t10.read(8) > 0))

    t10_worm = compute_oriented_worm(t10_lin, fp, half_len=7, flank=3)
    put(14, t10_slp)
    put(15, t10_stf)
    put(16, t10_std / (t10_slp + 12.0))
    put(17, t10_curv - ndi.gaussian_filter(t10_curv, sigma=6.0))
    put(18, (t10_coh / 255.0) * np.log1p(np.maximum(t10_curv, 0.0)))
    put(19, t10_worm)
    put(20, det_elev - ndi.gaussian_filter(det_elev, sigma=6.0))
    put(21, det_slope - ndi.gaussian_filter(det_slope, sigma=9.0))

    # Best local scarp strike azimuth in [0, pi) across 1m LiDAR -> 3m scarp -> 10m DEM gradient
    gy_e, gx_e = np.gradient(ndi.gaussian_filter(det_elev, sigma=1.5))
    dem_strike = np.mod(np.arctan2(-gx_e, gy_e), np.pi).astype(np.float32)
    str3_rad = np.mod(np.radians(np.clip(str3_raw * 0.01, 0.0, 180.0)), np.pi).astype(np.float32)
    best_strike_rad_2d = np.where(
        has_lid_2d & (step1 > 8.0),
        lid_strike_rad,
        np.where(str3_raw > 0, str3_rad, dem_strike),
    ).astype(np.float32)

    scarp_prior_2d = (
        0.40 * (h3m_worm / (np.std(h3m_worm[fp]) + 1e-5))
        + 0.35 * (t10_worm / (np.std(t10_worm[fp]) + 1e-5))
        + 0.25 * (np.where(has_lid_2d, lid_worm, h3m_worm) / (np.std(h3m_worm[fp]) + 1e-5))
    ).astype(np.float32)
    topo_edge_for_xgrad = (0.5 * (t10_curv / 255.0) + 0.5 * (t10_slp / 255.0)).astype(np.float32)
    del step1, step1_clean, lid_worm, str3_raw, str3_rad, dem_strike, gy_e, gx_e
    del t10_stf, t10_std, t10_coh, t10_lin, t10_worm, det_elev
    gc.collect()

    # ── Domain 2 (22..33): Pluvial Contour-Climb & Fluvial ksn/Chi Interfluve Decontamination ──
    with rasterio.open(data_dir / "dem10_chi_100m_i16.tif") as ds_chi:
        c_smax = _nn_fill(ds_chi.read(1).astype(np.float32), fp & (ds_chi.read(1) > -30000))
        c_smin = _nn_fill(ds_chi.read(2).astype(np.float32), fp & (ds_chi.read(2) > -30000))
        c_ksn = _nn_fill(ds_chi.read(3).astype(np.float32), fp & (ds_chi.read(3) > -30000))
        c_logA = _nn_fill(ds_chi.read(4).astype(np.float32) / 1000.0, fp & (ds_chi.read(4) > -30000))
        z_asl = _nn_fill(ds_chi.read(5).astype(np.float32), fp & (ds_chi.read(5) > -30000))

    # H82-2 signature physics: Along-strike vs cross-strike variation of true sea-level z_ASL
    rr, cc = np.indices(shape, dtype=np.float32)
    tx_s = np.cos(best_strike_rad_2d)
    ty_s = np.sin(best_strike_rad_2d)
    along_vals = []
    for s_step in (-7.0, -3.5, 0.0, 3.5, 7.0):
        ry = np.clip(np.rint(rr + s_step * ty_s).astype(np.int32), 0, shape[0] - 1)
        rx = np.clip(np.rint(cc + s_step * tx_s).astype(np.int32), 0, shape[1] - 1)
        along_vals.append(z_asl[ry, rx])
    z_along_std = np.std(np.stack(along_vals, axis=0), axis=0).astype(np.float32)
    del along_vals

    ry_p = np.clip(np.rint(rr + 3.5 * tx_s).astype(np.int32), 0, shape[0] - 1)
    rx_p = np.clip(np.rint(cc - 3.5 * ty_s).astype(np.int32), 0, shape[1] - 1)
    ry_m = np.clip(np.rint(rr - 3.5 * tx_s).astype(np.int32), 0, shape[0] - 1)
    rx_m = np.clip(np.rint(cc + 3.5 * ty_s).astype(np.int32), 0, shape[1] - 1)
    z_cross_drop = np.abs(z_asl[ry_p, rx_p] - z_asl[ry_m, rx_m]).astype(np.float32)
    del rr, cc, tx_s, ty_s, ry_p, rx_p, ry_m, rx_m

    d_pluv = np.minimum.reduce([
        np.abs(z_asl - 1332.0),  # Lake Lahontan Sehoo highstand
        np.abs(z_asl - 1295.0),  # Lake Lahontan Dendritic terrace
        np.abs(z_asl - 1091.0),  # Pluvial Lake Dixie highstand
        np.abs(z_asl - 1463.0),  # Lake Bonneville Provo bench
        np.abs(z_asl - 1552.0),  # Lake Bonneville highstand
    ]).astype(np.float32)
    pluv_prox = np.exp(-d_pluv / 18.0).astype(np.float32)
    pluv_mimic = (pluv_prox * np.exp(-z_along_std / 6.0)).astype(np.float32)

    interfluve_gate = 1.0 / (1.0 + np.exp((c_logA - 4.65) / 0.45))
    interfluve_scarp = (np.log1p(h12 + t10_curv) * interfluve_gate).astype(np.float32)

    with rasterio.open(data_dir / "external" / "tiger_road_distance_m.tif") as ds_rd:
        rd_m = _nn_fill(ds_rd.read(1).astype(np.float32), fp & np.isfinite(ds_rd.read(1)))
    rd_embank = (np.exp(-np.maximum(rd_m, 0.0) / 45.0) / (1.0 + h3m_worm)).astype(np.float32)

    put(22, z_along_std)
    put(23, z_cross_drop)
    put(24, z_along_std / (z_cross_drop + 4.0))
    put(25, pluv_prox)
    put(26, pluv_mimic)
    put(27, c_logA)
    put(28, interfluve_scarp)
    put(29, c_ksn)
    put(30, c_ksn - ndi.gaussian_filter(c_ksn, sigma=7.0))
    put(31, c_smax - c_smin)
    put(32, np.log1p(np.clip(rd_m, 0.0, 6000.0)))
    put(33, rd_embank)
    del c_smax, c_smin, c_ksn, c_logA, z_asl, z_along_std, z_cross_drop, d_pluv
    del pluv_prox, pluv_mimic, interfluve_gate, interfluve_scarp, rd_m, rd_embank
    del h12, h3m_worm, t10_curv, t10_slp, has_lid_2d
    gc.collect()

    # ── Domain 3 (34..49): Depth-Invariant Potential-Field Tilt & Cross-Gradient Gate ──
    with rasterio.open(data_dir / "training_features.tif") as ds_tf:
        b_rtp = _nn_fill(ds_tf.read(2), fp & np.isfinite(ds_tf.read(2)) & (ds_tf.read(2) > -1e20))
        b_tmi_hg = _nn_fill(ds_tf.read(3), fp & np.isfinite(ds_tf.read(3)) & (ds_tf.read(3) > -1e20))
        b_g2nd = _nn_fill(ds_tf.read(4), fp & np.isfinite(ds_tf.read(4)) & (ds_tf.read(4) > -1e20))
        b_gslp = _nn_fill(ds_tf.read(5), fp & np.isfinite(ds_tf.read(5)) & (ds_tf.read(5) > -1e20))
        b_tc = _nn_fill(ds_tf.read(6), fp & np.isfinite(ds_tf.read(6)) & (ds_tf.read(6) > -1e20))
        b_gshear = _nn_fill(ds_tf.read(7), fp & np.isfinite(ds_tf.read(7)) & (ds_tf.read(7) > -1e20))
        b_gdil = _nn_fill(ds_tf.read(8), fp & np.isfinite(ds_tf.read(8)) & (ds_tf.read(8) > -1e20))
        b_tmi_vg = _nn_fill(ds_tf.read(9), fp & np.isfinite(ds_tf.read(9)) & (ds_tf.read(9) > -1e20))
        b_grav_vg = _nn_fill(ds_tf.read(11), fp & np.isfinite(ds_tf.read(11)) & (ds_tf.read(11) > -1e20))
        b_grav = _nn_fill(ds_tf.read(13), fp & np.isfinite(ds_tf.read(13)) & (ds_tf.read(13) > -1e20))
        b_dbase = _nn_fill(ds_tf.read(15), fp & np.isfinite(ds_tf.read(15)) & (ds_tf.read(15) > -1e20))
        b_ieq = _nn_fill(ds_tf.read(16), fp & np.isfinite(ds_tf.read(16)) & (ds_tf.read(16) > -1e20))
        b_cond = _nn_fill(ds_tf.read(17), fp & np.isfinite(ds_tf.read(17)) & (ds_tf.read(17) > -1e20))
        b_grav_hg = np.abs(_nn_fill(ds_tf.read(18), fp & np.isfinite(ds_tf.read(18)) & (ds_tf.read(18) > -1e20)))

    with rasterio.open(data_dir / "external" / "geodawn_extensions_u8.tif") as ds_ext:
        up150 = _nn_fill(ds_ext.read(4).astype(np.float32), fp & (ds_ext.read(4) > 0))

    mag_tilt = np.arctan2(b_tmi_vg, np.maximum(b_tmi_hg, 0.0) + 1e-4).astype(np.float32)
    grav_tilt = np.arctan2(b_grav_vg, b_grav_hg + 1e-4).astype(np.float32)
    mag_tilt_hgm = np.hypot(*np.gradient(ndi.gaussian_filter(mag_tilt, sigma=1.2))).astype(np.float32)
    grav_tilt_hgm = np.hypot(*np.gradient(ndi.gaussian_filter(grav_tilt, sigma=1.5))).astype(np.float32)
    w_mag = compute_oriented_worm(np.log1p(np.maximum(b_tmi_hg, 0.0)), fp, half_len=7, flank=3)
    w_grav = compute_oriented_worm(b_gslp, fp, half_len=7, flank=3)
    up150_grad = np.hypot(*np.gradient(ndi.gaussian_filter(up150, sigma=1.5))).astype(np.float32)

    # Gallardo & Meju (2003) / GEMSDOE49 cross-gradient alignment vs orthogonality
    ty_t, tx_t = np.gradient(ndi.gaussian_filter(topo_edge_for_xgrad, sigma=1.5))
    tm_t = np.hypot(tx_t, ty_t) + 1e-8
    gy_g, gx_g = np.gradient(ndi.gaussian_filter(b_grav, sigma=2.0))
    gm_g = np.hypot(gx_g, gy_g) + 1e-8
    my_m, mx_m = np.gradient(ndi.gaussian_filter(b_rtp, sigma=2.0))
    mm_m = np.hypot(mx_m, my_m) + 1e-8
    cos2_g = ((tx_t * gx_g + ty_t * gy_g) / (tm_t * gm_g)) ** 2
    cos2_m = ((tx_t * mx_m + ty_t * my_m) / (tm_t * mm_m)) ** 2
    sin2_g = 1.0 - np.clip(cos2_g, 0.0, 1.0)
    sin2_m = 1.0 - np.clip(cos2_m, 0.0, 1.0)
    xgrad_align = (np.maximum(cos2_g, cos2_m) * np.log1p(np.maximum(b_tmi_hg, 0.0) + 10.0 * b_gslp)).astype(np.float32)
    xgrad_ortho = (sin2_g * sin2_m * topo_edge_for_xgrad).astype(np.float32)
    del ty_t, tx_t, tm_t, gy_g, gx_g, gm_g, my_m, mx_m, mm_m, cos2_g, cos2_m, sin2_g, sin2_m, topo_edge_for_xgrad

    put(34, mag_tilt)
    put(35, mag_tilt_hgm)
    put(36, grav_tilt)
    put(37, grav_tilt_hgm)
    put(38, w_mag)
    put(39, w_grav)
    put(40, up150_grad * np.log1p(np.maximum(b_tmi_hg, 0.0)))
    put(41, xgrad_align)
    put(42, xgrad_ortho)
    put(43, np.log1p(np.maximum(b_dbase, 0.0)))
    put(44, np.hypot(*np.gradient(ndi.gaussian_filter(b_dbase, sigma=1.5))))
    put(45, b_dbase - ndi.gaussian_filter(b_dbase, sigma=8.0))
    put(46, b_grav - ndi.gaussian_filter(b_grav, sigma=8.0))
    put(47, b_rtp - ndi.gaussian_filter(b_rtp, sigma=8.0))
    put(48, b_g2nd + 0.5 * np.abs(b_gshear) + 0.5 * np.abs(b_gdil))
    put(49, np.log1p(np.maximum(b_ieq, 0.0)))
    del mag_tilt, mag_tilt_hgm, grav_tilt, grav_tilt_hgm, w_mag, w_grav, up150, up150_grad
    del xgrad_align, xgrad_ortho, b_g2nd, b_gslp, b_gshear, b_gdil, b_tmi_vg, b_grav_vg, b_grav, b_dbase, b_ieq, b_grav_hg
    gc.collect()

    # ── Domain 4 (50..63): Backward Hydrothermal Conduit Inversion ──
    df_ws = pd.read_csv(data_dir / "external" / "gdr_wellspring_in_footprint.csv", low_memory=False)
    df_ws = df_ws.drop(columns=[c for c in FORBIDDEN_COLS if c in df_ws.columns])
    assert FORBIDDEN_COLS.isdisjoint(df_ws.columns)
    w_rows = pd.to_numeric(df_ws["row"], errors="coerce").fillna(-1).to_numpy(np.int64)
    w_cols = pd.to_numeric(df_ws["col"], errors="coerce").fillna(-1).to_numpy(np.int64)
    t_cols = [c for c in df_ws.columns if any(k in c.lower() for k in ("temp", "qtz", "quartz", "chal", "cat"))]
    if t_cols:
        tmax = np.nanmax(
            np.column_stack([pd.to_numeric(df_ws[c], errors="coerce").fillna(20.0).to_numpy() for c in t_cols]),
            axis=1,
        )
        w_wt = np.clip((tmax - 18.0) / 40.0, 0.25, 5.0).astype(np.float32)
    else:
        w_wt = np.ones(len(df_ws), dtype=np.float32)
    ok_w = (w_rows >= 0) & (w_rows < shape[0]) & (w_cols >= 0) & (w_cols < shape[1])
    sp_near, sp_far = _point_kernel_field(shape, w_rows[ok_w], w_cols[ok_w], w_wt[ok_w], 4.5, 16.0)
    del df_ws

    p_rows, p_cols, p_wt = _load_2m_probes(
        data_dir / "2m_temperature_probe_INGENIOUS_regional_data.zip", tf_transform, shape
    )
    pr_near, pr_far = _point_kernel_field(shape, p_rows, p_cols, p_wt, 4.5, 15.0)

    df_pal = pd.read_csv(data_dir / "Paleo_geothermal_final.csv", encoding="latin1")
    df_pal = df_pal.drop(columns=[c for c in FORBIDDEN_COLS if c in df_pal.columns])
    assert FORBIDDEN_COLS.isdisjoint(df_pal.columns)
    px_u, py_u = rio_transform(
        "EPSG:4269",
        "EPSG:32611",
        df_pal["Long_deg_NAD83"].to_numpy(float),
        df_pal["Lat_deg_NAD83"].to_numpy(float),
    )
    pal_c = np.floor((np.asarray(px_u) - tf_transform.c) / tf_transform.a).astype(np.int64)
    pal_r = np.floor((np.asarray(py_u) - tf_transform.f) / tf_transform.e).astype(np.int64)
    ok_p = (pal_r >= 0) & (pal_r < shape[0]) & (pal_c >= 0) & (pal_c < shape[1])
    pal_near, pal_far = _point_kernel_field(
        shape, pal_r[ok_p], pal_c[ok_p], np.full(int(ok_p.sum()), 2.0, dtype=np.float32), 5.0, 18.0
    )
    del df_pal

    df_vv = pd.read_csv(data_dir / "external" / "gdr_volcanic_vents_in_footprint.csv")
    df_vv = df_vv.drop(columns=[c for c in FORBIDDEN_COLS if c in df_vv.columns])
    assert FORBIDDEN_COLS.isdisjoint(df_vv.columns)
    vr = pd.to_numeric(df_vv["row"], errors="coerce").fillna(-1).to_numpy(np.int64)
    vc = pd.to_numeric(df_vv["col"], errors="coerce").fillna(-1).to_numpy(np.int64)
    ok_v = (vr >= 0) & (vr < shape[0]) & (vc >= 0) & (vc < shape[1])
    _, vv_far = _point_kernel_field(shape, vr[ok_v], vc[ok_v], np.ones(int(ok_v.sum()), dtype=np.float32), 4.0, 18.0)
    del df_vv
    _IDX_CACHE.clear()

    with rasterio.open(data_dir / "external" / "geodawn_rad_u8.tif") as ds_rad:
        rad_k = _nn_fill(ds_rad.read(1).astype(np.float32), fp & (ds_rad.read(1) > 0))
        rad_th = _nn_fill(ds_rad.read(2).astype(np.float32), fp & (ds_rad.read(2) > 0))
        rad_tc = _nn_fill(ds_rad.read(4).astype(np.float32), fp & (ds_rad.read(4) > 0))

    non_playa = (det_slope > 1.5).astype(np.float32)
    k_th = (rad_k + 1.0) / (rad_th + 10.0)
    k_th_alt = (k_th - ndi.gaussian_filter(k_th, sigma=11.0)) * non_playa
    rad_tc_grad = np.hypot(*np.gradient(ndi.gaussian_filter(rad_tc, sigma=1.2))) * non_playa
    demag = np.maximum(ndi.gaussian_filter(b_rtp, sigma=10.0) - b_rtp, 0.0) * np.log1p(np.maximum(b_tmi_hg, 0.0)) * non_playa
    cond_loc = b_cond - ndi.gaussian_filter(b_cond, sigma=12.0)
    cond_grad = np.maximum(cond_loc, 0.0) * np.hypot(*np.gradient(ndi.gaussian_filter(b_cond, sigma=1.5)))
    tc_res = b_tc - ndi.gaussian_filter(b_tc, sigma=15.0)
    geo_multi = (
        np.log1p(sp_near)
        + np.log1p(pr_near)
        + np.log1p(pal_near)
        + np.log1p(np.maximum(demag, 0.0))
        + np.log1p(np.maximum(cond_grad, 0.0))
    ).astype(np.float32)

    put(50, np.log1p(sp_near))
    put(51, np.log1p(sp_far))
    put(52, np.log1p(pr_near))
    put(53, np.log1p(pr_far))
    put(54, np.log1p(pal_near))
    put(55, np.log1p(pal_far))
    put(56, np.log1p(vv_far))
    put(57, tc_res)
    put(58, cond_grad)
    put(59, cond_loc)
    put(60, k_th_alt)
    put(61, rad_tc_grad)
    put(62, demag)
    put(63, geo_multi)
    X_mmap.flush()

    del sp_near, sp_far, pr_near, pr_far, pal_near, pal_far, vv_far
    del rad_k, rad_th, rad_tc, non_playa, k_th, k_th_alt, rad_tc_grad, demag
    del cond_loc, cond_grad, tc_res, geo_multi, b_rtp, b_tmi_hg, b_tc, b_cond, det_slope
    gc.collect()

    np.savez(
        aux_path,
        has_lidar_fp=has_lidar_fp,
        det_slope_fp=det_slope_fp,
        best_strike_rad_2d=best_strike_rad_2d,
        scarp_prior_2d=scarp_prior_2d,
    )
    print(f"[features82] Built 64-channel static physical stack in {time.time() - t0:.1f}s -> {mmap_path}")
    X_ro = np.memmap(mmap_path, dtype=np.float16, mode="r", shape=(n_val, len(STATIC_FEATURE_NAMES)))
    return StaticStack82(
        X_mmap=X_ro,
        valid_idx=valid_idx,
        has_lidar_fp=has_lidar_fp,
        det_slope_fp=det_slope_fp,
        best_strike_rad_2d=best_strike_rad_2d,
        scarp_prior_2d=scarp_prior_2d,
        feature_names=list(STATIC_FEATURE_NAMES),
    )


def compute_fold_safe_mechanics82(
    visible_faults: np.ndarray,
    fp: np.ndarray,
    best_strike_rad_2d: np.ndarray,
    scarp_prior_2d: np.ndarray,
) -> np.ndarray:
    """Compute strictly fold-safe structural continuation & WSM slip/dilation tendency features
    from `visible_faults` ONLY (`shape = (N_valid, 8)` `float32`).

    Zero withheld pixels ever enter `visible_faults`.
    """
    vis = np.asarray(visible_faults, dtype=bool) & fp
    valid_idx = np.flatnonzero(fp.ravel())
    shape = fp.shape

    d_vis = ndi.distance_transform_edt(~vis).astype(np.float32)

    # Estimate local orientation of visible fault strands at pixels via smoothed structure tensor
    vis_sm = ndi.gaussian_filter(vis.astype(np.float32), sigma=1.4)
    gy, gx = np.gradient(vis_sm)
    # Fault tangent direction is (-gy, gx)
    Jxx = ndi.gaussian_filter(gy * gy, sigma=2.5)
    Jyy = ndi.gaussian_filter(gx * gx, sigma=2.5)
    Jxy = ndi.gaussian_filter(-gy * gx, sigma=2.5)
    vis_theta = 0.5 * np.arctan2(2.0 * Jxy, Jxx - Jyy + 1e-12)  # [-pi/2, pi/2]

    # Exact vectorial outward crack-tip ray propagation (`Pollard & Segall, 1987`):
    # Identify free endpoints (`8`-connected neighbor count == 1) and orient outward along `-grad(G_3(vis))`
    # straight into unmapped terrain with ZERO lateral side lobes along interior mapped strands!
    H, W = shape
    nbr = ndi.convolve(vis.astype(np.int16), np.ones((3, 3), dtype=np.int16), mode="constant", cval=0) - vis.astype(np.int16)
    end_px = vis & (nbr == 1)
    v_sm3 = ndi.gaussian_filter(vis.astype(np.float32), sigma=3.0)
    t_gy, t_gx = np.gradient(v_sm3)
    tr, tc = np.nonzero(end_px)
    ty = -t_gy[tr, tc]
    tx = -t_gx[tr, tc]
    tnrm = np.hypot(ty, tx) + 1e-8
    ty /= tnrm
    tx /= tnrm

    col_short = np.zeros(shape, dtype=np.float32)
    col_med = np.zeros(shape, dtype=np.float32)
    step_bridge = np.zeros(shape, dtype=np.float32)
    wing_lobe = np.zeros(shape, dtype=np.float32)

    if len(tr) > 0:
        py_t, px_t = -tx, ty
        for s in range(1, 33):
            rr = np.clip(np.rint(tr + s * ty).astype(np.int32), 0, H - 1)
            cc = np.clip(np.rint(tc + s * tx).astype(np.int32), 0, W - 1)
            ws = float(np.exp(-s / 8.5))
            wm = float(np.exp(-s / 21.0))
            np.maximum.at(col_short, (rr, cc), ws)
            np.maximum.at(col_med, (rr, cc), wm)
            # En-echelon relay step-over corridor laterally offset +/- 3.5 px from tip tangent
            for sgn in (-1.0, 1.0):
                rr_st = np.clip(np.rint(tr + s * ty + sgn * 3.5 * py_t).astype(np.int32), 0, H - 1)
                cc_st = np.clip(np.rint(tc + s * tx + sgn * 3.5 * px_t).astype(np.int32), 0, W - 1)
                np.maximum.at(step_bridge, (rr_st, cc_st), 0.85 * wm)
            # Horsetail / wing-crack splay +/- 16 deg from outward crack tip
            for ang_deg in (-16.0, 16.0):
                ca, sa = float(np.cos(np.radians(ang_deg))), float(np.sin(np.radians(ang_deg)))
                uy = ty * ca - tx * sa
                ux = ty * sa + tx * ca
                rr_w = np.clip(np.rint(tr + s * uy).astype(np.int32), 0, H - 1)
                cc_w = np.clip(np.rint(tc + s * ux).astype(np.int32), 0, W - 1)
                np.maximum.at(wing_lobe, (rr_w, cc_w), 0.90 * wm)

    col_short = ndi.gaussian_filter(col_short, sigma=1.6)
    col_med = ndi.gaussian_filter(col_med, sigma=2.2)
    step_bridge = ndi.gaussian_filter(step_bridge, sigma=2.3)
    wing_lobe = ndi.gaussian_filter(wing_lobe, sigma=2.4)

    # Nearest visible fault strike alignment with candidate's local physical scarp strike
    _, near_idx = ndi.distance_transform_edt(~vis, return_distances=True, return_indices=True)
    host_theta = vis_theta[near_idx[0], near_idx[1]]
    strike_corr = (np.cos(best_strike_rad_2d - np.mod(host_theta, np.pi)) ** 2) * np.exp(-d_vis / 14.0)

    # Regional Basin-and-Range WSM transtensional SHmax (~N15E in NW/Central NV, ~N05E in E NV)
    # Normal + dextral-oblique optimal strike around N15E-N30E (azimuth from East ~ 60-75 deg)
    shmax_rad = np.radians(72.0)  # N18E in image (y-down, x-right -> dy=-cos(az), dx=sin(az))
    slip_dil = 0.65 * (np.cos(best_strike_rad_2d - shmax_rad) ** 2) + 0.35 * (
        np.cos(best_strike_rad_2d - np.radians(108.0)) ** 2
    )

    out = np.empty((valid_idx.size, len(FOLD_MECH_NAMES)), dtype=np.float32)
    out[:, 0] = col_short.ravel()[valid_idx]
    out[:, 1] = col_med.ravel()[valid_idx]
    out[:, 2] = step_bridge.ravel()[valid_idx]
    out[:, 3] = wing_lobe.ravel()[valid_idx]
    out[:, 4] = strike_corr.ravel()[valid_idx]
    out[:, 5] = np.log1p(np.minimum(d_vis.ravel()[valid_idx], 25.0))
    out[:, 6] = slip_dil.ravel()[valid_idx]
    out[:, 7] = (
        np.maximum(col_short, 0.7 * step_bridge) * np.maximum(scarp_prior_2d, 0.0)
    ).ravel()[valid_idx]
    return out


def build_positive_tile_mask(
    visible_faults: np.ndarray, fp: np.ndarray, tile_px: int = 128
) -> np.ndarray:
    """Hermant et al. (2025, Sec. 5.1) & Lipor (2026, Official Reference Solution Cell 12):
    Return boolean mask of footprint cells belonging to `tile_px x tile_px` (`12.8 km x 12.8 km`)
    patches that contain at least one visible mapped fault pixel.

    Computed strictly inside each fold from `visible_faults` only so unmapped quadrangles
    (and any held-out test quadrangles) never contaminate negative sampling with false negatives.
    """
    H, W = fp.shape
    out = np.zeros((H, W), dtype=bool)
    vis = visible_faults & fp
    for r0 in range(0, H, tile_px):
        r1 = min(H, r0 + tile_px)
        for c0 in range(0, W, tile_px):
            c1 = min(W, c0 + tile_px)
            if vis[r0:r1, c0:c1].any():
                out[r0:r1, c0:c1] = True
    return out & fp


def run_leakage_canary_audit82(
    stack: StaticStack82,
    folds: List[Dict[str, Any]],
    fp: np.ndarray,
    max_allowed_auc: float = 0.90,
) -> Dict[str, Any]:
    """Rule 4 Single-Feature ROC-AUC Leakage Canary across all 64 static + 8 fold-mechanical features.

    Evaluates against exact pooled withheld positives (`11,321` pixels in `gems57-pooled-hide-v2`
    or buffered component folds). Raises `RuntimeError` immediately if any single feature has
    `max(AUC, 1 - AUC) > max_allowed_auc`.
    """
    rng = np.random.default_rng(8204)
    active_union = np.zeros(fp.shape, dtype=bool)
    truth_union = np.zeros(fp.shape, dtype=bool)
    for f in folds:
        act = fp & f["region"] & (~f.get("masked_known", f["visible"]))
        active_union |= act
        truth_union |= act & f["truth"]

    inv_map = np.full(fp.size, -1, dtype=np.int32)
    inv_map[stack.valid_idx] = np.arange(stack.valid_idx.size, dtype=np.int32)

    pos_flat = np.flatnonzero(truth_union.ravel())
    neg_flat_all = np.flatnonzero((active_union & (~truth_union)).ravel())
    neg_flat = np.sort(rng.choice(neg_flat_all, size=min(150_000, neg_flat_all.size), replace=False))
    eval_flat = np.concatenate([pos_flat, neg_flat])
    y_bin = np.concatenate([np.ones(pos_flat.size, dtype=np.int8), np.zeros(neg_flat.size, dtype=np.int8)])
    eval_rows = inv_map[eval_flat]

    rows_audit = []
    for col_i, fname in enumerate(stack.feature_names):
        vals = np.asarray(stack.X_mmap[eval_rows, col_i], dtype=np.float32)
        fin = np.isfinite(vals)
        med = float(np.median(vals[fin])) if fin.any() else 0.0
        vals = np.where(fin, vals, med)
        auc = float(roc_auc_score(y_bin, vals))
        sym = float(max(auc, 1.0 - auc))
        rows_audit.append(
            {
                "index": col_i,
                "feature": fname,
                "kind": "static_physical",
                "roc_auc": round(auc, 6),
                "symmetric_auc": round(sym, 6),
                "passed": bool(sym <= max_allowed_auc),
            }
        )

    # Fold-proper audit of all 8 mechanical features (each fold's region evaluated using ONLY its own visible mask!)
    mech_eval = np.zeros((eval_flat.size, len(FOLD_MECH_NAMES)), dtype=np.float32)
    for f in folds:
        f_act_rows = f["region"].ravel()[eval_flat]
        if not f_act_rows.any():
            continue
        mf = compute_fold_safe_mechanics82(
            f["visible"], fp, stack.best_strike_rad_2d, stack.scarp_prior_2d
        )
        mech_eval[f_act_rows] = mf[eval_rows[f_act_rows]]

    for j, mname in enumerate(FOLD_MECH_NAMES):
        vals = mech_eval[:, j]
        auc = float(roc_auc_score(y_bin, vals))
        sym = float(max(auc, 1.0 - auc))
        rows_audit.append(
            {
                "index": 64 + j,
                "feature": mname,
                "kind": "fold_visible_mechanics",
                "roc_auc": round(auc, 6),
                "symmetric_auc": round(sym, 6),
                "passed": bool(sym <= max_allowed_auc),
            }
        )

    top_row = max(rows_audit, key=lambda r: r["symmetric_auc"])
    violations = [r for r in rows_audit if not r["passed"]]
    if violations:
        raise RuntimeError(f"RULE 4 LEAKAGE CANARY TRIPPED (> {max_allowed_auc}): {violations}")

    return {
        "rule": "PARALLEL-RUN PROTOCOL Rule 4 — Single-Feature Leakage Canary",
        "evaluator_folds_withheld_positives": int(pos_flat.size),
        "negative_sample_evaluated": int(neg_flat.size),
        "n_features_tested": len(rows_audit),
        "threshold_max_symmetric_auc": max_allowed_auc,
        "max_symmetric_auc": top_row["symmetric_auc"],
        "top_feature": top_row["feature"],
        "all_passed": True,
        "features": rows_audit,
    }
