#!/usr/bin/env python3
"""Compare a candidate against the available public owner-repository rasters.

The standing lane gate is deliberately literal: a candidate is a duplicate if
any scanned registry raster has sampled full-footprint Spearman correlation
above 0.90, or if more than 70% of candidate dots are within 3 pixels of its
dots.  This is an owner-repository inventory, not an organizer-complete
registry; missing/private rasters remain an irregularity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage, stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gemsdoe82.paths import SHAPE  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_candidate(path: Path) -> tuple[np.ndarray, object, object]:
    with rasterio.open(path) as src:
        if src.count != 1 or src.shape != SHAPE:
            raise ValueError(f"candidate is not the competition grid: {path}")
        return src.read(1, masked=False).astype(np.float32), src.crs, src.transform


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", type=Path)
    ap.add_argument("--root", action="append", type=Path, default=[])
    ap.add_argument("--sample", type=Path, default=ROOT / ".cache/gems_data/core/sample_submission.tif")
    ap.add_argument("--out", type=Path, default=ROOT / "evidence/uniqueness.json")
    ap.add_argument("--phase", choices=("surface", "final dots"), default="final dots")
    args = ap.parse_args()
    candidate, crs, transform = load_candidate(args.candidate)
    with rasterio.open(args.sample) as ref:
        footprint = np.isfinite(ref.read(1, masked=False))
        if ref.shape != candidate.shape or ref.crs != crs or ref.transform != transform:
            raise ValueError("candidate/sample grid mismatch")
    candidate_positive = footprint & (candidate > 0)
    candidate_count = int(candidate_positive.sum())
    reports = []
    seen: set[Path] = set()
    skipped = []
    for root in args.root:
        if not root.exists():
            skipped.append({"root": str(root), "reason": "not found"})
            continue
        for path in sorted(root.rglob("*.tif")):
            resolved = path.resolve()
            if resolved in seen or resolved == args.candidate.resolve() or path.name == args.candidate.name:
                continue
            seen.add(resolved)
            lower = str(path).lower()
            if any(token in lower for token in ("sample_submission", "example_submission", "existing_faults", "labels.tif", "training_features")):
                continue
            try:
                with rasterio.open(path) as src:
                    if src.count != 1 or src.shape != candidate.shape or src.crs != crs or src.transform != transform:
                        skipped.append({"path": str(path), "reason": "not matching single-band competition grid"})
                        continue
                    prior = src.read(1, masked=False).astype(np.float32)
            except Exception as exc:
                skipped.append({"path": str(path), "reason": f"read error: {exc}"})
                continue
            prior_positive = footprint & np.isfinite(prior) & (prior > 0)
            if not prior_positive.any():
                skipped.append({"path": str(path), "reason": "no positive support"})
                continue
            distance = ndimage.distance_transform_edt(~prior_positive)
            near_fraction = float((distance[candidate_positive] <= 3.0).mean()) if candidate_count else 0.0
            exact_intersection = int((candidate_positive & prior_positive).sum())
            union = int((candidate_positive | prior_positive).sum())
            sample_ids = np.flatnonzero(footprint)
            if len(sample_ids) > 250_000:
                rng = np.random.default_rng(82082)
                sample_ids = rng.choice(sample_ids, size=250_000, replace=False)
            a = candidate.ravel()[sample_ids]
            b = np.where(np.isfinite(prior.ravel()[sample_ids]), prior.ravel()[sample_ids], 0.0)
            spearman = float(stats.spearmanr(a, b).statistic)
            reports.append({
                "path": str(path),
                "sha256": sha256(path),
                "candidate_dots": candidate_count,
                "registry_dots": int(prior_positive.sum()),
                "within_3px_fraction_of_candidate_dots": near_fraction,
                "exact_jaccard": float(exact_intersection / union) if union else 1.0,
                "spearman_sampled_full_footprint": spearman,
                "rank_correlation_fires": bool(np.isfinite(spearman) and spearman > 0.90),
                "overlap_fires": bool(near_fraction > 0.70),
                "duplicate": bool((np.isfinite(spearman) and spearman > 0.90) or near_fraction > 0.70),
            })
    max_rank = max((item["spearman_sampled_full_footprint"] for item in reports), default=float("nan"))
    max_overlap = max((item["within_3px_fraction_of_candidate_dots"] for item in reports), default=float("nan"))
    result = {
        "evidence_class": "SURFACE-UNIQUENESS-REGISTRY-CHECK-NOT-ORGANIZER-COMPLETE",
        "candidate": str(args.candidate),
        "candidate_sha256": sha256(args.candidate),
        "candidate_positive_pixels": candidate_count,
        "phase": args.phase,
        "thresholds": {"rank_correlation_gt": 0.90, "candidate_dots_within_3px_gt": 0.70},
        "scanned_rasters": len(reports),
        "max_spearman_sampled_full_footprint": max_rank,
        "max_within_3px_fraction": max_overlap,
        "duplicate": any(item["duplicate"] for item in reports),
        "unique_within_scanned_inventory": not any(item["duplicate"] for item in reports),
        "reports": sorted(reports, key=lambda item: max(item["within_3px_fraction_of_candidate_dots"], abs(item["spearman_sampled_full_footprint"])), reverse=True),
        "skipped": skipped,
        "irregularity": "The scan covers only rasters available under the supplied local roots; it cannot clear private, deleted, or uncommitted files.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 2 if result["duplicate"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
