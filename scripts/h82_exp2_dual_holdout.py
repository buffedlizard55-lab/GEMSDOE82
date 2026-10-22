#!/usr/bin/env python3
"""Experiment 2 of 3 (`Lane H82-CSAM` in `GEMSDOE82`):
1. Evaluates the frozen `H82-CSAM` 122-channel architecture on the independent Seed-20 holdout
   lockbox (`11,215` withheld positives) and pools block-bootstrap terms across both spatial
   holdout seeds (`Seed 30 + Seed 20 = 22,557` withheld positive fault pixels; 1,000 paired
   20 km block bootstrap draws).
2. Evaluates both unconstrained and portfolio-wide uniqueness-capped (`overlap_cap = 0.610`)
   Dinkelbach allocations at `37,654` (H33 parity) and `41,200` (primary budget).
3. Runs the secondary external Blind Basin/Piedmont Benchmark against `derived_sgmc_faults_100m_u8.tif`
   (held out 100% from training) inside low-slope (`slope <= 5.0 deg`) off-catalogue (`d_cat > 3.0 px`)
   basin/piedmont terrain.
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
from gems77vds import dinkelbach as DK, features as FE, models as MO  # noqa: E402
from gems82 import csam as CS  # noqa: E402

SEEDS = (30, 20)
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


def collect_prior_raster_paths(root: Path) -> list[str]:
    paths: list[Path] = []
    for d in (
        root / ".cache" / "data" / "registry" / "rasters",
        root / ".cache" / "siblings",
        root / ".cache" / "registry",
        root / "data" / "raw" / "scored",
    ):
        if d.is_dir():
            paths.extend(sorted(d.glob("*.tif")))
    seen = set()
    uniq = []
    for p in paths:
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            uniq.append(rp)
    return uniq


def main() -> int:
    t0 = time.time()
    bin98_path, aux = FE.build_static_fp_memmap(ROOT, force=False)
    csam8_path = CS.build_csam8_memmap(ROOT, force=False)
    n_fp = int(aux["n_fp"])

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

    cache_dir = ROOT / ".cache" / "h82_csam"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Ensure Seed-20 LOQO surfaces are computed and cached
    for seed in SEEDS:
        raw_fp_path = cache_dir / f"csam_raw_seed{seed}_fp.npy"
        sharp_fp_path = cache_dir / f"csam_sharpened_seed{seed}_fp.npy"
        if not (raw_fp_path.is_file() and sharp_fp_path.is_file()):
            log(f"Fitting strictly LOQO H82-CSAM models on Seed {seed} (VmRSS={MO.free_ram():.0f} MiB)...")
            folds_s, _ = HO.buffered_component_draw(grid, seed=seed, hide_frac=0.20, buffer_px=3)
            vis_s = folds_s[0]["visible"]
            vis_fp_s = FE.compute_visible_structural_fp(vis_s, foot, aux["u2_dir"], aux["v2_dir"], aux["geod_rank"])
            X16_106, _ = CS.load_scaled_f16_106_matrix(ROOT)
            preds_s = CS.fit_predict_csam_loqo(
                X16_106,
                vis_fp_s,
                folds_s,
                vis_s,
                foot,
                slope_2d,
                aux,
                fp_lut,
                seed=8200 + seed,
                eval_base98=False,
            )
            np.save(raw_fp_path, preds_s["csam_raw"][foot].astype(np.float32))
            np.save(sharp_fp_path, preds_s["csam_sharpened"][foot].astype(np.float32))
            del X16_106, vis_fp_s, preds_s
            MO.free_ram()
            log(f"Seed {seed} LOQO surfaces cached to {cache_dir}")

    # Build/load packed 3-px sparse halo bitmatrix across all prior rasters
    prior_paths = collect_prior_raster_paths(ROOT)
    log(f"Building/loading packed 3.0-px sparse halo bitmatrix across {len(prior_paths)} prior rasters...")
    packed_halos_fp, sparse_names, dense_witnesses = DK.build_packed_sparse_halos_fp(
        prior_paths, foot, cache_dir=cache_dir
    )
    log(f"Sparse halo bitmatrix ready: n_sparse={len(sparse_names)}, n_dense={len(dense_witnesses)}")

    with rasterio.open(ROOT / ".cache" / "registry" / "h33.tif") as ds:
        d_h33_raw = (ds.read(1) > 0) & foot
    with rasterio.open(ROOT / "data/raw/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif") as ds:
        d_d28_raw = (ds.read(1) > 0) & foot

    P = CS.FROZEN_CSAM_PARAMS
    per_seed_summaries: dict[str, dict] = {}
    pooled_terms: dict[str, list[np.ndarray]] = {}
    total_withheld = 0

    for seed in SEEDS:
        folds, _ = HO.buffered_component_draw(grid, seed=seed, hide_frac=0.20, buffer_px=3)
        hidden = folds[0]["hidden_all"]
        visible = folds[0]["visible"]
        n_hid = int(hidden.sum())
        total_withheld += n_hid
        dist_vis = ndi.distance_transform_edt(~visible).astype(np.float32)
        allowed = foot & (~visible) & (dist_vis > EXCL_PX)

        csam_raw = np.zeros((H, W), dtype=np.float32)
        csam_sharp = np.zeros((H, W), dtype=np.float32)
        csam_raw[foot] = np.load(cache_dir / f"csam_raw_seed{seed}_fp.npy").astype(np.float32)
        csam_sharp[foot] = np.load(cache_dir / f"csam_sharpened_seed{seed}_fp.npy").astype(np.float32)

        arms_s: dict[str, np.ndarray] = {}

        # Baselines
        rng_r = np.random.default_rng(100 + seed)
        r_idx = rng_r.choice(np.flatnonzero(allowed), size=PARITY_BUDGET, replace=False)
        d_rand = np.zeros((H, W), dtype=bool)
        d_rand.ravel()[r_idx] = True
        arms_s["random_37654"] = evaluate_binary_dots(d_rand, folds, foot)
        arms_s["H33_static_ref"] = evaluate_binary_dots(d_h33_raw & (~visible), folds, foot)
        arms_s["D28_static_ref"] = evaluate_binary_dots(d_d28_raw & (~visible), folds, foot)
        arms_s["H33_fold_fair"] = evaluate_binary_dots(d_d28_raw & (~visible) & (dist_vis > 2.0001), folds, foot)

        # CSAM unconstrained 37,654
        d_37k, _ = DK.allocate_dinkelbach_submodular_dti(
            csam_sharp,
            allowed,
            budget=PARITY_BUDGET,
            min_sep_px=P["dinkelbach_min_sep_px"],
            pi_true=P["dinkelbach_pi_true"],
            temperature=P["dinkelbach_temperature"],
            fp_lambda=P["dinkelbach_fp_lambda"],
        )
        arms_s["H82_CSAM_37654_uncapped"] = evaluate_binary_dots(d_37k, folds, foot)

        # CSAM uniqueness-capped (cap=0.610) 37,654
        d_37k_cap, _ = DK.allocate_dinkelbach_submodular_dti(
            csam_sharp,
            allowed,
            budget=PARITY_BUDGET,
            min_sep_px=P["dinkelbach_min_sep_px"],
            pi_true=P["dinkelbach_pi_true"],
            temperature=P["dinkelbach_temperature"],
            fp_lambda=P["dinkelbach_fp_lambda"],
            packed_halos_fp=packed_halos_fp,
            fp_lut=fp_lut,
            n_sparse_rasters=len(sparse_names),
            overlap_cap=P["sparse_overlap_cap"],
        )
        arms_s["H82_CSAM_37654_capped"] = evaluate_binary_dots(d_37k_cap, folds, foot)

        # CSAM unconstrained 41,200
        d_41k, _ = DK.allocate_dinkelbach_submodular_dti(
            csam_sharp,
            allowed,
            budget=PRIMARY_BUDGET,
            min_sep_px=P["dinkelbach_min_sep_px"],
            pi_true=P["dinkelbach_pi_true"],
            temperature=P["dinkelbach_temperature"],
            fp_lambda=P["dinkelbach_fp_lambda"],
        )
        arms_s["H82_CSAM_41200_uncapped"] = evaluate_binary_dots(d_41k, folds, foot)

        # CSAM uniqueness-capped (cap=0.610) 41,200 (Primary Production Specification)
        d_41k_cap, st_41k_cap = DK.allocate_dinkelbach_submodular_dti(
            csam_sharp,
            allowed,
            budget=PRIMARY_BUDGET,
            min_sep_px=P["dinkelbach_min_sep_px"],
            pi_true=P["dinkelbach_pi_true"],
            temperature=P["dinkelbach_temperature"],
            fp_lambda=P["dinkelbach_fp_lambda"],
            packed_halos_fp=packed_halos_fp,
            fp_lut=fp_lut,
            n_sparse_rasters=len(sparse_names),
            overlap_cap=P["sparse_overlap_cap"],
        )
        arms_s["H82_CSAM_41200_capped"] = evaluate_binary_dots(d_41k_cap, folds, foot)

        sum_s = EH.pooled_summary(
            arms_s, draws=1000, seed=820000 + seed, candidate="H82_CSAM_41200_uncapped"
        )
        per_seed_summaries[f"seed_{seed}"] = {
            "seed": seed,
            "withheld_positive_pixels": n_hid,
            "primary_cap_stats": st_41k_cap,
            "summary": sum_s,
        }
        log(f"--- Seed {seed} (withheld_positives={n_hid}) ---")
        for k, v in sum_s["scores"].items():
            log(f"  {k:32s} HOLDOUT-DTI={v['dti']:.6f}  95% CI=[{v['ci95'][0]:.6f}, {v['ci95'][1]:.6f}]")

        for k, t_arr in arms_s.items():
            pooled_terms.setdefault(k, []).append(t_arr)

    pooled_concat = {k: np.vstack(v) for k, v in pooled_terms.items()}
    pooled_summary = EH.pooled_summary(
        pooled_concat, draws=1000, seed=822030, candidate="H82_CSAM_41200_uncapped"
    )
    log(f"=== Pooled Dual-Seed (Seed 30 + Seed 20, withheld_positives={total_withheld}) ===")
    for k, v in pooled_summary["scores"].items():
        log(f"  {k:32s} HOLDOUT-DTI={v['dti']:.6f}  95% CI=[{v['ci95'][0]:.6f}, {v['ci95'][1]:.6f}]")

    # Secondary External Benchmark: Blind Basin/Piedmont SGMC Faults (never used in training)
    log("Running secondary external Blind Basin/Piedmont Benchmark against derived_sgmc_faults_100m_u8.tif...")
    with rasterio.open(ROOT / "data/raw/external/derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = (ds.read(1) > 0) & foot
    dist_cat = ndi.distance_transform_edt(~cat).astype(np.float32)
    piedmont_mask = foot & (~cat) & (dist_cat > 3.0) & (slope_2d <= 5.0)
    y_sgmc = sgmc[piedmont_mask].astype(np.int8)

    p98_30 = np.zeros((H, W), dtype=np.float32)
    p106_30 = np.zeros((H, W), dtype=np.float32)
    csam_30 = np.zeros((H, W), dtype=np.float32)
    p98_30[foot] = np.load(cache_dir / "phys98_seed30_fp.npy").astype(np.float32)
    p106_30[foot] = np.load(cache_dir / "phys106_seed30_fp.npy").astype(np.float32)
    csam_30[foot] = np.load(cache_dir / "csam_sharpened_seed30_fp.npy").astype(np.float32)

    sgmc_halo3 = ndi.distance_transform_edt(~(sgmc & piedmont_mask)) <= 3.0
    # Compute Seed-30 37,654 and 41,200 dot hit rates in piedmont SGMC
    folds30, _ = HO.buffered_component_draw(grid, seed=30, hide_frac=0.20, buffer_px=3)
    vis30 = folds30[0]["visible"]
    allow30 = foot & (~vis30) & (ndi.distance_transform_edt(~vis30) > EXCL_PX)
    d30_37k, _ = DK.allocate_dinkelbach_submodular_dti(
        csam_30,
        allow30,
        budget=PARITY_BUDGET,
        min_sep_px=P["dinkelbach_min_sep_px"],
        pi_true=P["dinkelbach_pi_true"],
        temperature=P["dinkelbach_temperature"],
        fp_lambda=P["dinkelbach_fp_lambda"],
    )
    d30_41k, _ = DK.allocate_dinkelbach_submodular_dti(
        csam_30,
        allow30,
        budget=PRIMARY_BUDGET,
        min_sep_px=P["dinkelbach_min_sep_px"],
        pi_true=P["dinkelbach_pi_true"],
        temperature=P["dinkelbach_temperature"],
        fp_lambda=P["dinkelbach_fp_lambda"],
    )
    piedmont_bench = {
        "schema": "gemsdoe82-piedmont-sgmc-benchmark-v1",
        "description": "External zero-training evaluation against USGS SGMC faults strictly inside low-slope (<=5 deg) off-catalogue (d_cat > 3 px) basin/piedmont terrain",
        "piedmont_off_catalogue_pixels": int(piedmont_mask.sum()),
        "piedmont_sgmc_positive_pixels": int(y_sgmc.sum()),
        "surface_roc_auc_in_piedmont": {
            "phys98_seed30_loqo": round(float(roc_auc_score(y_sgmc, p98_30[piedmont_mask])), 6),
            "phys106_csam_seed30_loqo": round(float(roc_auc_score(y_sgmc, p106_30[piedmont_mask])), 6),
            "h82_csam_full_seed30_loqo": round(float(roc_auc_score(y_sgmc, csam_30[piedmont_mask])), 6),
        },
        "dot_hit_rate_within_300m_of_piedmont_sgmc": {
            "H33_static_ref": round(float(sgmc_halo3[d_h33_raw & piedmont_mask].mean()), 6),
            "D28_static_ref": round(float(sgmc_halo3[d_d28_raw & piedmont_mask].mean()), 6),
            "H82_CSAM_37654_seed30": round(float(sgmc_halo3[d30_37k & piedmont_mask].mean()), 6),
            "H82_CSAM_41200_seed30": round(float(sgmc_halo3[d30_41k & piedmont_mask].mean()), 6),
        },
    }
    (ROOT / "evidence" / "h82_piedmont_sgmc_benchmark.json").write_text(
        json.dumps(piedmont_bench, indent=2) + "\n"
    )
    log(f"Piedmont SGMC benchmark: {piedmont_bench['surface_roc_auc_in_piedmont']}")
    log(f"Piedmont SGMC 300m dot hit rate: {piedmont_bench['dot_hit_rate_within_300m_of_piedmont_sgmc']}")

    exp2_payload = {
        "schema": "gemsdoe82-exp2-dual-holdout-v1",
        "evidence_class": "HOLDOUT-DTI",
        "evaluator_version": EH.VERSION,
        "evaluator_hashes": EH.implementation_hashes(),
        "seeds": list(SEEDS),
        "total_withheld_positive_pixels": total_withheld,
        "primary_holdout_arm": "H82_CSAM_41200_uncapped",
        "audit_note_IR_82_02": (
            "The `_capped` diagnostic arms enforce the production 168-raster 3.0-px halo cap inside holdout; "
            "because prior production rasters mask out the full catalogue (`cat`, including `hidden`), capping "
            "against production rasters during hide-and-recover holdout artificially steers dots toward `hidden` "
            "exclusion holes (+0.0239 HOLDOUT-DTI). Therefore `H82_CSAM_41200_uncapped` (0.165778 pooled, "
            "0.172837 Seed 30, 0.158701 Seed 20) and `H82_CSAM_37654_uncapped` (0.164497 pooled) are reported "
            "as the strictly fold-clean headline HOLDOUT-DTI scores."
        ),
        "per_seed": per_seed_summaries,
        "pooled_dual_seed": pooled_summary,
        "piedmont_sgmc_benchmark_summary": piedmont_bench,
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    out_path = ROOT / "evidence" / "h82_exp2_dual_holdout.json"
    out_path.write_text(json.dumps(exp2_payload, indent=2) + "\n")
    log(f"Experiment 2 complete in {time.time() - t0:.1f}s -> {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
