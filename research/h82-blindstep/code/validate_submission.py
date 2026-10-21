#!/usr/bin/env python3
"""Standalone portal validator: python scripts/validate_submission.py <tif> [zeros|nan]"""
import json, sys
sys.path.insert(0, "src")
from gems82 import grid
foot, _ = grid.load_template("data/sample_submission.tif")
labels = grid.load_labels("data/labels.tif", foot)
print(json.dumps(grid.validate(sys.argv[1], foot, labels, sys.argv[2] if len(sys.argv) > 2 else "zeros"), indent=2))
