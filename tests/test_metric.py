import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from gemsdoe82 import metric  # noqa: E402


def test_distance_transform_matches_literal_oracle():
    pred = np.zeros((15, 15), dtype=np.float32)
    pred[5, 5] = 1.0
    pred[8, 9] = 0.4
    truth = np.zeros_like(pred, dtype=bool)
    truth[5, 7] = True
    truth[10, 10] = True
    exact = metric.dti_exact(pred, truth)
    oracle = metric.brute_force(pred, truth)
    np.testing.assert_allclose([exact["tp"], exact["fp"], exact["fn"], exact["dti"]], [oracle["tp"], oracle["fp"], oracle["fn"], oracle["dti"]], rtol=1e-12, atol=1e-12)


def test_range_is_fail_closed():
    pred = np.zeros((3, 3), dtype=np.float32)
    pred[0, 0] = np.nan
    truth = np.zeros((3, 3), dtype=bool)
    truth[1, 1] = True
    try:
        metric.dti_exact(pred, truth)
    except ValueError as exc:
        assert "finite" in str(exc)
    else:
        raise AssertionError("NaN prediction was not rejected")
