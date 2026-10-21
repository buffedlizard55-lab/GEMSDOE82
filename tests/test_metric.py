"""Metric verification: fast paths == brute-force oracle; marginal-bar algebra."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pytest

from gems82 import metric as M


def _toy(seed=0):
    rng = np.random.default_rng(seed)
    H = W = 40
    truth = np.zeros((H, W), bool)
    truth[5, 5:35] |= True
    truth[20:30, 20] |= True
    pred = np.zeros((H, W))
    pred[5, 6:34:2] = 1.0
    pred[22:28, 21] = 0.7
    pred[rng.random((H, W)) < 0.002] = 1.0
    return pred, truth


def test_binary_matches_bruteforce():
    pred, truth = _toy()
    fast = M.dti_binary(pred > 0.5, truth)
    slow = M.dti_bruteforce((pred > 0.5).astype(float), truth)
    assert fast["dti"] == pytest.approx(slow["dti"], abs=1e-9)
    assert fast["tp"] == pytest.approx(slow["tp"], abs=1e-9)
    assert fast["fp"] == pytest.approx(slow["fp"], abs=1e-9)


def test_exact_matches_bruteforce_soft():
    pred, truth = _toy()
    fast = M.dti_exact(pred, truth)
    slow = M.dti_bruteforce(pred, truth)
    assert fast["dti"] == pytest.approx(slow["dti"], abs=1e-9)
    assert fast["tp"] == pytest.approx(slow["tp"], abs=1e-9)
    assert fast["fp"] == pytest.approx(slow["fp"], abs=1e-9)


def test_known_masking_excludes_catalogue():
    pred, truth = _toy()
    known = np.zeros_like(truth)
    known[5, 5:35] = True  # mask the horizontal fault out of scoring
    r = M.dti_binary(pred > 0.5, truth, known=known)
    assert r["n_truth"] == int((truth & ~known).sum())
    # predictions ON masked pixels cost nothing: zeroing them changes nothing
    p = (pred > 0.5)
    r2 = M.dti_binary(p & ~known, truth, known=known)
    assert r2["fp"] == pytest.approx(r["fp"], abs=1e-9)
    assert r2["tp"] == pytest.approx(r["tp"], abs=1e-9)
    # masking truth can only remove coverage: remaining FP is >= the FP those
    # same active predictions had when the masked truth still covered them
    r_active_only = M.dti_binary(p & ~known, truth & ~known)
    assert r["fp"] == pytest.approx(r_active_only["fp"], abs=1e-9)


def test_marginal_bar_by_bruteforce():
    # At score s, adding a dot with credit k must help iff k > alpha*s.
    rng = np.random.default_rng(3)
    H = W = 60
    truth = np.zeros((H, W), bool)
    truth[30, 10:50] = True
    pred = np.zeros((H, W))
    pred[30, 12:48:3] = 1.0
    s0 = M.dti_bruteforce(pred, truth)["dti"]
    bar = M.marginal_inclusion_threshold(s0)
    assert 0.0 < bar < 0.2
    # dot exactly on an uncovered truth pixel: k=1 > bar -> must improve
    p1 = pred.copy()
    uncovered = np.argwhere(truth & (pred == 0))[0]
    p1[tuple(uncovered)] = 1.0
    assert M.dti_bruteforce(p1, truth)["dti"] > s0
    # dot 100 px from all truth: k=0 < bar -> must hurt
    p2 = pred.copy()
    p2[0, 0] = 1.0
    assert M.dti_bruteforce(p2, truth)["dti"] < s0


def test_removal_gain_formula():
    tp, dn, alpha = 5073.3, 3891, 0.2
    K, S = 12226.0, 44090.0  # D2.8-like operating point
    D = alpha * S + 0.8 * K  # = T/s identity check below uses exact D
    T = tp
    s = T / (alpha * (T + (S - T)) + 0.8 * K)
    new = M.removal_gain(T, alpha * S + 0.8 * K, dn, 0.0)
    assert new > s  # removing zero-credit mass always helps
