import sys; sys.path.insert(0, "src")
import numpy as np
from gems82 import metric

def test_official_worked_example():
    # Organizer page: TP=3.00 FP=1.89 FN=2.00 -> 0.60
    assert abs(metric.dti_from(3.00, 1.89, 2.00) - 0.6024) < 0.005

def test_exact_vs_bruteforce():
    rng = np.random.default_rng(0)
    truth = np.zeros((30, 30), bool); truth[5:25, 10] = True; truth[8, 20:26] = True
    pred = (rng.random((30, 30)) > 0.9).astype(np.float32) * rng.random((30, 30), dtype=np.float32) if False else (rng.random((30,30))>0.9).astype(np.float32)
    a = metric.components(pred, truth); b = metric.bruteforce(pred, truth)
    assert abs(a["tp"]-b["tp"])<1e-9 and abs(a["fp"]-b["fp"])<1e-9 and abs(a["dti"]-b["dti"])<1e-9

def test_perfect_and_empty():
    t = np.zeros((20,20), bool); t[3:9, 7] = True
    assert metric.components(t.astype(np.float32), t)["dti"] > 0.999
    assert metric.components(np.zeros((20,20), np.float32), t)["dti"] == 0.0

def test_marginal_bar():
    assert abs(metric.marginal_bar(0.2708) - 0.05416) < 1e-9

def test_known_mask_pixel_exact():
    t = np.zeros((20,20), bool); t[10, 5:15] = True
    p = t.astype(np.float32)
    c = metric.components(p, t, known=t)
    assert c["n_truth"] == 0  # all truth masked as known
