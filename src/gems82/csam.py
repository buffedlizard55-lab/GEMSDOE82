"""H82-CSAM (`GEMSDOE82`) novel geophysical & hydro-mechanical operators,
1D across-strike ridge-crest sharpening, and strictly LOQO cross-fitted ensemble.

All 8 new H82-CSAM channels are 100% label-free and zero-SGMC:
  1. csam_updip_grav_scarp      : 250 m up-dip (-grad B15) advected gravity HGM & tilt-zero x surface deconfounded scarp
  2. csam_updip_mag_scarp       : 250 m up-dip (-grad B15) advected RTP analytic signal & shallow-150m edge x surface scarp
  3. csam_updip_claycap_sinter  : 250 m up-dip (-grad B15) advected MT clay-cap edge x opaline sinter / 2m probe / geothermometer
  4. csam_upgrad_thermal_source : 300 m upslope (+grad z_smooth) hydraulic-head back-advected thermal upflow source (H82-D)
  5. csam_basement_flex_hinge   : Biharmonic thin-plate flexural hinge |lap(lap(B15))| in piedmont/basin regime (H82-E)
  6. csam_chi_divide_diseq      : Cross-branch fluvial chi disequilibrium & ksn contrast across drainage signatures (H82-C)
  7. csam_transtens_valve_index : Critically stressed transtensional shear*dilatation x seismic swarm x geothermometer excess
  8. csam_phase_congruency_edge : Multi-scale (sigma=1.5, 3.0, 6.0 px) potential-field tilt-phase stationarity x K/Th alteration (H82-B)
"""
from __future__ import annotations

import gc
import json
import os
import time
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier

from gems77vds import features as FE, models as MO

CSAM_CHANNEL_NAMES: list[str] = [
    "csam_updip_grav_scarp",
    "csam_updip_mag_scarp",
    "csam_updip_claycap_sinter",
    "csam_upgrad_thermal_source",
    "csam_basement_flex_hinge",
    "csam_chi_divide_diseq",
    "csam_transtens_valve_index",
    "csam_phase_congruency_edge",
]

ALL_STATIC_106_NAMES: list[str] = FE.STATIC_CHANNEL_NAMES + CSAM_CHANNEL_NAMES
ALL_AUDITED_114_NAMES: list[str] = ALL_STATIC_106_NAMES + FE.VISIBLE_CHANNEL_NAMES

FROZEN_CSAM_PARAMS: dict[str, Any] = {
    "pi_scale_ht": 0.25,
    "w_stack_log_odds": 0.70,
    "ridge_sharpen_alpha": 0.22,
    "dinkelbach_pi_true": 0.0023,
    "dinkelbach_temperature": 0.98,
    "dinkelbach_fp_lambda": 0.0115,
    "dinkelbach_min_sep_px": 2.40,
    "dinkelbach_candidate_pool": 680_000,
    "quadrant_calibrate": True,
    "excl_px": 3.0,
    "primary_budget": 41_200,
    "parity_budget": 37_654,
    "sparse_overlap_cap": 0.610,
    "max_sparse_positives": 125_000,
}


def _gf32(a: np.ndarray, sigma: float) -> np.ndarray:
    return ndi.gaussian_filter(np.asarray(a, dtype=np.float32), sigma=sigma, mode="nearest").astype(np.float32)


def _advect_2d(field: np.ndarray, vy: np.ndarray, vx: np.ndarray, step_px: float) -> np.ndarray:
    """Evaluate `field` at `(r + step_px * vy, c + step_px * vx)` via bilinear interpolation.
    Used to project deep hanging-wall anomalies (at `r + step_px * dy_down, c + step_px * dx_down`)
    back up-dip to the surface fault trace `(r, c)`.
    """
    H, W = field.shape
    rr, cc = np.indices((H, W), dtype=np.float32)
    rq = np.clip(rr + np.float32(step_px) * vy, 0.0, float(H - 1))
    cq = np.clip(cc + np.float32(step_px) * vx, 0.0, float(W - 1))
    return ndi.map_coordinates(field, [rq, cq], order=1, mode="nearest").astype(np.float32)


