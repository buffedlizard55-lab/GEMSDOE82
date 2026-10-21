#!/usr/bin/env python3
"""Build the unique H82-B candidate after the three-experiment holdout gate.

This performs no new model experiment and spends no organizer submission slot.
It only packages the best preregistered surface from ``evidence/experiments.json``
using the shared fail-closed writer.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gemsdoe82 import evaluate_holdout, feature_stack  # noqa: E402
from gemsdoe82.paths import downloads_dir  # noqa: E402
from gemsdoe82.submission_writer import write_submission  # noqa: E402

BUDGET = 37_654
SUBMISSION_NAME = "GEMSDOE82-H82B-20261021"
NOTE = "H82-B signed curvature discordance; 37654 dots; HOLDOUT-DTI 0.01393 [0.00995,0.01829]; local validation only"


def main() -> int:
    experiment_path = ROOT / "evidence" / "experiments.json"
    if not experiment_path.exists():
        raise FileNotFoundError("Run scripts/run_experiments.py before building the artifact")
    experiments = json.loads(experiment_path.read_text(encoding="utf-8"))
    best = experiments["best_candidate"]
    if best != "H82-B":
        raise RuntimeError(f"Unexpected best candidate {best}; this script is frozen for the recorded top candidate")
    surface_path = ROOT / experiments["candidates"][best]["surface_cache"]
    surface = np.load(surface_path).astype(np.float32, copy=False)
    footprint, catalogue, _, grid_metadata = feature_stack.read_grid_inputs()
    allowed = footprint & (ndimage.distance_transform_edt(~catalogue) > float(evaluate_holdout.BUFFER_PX))
    prediction = evaluate_holdout.emit_top(surface, allowed, BUDGET)
    digest = hashlib.sha256(np.packbits(prediction > 0.5).tobytes()).hexdigest()[:12]
    output = downloads_dir() / f"gemsdoe82-h82b-signed-curvature-37654-20261021-{digest}-SUBMIT.tif"
    holdout = experiments["candidates"][best]["holdout"]
    metadata = {
        "hypothesis": "H82-B",
        "mechanism": "Signed multi-physics curvature discordance across magnetic RTP, gravity, basement depth and conductivity, gated by weak detrended-elevation curvature.",
        "named_non_fault_mimic": "lithologic contacts and processing edge artifacts can create coincident geophysical curvature without a fault",
        "holdout": holdout,
        "canaries": experiments["candidates"][best]["canaries"],
        "grid": grid_metadata,
        "emission": {"budget": BUDGET, "catalogue_buffer_px": evaluate_holdout.BUFFER_PX, "positive_pixels": int((prediction > 0).sum())},
        "selection": "Best of exactly three preregistered H82 experiments by HOLDOUT-DTI; no organizer slot used; selector remains negative because no comparison to a current in-repository holdout incumbent was passed.",
        "surface_bitpack_sha12": digest,
    }
    receipt = write_submission(
        prediction,
        feature_stack.data_dir() / "sample_submission.tif",
        footprint,
        output,
        submission_name=SUBMISSION_NAME,
        note=NOTE,
        catalogue=catalogue,
        metadata=metadata,
    )
    print(json.dumps(receipt, indent=2, allow_nan=False))
    print(f"download={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
