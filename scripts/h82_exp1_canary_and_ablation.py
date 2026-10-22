#!/usr/bin/env python3
"""Experiment 1 of 3 (`Lane H82-CSAM` in `GEMSDOE82`):
1. Builds & verifies the 106-channel zero-SGMC static feature store (98 base + 8 novel H82-CSAM).
2. Runs single-feature symmetric ROC-AUC leakage canaries across ALL 114 channels
   (98 base static + 8 H82-CSAM static + 8 fold-visible structural) on the official buffered
   whole-component Seed-30 holdout (`11,342` withheld positives; gate <= 0.90).
3. Evaluates strictly nested physical & emitter arms on unmodified `vendor/gems57/evaluate_holdout.py`
   (`gems57-pooled-hide-v2`, alpha=0.2, beta=0.8, R=300 m, 1,000 paired 20 km block bootstrap draws).
"""
from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor"))

from gems57 import evaluate_holdout as EH, grid as G, holdout as HO  # noqa: E402
from gems77lia import allocate as LIA_AL  # noqa: E402
from gems77vds import dinkelbach as DK, features as FE, models as MO  # noqa: E402
from gems82 import csam as CS  # noqa: E402

SEED = 30
PARITY_BUDGET = 37_654
PRIMARY_BUDGET = 41_200
EXCL_PX = 3.0


def log(*a: object) -> None:
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def evaluate_binary_dots(dots: np.ndarray, folds: list[dict], foot: np.ndarray) -> np.ndarray:
    pred = np.where(dots & foot, np.float32(1.0), np.float32(0.0))
    terms = None
    for f in folds:
        _, t = EH.evaluate(pred, f, valid=foot, block_side=200)
        terms = t if terms is None else terms + t
    return terms