def build_csam8_memmap(root: Path, force: bool = False) -> Path:
    """Compute or verify the 8 novel H82-CSAM physical channels in `.cache/h82_csam/csam8_ch_fp.f32`."""
    os.environ.setdefault("GDAL_CACHEMAX", "64")
    cache_dir = root / ".cache" / "h82_csam"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / "csam8_ch_fp.f32"
    meta_path = cache_dir / "csam8_meta.json"

    bin98_path, aux = FE.build_static_fp_memmap(root, force=False)
    n_fp = int(aux["n_fp"])
    n_csam = len(CSAM_CHANNEL_NAMES)
    expected_bytes = n_fp * n_csam * 4
    if not force and out_path.is_file() and out_path.stat().st_size == expected_bytes and meta_path.is_file():
        return out_path

    t0 = time.time()
    raw_dir = root / "data" / "raw"
    ext_dir = raw_dir / "external"
    with rasterio.open(raw_dir / "sample_submission.tif") as ds:
        foot = np.isfinite(ds.read(1))
    H, W = foot.shape

    def get_static_2d(name: str) -> np.ndarray:
        col = FE.read_static_rows(bin98_path, n_fp, slice(None), [FE.STATIC_IDX[name]])[:, 0]
        arr = np.zeros((H, W), dtype=np.float32)
        arr[foot] = np.nan_to_num(col, nan=0.0, posinf=0.0, neginf=0.0)
        return arr

    # Read official bands needed for dip-vector, biharmonic flexure, and multi-scale phase congruency
    with rasterio.open(raw_dir / "training_features.tif") as tf:
        b_rtp = FE._clean_band(tf.read(2), foot)
        b_tmi_vg = FE._clean_band(tf.read(9), foot)
        b_grav_vg = FE._clean_band(tf.read(11), foot)
        b_det_elev = FE._clean_band(tf.read(12), foot)
        b_iso_grav = FE._clean_band(tf.read(13), foot)
        b_depth_b = FE._clean_band(tf.read(15), foot)
        b_det_slp = FE._clean_band(tf.read(19), foot)

    # Down-dip unit vector (+grad depth_to_basement points from shallow footwall into deep hanging-wall basin)
    db_smooth = _gf32(b_depth_b, 2.0)
    dby, dbx = np.gradient(db_smooth)
    db_mag = np.hypot(dby, dbx) + np.float32(1e-5)
    dy_downdip = (dby / db_mag).astype(np.float32)
    dx_downdip = (dbx / db_mag).astype(np.float32)

    # Surface natural deconfounded scarp composite
    lid_step = get_static_2d("lidar_step_deconf_road_mine")
    lid_val = get_static_2d("lidar_valid_flag") > 0.5
    t10_step = get_static_2d("topo10_onesided_step_deconf")
    rad_scarp = get_static_2d("radon_scarp_max_1p2km")
    surf_scarp = (
        0.50 * np.where(lid_val, FE._rank01_fp(lid_step, lid_val), FE._rank01_fp(t10_step, foot))
        + 0.30 * FE._rank01_fp(t10_step, foot)
        + 0.20 * FE._rank01_fp(rad_scarp, foot)
    ).astype(np.float32)
    del lid_step, lid_val, t10_step, rad_scarp

    # 1. csam_updip_grav_scarp: pull hanging-wall gravity HGM + tilt-zero at +2.5 px down-dip back to surface scarp
    grav_deep = (
        0.55 * FE._rank01_fp(get_static_2d("pot_grav_thdr_log"), foot)
        + 0.45 * FE._rank01_fp(get_static_2d("pot_grav_tilt_zero"), foot)
    ).astype(np.float32)
    grav_updip = _advect_2d(grav_deep, dy_downdip, dx_downdip, step_px=2.5)
    c1_updip_grav = (grav_updip * surf_scarp).astype(np.float32)
    del grav_deep, grav_updip

    # 2. csam_updip_mag_scarp: pull hanging-wall RTP analytic signal + shallow 150m edge at +2.5 px down-dip back to surface scarp
    mag_deep = (
        0.50 * FE._rank01_fp(get_static_2d("pot_mag_as_log"), foot)
        + 0.30 * FE._rank01_fp(get_static_2d("mag_shallow_up150_grad"), foot)
        + 0.20 * FE._rank01_fp(get_static_2d("pot_mag_tilt_zero"), foot)
    ).astype(np.float32)
    mag_updip = _advect_2d(mag_deep, dy_downdip, dx_downdip, step_px=2.5)
    c2_updip_mag = (mag_updip * surf_scarp).astype(np.float32)
    del mag_deep, mag_updip

    # 3. csam_updip_claycap_sinter: pull hanging-wall MT clay-cap gradient + demag conduit back to surface thermal/sinter
    clay_deep = (
        0.55 * FE._rank01_fp(get_static_2d("hydro_claycap_grad"), foot)
        + 0.45 * FE._rank01_fp(get_static_2d("hydro_demag_conduit_deconf"), foot)
    ).astype(np.float32)
    clay_updip = _advect_2d(clay_deep, dy_downdip, dx_downdip, step_px=2.5)
    hydro_surf = (
        0.35 * FE._rank01_fp(get_static_2d("hydro_geotherm_diseq_s5"), foot)
        + 0.30 * FE._rank01_fp(get_static_2d("hydro_probe2m_dab_s3"), foot)
        + 0.20 * FE._rank01_fp(get_static_2d("hydro_paleo_sinter_s4"), foot)
        + 0.15 * FE._rank01_fp(get_static_2d("hydro_temp_excess_s4"), foot)
    ).astype(np.float32)
    c3_updip_clay = (clay_updip * (0.60 * hydro_surf + 0.40 * surf_scarp)).astype(np.float32)
    del clay_deep, clay_updip, dy_downdip, dx_downdip

    # 4. csam_upgrad_thermal_source (H82-D): upslope hydraulic-head back-advection of outflow thermal plumes
    # Down-slope outflows sit at (-grad z_smooth); at a range-front feeder fault (r, c), its outflow sits at
    # (r - 3.0 * u_upslope_y, c - 3.0 * u_upslope_x), so sampling downslope thermal excess and gating by
    # range-front scarp/basement edge recovers the concealed range-front upflow conduit!
    z_hyd = _gf32(b_det_elev, 4.0)
    zhy, zhx = np.gradient(z_hyd)
    zh_mag = np.hypot(zhy, zhx) + np.float32(1e-5)
    dy_downslope = (-zhy / zh_mag).astype(np.float32)
    dx_downslope = (-zhx / zh_mag).astype(np.float32)
    outflow_plume = _advect_2d(hydro_surf, dy_downslope, dx_downslope, step_px=3.0)
    base_edge = FE._rank01_fp(get_static_2d("pot_base_grad_log"), foot)
    c4_upgrad_thermal = (outflow_plume * (0.55 * surf_scarp + 0.45 * base_edge)).astype(np.float32)
    del z_hyd, zhy, zhx, zh_mag, dy_downslope, dx_downslope, outflow_plume, hydro_surf

    # 5. csam_basement_flex_hinge (H82-E): biharmonic thin-plate flexural curvature |lap(lap(B15))| in piedmont/basin
    lap1 = ndi.laplace(db_smooth).astype(np.float32)
    biharm = np.abs(ndi.laplace(_gf32(lap1, 1.5))).astype(np.float32)
    slp_rank = FE._rank01_fp(b_det_slp, foot)
    pied_weight = np.exp(-np.maximum(slp_rank - np.float32(0.72), np.float32(0.0)) * np.float32(4.0)).astype(np.float32)
    c5_flex_hinge = (FE._rank01_fp(np.log1p(biharm), foot) * pied_weight * (0.5 + 0.5 * base_edge)).astype(np.float32)
    del lap1, biharm, db_smooth, b_depth_b, b_det_elev, b_det_slp

    # 6. csam_chi_divide_diseq (H82-C): cross-branch fluvial chi contrast across tributary drainage divides
    with rasterio.open(ext_dir / "dem10_chi_100m_i16.tif") as ds:
        chi_smax = ds.read(1).astype(np.float32) / np.float32(1000.0)
    chi_smax = FE._clean_band(np.where(chi_smax > -30.0, chi_smax, np.nan), foot)
    chi_local_range = (
        ndi.maximum_filter(chi_smax, size=3, mode="nearest")
        - ndi.minimum_filter(chi_smax, size=3, mode="nearest")
    ).astype(np.float32)
    bjump = get_static_2d("chi_branch_jump_s1")
    ksn_n = FE._rank01_fp(get_static_2d("chi_ksn_norm"), foot)
    c6_chi_diseq = (FE._rank01_fp(chi_local_range, foot) * (0.55 * bjump + 0.45 * ksn_n) * surf_scarp).astype(np.float32)
    del chi_smax, chi_local_range, bjump, ksn_n

    # 7. csam_transtens_valve_index: transtensional obliquity sqrt(r(shear)*r(dilat)) x seismic swarm x geothermometer diseq
    r_shr = FE._rank01_fp(get_static_2d("raw_geod_shear"), foot)
    r_dil = FE._rank01_fp(get_static_2d("raw_geod_dilat"), foot)
    r_swm = FE._rank01_fp(get_static_2d("seism_swarm_ridge_s2"), foot)
    r_gdq = FE._rank01_fp(get_static_2d("hydro_geotherm_diseq_s14"), foot)
    c7_transtens = (np.sqrt(r_shr * r_dil) * (0.45 * r_swm + 0.35 * r_gdq + 0.20 * surf_scarp)).astype(np.float32)
    del r_shr, r_dil, r_swm, r_gdq, surf_scarp, base_edge

    # 8. csam_phase_congruency_edge (H82-B): multi-scale (sigma=1.5, 3.0, 6.0) potential-field tilt-phase stationarity x K/Th
    cos_sum_m = np.zeros((H, W), dtype=np.float32)
    sin_sum_m = np.zeros((H, W), dtype=np.float32)
    cos_sum_g = np.zeros((H, W), dtype=np.float32)
    sin_sum_g = np.zeros((H, W), dtype=np.float32)
    for sig in (1.5, 3.0, 6.0):
        m_s = _gf32(b_rtp, sig)
        mv_s = _gf32(b_tmi_vg, sig)
        mgy, mgx = np.gradient(m_s)
        mh = np.hypot(mgy, mgx) + np.float32(1e-4)
        phi_m = np.arctan2(mv_s, mh)
        cos_sum_m += np.cos(phi_m).astype(np.float32)
        sin_sum_m += np.sin(phi_m).astype(np.float32)

        g_s = _gf32(b_iso_grav, sig)
        gv_s = _gf32(b_grav_vg, sig)
        ggy, ggx = np.gradient(g_s)
        gh = np.hypot(ggy, ggx) + np.float32(1e-5)
        phi_g = np.arctan2(gv_s, gh)
        cos_sum_g += np.cos(phi_g).astype(np.float32)
        sin_sum_g += np.sin(phi_g).astype(np.float32)

    # Phase coherence across scales (1/3 * resultant length) weighted by zero-tilt proximity (cos(mean_phi))
    pc_m = (np.hypot(cos_sum_m, sin_sum_m) / np.float32(3.0)) * np.maximum(cos_sum_m / (np.hypot(cos_sum_m, sin_sum_m) + 1e-5), 0.0)
    pc_g = (np.hypot(cos_sum_g, sin_sum_g) / np.float32(3.0)) * np.maximum(cos_sum_g / (np.hypot(cos_sum_g, sin_sum_g) + 1e-5), 0.0)
    kth_blk = get_static_2d("blk_std_kth_ratio")
    ky, kx = np.gradient(_gf32(kth_blk, 1.5))
    k_edge = FE._rank01_fp(np.hypot(ky, kx), foot)
    c8_phase_cong = ((0.45 * pc_m + 0.45 * pc_g) * (0.65 + 0.35 * k_edge)).astype(np.float32)
    del b_rtp, b_tmi_vg, b_grav_vg, b_iso_grav, cos_sum_m, sin_sum_m, cos_sum_g, sin_sum_g, pc_m, pc_g, kth_blk, ky, kx, k_edge

    channels_2d = [
        c1_updip_grav,
        c2_updip_mag,
        c3_updip_clay,
        c4_upgrad_thermal,
        c5_flex_hinge,
        c6_chi_diseq,
        c7_transtens,
        c8_phase_cong,
    ]
    stride_bytes = n_fp * 4
    with open(out_path, "wb") as fh:
        for ch2d in channels_2d:
            vec = np.ascontiguousarray(ch2d[foot], dtype=np.float32)
            fh.write(vec.tobytes())
        fh.flush()

    meta_path.write_text(
        json.dumps(
            {
                "n_footprint": n_fp,
                "n_channels": n_csam,
                "channels": CSAM_CHANNEL_NAMES,
                "sgmc_channels_used": 0,
                "build_seconds": round(time.time() - t0, 2),
            },
            indent=2,
        )
        + "\n"
    )
    gc.collect()
    return out_path


