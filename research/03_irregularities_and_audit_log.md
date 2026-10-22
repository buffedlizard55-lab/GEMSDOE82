# Forensic Irregularities & Methodological Audit Log (`GEMSDOE82`)

In accordance with the competition prompt requirement to **work line by line verifying from official trusted sources and flag any irregularities for review**, we document four specific methodological and data irregularities discovered during our forensic inspection of the GEMSDOE portfolio (`GEMSDOE19`–`GEMSDOE92`).

---

## `IR-82-01` (Critical — Resolved in `GEMSDOE82`): Three Fold-Isolation & Budget Irregularities in `GEMSDOE77` Lane `H85-EDTI`

While inspecting `/home/user/GEMSDOE82/src/gems85/` and `GEMSDOE77/scripts/h85_edti_pipeline.py` (which reported a local score of `0.2966` in `GEMSDOE77`), line-by-line code verification uncovered three severe methodological irregularities that invalidate `H85-EDTI`'s `0.2966` figure as a fold-clean `HOLDOUT-DTI` comparison:

1. **`IR-82-01a` — In-Quadrant Training & Full-Catalogue Negative Filtering:**
   In `h85_edti_pipeline.py` (`train_fold_surface`), the gradient-boosted trees were trained on `allowed = foot & (~visible)` across **all four quadrants simultaneously** (including the held-out test quadrant `f["region"]`!), and negatives were filtered using `d_cat > 3.0` where `d_cat` was computed from the **entire mapped catalogue `cat`** (including `hidden` test faults!) rather than `visible` faults only.
2. **`IR-82-01b` — Test-Fold Truth-Count Oracle (`k_fold`) Used During Holdout Allocation:**
   In `h85_edti_pipeline.py`, each test quadrant's emitter (`emit_edti_surface`) received `k_fold = float(f["truth"].sum())` — the exact ground-truth pixel count of the withheld test fold — to calibrate its Dinkelbach stopping threshold per quadrant.
