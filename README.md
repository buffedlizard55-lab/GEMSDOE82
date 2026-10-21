# GEMSDOE82 — blind-fault lane for the DOE GEMS Prize (DrivenData #306)

**Read [PROMPT.md](PROMPT.md) first, every session.** Core values: **Maximize P(Win)** ·
**Own the Outcome**. Competition: [DOE GEMS Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
· Live site (GitHub Pages, `docs/`): <https://buffedlizard55-lab.github.io/GEMSDOE82/>

## ⛔ Submission clearance — read this first

| | |
|---|---|
| **Unique file** | [`docs/downloads/gems82-blindstep-line-37654-20261021T221925Z-f73ec641-zeros.tif`](docs/downloads/gems82-blindstep-line-37654-20261021T221925Z-f73ec641-zeros.tif) ([zip](docs/downloads/gems82-blindstep-line-37654-20261021T221925Z-f73ec641-zeros.zip) · [NaN twin](docs/downloads/gems82-blindstep-line-37654-20261021T221925Z-f73ec641-nan.tif) · [receipt](docs/downloads/gems82-blindstep-line-37654-20261021T221925Z-f73ec641-receipt.json)) |
| **Download for inspection** | ✅ **OK** — automated validator re-read the bytes: float32, EPSG:32611, 3730×3292, transform match, 0 NaN inside footprint, all values in [0,1], no nodata tag, 0 on-catalogue. sha256 `cfd9a327…61307` |
| **Submit to DrivenData** | ⛔ **NO — DO NOT SUBMIT.** Verdict **negative**: HOLDOUT-DTI 0.0745 [0.0693, 0.0799] vs random 0.0693 (paired Δ +0.0053, CI includes 0) and below the scarp control 0.0779 (`gems82-hide-v1`, 57,407 withheld). Protocol forbids spending a slot. Slots used: **0**. |
| Unique name / note | `GEMSDOE82-BLINDSTEP-LINE-37654` / `GEMSDOE82 blind-step line 37,654 dots; HOLDOUT-DTI 0.0745 n.s. vs random; DO NOT SUBMIT negative lane` (101/140) |

How a (future, cleared) submission is made, step by step: [docs/executive-summary.html](docs/executive-summary.html).
The portal error *"Predicted values must be in range [0, 1]"* is structurally impossible for the
zeros file (all-finite, `nodata=None`; the error comes from the −3.4e38 sentinel / sentinel nodata tag).

## Why H33-2-B2 leads the group, and can it be beaten? (answer in brief)

H33-2-B2 (brief: 0.2778) is the H19-5 surface after **dot-thinning** (121k→44k px; owner-report
0.1922→0.2600) and a **catalogue-flank prune** (dots ≤2px from mapped faults deleted; 40,199→37,654).
From the organizer's formula, DTI = T/(0.2(T+S−M)+0.8|G|): every unit mass raises the denominator by
exactly 0.2, so a dot helps only if its kernel credit exceeds 0.2·DTI ≈ 0.054. Dense lines and
catalogue-halo dots fall below that bar (one dot already credits truth within 300 m; mapped pixels
are masked and their halo is mapper-saturated). Removing below-bar mass is the whole trick — it is
emission geometry, not new geology. Beating it needs a better *ranking* (~+25% credit/dot for
0.3262 at equal mass). **This lane did not produce that ranking on catalogue holdout** (but see the
low-slope subgroup signal below). No score is claimed for any file here; ORGANIZER-CONFIRMED = none.

## This lane (H82-1) and results

Buried faults missing from the scarp-biased catalogue should step coincidentally in gravity(13) +
RTP(2) + basement depth(15) with shared strike and **low** slope(19). Mimic: buried lithologic
contact. Ranked alternatives H82-2…4: [registry/hypotheses.json](registry/hypotheses.json).

| Experiment | Result (HOLDOUT-DTI, gems82-hide-v1, n=57,407) |
|---|---|
| E1 gradient-step blind | 0.0701 vs random 0.0736, scarp control 0.0779 — **fails**; canary max AUC 0.544 (no leakage) |
| E2 Hessian-line blind | 0.0745 vs random 0.0693 (n.s. overall); **low-slope stratum (n=21,246): 0.0748 vs 0.0556, Δ+0.0190 [+0.0099,+0.0281]** |
| E3 build + uniqueness | Unique: ρ≈0.007, ≤3px overlap ≈19–20% vs H33-2-B2 & dotted-0.26 (gates 0.90/70%) |

Run card: [registry/run_card.json](registry/run_card.json). Evidence: `evidence/e1_*.json`, `e2_holdout.json`.

## Reproduce (CPU, no DrivenData login)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# restore data per scripts/restore_data.py docstring (sha256-pinned mirrors), then:
.venv/bin/python scripts/restore_data.py
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/run_e1.py && .venv/bin/python scripts/run_e2.py
.venv/bin/python scripts/build_submission.py && .venv/bin/python scripts/build_site.py
.venv/bin/python scripts/validate_submission.py docs/downloads/*-zeros.tif zeros
```

## Irregularities flagged

- **IR-82-01** Brief asserts H33-2-B2 = 0.2778; GEMSDOE32's site calls it UNSCORED (projected 0.2747 = model). Treated as OWNER-REPORT pending portal receipt.
- **IR-82-02** No method paragraph/lane was included for GEMSDOE82; lane H82-1 self-assigned & uniqueness-gated.
- **IR-82-03** `labels.tif` and `existing_faults.tif` mirrors are byte-identical (same sha256 in GEMSDOE32 pins too).
- **IR-82-04** Brief leaderboard highs conflict (0.4413 vs 0.3195; GEMSDOE32 read 0.3262 on 2026-10-04). Verify live; none asserted here.
- **IR-82-05** Holdout buffer-ring catalogue pixels inform the exclusion distance (conservative; disclosed in `src/gems82/holdout.py`).

## Limitations & next work (selector/science, in order)

1. Adjudicate the low-slope signal against **off-catalogue truth** (SGMC ≥300m proxy like GEMSDOE70 Instrument B′, or expert labels) — catalogue truth is biased against this lane by construction; until then, no slot.
2. Test **H82-3** (TC-low × conductivity-high line coincidence) — next-ranked, official bands only.
3. Uniqueness registry here covers 2 rasters (H33 + dotted); extend to the full archive before any promotion.
4. Limitations: no GPU/U-Net, no 1m LiDAR stack, quadrant (not whole-segment) folds, owner-mirror data not organizer-authenticated, sandbox cannot reach DrivenData/USGS FDSN directly.