def read_csam8_rows(csam_path: Path, n_fp: int, row_idx: np.ndarray | slice) -> np.ndarray:
    """Sequential reader for `(8, n_fp)` channel-major float32 store."""
    n_rows = len(range(*row_idx.indices(n_fp))) if isinstance(row_idx, slice) else int(len(row_idx))
    out = np.empty((n_rows, len(CSAM_CHANNEL_NAMES)), dtype=np.float32)
    stride_bytes = int(n_fp) * 4
    with open(csam_path, "rb") as fh:
        for j in range(len(CSAM_CHANNEL_NAMES)):
            fh.seek(j * stride_bytes)
            buf = np.fromfile(fh, dtype=np.float32, count=n_fp)
            out[:, j] = buf[row_idx]
    return out


def load_scaled_f16_106_matrix(root: Path) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Load all 106 static channels (98 base + 8 H82-CSAM) into a single `(n_fp, 106)` float16 matrix (~1.04 GiB)."""
    bin98_path, aux = FE.build_static_fp_memmap(root, force=False)
    csam8_path = build_csam8_memmap(root, force=False)
    n_fp = int(aux["n_fp"])
    n_base = len(FE.STATIC_CHANNEL_NAMES)
    n_csam = len(CSAM_CHANNEL_NAMES)
    X16 = np.empty((n_fp, n_base + n_csam), dtype=np.float16)
    stride_bytes = n_fp * 4

    with open(bin98_path, "rb") as fh:
        for c in range(n_base):
            fh.seek(c * stride_bytes)
            col = np.fromfile(fh, dtype=np.float32, count=n_fp)
            fin = np.isfinite(col)
            if int(fin.sum()) > 16:
                sub = col[fin][::16]
                q25, q50, q75 = np.percentile(sub, [25.0, 50.0, 75.0])
                scale = max(float(q75 - q25), float(np.std(sub)), 1e-12)
                norm = np.where(fin, np.clip((col - np.float32(q50)) / np.float32(scale), -2048.0, 2048.0), np.nan)
            else:
                norm = np.where(fin, np.clip(col, -2048.0, 2048.0), np.nan)
            X16[:, c] = norm.astype(np.float16)
            del col, fin, norm
        if hasattr(os, "posix_fadvise") and hasattr(os, "POSIX_FADV_DONTNEED"):
            os.posix_fadvise(fh.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)

    with open(csam8_path, "rb") as fh:
        for c in range(n_csam):
            fh.seek(c * stride_bytes)
            col = np.fromfile(fh, dtype=np.float32, count=n_fp)
            fin = np.isfinite(col)
            if int(fin.sum()) > 16:
                sub = col[fin][::16]
                q25, q50, q75 = np.percentile(sub, [25.0, 50.0, 75.0])
                scale = max(float(q75 - q25), float(np.std(sub)), 1e-12)
                norm = np.where(fin, np.clip((col - np.float32(q50)) / np.float32(scale), -2048.0, 2048.0), np.nan)
            else:
                norm = np.where(fin, np.clip(col, -2048.0, 2048.0), np.nan)
            X16[:, n_base + c] = norm.astype(np.float16)
            del col, fin, norm
        if hasattr(os, "posix_fadvise") and hasattr(os, "POSIX_FADV_DONTNEED"):
            os.posix_fadvise(fh.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)

    MO.free_ram()
    return X16, aux


def anisotropic_ridge_sharpen(p_surf: np.ndarray, foot: np.ndarray, alpha: float = 0.22) -> np.ndarray:
    """Fold-clean 1D ridge-crest concentration in log-odds space.

    Enhances pixels that are local 1D ridge maxima (largest negative principal curvature
    -lambda_min of the smoothed posterior surface) while mildly damping off-crest flank shoulders,
    preventing diffuse 2D mountain-blob false positives without hard-threshold zeroing.
    """
    if alpha <= 0.0:
        return p_surf
    p_clip = np.clip(p_surf.astype(np.float32), 1e-6, 1.0 - 1e-6)
    logit = np.where(foot, np.log(p_clip / (1.0 - p_clip)), -12.0).astype(np.float32)
    s = _gf32(p_clip, 1.15)
    gy, gx = np.gradient(s)
    gyy, gyx = np.gradient(gy)
    gxy, gxx = np.gradient(gx)
    b = 0.5 * (gxy + gyx)
    tr = gxx + gyy
    det = np.sqrt(np.maximum(0.25 * (gxx - gyy) ** 2 + b * b, np.float32(0.0)))
    lam_min = 0.5 * tr - det
    ridge_pos = np.maximum(-lam_min, np.float32(0.0))
    mx3 = ndi.maximum_filter(p_clip, size=3, mode="nearest")
    crest_ratio = (p_clip / (mx3 + np.float32(1e-6))).astype(np.float32)
    r_rank = FE._rank01_fp(ridge_pos, foot)
    delta_logit = np.float32(alpha) * (r_rank * crest_ratio - np.float32(0.35) * (np.float32(1.0) - crest_ratio))
    out = np.zeros_like(p_surf, dtype=np.float32)
    out[foot] = (1.0 / (1.0 + np.exp(-(logit[foot] + delta_logit[foot])))).astype(np.float32)
    return out


def _build_csam_interactions(p_phys_vec: np.ndarray, V_mat: np.ndarray, X_csam_sub: np.ndarray) -> np.ndarray:
    """Construct 8 geomechanical x H82-CSAM interaction columns (`shape = (N, 8)` float32)."""
    p = np.clip(p_phys_vec.astype(np.float32), 1e-6, 1.0 - 1e-6)
    logit_p = np.log(p / (1.0 - p)).astype(np.float32)
    d_approx = np.expm1(np.maximum(V_mat[:, 0], 0.0))
    corridor = np.exp(-d_approx / np.float32(18.0)).astype(np.float32)
    blind = (np.float32(1.0) - np.exp(-d_approx / np.float32(22.0))).astype(np.float32)
    updip_sum = np.nan_to_num(X_csam_sub[:, 0], nan=0.0) + np.nan_to_num(X_csam_sub[:, 1], nan=0.0)
    hydro_up = np.nan_to_num(X_csam_sub[:, 2], nan=0.0) + np.nan_to_num(X_csam_sub[:, 3], nan=0.0)
    return np.column_stack(
        [
            logit_p,
            p * V_mat[:, 5],        # physical scarp inside Pollard-Segall crack-tip cone
            p * V_mat[:, 6],        # physical scarp parallel to strike
            p * V_mat[:, 4],        # physical bridge inside relay-ramp step-over
            p * corridor,           # near-network continuation coupling
            p * blind,              # detached blind-basin fault coupling
            p * updip_sum,          # posterior x up-dip advected gravity/magnetic scarp
            p * hydro_up,           # posterior x up-dip clay-cap & upslope thermal source
        ]
    ).astype(np.float32)


def fit_predict_csam_loqo(
    X16_106: np.ndarray,
    vis_full_fp: np.ndarray,
    folds: list[dict],
    visible: np.ndarray,
    foot: np.ndarray,
    slope_2d: np.ndarray,
    aux: dict,
    fp_lut: np.ndarray,
    seed: int = 8200,
    cache_path: Path | None = None,
    eval_base98: bool = True,
) -> dict[str, np.ndarray]:
    """Strictly Leave-One-Quadrant-Out (LOQO) 4-quadrant fitting & prediction on 106 static
    + 8 fold-visible + 8 CSAM-geomechanical interaction channels (`peak RSS < 2.40 GiB`).
    Also returns the base 98-channel physical LOQO prediction for strictly nested ablation in E1.
    """
    if cache_path is not None and Path(cache_path).is_file():
        z = np.load(cache_path)
        return {
            k: z[k].astype(np.float32)
            for k in ("phys98_ens", "phys106_ens", "stack114_ens", "csam_raw", "csam_sharpened")
        }

    H, W = foot.shape
    n_fp = X16_106.shape[0]
    rng = np.random.default_rng(seed)

    phys98_ens = np.zeros((H, W), dtype=np.float32)
    phys106_ens = np.zeros((H, W), dtype=np.float32)
    stack114_ens = np.zeros((H, W), dtype=np.float32)

    quad_fp = [fp_lut[np.flatnonzero(folds[q]["region"] & foot)] for q in range(4)]

    # Pre-fit the C(4, 2) = 6 two-quadrant 106-ch physical models ONCE for inner OOF stacking
    pair_quad_pred: dict[tuple[tuple[int, int], int], np.ndarray] = {}
    for a_q in range(4):
        for b_q in range(a_q + 1, 4):
            sub_reg = folds[a_q]["region"] | folds[b_q]["region"]
            v_sub = visible & sub_reg
            d_sub = ndi.distance_transform_edt(~v_sub).astype(np.float32)
            i_sub, y_sub, w_sub = MO.sample_ht_strata(
                v_sub & foot,
                sub_reg & foot & (~v_sub) & (d_sub > 3.0),
                d_sub,
                slope_2d,
                fp_lut,
                rng,
                max_pos=30_000,
                max_h=30_000,
                max_s=30_000,
                max_b=20_000,
                pi_scale=FROZEN_CSAM_PARAMS["pi_scale_ht"],
            )
            X_sub = X16_106[i_sub].astype(np.float32)
            clf_p = lgb.LGBMClassifier(**MO.LGB_KW).fit(X_sub, y_sub, sample_weight=w_sub)
            del X_sub, y_sub, w_sub
            for q in range(4):
                if q not in (a_q, b_q):
                    q_fp = quad_fp[q]
                    pr = np.empty(q_fp.size, dtype=np.float32)
                    for s0 in range(0, q_fp.size, 200_000):
                        s1 = min(q_fp.size, s0 + 200_000)
                        Xb = X16_106[q_fp[s0:s1]].astype(np.float32)
                        pr[s0:s1] = np.clip(clf_p.predict_proba(Xb)[:, 1], 1e-6, 1.0 - 1e-6).astype(np.float32)
                        del Xb
                    pair_quad_pred[((a_q, b_q), q)] = pr
            del clf_p
    MO.free_ram()

    lgb_kw2 = {
        **MO.LGB_KW,
        "n_estimators": 210,
        "learning_rate": 0.055,
        "num_leaves": 35,
        "min_child_samples": 75,
        "colsample_bytree": 0.78,
        "reg_alpha": 2.5,
        "reg_lambda": 6.0,
        "random_state": 8209,
    }
    hgb_fast_kw = {
        **MO.HGB_KW,
        "max_iter": 70,
        "max_bins": 127,
        "learning_rate": 0.095,
        "max_leaf_nodes": 45,
    }

    for k, fold in enumerate(folds):
        t_k = time.time()
        other_js = [j for j in range(4) if j != k]
        tr_reg = np.zeros((H, W), dtype=bool)
        for j in other_js:
            tr_reg |= folds[j]["region"]

        vis_tr = visible & tr_reg
        d_tr = ndi.distance_transform_edt(~vis_tr).astype(np.float32)
        idx_p, y_p, w_p = MO.sample_ht_strata(
            vis_tr & foot,
            tr_reg & foot & (~vis_tr) & (d_tr > 3.0),
            d_tr,
            slope_2d,
            fp_lut,
            rng,
            pi_scale=FROZEN_CSAM_PARAMS["pi_scale_ht"],
        )
        Xp106 = X16_106[idx_p].astype(np.float32)
        te_mask = fold["region"] & foot
        te_fp = quad_fp[k]

        # Fit base-98 physical ensemble on held-in quadrants `tr_reg` when requested
        if eval_base98:
            c98_1 = lgb.LGBMClassifier(**MO.LGB_KW).fit(Xp106[:, :98], y_p, sample_weight=w_p)
            c98_2 = lgb.LGBMClassifier(**lgb_kw2).fit(Xp106[:, :98], y_p, sample_weight=w_p)
            p98_e = np.empty(te_fp.size, dtype=np.float32)
            for s0 in range(0, te_fp.size, 200_000):
                s1 = min(te_fp.size, s0 + 200_000)
                Xb98 = X16_106[te_fp[s0:s1], :98].astype(np.float32)
                q98_1 = np.clip(c98_1.predict_proba(Xb98)[:, 1], 1e-6, 1.0 - 1e-6)
                q98_2 = np.clip(c98_2.predict_proba(Xb98)[:, 1], 1e-6, 1.0 - 1e-6)
                lo98 = 0.5 * np.log(q98_1 / (1.0 - q98_1)) + 0.5 * np.log(q98_2 / (1.0 - q98_2))
                p98_e[s0:s1] = (1.0 / (1.0 + np.exp(-lo98))).astype(np.float32)
                del Xb98
            phys98_ens[te_mask] = p98_e
            del p98_e, c98_1, c98_2
            MO.free_ram()

        # Fit CSAM-106 physical ensemble on held-in quadrants `tr_reg` and immediately free models
        c106_1 = lgb.LGBMClassifier(**MO.LGB_KW).fit(Xp106, y_p, sample_weight=w_p)
        c106_2 = lgb.LGBMClassifier(**lgb_kw2).fit(Xp106, y_p, sample_weight=w_p)
        del Xp106, y_p, w_p
        MO.free_ram()

        p106_e = np.empty(te_fp.size, dtype=np.float32)
        for s0 in range(0, te_fp.size, 200_000):
            s1 = min(te_fp.size, s0 + 200_000)
            Xb106 = X16_106[te_fp[s0:s1]].astype(np.float32)
            q106_1 = np.clip(c106_1.predict_proba(Xb106)[:, 1], 1e-6, 1.0 - 1e-6)
            q106_2 = np.clip(c106_2.predict_proba(Xb106)[:, 1], 1e-6, 1.0 - 1e-6)
            lo106 = 0.5 * np.log(q106_1 / (1.0 - q106_1)) + 0.5 * np.log(q106_2 / (1.0 - q106_2))
            p106_e[s0:s1] = (1.0 / (1.0 + np.exp(-lo106))).astype(np.float32)
            del Xb106
        phys106_ens[te_mask] = p106_e
        del c106_1, c106_2
        MO.free_ram()

        # Inner out-of-quadrant physical prediction on `other_js`
        p_phys_inner_fp = np.zeros(n_fp, dtype=np.float32)
        for j_val in other_js:
            rem_pair = tuple(sorted(m for m in other_js if m != j_val))
            p_phys_inner_fp[quad_fp[j_val]] = pair_quad_pred[(rem_pair, j_val)]

        # Inner 2-split buffered whole-component cross-fitting for 122-ch structural + CSAM stacker
        comp, n_comp = ndi.label(vis_tr, MO.STRUCT8)
        perm = rng.permutation(np.arange(1, n_comp + 1))
        groups = np.array_split(perm, 2)

        X_parts, y_parts, w_parts = [], [], []
        for g_ids in groups:
            hold_c = np.isin(comp, g_ids) & vis_tr
            collar_c = ndi.distance_transform_edt(~hold_c) <= 3.0
            ctx_m = vis_tr & (~collar_c)
            d_ctx = ndi.distance_transform_edt(~ctx_m).astype(np.float32)

            idx_m, y_m, w_m = MO.sample_ht_strata(
                hold_c & foot & (d_ctx > 3.0),
                tr_reg & foot & (~vis_tr) & (d_ctx > 3.0),
                d_ctx,
                slope_2d,
                fp_lut,
                rng,
                max_pos=22_000,
                max_h=24_000,
                max_s=24_000,
                max_b=16_000,
                pi_scale=FROZEN_CSAM_PARAMS["pi_scale_ht"],
            )
            Vm_fp = FE.compute_visible_structural_fp(
                ctx_m, foot, aux["u2_dir"], aux["v2_dir"], aux["geod_rank"]
            )
            Vm_sub = Vm_fp[idx_m]
            X_sub106 = X16_106[idx_m].astype(np.float32)
            inter_sub = _build_csam_interactions(p_phys_inner_fp[idx_m], Vm_sub, X_sub106[:, 98:106])
            Xm = np.empty((idx_m.size, 122), dtype=np.float32)
            Xm[:, :106] = X_sub106
            Xm[:, 106:114] = Vm_sub
            Xm[:, 114:122] = inter_sub
            X_parts.append(Xm)
            y_parts.append(y_m)
            w_parts.append(w_m)
            del Vm_fp, Vm_sub, X_sub106, inter_sub
            MO.free_ram()

        del p_phys_inner_fp
        X_st = np.vstack(X_parts)
        y_st = np.concatenate(y_parts)
        w_st = np.concatenate(w_parts)
        w_st *= float(w_st.size) / float(w_st.sum())
        del X_parts, y_parts, w_parts
        MO.free_ram()

        c_shgb = HistGradientBoostingClassifier(**hgb_fast_kw).fit(X_st, y_st, sample_weight=w_st)
        c_slgb = lgb.LGBMClassifier(**MO.LGB_KW).fit(X_st, y_st, sample_weight=w_st)
        del X_st, y_st, w_st
        MO.free_ram()

        she = np.empty(te_fp.size, dtype=np.float32)
        Xb = np.empty((150_000, 122), dtype=np.float32)
        for s0 in range(0, te_fp.size, 150_000):
            s1 = min(te_fp.size, s0 + 150_000)
            nb = s1 - s0
            V_chunk = vis_full_fp[te_fp[s0:s1]]
            X_c106 = X16_106[te_fp[s0:s1]].astype(np.float32)
            inter_chunk = _build_csam_interactions(p106_e[s0:s1], V_chunk, X_c106[:, 98:106])
            sub_X = Xb[:nb]
            sub_X[:, :106] = X_c106
            sub_X[:, 106:114] = V_chunk
            sub_X[:, 114:122] = inter_chunk
            q1 = np.clip(c_shgb.predict_proba(sub_X)[:, 1], 1e-6, 1.0 - 1e-6)
            q2 = np.clip(c_slgb.predict_proba(sub_X)[:, 1], 1e-6, 1.0 - 1e-6)
            lo = 0.5 * np.log(q1 / (1.0 - q1)) + 0.5 * np.log(q2 / (1.0 - q2))
            she[s0:s1] = (1.0 / (1.0 + np.exp(-lo))).astype(np.float32)
            del X_c106, inter_chunk
        del Xb, p106_e, c_shgb, c_slgb
        stack114_ens[te_mask] = she
        del she
        rss_now = MO.free_ram()
        print(f"    [CSAM fold {fold['name']}] completed in {time.time() - t_k:.1f}s (live VmRSS={rss_now:.0f} MiB)", flush=True)

    del pair_quad_pred, quad_fp
    gc.collect()

    ws = FROZEN_CSAM_PARAMS["w_stack_log_odds"]
    csam_raw = np.zeros((H, W), dtype=np.float32)
    p1 = np.clip(phys106_ens[foot].astype(np.float64), 1e-6, 1.0 - 1e-6)
    p2 = np.clip(stack114_ens[foot].astype(np.float64), 1e-6, 1.0 - 1e-6)
    lo_pool = (1.0 - ws) * np.log(p1 / (1.0 - p1)) + ws * np.log(p2 / (1.0 - p2))
    csam_raw[foot] = (1.0 / (1.0 + np.exp(-lo_pool))).astype(np.float32)

    csam_sharpened = anisotropic_ridge_sharpen(
        csam_raw, foot, alpha=float(FROZEN_CSAM_PARAMS["ridge_sharpen_alpha"])
    )

    out_dict = {
        "phys98_ens": phys98_ens,
        "phys106_ens": phys106_ens,
        "stack114_ens": stack114_ens,
        "csam_raw": csam_raw,
        "csam_sharpened": csam_sharpened,
    }
    if cache_path is not None:
        cp = Path(cache_path)
        cp.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cp, **out_dict)
    return out_dict


def fit_predict_phys98_and_106_loqo(
    X16_106: np.ndarray,
    folds: list[dict],
    visible: np.ndarray,
    foot: np.ndarray,
    slope_2d: np.ndarray,
    fp_lut: np.ndarray,
    seed: int = 8200,
) -> tuple[np.ndarray, np.ndarray]:
    """Fast (~24s) strictly LOQO 4-quadrant fitting for the 98-ch and 106-ch physical ablation arms."""
    H, W = foot.shape
    rng = np.random.default_rng(seed)
    phys98_ens = np.zeros((H, W), dtype=np.float32)
    phys106_ens = np.zeros((H, W), dtype=np.float32)
    quad_fp = [fp_lut[np.flatnonzero(folds[q]["region"] & foot)] for q in range(4)]

    # Advance rng identically to the 6 pair draws in fit_predict_csam_loqo so fold sampling matches
    for a_q in range(4):
        for b_q in range(a_q + 1, 4):
            sub_reg = folds[a_q]["region"] | folds[b_q]["region"]
            v_sub = visible & sub_reg
            d_sub = ndi.distance_transform_edt(~v_sub).astype(np.float32)
            _ = MO.sample_ht_strata(
                v_sub & foot,
                sub_reg & foot & (~v_sub) & (d_sub > 3.0),
                d_sub,
                slope_2d,
                fp_lut,
                rng,
                max_pos=30_000,
                max_h=30_000,
                max_s=30_000,
                max_b=20_000,
                pi_scale=FROZEN_CSAM_PARAMS["pi_scale_ht"],
            )

    lgb_kw2 = {
        **MO.LGB_KW,
        "n_estimators": 210,
        "learning_rate": 0.055,
        "num_leaves": 35,
        "min_child_samples": 75,
        "colsample_bytree": 0.78,
        "reg_alpha": 2.5,
        "reg_lambda": 6.0,
        "random_state": 8209,
    }

    for k, fold in enumerate(folds):
        other_js = [j for j in range(4) if j != k]
        tr_reg = np.zeros((H, W), dtype=bool)
        for j in other_js:
            tr_reg |= folds[j]["region"]
        vis_tr = visible & tr_reg
        d_tr = ndi.distance_transform_edt(~vis_tr).astype(np.float32)
        idx_p, y_p, w_p = MO.sample_ht_strata(
            vis_tr & foot,
            tr_reg & foot & (~vis_tr) & (d_tr > 3.0),
            d_tr,
            slope_2d,
            fp_lut,
            rng,
            pi_scale=FROZEN_CSAM_PARAMS["pi_scale_ht"],
        )
        Xp106 = X16_106[idx_p].astype(np.float32)
        te_mask = fold["region"] & foot
        te_fp = quad_fp[k]

        c98_1 = lgb.LGBMClassifier(**MO.LGB_KW).fit(Xp106[:, :98], y_p, sample_weight=w_p)
        c98_2 = lgb.LGBMClassifier(**lgb_kw2).fit(Xp106[:, :98], y_p, sample_weight=w_p)
        p98_e = np.empty(te_fp.size, dtype=np.float32)
        for s0 in range(0, te_fp.size, 200_000):
            s1 = min(te_fp.size, s0 + 200_000)
            Xb98 = X16_106[te_fp[s0:s1], :98].astype(np.float32)
            q98_1 = np.clip(c98_1.predict_proba(Xb98)[:, 1], 1e-6, 1.0 - 1e-6)
            q98_2 = np.clip(c98_2.predict_proba(Xb98)[:, 1], 1e-6, 1.0 - 1e-6)
            lo98 = 0.5 * np.log(q98_1 / (1.0 - q98_1)) + 0.5 * np.log(q98_2 / (1.0 - q98_2))
            p98_e[s0:s1] = (1.0 / (1.0 + np.exp(-lo98))).astype(np.float32)
            del Xb98
        phys98_ens[te_mask] = p98_e
        del p98_e, c98_1, c98_2
        MO.free_ram()

        c106_1 = lgb.LGBMClassifier(**MO.LGB_KW).fit(Xp106, y_p, sample_weight=w_p)
        c106_2 = lgb.LGBMClassifier(**lgb_kw2).fit(Xp106, y_p, sample_weight=w_p)
        del Xp106, y_p, w_p
        MO.free_ram()

        p106_e = np.empty(te_fp.size, dtype=np.float32)
        for s0 in range(0, te_fp.size, 200_000):
            s1 = min(te_fp.size, s0 + 200_000)
            Xb106 = X16_106[te_fp[s0:s1]].astype(np.float32)
            q106_1 = np.clip(c106_1.predict_proba(Xb106)[:, 1], 1e-6, 1.0 - 1e-6)
            q106_2 = np.clip(c106_2.predict_proba(Xb106)[:, 1], 1e-6, 1.0 - 1e-6)
            lo106 = 0.5 * np.log(q106_1 / (1.0 - q106_1)) + 0.5 * np.log(q106_2 / (1.0 - q106_2))
            p106_e[s0:s1] = (1.0 / (1.0 + np.exp(-lo106))).astype(np.float32)
            del Xb106
        phys106_ens[te_mask] = p106_e
        del p106_e, c106_1, c106_2
        MO.free_ram()

        # Advance rng identically to the inner 2-split stacker
        comp, n_comp = ndi.label(vis_tr, MO.STRUCT8)
        perm = rng.permutation(np.arange(1, n_comp + 1))
        groups = np.array_split(perm, 2)
        for g_ids in groups:
            hold_c = np.isin(comp, g_ids) & vis_tr
            collar_c = ndi.distance_transform_edt(~hold_c) <= 3.0
            ctx_m = vis_tr & (~collar_c)
            d_ctx = ndi.distance_transform_edt(~ctx_m).astype(np.float32)
            _ = MO.sample_ht_strata(
                hold_c & foot & (d_ctx > 3.0),
                tr_reg & foot & (~vis_tr) & (d_ctx > 3.0),
                d_ctx,
                slope_2d,
                fp_lut,
                rng,
                max_pos=22_000,
                max_h=24_000,
                max_s=24_000,
                max_b=16_000,
                pi_scale=FROZEN_CSAM_PARAMS["pi_scale_ht"],
            )

    return phys98_ens, phys106_ens
