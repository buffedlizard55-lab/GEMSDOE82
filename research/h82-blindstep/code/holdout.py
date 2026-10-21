"""Hide-and-recover holdout (parallel-run protocol §2).

Four quadrant folds, 30-px buffer excluded from scoring. Withheld truth = catalogue pixels in
the fold interior; visible catalogue = everything outside fold+buffer. The H82-1 surface is
label-free; the ONLY catalogue-derived object is the emission exclusion (d_visible > 2 px),
derived per fold from visible faults only. Visible faults are masked pixel-exactly in scoring.
Pooled DTI sums TP/FP/FN components across folds (alpha .2 beta .8, R=3px). CIs: 50-px block
bootstrap of per-block (tp, fp, fn=K_block - tp_block) contributions, paired across arms.
LIMITATION (disclosed): truth is the visible catalogue, which is surface-biased; a blind-fault
detector is therefore graded on the population it least targets. A catalogue-holdout pass
licenses packaging, never a leaderboard claim (cf. GEMSDOE32 IR-32-PROXY-01).
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import distance_transform_edt
from . import metric

def quadrant_folds(shape, buffer_px=30):
    H, W = shape; hy, hx = H // 2, W // 2; folds = {}
    quads = dict(NW=(slice(0, hy), slice(0, hx)), NE=(slice(0, hy), slice(hx, W)),
                 SW=(slice(hy, H), slice(0, hx)), SE=(slice(hy, H), slice(hx, W)))
    for name, (ys, xs) in quads.items():
        inner = np.zeros(shape, bool); inner[ys, xs] = True
        # erode by buffer: keep pixels whose distance to outside-fold > buffer
        d = distance_transform_edt(inner)
        folds[name] = inner & (d > buffer_px)
    return folds

def emit_in_fold(surface, fold, foot, visible_cat, n, rule_fn):
    d = distance_transform_edt(~visible_cat)
    allowed = fold & foot & (d > 2)
    return rule_fn(surface, allowed, n)

def score_fold(pred_bool, withheld, valid_fold, visible_cat):
    return metric.components(pred_bool.astype(np.float32), withheld, valid=valid_fold, known=visible_cat)

def block_bootstrap_ci(fold_results, n_boot=1000, seed=82, block=50):
    """fold_results: list of metric.components dicts (with credit/fp maps + truth_mask).
    Resamples 50px blocks (pooled across folds) -> CI for pooled DTI per arm and paired deltas."""
    rng = np.random.default_rng(seed)
    arms = list(fold_results.keys())  # {arm: [components per fold]}
    # per-block (tp, fp, K) for each arm, aligned block list
    blocks = {a: [] for a in arms}
    for fi in range(len(next(iter(fold_results.values())))):
        ref = fold_results[arms[0]][fi]; H, W = ref["credit_map"].shape
        for by in range(0, H, block):
            for bx in range(0, W, block):
                sl = (slice(by, min(by + block, H)), slice(bx, min(bx + block, W)))
                K = float(ref["truth_mask"][sl].sum())
                if K == 0 and all(float(fold_results[a][fi]["fp_map"][sl].sum()) == 0 for a in arms): continue
                for a in arms:
                    c = fold_results[a][fi]
                    blocks[a].append((float(c["credit_map"][sl].sum()), float(c["fp_map"][sl].sum()), K))
    B = {a: np.array(v) for a, v in blocks.items()}; nb = len(B[arms[0]])
    out = {}
    draws = {a: [] for a in arms}
    for _ in range(n_boot):
        sel = rng.integers(0, nb, nb)
        for a in arms:
            tp, fp, K = B[a][sel].sum(axis=0)
            draws[a].append(metric.dti_from(tp, fp, K - tp))
    for a in arms:
        d = np.array(draws[a]); tp, fp, K = B[a].sum(axis=0)
        out[a] = dict(pooled_dti=metric.dti_from(tp, fp, K - tp), ci95=[float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                      tp=float(tp), fp=float(fp), n_truth=int(K))
    deltas = {}
    base = arms[0]
    for a in arms[1:]:
        dd = np.array(draws[base]) - np.array(draws[a])
        deltas[f"{base} - {a}"] = dict(mean=float(dd.mean()), ci95=[float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))])
    return out, deltas, nb

def blocks_from_components(comp, block=50):
    """Per-block (tp, fp, K) rows from one fold's component maps; frees caller to drop maps."""
    cm, fm, tm = comp["credit_map"], comp["fp_map"], comp["truth_mask"]
    H, W = cm.shape; rows = []
    for by in range(0, H, block):
        for bx in range(0, W, block):
            sl = (slice(by, min(by+block, H)), slice(bx, min(bx+block, W)))
            rows.append(((by, bx), float(cm[sl].sum()), float(fm[sl].sum()), float(tm[sl].sum())))
    return rows

def bootstrap_from_blocks(block_rows_by_arm, n_boot=1000, seed=82):
    """block_rows_by_arm: {arm: {(fold,by,bx): (tp,fp,K)}} aligned by key."""
    arms = list(block_rows_by_arm); keys = sorted(block_rows_by_arm[arms[0]])
    keys = [k for k in keys if any(block_rows_by_arm[a][k][1] > 0 or block_rows_by_arm[a][k][2] > 0 for a in arms)]
    B = {a: np.array([block_rows_by_arm[a][k] for k in keys]) for a in arms}
    rng = np.random.default_rng(seed); nb = len(keys); draws = {a: [] for a in arms}
    for _ in range(n_boot):
        sel = rng.integers(0, nb, nb)
        for a in arms:
            tp, fp, K = B[a][sel].sum(axis=0); draws[a].append(metric.dti_from(tp, fp, K - tp))
    out = {}
    for a in arms:
        d = np.array(draws[a]); tp, fp, K = B[a].sum(axis=0)
        out[a] = dict(pooled_dti=metric.dti_from(tp, fp, K - tp),
                      ci95=[float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                      tp=float(tp), fp=float(fp), n_truth=int(K))
    deltas = {}; base = arms[0]
    for a in arms[1:]:
        dd = np.array(draws[base]) - np.array(draws[a])
        deltas[f"{base} - {a}"] = dict(mean=float(dd.mean()), ci95=[float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))])
    return out, deltas, nb
