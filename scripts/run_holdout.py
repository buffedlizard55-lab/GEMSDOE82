"""Evaluate one or more boolean masks (or .tif paths) on both holdout instruments.

Usage:
  python3 scripts/run_holdout.py --data-dir data --mask-tif a.tif --mask-tif b.tif --out evidence/holdout.json
  python3 scripts/run_holdout.py --data-dir data --mask-npy mask.npy --name my-mask --out evidence/x.json

All numbers are HOLDOUT-DTI with 95% CI. A projection is never written as a score.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems82 import grid as G
from gems82.holdout import evaluate_candidate, load_holdout_context

EVALUATOR_VERSION = ("gems82-holdout-v2 (sgmc-far moat>6 PRIMARY + sgmc-mid moat>3 + "
                     "sgmc-offcat raw, pooled+quad DTI; cat-hidden 4q x 2draw diagnostic)")


def load_mask(spec: str) -> tuple[str, np.ndarray]:
    p = Path(spec)
    if p.suffix == ".npy":
        return p.stem, np.load(p).astype(bool)
    return p.stem, G.read_binary_mask(p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--mask-tif", action="append", default=[])
    ap.add_argument("--mask-npy", action="append", default=[])
    ap.add_argument("--name", action="append", default=[])
    ap.add_argument("--out", default="evidence/holdout.json")
    args = ap.parse_args()
    specs = list(args.mask_tif) + list(args.mask_npy)
    if not specs:
        print("no masks given")
        return 2
    print("loading holdout context...", flush=True)
    ctx = load_holdout_context(args.data_dir)
    print(f"foot={ctx.foot.sum()} labels={ctx.labels.sum()} sgmc_off={ctx.n_sgmc_truth} "
          f"cells={len(ctx.cells)}", flush=True)
    out = {"evaluator": EVALUATOR_VERSION, "results": []}
    for i, spec in enumerate(specs):
        stem, m = load_mask(spec)
        name = args.name[i] if i < len(args.name) else stem
        r = evaluate_candidate(m, ctx, name=name)
        r["n_withheld_positives_cat_hidden"] = sum(c["n_truth"] for c in ctx.cells)
        out["results"].append(r)
        print(f"[{name}] n={r['sgmc_far']['n_emitted']} "
              f"oncat={r['sgmc_far']['n_on_catalogue']}", flush=True)
        for key in ("sgmc_far", "sgmc_mid", "sgmc_offcat"):
            s = r[key]
            print(f"  {key:11s} pooled={s['pooled_dti']:.6f} tp={s['tp']:.1f} "
                  f"fp={s['fp']:.1f} K={s['n_truth']} quad_mean={s['quad_mean']:.6f} "
                  f"CI95=±{s['ci95_half']:.6f}", flush=True)
        ch = r["cat_hidden"]
        print(f"  cat_hidden  pooled={ch['pooled_dti']:.6f} tp={ch['tp']:.1f} "
              f"fp={ch['fp']:.1f} K={ch['n_truth']} cell_mean={ch['cell_mean']:.6f} "
              f"CI95=±{ch['ci95_half']:.6f}", flush=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1, default=str))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
