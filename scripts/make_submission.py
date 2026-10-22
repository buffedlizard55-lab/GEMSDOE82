"""Build a lane-local research artifact and record its internal gate checks.

This utility is not the canonical shared submission writer and does not
authorize a competition upload. It writes candidate bytes and local audit
receipts for inspection. A separate selector authorization, bound to the exact
SHA-256, is required before any site may say OK TO SUBMIT. Its gate result is
RESEARCH_GATE_PASS or RESEARCH_GATE_NEGATIVE, never submission promotion.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems82 import grid as G
from gems82 import holdout as H
from gems82 import registry_check as RC
from gems82 import submission as SUB

SLUG = "gems82-h82-antislope-corroborated"
NOTE = ("GEMSDOE82 H82 antislope+conjugate corroborated surgery+addition on H33-2-B2 "
        "base; UNSCORED; see receipt")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--mask", default="work/exp3_added.npy")
    ap.add_argument("--pipeline", default="evidence/pipeline.json")
    ap.add_argument("--gate", default="registry/slot_gate.json")
    ap.add_argument("--out-dir", default="docs/downloads")
    ap.add_argument("--stamp", default="")
    args = ap.parse_args()
    stamp = args.stamp or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ddir = Path(args.data_dir)

    gate = json.loads(Path(args.gate).read_text())
    pipe = json.loads(Path(args.pipeline).read_text())
    ctx = H.load_holdout_context(ddir)
    foot = ctx.foot
    labels = ctx.labels
    mask = np.load(args.mask).astype(bool)
    assert mask.shape == (G.HEIGHT, G.WIDTH)
    assert (mask & ~foot).sum() == 0, "dots outside footprint"
    assert (mask & labels).sum() == 0, "dots on catalogue"

    base_far = gate["base_holdout_dti"]["sgmc_far_pooled"]
    base_mid = gate["base_holdout_dti"]["sgmc_mid_pooled"]
    base_raw = gate["base_holdout_dti"]["sgmc_offcat_pooled"]
    r = H.evaluate_candidate(mask, ctx, name="gems82-candidate")
    base_mask = G.read_binary_mask(ddir / "registry" / "h33-2-b2-37654-nan.tif")
    rb = H.evaluate_candidate(base_mask, ctx, name="h33-2-b2-base")
    exp3q = r["sgmc_far"]["per_quadrant"]
    baseq = rb["sgmc_far"]["per_quadrant"]
    qpos = sum(exp3q[q] >= baseq[q] - 1e-12 for q in baseq)

    m_far = r["sgmc_far"]["pooled_dti"] - base_far
    m_mid = r["sgmc_mid"]["pooled_dti"] - base_mid
    m_raw = r["sgmc_offcat"]["pooled_dti"] - base_raw
    _s1 = pipe["experiments"]["exp1"]["live_safety"]
    _s2 = pipe["experiments"]["exp2"]["live_safety"]
    safety = min(s if s is not None else float("inf") for s in (_s1, _s2))
    safety_json = None if safety == float("inf") else safety
    cpd = pipe["experiments"]["exp3"]["screen_credit_per_dot"]
    n_added = pipe["experiments"]["exp3"]["added"]

    # Required protocol screen: candidate surface BEFORE placement and the
    # complete FINAL dot mask against every available registry raster. The
    # full final-mask result is a hard stop, not report-only carrier disclosure.
    data_manifest = json.loads(Path("registry/data_manifest.json").read_text())
    reg_meta = data_manifest.get("registry_rasters", {})
    reg_entries = [
        item for item in data_manifest.get("lane82_mirror_inputs", [])
        if item.get("id", "").startswith("reg_")
    ]
    reg = {}
    for item in reg_entries:
        p = ddir / item["path"]
        if p.exists():
            reg[item["id"][4:]] = G.read_binary_mask(p)
    from scipy.stats import rankdata
    C = np.load(Path("work/corroboration_C.npy"))
    add = np.load(Path("work/exp3_addmask.npy"))
    foot_s = foot[::3, ::3]
    lane = {}
    for name, ref in reg.items():
        a = C[::3, ::3][foot_s].astype(float)
        b = ref[::3, ::3][foot_s].astype(float)
        ra = rankdata(a) - len(a) / 2
        rb = rankdata(b) - len(b) / 2
        rho = float((ra * rb).sum() / np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
        ov = RC.overlap_within_3px(add, ref)
        lane[name] = dict(surface_rho=rho, added_overlap_3px=ov,
                          duplicate=bool(rho > 0.90 or ov > 0.70))
    dup_full = RC.check_vs_registry(mask, reg)
    # Registry completeness must be explicitly certified in the shared
    # manifest. A convenient partial list is not a complete duplicate screen.
    expected_registry_count = reg_meta.get("expected_count")
    registry_complete = (
        reg_meta.get("status") == "complete"
        and isinstance(expected_registry_count, int)
        and len(reg) == expected_registry_count == len(reg_entries)
    )
    n_removed = int(base_mask.sum() - (base_mask & mask).sum())
    novel_frac = float((n_removed + int(add.sum())) / int(mask.sum()))

    duplicate_pass = RC.lane_independence_pass(
        lane, dup_full, len(reg), expected_registry_count=expected_registry_count
    )
    if not duplicate_pass:
        stop_card = {
            "verdict": "DUPLICATE_OR_INCOMPLETE_REGISTRY — STOP BEFORE TIFF WRITING",
            "surface_screen": lane,
            "final_dot_screen": dup_full,
            "registry_complete": registry_complete,
            "registry_expected_count": expected_registry_count,
            "registry_observed_count": len(reg),
            "note": "Protocol requires surface screening before placement and complete final-dot screening; no candidate TIFF was written by this run.",
        }
        Path("evidence/duplicate_screen.json").write_text(json.dumps(stop_card, indent=1))
        print(stop_card["verdict"], "-> evidence/duplicate_screen.json", flush=True)
        return 2

    r5 = bool(safety >= 2.0 and ((n_added <= 1500 and cpd >= 0.111) or (n_added <= 1000 and cpd >= 0.05556) or n_added == 0))
    verdict = {
        "R1_primary_win": bool(m_far >= 0.0005),
        "R2_quadrant_consistency": bool(qpos >= 3),
        "R3_no_loss_mid": bool(m_mid >= -0.001),
        "R4_no_loss_raw": bool(m_raw >= -0.001),
        "R5_live_safety": r5,
        "R6a_lane_independence": duplicate_pass,
    }
    print(f"margins: far={m_far:+.6f} mid={m_mid:+.6f} raw={m_raw:+.6f} quads_pos={qpos}/4 "
          f"safety={safety} cpd={cpd:.4f} n_added={n_added}", flush=True)
    print("R6a lane:", {k: (round(v['surface_rho'], 4), round(v['added_overlap_3px'], 4)) for k, v in lane.items()}, flush=True)
    print("R6b carrier:", {k: (round(v['spearman_rho'], 4), round(v['overlap_3px'], 4)) for k, v in dup_full["per_ref"].items()},
          "novel_frac=", round(novel_frac, 4), flush=True)
    dup = {"surface_screen": lane, "final_dot_screen": dup_full["per_ref"],
           "registry_complete": registry_complete,
           "registry_expected_count": expected_registry_count,
           "registry_observed_count": len(reg),
           "n_removed_vs_base": n_removed, "n_added": int(add.sum()),
           "novel_fraction": novel_frac}

    slug = f"{SLUG}-{stamp}"
    content8 = G.sha256(args.mask)[:8] if False else None
    # content digest from mask bytes (stable id)
    import hashlib
    content8 = hashlib.sha256(np.packbits(mask).tobytes()).hexdigest()[:8]
    slug = f"{SLUG}-{mask.sum()}-{stamp}-{content8}"
    receipts = SUB.write_submission_pair(mask, foot, labels, ddir / "sample_submission.tif",
                                         out_dir, slug)
    verdict["R7_audit"] = True  # write_submission_pair raises unless 12/12 pass
    zp = out_dir / f"{slug}-zeros.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out_dir / f"{slug}-zeros.tif", arcname=f"{slug}-zeros.tif")
    promoted = all(verdict.values())
    gate_out = {
        "slug": slug, "stamp_utc": stamp, "submission_note": NOTE,
        "margins": {"sgmc_far": m_far, "sgmc_mid": m_mid, "sgmc_offcat": m_raw,
                    "quadrants_positive": qpos},
        "live_safety": safety_json,
        "live_safety_note": "infinite (zero measured MID-credit cost)" if safety_json is None else "",
        "screen_credit_per_dot": cpd, "n_added": n_added,
        "duplicate_guard": dup, "rules": verdict,
        "verdict": "RESEARCH_GATE_PASS" if promoted else "RESEARCH_GATE_NEGATIVE",
        "receipts": receipts,
        "raster_sha256_zeros": receipts["zeros"]["sha256"],
        "zip": {"filename": zp.name, "size_bytes": zp.stat().st_size,
                "sha256": G.sha256(zp)},
        "holdout": {k: {kk: vv[kk] for kk in ("pooled_dti", "tp", "fp", "n_truth", "quad_mean", "ci95_half", "per_quadrant") if kk in vv} for k, vv in r.items() if k != "name"},
    }
    Path("evidence/gate.json").write_text(json.dumps(gate_out, indent=1, default=str))
    (out_dir / f"checks-{slug}-zeros.tif.json").write_text(json.dumps(receipts["zeros"], indent=1))
    (out_dir / f"checks-{slug}-nan.tif.json").write_text(json.dumps(receipts["nan"], indent=1))
    manifest = {"slug": slug, "verdict": gate_out["verdict"], "note": NOTE,
                "files": [f"{slug}-zeros.tif", f"{slug}-nan.tif", f"{slug}-zeros.zip"]}
    (out_dir / "submissions_manifest.json").write_text(json.dumps(manifest, indent=1))
    print("slug:", slug, flush=True)
    print("verdict:", gate_out["verdict"], verdict, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
