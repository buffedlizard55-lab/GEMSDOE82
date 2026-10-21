import sys; sys.path.insert(0, "src")
import numpy as np
from gems82 import grid

def test_writer_zeros_roundtrip(tmp_path):
    foot, prof = grid.load_template("data/sample_submission.tif")
    labels = grid.load_labels("data/labels.tif", foot)
    m = np.zeros((grid.H, grid.W), np.float32); m[100, 100] = 1.0
    if not foot[100,100]: m[100,100] = 0.0
    p = grid.write_submission(m, foot, prof, tmp_path/"t.tif", outside="zeros")
    r = grid.validate(p, foot, labels=None, mode="zeros")
    assert r["all_passed"] and r["min_in"] >= 0 and r["max_in"] <= 1
