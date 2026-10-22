"""Grid constants + quadrant sanity (no data files needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from gems82 import grid as G
from gems82.holdout import quadrant_ids


def test_constants():
    assert (G.HEIGHT, G.WIDTH) == (3730, 3292)
    assert G.TOTAL_PIXELS == 3730 * 3292 == 12279160
    assert G.FOOTPRINT_PIXELS == 5167373
    assert G.CRS == "EPSG:32611"
    assert G.TRANSFORM == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def test_quadrants_partition_footprint():
    rng = np.random.default_rng(0)
    foot = rng.random((200, 160)) < 0.7
    q = quadrant_ids(foot)
    assert set(np.unique(q[foot])).issubset({0, 1, 2, 3})
    assert (q[~foot] == -1).all()
    assert all((q[foot] == f).sum() > 100 for f in range(4))
