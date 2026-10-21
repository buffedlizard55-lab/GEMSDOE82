"""Duplicate-guard math on synthetic masks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from gems82 import registry_check as RC


def test_identical_is_duplicate():
    rng = np.random.default_rng(0)
    a = rng.random((200, 200)) < 0.05
    r = RC.check_vs_registry(a, {"same": a.copy()})
    assert r["duplicate"] is True
    assert r["per_ref"]["same"]["spearman_rho"] > 0.99
    assert r["per_ref"]["same"]["overlap_3px"] == 1.0


def test_independent_is_clean():
    rng = np.random.default_rng(1)
    a = rng.random((300, 300)) < 0.02
    b = rng.random((300, 300)) < 0.02
    r = RC.check_vs_registry(a, {"other": b})
    assert r["duplicate"] is False
    assert r["per_ref"]["other"]["overlap_3px"] < 0.70


def test_shifted_overlap_counts():
    a = np.zeros((100, 100), bool)
    a[50, 50] = True
    b = np.zeros((100, 100), bool)
    b[50, 52] = True  # 2 px away -> within 3 px
    assert RC.overlap_within_3px(a, b) == 1.0
    c = np.zeros((100, 100), bool)
    c[10, 10] = True
    assert RC.overlap_within_3px(a, c) == 0.0
