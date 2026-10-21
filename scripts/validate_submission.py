#!/usr/bin/env python3
"""Independently re-open and validate one generated GeoTIFF."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gemsdoe82.feature_stack import read_grid_inputs  # noqa: E402
from gemsdoe82.submission_writer import validate_submission  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tif", type=Path)
    args = ap.parse_args()
    footprint, catalogue, _, _ = read_grid_inputs()
    from gemsdoe82.paths import data_dir
    report = validate_submission(args.tif, data_dir() / "sample_submission.tif", footprint, catalogue)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
