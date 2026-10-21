#!/usr/bin/env python3
"""E2 (2/3), memory-safe: line-localised H82-1 + low-slope stratification. See git history for design."""
import json, sys, time, gc
from pathlib import Path
import numpy as np
sys.path.insert(0, "src")
from gems82 import grid, emission, holdout
from gems82.surface import _fill, robust_unit
from scipy.ndimage import gaussian_filter, distance_transform_edt

t0 = time.time(); CACHE = Path(".cache")
foot = np.load(CACHE/"foot.npy"); labels = np.load(CACHE/"labels.npy")
slope = np.load(CACHE/"slope_unit.npy"); agree = np.load(CACHE/"strike_agree.npy")
def line_response(idx, sigma):
    a = gaussian_filter(_fill(grid.read_band("data/training_features.tif", idx), foot), sigma, mode="nearest")
    axx = gaussian_filter(a, sigma, order=(0,2), mode="nearest"); ayy = gaussian_filter(a, sigma, order=(2,0), mode="nearest")
    axy = gaussian_filter(a, sigma, order=(1,1), mode="nearest"); del a
    tmp = np.sqrt(np.maximum(((axx-ayy)*0.5)**2 + axy**2, 0))
    l1 = (axx+ayy)*0.5 + tmp; l2 = (axx+ayy)*0.5 - tmp; del axx, ayy, axy, tmp
    small = np.where(np.abs(l1) >= np.abs(l2), l2, l1); del l1, l2
    return robust_unit(-small, foot)
Lg = np.maximum(line_response(13,1.5), line_response(13,3.0)); gc.collect()
Lr = np.maximum(line_response(2,1.5), line_response(2,3.0)); gc.collect()
Ld = np.maximum(line_response(15,1.5), line_response(15,3.0)); gc.collect()
core = (Lg*Lr*Ld)**(1/3); del Lg, Lr, Ld
gate = (0.15 + 0.85*(1-slope)).astype(np.float32)
s_line_blind = np.where(foot, core*(0.5+0.5*agree)*gate, 0).astype(np.float32)
s_line_nogate = np.where(foot, core*(0.5+0.5*agree), 0).astype(np.float32); del core, gate, agree
np.save(CACHE/"s_line_blind.npy", s_line_blind); np.save(CACHE/"s_line_nogate.npy", s_line_nogate)
s_blind_e1 = np.load(CACHE/"s_blind.npy")
print(f"E2 surfaces {time.time()-t0:.0f}s", flush=True)
folds = holdout.quadrant_folds(foot.shape, buffer_px=30)
DENSITY = 37654/int(foot.sum()); rng = np.random.default_rng(82)
arms = {"line_blind_thin": s_line_blind, "line_nogate_thin": s_line_nogate, "blind_e1_thin": s_blind_e1}
blocks = {a: {} for a in list(arms)+["random"]}; sblocks = {a: {} for a in list(arms)+["random"]}
per_fold = {a: [] for a in blocks}
low = slope <= np.percentile(slope[foot], 50); del slope
for name, fold in folds.items():
    withheld = labels & fold; visible = labels & ~fold; known_mask = labels & ~fold
    n_fold = int(round(DENSITY*int((fold & foot).sum())))
    preds = {}
    for arm, s in arms.items():
        preds[arm] = holdout.emit_in_fold(s, fold, foot, visible, n_fold, lambda su, al, n: emission.thin_topn(su, al, n, spacing=2))
    d = distance_transform_edt(~visible); allowed = fold & foot & (d > 2); del d
    ay, ax = np.nonzero(allowed); sel = rng.choice(len(ay), size=n_fold, replace=False)
    pr = np.zeros(foot.shape, bool); pr[ay[sel], ax[sel]] = True; preds["random"] = pr; del ay, ax, allowed
    for arm, pred in preds.items():
        c = holdout.score_fold(pred, withheld, fold, known_mask); per_fold[arm].append(c["dti"])
        for (by, bx), tp, fp, K in holdout.blocks_from_components(c): blocks[arm][(name, by, bx)] = (tp, fp, K)
        del c; gc.collect()
        c2 = holdout.score_fold(pred, withheld & low, fold, known_mask)
        for (by, bx), tp, fp, K in holdout.blocks_from_components(c2): sblocks[arm][(name, by, bx)] = (tp, fp, K)
        del c2; gc.collect()
    del preds; gc.collect()
    print(f"fold {name} done {time.time()-t0:.0f}s withheld_low={int((withheld&low).sum())}/{int(withheld.sum())}", flush=True)
pooled, deltas, nb = holdout.bootstrap_from_blocks(blocks, n_boot=1000, seed=82)
spooled, sdeltas, snb = holdout.bootstrap_from_blocks(sblocks, n_boot=1000, seed=83)
json.dump(dict(evaluator="gems82-hide-v1", pooled=pooled, paired_deltas=deltas,
               lowslope_stratified_pooled=spooled, lowslope_deltas=sdeltas, per_fold_dti=per_fold,
               seconds=time.time()-t0), open("evidence/e2_holdout.json","w"), indent=2)
print("POOLED", json.dumps(pooled, indent=2)); print("DELTAS", json.dumps(deltas, indent=2))
print("LOWSLOPE", json.dumps(spooled, indent=2)); print("LOWSLOPE_DELTAS", json.dumps(sdeltas, indent=2))
