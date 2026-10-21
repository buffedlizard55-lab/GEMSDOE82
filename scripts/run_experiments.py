#!/usr/bin/env python3
"""Run the three preregistered H82 experiments and write machine-readable receipts.

This script is deliberately the only experiment runner for the session.  It
uses the shared feature builder and shared hide-and-recover evaluator; no
candidate is selected by a leaderboard projection.
"""
from __future__ import annotations

import gc
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gemsdoe82 import evaluate_holdout, feature_stack  # noqa: E402

BUDGET = 37_654
EXPERIMENTS = ("H82-A", "H82-B", "H82-C")


def main() -> int:
    footprint, catalogue, bands, grid_metadata = feature_stack.read_grid_inputs()
    folds = evaluate_holdout.build_folds(catalogue, footprint)
    cache = ROOT / ".cache" / "gemsdoe82"
    cache.mkdir(parents=True, exist_ok=True)
    receipt = {
        "evidence_class": "HOLDOUT-DTI",
        "session_limit": {"maximum_experiments": 3, "experiments_run": list(EXPERIMENTS)},
        "grid": grid_metadata,
        "holdout": {
            "evaluator_version": evaluate_holdout.VERSION,
            "folds": [
                {
                    "name": fold.name,
                    "withheld_components": fold.withheld_components,
                    "withheld_positive_pixels": int(fold.truth.sum()),
                    "visible_catalogue_pixels": int(fold.visible.sum()),
                    "feature_visible_pixels": int(fold.feature_visible.sum()),
                    "active_pixels": int(fold.active.sum()),
                    "buffer_px": evaluate_holdout.BUFFER_PX,
                    "domain_erosion_px": evaluate_holdout.DOMAIN_EROSION_PX,
                }
                for fold in folds
            ],
        },
        "candidates": {},
    }
    for candidate_id in EXPERIMENTS:
        builder = feature_stack.BUILDERS[candidate_id]
        surface, surface_meta = builder(bands, footprint)
        surface_path = cache / f"{candidate_id.lower()}_surface.npy"
        np.save(surface_path, surface)
        canary_fields = {
            "surface": surface,
            **{name: bands[name] for name in surface_meta.get("layers", []) if name in bands},
        }
        canaries = evaluate_holdout.canary_report(canary_fields, folds)
        if any(item["suspicious"] for item in canaries.values()):
            raise RuntimeError(f"LEAKAGE CANARY STOP for {candidate_id}: {canaries}")
        evaluation = evaluate_holdout.evaluate_surface(
            surface,
            folds,
            budget=BUDGET,
            buffer_px=evaluate_holdout.BUFFER_PX,
            seed=8203,
            draws=2000,
        )
        evaluation.pop("predictions", None)
        receipt["candidates"][candidate_id] = {
            "surface_metadata": surface_meta,
            "surface_cache": str(surface_path.relative_to(ROOT)),
            "canaries": canaries,
            "holdout": evaluation,
        }
        print(candidate_id, json.dumps(receipt["candidates"][candidate_id]["holdout"]["pooled"], indent=2), flush=True)
        del surface, canary_fields, canaries, evaluation
        gc.collect()
    ranked = sorted(
        receipt["candidates"],
        key=lambda name: receipt["candidates"][name]["holdout"]["pooled"]["dti"],
        reverse=True,
    )
    receipt["ranking"] = ranked
    receipt["best_candidate"] = ranked[0]
    receipt["interpretation"] = (
        "The ranking is HOLDOUT-DTI only. It is not an organizer score, not a projection, "
        "and does not authorize a weekly submission slot."
    )
    out = ROOT / "evidence" / "experiments.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}; best candidate by HOLDOUT-DTI: {ranked[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