3. **`IR-82-01c` — 5.38× Production Emission Inflation (`201,260` Positive Pixels vs. `~37,429` Holdout Dots):**
   On holdout (`Seed 30`), `H85-EDTI` emitted `~37,429` positive pixels (`8,600–9,800` per quadrant), whereas its production GeoTIFF (`gems85-h85-edti-ridge-20261021-zeros.tif`) emitted **`201,260` positive pixels** (5.38× more positive pixels than `H33`'s `37,654` dots), which would incur a massive false-positive denominator penalty $\alpha\,\text{FP}_w$ on the live leaderboard.

**Resolution in `GEMSDOE82` (`H82-CSAM`):**
- `H82-CSAM` (`src/gems82/csam.py`) enforces **100% strict Leave-One-Quadrant-Out (`LOQO`) spatial isolation**: for each held-out quadrant $k \in \{\text{NW, NE, SW, SE}\}$, all physical and stacker trees are trained exclusively on the other three quadrants `tr_reg`, using only `vis_tr = visible & tr_reg` and `d_tr = edt(~vis_tr) > 3.0`.
- `H82-CSAM` never queries `f["truth"]` during calibration or dot allocation; Bayes prior calibration uses a fixed off-catalogue prior $\pi_{\text{true}} = 0.0022$.
- `H82-CSAM` uses the **exact same discrete dot budget** in holdout and production (`41,200` primary binary dots and `37,654` H33-parity binary dots).

---

## `IR-82-02` (High — Resolved in `GEMSDOE82`): Production-Halo Overlap Cap Inside Hide-and-Recover Holdout Steers Dots Toward Withheld Catalogue Holes

During Experiment 2 (`scripts/h82_exp2_dual_holdout.py`), we tested both:
- `H82_CSAM_41200_uncapped` (`packed_halos_fp = None` during holdout): Pooled `HOLDOUT-DTI = 0.165778` (`95% CI [0.151457, 0.179874]`).
- `H82_CSAM_41200_capped` (`packed_halos_fp` enforcing `overlap_cap = 0.610` against the 168 prior production rasters during holdout): Pooled `HOLDOUT-DTI = 0.189695` (`+0.023918` higher!).

**Why did enforcing a 3.0-px overlap cap against prior production rasters *increase* `HOLDOUT-DTI` by `+0.0239`?**
Because prior production rasters (`H33`, `D2.8`, `GEMSDOE73`–`GEMSDOE77`) were generated for the live test set and therefore **masked out 100% of `existing_faults.tif` (`cat = visible | hidden`) plus a 2–3 px exclusion collar**! When evaluating on a hide-and-recover holdout where 20% of `cat` is withheld as `hidden`, prior production rasters have empty 2–3 px holes along `hidden` fault segments. Capping overlap against those production rasters during holdout evaluation suppresses off-catalogue pixels and indirectly steers holdout dots into the `hidden` catalogue holes!

**Resolution in `GEMSDOE82`:**
- We report **`H82_CSAM_41200_uncapped` (`0.165778` pooled `HOLDOUT-DTI`, `0.172837` Seed 30, `0.158701` Seed 20)** and **`H82_CSAM_37654_uncapped` (`0.164497` pooled `HOLDOUT-DTI`)** as our strictly fold-clean headline `HOLDOUT-DTI` metrics (`evidence/h82_exp2_dual_holdout.json`, `run_card.json`), while explicitly logging `IR-82-02` so the `+0.0239` production-hole artifact is never conflated with genuine out-of-fold generalization.

---

## `IR-82-03` (Medium — Documented in `vendor/gems57/uniqueness.py`): Whole-Footprint Lattice / Continuous Witness Rasters vs. Sparse Dot Overlap Gate

Out of the `188` restored prior rasters (`62` archive rasters + `112` sibling rasters + `12` scored rasters + `2` witness rasters), **`19` rasters** (`dense_witness.tif` and 18 continuous-surface or 5-px lattice diagnostic rasters) have $> 125,000$ positive pixels whose 3.0-px dilation covers $98.9\%\text{--}100.0\%$ of the entire valid footprint (`5,167,373` pixels). Against a raster whose 3-px halo covers $100\%$ of the footprint, *every* non-empty submission (including uniform random noise) has a literal 3-px overlap of `1.0000`.
As documented in `vendor/gems57/uniqueness.py`:
- Whole-footprint continuous surfaces (`19` rasters) are audited via **full-footprint Spearman rank correlation $\rho \le 0.90$** (`H82-CSAM` achieves $\max \rho = 0.2521 \le 0.90$ pre-placement and $\max \rho = 0.0740 \le 0.90$ on final dots against `dense_witness.tif`).
- All **`168` sparse dot rasters** ($\le 125,000$ positive pixels) are audited via **both** $\rho \le 0.90$ AND **3.0-px Euclidean halo overlap $\le 0.70$** (`H82-CSAM` achieves $\max \text{overlap} = 0.6100 \le 0.70$ and $\max \rho = 0.1687 \le 0.90$ across all 168 sparse rasters).

---

## `IR-82-04` (Low — Verified & Handled): Empty Repository Stubs in `GEMSDOE78`–`GEMSDOE92`

When auditing the GitHub portfolio (`buffedlizard55-lab/GEMSDOE*`), repositories `GEMSDOE78` through `GEMSDOE92` (including `GEMSDOE82` at initial branch creation `fe1371993775db6ec13e592d37fa634f3e39622a`) contained only a 10-byte `README.md` stub (`# GEMSDOE82`), while competition bridge templates, external geoscience layers, and registry manifests resided in populated sibling repositories (`GEMSDOE24`, `GEMSDOE32`, `GEMSDOE57`, `GEMSDOE73`–`GEMSDOE77`).
**Resolution in `GEMSDOE82`:**
`scripts/download_competition_data.sh` and `scripts/prepare_data.py` autonomously restore and SHA-256 verify all competition rasters, external geoscience layers, audit source rasters, and 188 reference/sibling rasters (`evidence/data_receipt.json`).