def main() -> int:
    t0 = time.time()
    log("Building / verifying 98-channel base + 8-channel H82-CSAM static feature stores...")
    bin98_path, aux = FE.build_static_fp_memmap(ROOT, force=False)
    csam8_path = CS.build_csam8_memmap(ROOT, force=False)
    n_fp = int(aux["n_fp"])
    log(f"Static feature stores ready in {time.time() - t0:.1f}s: n_fp={n_fp}, total_static_ch=106")

    grid = G.load_grid(ROOT / "data" / "raw")
    foot, cat = grid.footprint, grid.catalogue
    H, W = foot.shape
    fp_flat = np.flatnonzero(foot)
    fp_lut = np.full(H * W, -1, dtype=np.int32)
    fp_lut[fp_flat] = np.arange(fp_flat.size, dtype=np.int32)

    slope_2d = np.zeros((H, W), dtype=np.float32)
    slope_2d[foot] = np.nan_to_num(
        FE.read_static_rows(bin98_path, n_fp, slice(None), [FE.STATIC_IDX["topo10_slope_max"]])[:, 0], nan=0.0
    )

    folds, _ = HO.buffered_component_draw(grid, seed=SEED, hide_frac=0.20, buffer_px=3)
    hidden = folds[0]["hidden_all"]
    visible = folds[0]["visible"]
    dist_vis = ndi.distance_transform_edt(~visible).astype(np.float32)
    log(f"Seed {SEED}: withheld_positive_pixels={int(hidden.sum())}, visible_pixels={int(visible.sum())}")

    # 1. Single-feature symmetric ROC-AUC leakage canaries across ALL 114 channels
    cache_dir = ROOT / ".cache" / "h82_csam"
    canary_cache_path = cache_dir / f"canary_seed{SEED}.json"
    raw_fp_path = cache_dir / f"csam_raw_seed{SEED}_fp.npy"
    sharp_fp_path = cache_dir / f"csam_sharpened_seed{SEED}_fp.npy"
    p98_fp_path = cache_dir / f"phys98_seed{SEED}_fp.npy"
    p106_fp_path = cache_dir / f"phys106_seed{SEED}_fp.npy"

    if canary_cache_path.is_file() and raw_fp_path.is_file() and sharp_fp_path.is_file() and p98_fp_path.is_file() and p106_fp_path.is_file():
        canary_rows = json.loads(canary_cache_path.read_text())
        canary_rows_sorted = sorted(canary_rows, key=lambda r: -r["symmetric_auc"])
        max_sym_auc = float(canary_rows_sorted[0]["symmetric_auc"])
        max_chan = canary_rows_sorted[0]["channel"]
        log(f"Loaded cached 114-channel canary: max_symmetric_auc={max_sym_auc:.6f} ({max_chan})")
        assert max_sym_auc <= 0.90, f"LEAKAGE CANARY FAILED: {max_chan} symmetric AUC = {max_sym_auc:.6f} > 0.90"
        log("Loading cached Seed-30 LOQO surfaces (phys98, phys106, csam_raw, csam_sharpened)...")
        phys98_ens = np.zeros((H, W), dtype=np.float32)
        phys106_ens = np.zeros((H, W), dtype=np.float32)
        csam_raw = np.zeros((H, W), dtype=np.float32)
        csam_sharpened = np.zeros((H, W), dtype=np.float32)
        phys98_ens[foot] = np.load(p98_fp_path).astype(np.float32)
        phys106_ens[foot] = np.load(p106_fp_path).astype(np.float32)
        csam_raw[foot] = np.load(raw_fp_path).astype(np.float32)
        csam_sharpened[foot] = np.load(sharp_fp_path).astype(np.float32)
        preds = {
            "phys98_ens": phys98_ens,
            "phys106_ens": phys106_ens,
            "csam_raw": csam_raw,
            "csam_sharpened": csam_sharpened,
        }
    else:
        log("Loading 106-channel scaled float16 matrix (~1.04 GiB)...")
        X16_106, _ = CS.load_scaled_f16_106_matrix(ROOT)
        log(f"Running single-feature symmetric ROC-AUC leakage canaries across all 114 channels (VmRSS={MO.free_ram():.0f} MiB)...")
        vis_fp = FE.compute_visible_structural_fp(visible, foot, aux["u2_dir"], aux["v2_dir"], aux["geod_rank"])

        rng = np.random.default_rng(1000 + SEED)
        pos_fp = fp_lut[np.flatnonzero(hidden & foot)]
        dist_cat = ndi.distance_transform_edt(~cat).astype(np.float32)
        neg_pool_fp = fp_lut[np.flatnonzero(foot & (~cat) & (dist_cat > 3.0))]
        neg_fp = rng.choice(neg_pool_fp, size=min(200_000, neg_pool_fp.size), replace=False)
        can_fp = np.concatenate([pos_fp, neg_fp])
        y_can = np.concatenate([np.ones(pos_fp.size, dtype=np.int8), np.zeros(neg_fp.size, dtype=np.int8)])
        del dist_cat, neg_pool_fp, neg_fp, pos_fp

        Xc_all = X16_106[can_fp].astype(np.float32)
        canary_rows = []
        for j, nm in enumerate(FE.STATIC_CHANNEL_NAMES):
            v = Xc_all[:, j]
            m = np.isfinite(v)
            raw_auc = float(roc_auc_score(y_can[m], v[m])) if (m.sum() > 100 and len(np.unique(y_can[m])) == 2) else 0.5
            canary_rows.append(
                {
                    "channel": nm,
                    "group": "static_base98",
                    "raw_auc": round(raw_auc, 6),
                    "symmetric_auc": round(max(raw_auc, 1.0 - raw_auc), 6),
                }
            )
        for j, nm in enumerate(CS.CSAM_CHANNEL_NAMES):
            v = Xc_all[:, 98 + j]
            m = np.isfinite(v)
            raw_auc = float(roc_auc_score(y_can[m], v[m])) if (m.sum() > 100 and len(np.unique(y_can[m])) == 2) else 0.5
            canary_rows.append(
                {
                    "channel": nm,
                    "group": "static_csam8",
                    "raw_auc": round(raw_auc, 6),
                    "symmetric_auc": round(max(raw_auc, 1.0 - raw_auc), 6),
                }
            )
        Vc = vis_fp[can_fp]
        for j, nm in enumerate(FE.VISIBLE_CHANNEL_NAMES):
            v = Vc[:, j]
            raw_auc = float(roc_auc_score(y_can, v))
            canary_rows.append(
                {
                    "channel": nm,
                    "group": "fold_visible8",
                    "raw_auc": round(raw_auc, 6),
                    "symmetric_auc": round(max(raw_auc, 1.0 - raw_auc), 6),
                }
            )
        del Xc_all, Vc, can_fp, y_can
        canary_cache_path.write_text(json.dumps(canary_rows, indent=2) + "\n")
        MO.free_ram()

        canary_rows_sorted = sorted(canary_rows, key=lambda r: -r["symmetric_auc"])
        max_sym_auc = float(canary_rows_sorted[0]["symmetric_auc"])
        max_chan = canary_rows_sorted[0]["channel"]
        log(f"Canary complete: n_channels={len(canary_rows)}, max_symmetric_auc={max_sym_auc:.6f} ({max_chan})")
        assert max_sym_auc <= 0.90, f"LEAKAGE CANARY FAILED: {max_chan} symmetric AUC = {max_sym_auc:.6f} > 0.90"

        if raw_fp_path.is_file() and sharp_fp_path.is_file():
            log("Loading cached Seed-30 LOQO stacker surfaces and computing/loading 98-ch & 106-ch ablation surfaces...")
            csam_raw = np.zeros((H, W), dtype=np.float32)
            csam_sharpened = np.zeros((H, W), dtype=np.float32)
            csam_raw[foot] = np.load(raw_fp_path).astype(np.float32)
            csam_sharpened[foot] = np.load(sharp_fp_path).astype(np.float32)
            if p98_fp_path.is_file() and p106_fp_path.is_file():
                phys98_ens = np.zeros((H, W), dtype=np.float32)
                phys106_ens = np.zeros((H, W), dtype=np.float32)
                phys98_ens[foot] = np.load(p98_fp_path).astype(np.float32)
                phys106_ens[foot] = np.load(p106_fp_path).astype(np.float32)
            else:
                phys98_ens, phys106_ens = CS.fit_predict_phys98_and_106_loqo(
                    X16_106, folds, visible, foot, slope_2d, fp_lut, seed=8200 + SEED
                )
                np.save(p98_fp_path, phys98_ens[foot].astype(np.float32))
                np.save(p106_fp_path, phys106_ens[foot].astype(np.float32))
            preds = {
                "phys98_ens": phys98_ens,
                "phys106_ens": phys106_ens,
                "csam_raw": csam_raw,
                "csam_sharpened": csam_sharpened,
            }
        else:
            log(f"Fitting strictly LOQO models on Seed 30 (VmRSS={MO.free_ram():.0f} MiB)...")
            preds = CS.fit_predict_csam_loqo(
                X16_106, vis_fp, folds, visible, foot, slope_2d, aux, fp_lut, seed=8200 + SEED
            )
            np.save(sharp_fp_path, preds["csam_sharpened"][foot].astype(np.float32))
            np.save(raw_fp_path, preds["csam_raw"][foot].astype(np.float32))
            np.save(p98_fp_path, preds["phys98_ens"][foot].astype(np.float32))
            np.save(p106_fp_path, preds["phys106_ens"][foot].astype(np.float32))

        del X16_106, vis_fp
        MO.free_ram()

    # 3. Evaluate strictly nested arms on unmodified `vendor/gems57/evaluate_holdout.py`
    allowed = foot & (~visible) & (dist_vis > EXCL_PX)
    P = CS.FROZEN_CSAM_PARAMS
    arms_terms: dict[str, np.ndarray] = {}
    arm_meta: dict[str, dict] = {}

    # Baseline 1: Random 37,654
    rng_r = np.random.default_rng(42)
    r_idx = rng_r.choice(np.flatnonzero(allowed), size=PARITY_BUDGET, replace=False)
    d_rand = np.zeros((H, W), dtype=bool)
    d_rand.ravel()[r_idx] = True
    arms_terms["random_37654"] = evaluate_binary_dots(d_rand, folds, foot)
    arm_meta["random_37654"] = {"n_dots": int(d_rand.sum()), "description": "Uniform random off-catalogue baseline (37,654 dots)"}

    # Baseline 2: Static H33 (GEMSDOE32)
    with rasterio.open(ROOT / ".cache" / "registry" / "h33.tif") as ds:
        d_h33 = (ds.read(1) > 0) & foot & (~visible)
    arms_terms["H33_static_ref"] = evaluate_binary_dots(d_h33, folds, foot)
    arm_meta["H33_static_ref"] = {"n_dots": int(d_h33.sum()), "description": "Pinned GEMSDOE32 h33-2-b2 static raster"}

    # Baseline 3: Static D2.8 (GEMSDOE25)
    with rasterio.open(ROOT / "data/raw/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif") as ds:
        d_d28_raw = (ds.read(1) > 0) & foot
    d_d28 = d_d28_raw & (~visible)
    arms_terms["D28_static_ref"] = evaluate_binary_dots(d_d28, folds, foot)
    arm_meta["D28_static_ref"] = {"n_dots": int(d_d28.sum()), "description": "Pinned GEMSDOE25 d2.8 static raster (44,090 dots)"}

    # Baseline 4: Fold-Fair H33 (D2.8 pruned within 2.0 px of VISIBLE faults only)
    d_h33_fair = d_d28_raw & (~visible) & (dist_vis > 2.0001)
    arms_terms["H33_fold_fair"] = evaluate_binary_dots(d_h33_fair, folds, foot)
    arm_meta["H33_fold_fair"] = {"n_dots": int(d_h33_fair.sum()), "description": "Fold-fair H33 comparator (D2.8 pruned within 2.0 px of visible faults only)"}

    # Arm E1_A: 98-ch physical LOQO + submodular 300m spacing
    d_e1a, st_a = DK.allocate_dinkelbach_submodular_dti(
        preds["phys98_ens"],
        allowed,
        budget=PARITY_BUDGET,
        min_sep_px=P["dinkelbach_min_sep_px"],
        pi_true=P["dinkelbach_pi_true"],
        temperature=P["dinkelbach_temperature"],
        fp_lambda=0.0,
    )
    arms_terms["E1_A_phys98_submod37654"] = evaluate_binary_dots(d_e1a, folds, foot)
    arm_meta["E1_A_phys98_submod37654"] = {"n_dots": int(d_e1a.sum()), "stats": st_a, "description": "Base 98-channel zero-SGMC physical LOQO ensemble"}

    # Arm E1_B: 106-ch (98 base + 8 H82-CSAM) physical LOQO
    d_e1b, st_b = DK.allocate_dinkelbach_submodular_dti(
        preds["phys106_ens"],
        allowed,
        budget=PARITY_BUDGET,
        min_sep_px=P["dinkelbach_min_sep_px"],
        pi_true=P["dinkelbach_pi_true"],
        temperature=P["dinkelbach_temperature"],
        fp_lambda=0.0,
    )
    arms_terms["E1_B_csam106_submod37654"] = evaluate_binary_dots(d_e1b, folds, foot)
    arm_meta["E1_B_csam106_submod37654"] = {"n_dots": int(d_e1b.sum()), "stats": st_b, "description": "106-channel (98 base + 8 H82-CSAM up-dip/upslope/phase/flexure) physical LOQO ensemble"}

    # Arm E1_C: 114-ch CSAM unsharpened Dinkelbach 37,654
    d_e1c, st_c = DK.allocate_dinkelbach_submodular_dti(
        preds["csam_raw"],
        allowed,
        budget=PARITY_BUDGET,
        min_sep_px=P["dinkelbach_min_sep_px"],
        pi_true=P["dinkelbach_pi_true"],
        temperature=P["dinkelbach_temperature"],
        fp_lambda=P["dinkelbach_fp_lambda"],
    )
    arms_terms["E1_C_csam114_raw_dinkelbach37654"] = evaluate_binary_dots(d_e1c, folds, foot)
    arm_meta["E1_C_csam114_raw_dinkelbach37654"] = {"n_dots": int(d_e1c.sum()), "stats": st_c}

    # Arm E1_D: 114-ch CSAM + anisotropic 1D ridge sharpening + Dinkelbach 37,654 (parity budget)
    d_e1d, st_d = DK.allocate_dinkelbach_submodular_dti(
        preds["csam_sharpened"],
        allowed,
        budget=PARITY_BUDGET,
        min_sep_px=P["dinkelbach_min_sep_px"],
        pi_true=P["dinkelbach_pi_true"],
        temperature=P["dinkelbach_temperature"],
        fp_lambda=P["dinkelbach_fp_lambda"],
    )
    arms_terms["E1_D_csam114_sharpened_dinkelbach37654"] = evaluate_binary_dots(d_e1d, folds, foot)
    arm_meta["E1_D_csam114_sharpened_dinkelbach37654"] = {"n_dots": int(d_e1d.sum()), "stats": st_d}

    # Arm E1_E: 114-ch CSAM + anisotropic 1D ridge sharpening + Dinkelbach 41,200 (primary budget)
    d_e1e, st_e = DK.allocate_dinkelbach_submodular_dti(
        preds["csam_sharpened"],
        allowed,
        budget=PRIMARY_BUDGET,
        min_sep_px=P["dinkelbach_min_sep_px"],
        pi_true=P["dinkelbach_pi_true"],
        temperature=P["dinkelbach_temperature"],
        fp_lambda=P["dinkelbach_fp_lambda"],
    )
    arms_terms["E1_E_csam114_sharpened_dinkelbach41200"] = evaluate_binary_dots(d_e1e, folds, foot)
    arm_meta["E1_E_csam114_sharpened_dinkelbach41200"] = {"n_dots": int(d_e1e.sum()), "stats": st_e}

    summary = EH.pooled_summary(
        arms_terms,
        draws=1000,
        seed=820030,
        candidate="E1_E_csam114_sharpened_dinkelbach41200",
    )
    for k, v in summary["scores"].items():
        log(f"  {k:42s} HOLDOUT-DTI={v['dti']:.6f}  95% CI=[{v['ci95'][0]:.6f}, {v['ci95'][1]:.6f}]")

    out_payload = {
        "schema": "gemsdoe82-exp1-canary-ablation-v1",
        "evidence_class": "HOLDOUT-DTI",
        "evaluator_version": EH.VERSION,
        "evaluator_hashes": EH.implementation_hashes(),
        "seed": SEED,
        "withheld_positive_pixels": int(hidden.sum()),
        "leakage_canary": {
            "n_channels_tested": len(canary_rows),
            "threshold_symmetric_auc": 0.90,
            "max_symmetric_auc": max_sym_auc,
            "max_channel": max_chan,
            "all_passed": max_sym_auc <= 0.90,
            "top_15_channels": canary_rows_sorted[:15],
            "csam8_channels": [r for r in canary_rows if r["group"] == "static_csam8"],
            "all_channels": canary_rows,
        },
        "arm_meta": arm_meta,
        "pooled_summary": summary,
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    (ROOT / "evidence" / "h82_exp1_canary_and_ablation.json").write_text(json.dumps(out_payload, indent=2) + "\n")
    log(f"Experiment 1 complete in {time.time() - t0:.1f}s -> evidence/h82_exp1_canary_and_ablation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
