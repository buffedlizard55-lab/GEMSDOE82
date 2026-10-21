#!/usr/bin/env python3
"""E1 (experiment 1/3): leakage canary + hide-and-recover holdout for H82-1 blind-step lane.
Arms at matched mass per fold: blind_thin, scarp_control_thin, gravonly_thin, random.
Outputs evidence/e1_canary.json, evidence/e1_holdout.json; caches surfaces to .cache/."""
import json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, "src")
from gems82 import grid, surface as surf, emission, holdout, metric
from sklearn.metrics import roc_auc_score

ROOT = Path("."); CACHE = ROOT / ".cache"; CACHE.mkdir(exist_ok=True)
t0 = time.time()
foot, prof = grid.load_template("data/sample_submission.tif")
labels = grid.load_labels("data/labels.tif", foot)
print(f"footprint={int(foot.sum())} catalogue={int(labels.sum())}", flush=True)
S = surf.build_surfaces("data/training_features.tif", foot)
for k, v in S.items(): np.save(CACHE / f"{k}.npy", v)
np.save(CACHE / "foot.npy", foot); np.save(CACHE / "labels.npy", labels)
print(f"surfaces built {time.time()-t0:.0f}s", flush=True)

folds = holdout.quadrant_folds(foot.shape, buffer_px=30)
DENSITY = 37654 / int(foot.sum())  # matched-mass reference density (H33 mass, for comparability)
rng = np.random.default_rng(82)
arms_surf = {"blind_thin": S["s_blind"], "scarp_control_thin": S["s_scarp_control"], "gravonly_thin": S["grav_step"]}
results = {a: [] for a in list(arms_surf) + ["random"]}
canary_y, canary_X = [], {k: [] for k in ["grav_step","rtp_step","depth_step","cond_step","strike_agree","slope_unit","core_geomean","s_blind","s_scarp_control"]}
for name, fold in folds.items():
    withheld = labels & fold
    visible = labels & ~fold
    # visible must exclude buffer ring too: anything in fold-extended area is not visible.
    # fold already eroded; buffer-ring catalogue pixels are neither truth nor visible-scored:
    # mask them as known so they cannot earn FP/TP either way.
    from scipy.ndimage import binary_dilation
    ring = binary_dilation(fold, iterations=30) & ~fold
    known_mask = (labels & ~fold)  # includes ring catalogue pixels -> pixel-exact masked. correct.
    n_fold = int(round(DENSITY * int((fold & foot).sum())))
    print(f"fold {name}: withheld={int(withheld.sum())} n_emit={n_fold}", flush=True)
    for arm, s in arms_surf.items():
        pred = holdout.emit_in_fold(s, fold, foot, visible, n_fold,
                                    lambda su, al, n: emission.thin_topn(su, al, n, spacing=2))
        results[arm].append(holdout.score_fold(pred, withheld, fold, known_mask))
    # random control: uniform allowed pixels
    from scipy.ndimage import distance_transform_edt
    d = distance_transform_edt(~visible); allowed = fold & foot & (d > 2)
    ay, ax = np.nonzero(allowed); sel = rng.choice(len(ay), size=n_fold, replace=False)
    pred = np.zeros(foot.shape, bool); pred[ay[sel], ax[sel]] = True
    results["random"].append(holdout.score_fold(pred, withheld, fold, known_mask))
    # canary samples: all withheld positives + 5x random fold negatives
    py, px = np.nonzero(withheld)
    ny, nx = np.nonzero(fold & foot & ~labels); nsel = rng.choice(len(ny), size=min(5*len(py), len(ny)), replace=False)
    ys = np.concatenate([py, ny[nsel]]); xs = np.concatenate([px, nx[nsel]])
    canary_y.append(np.concatenate([np.ones(len(py)), np.zeros(len(nsel))]))
    for k in canary_X: canary_X[k].append(S[k][ys, xs])
    print(f"  done {time.time()-t0:.0f}s", flush=True)

y = np.concatenate(canary_y); canary = {}
for k, v in canary_X.items():
    x = np.concatenate(v); auc = float(roc_auc_score(y, x))
    canary[k] = dict(auc=auc, max_auc_or_inverse=max(auc, 1-auc), leakage_flag=bool(max(auc, 1-auc) > 0.90))
pooled, deltas, nb = holdout.block_bootstrap_ci(results, n_boot=1000, seed=82)
per_fold = {a: [c["dti"] for c in results[a]] for a in results}
ev = ROOT / "evidence"; ev.mkdir(exist_ok=True)
json.dump(dict(evaluator="gems82-hide-v1 quadrants buf30 pooled-DTI a.2 b.8 R3px",
               n_withheld_total=int(sum(c["n_truth"] for c in results["blind_thin"])),
               canary_n_pos=int(y.sum()), canary_n=int(len(y)), canary=canary),
          open(ev / "e1_canary.json", "w"), indent=2)
json.dump(dict(evaluator="gems82-hide-v1", density=DENSITY, pooled=pooled, paired_deltas=deltas,
               per_fold_dti=per_fold, n_bootstrap_blocks=nb, seconds=time.time()-t0),
          open(ev / "e1_holdout.json", "w"), indent=2)
print(json.dumps(pooled, indent=2)); print(json.dumps(deltas, indent=2)); print("CANARY", json.dumps(canary, indent=2))
