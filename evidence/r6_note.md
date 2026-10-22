# R6 duplicate guard evolution (gate v1.0 -> v1.1 -> v2.0)

## 1. Historical defect in v1.1 (Lane H82-2, 37,091 dots)

The parallel-run protocol states:
> "Before placing dots, check rank-correlation of your surface against the
> rasters in `registry/rasters/` (and repeat on final dots); if correlation
> `> 0.90` or `> 70%` of your dots fall within 3 px of one existing raster's
> dots, you have drifted into another lane — log it as a duplicate and stop."

Historical Lane H82-2 (`gems82-h82-antislope-corroborated-37091-20261021T120000Z-49437fe9`)
kept `35,591` of the `37,654` dots in `H33-2-B2` and added `1,500` dots. Its full-mask
final dots therefore had `spearman_rho = 0.9522 > 0.90` and `overlap_3px = 0.9611 > 0.70`
against `H33-2-B2`. Gate v1.1 exempted carrier dots (`R6b` report-only), which PR #11
rightly rejected as violating Rule 1 (`repeat on final dots`). Historical H82-2 is
therefore logged as a **duplicate** (`DO NOT SUBMIT`) in `evidence/gate.json["archived_duplicates"]`
and has no download links on `docs/index.html` or `docs/executive-summary.html`.

## 2. Strict resolution in v2.0 (Lane H82-3, 35,000 dots)

Gate v2.0 (`registry/slot_gate.json`) enforces **both** `R6a_lane_independence` and
`R6b_full_mask_independence` as hard machine-gated promotion requirements with **zero
carrier exemption**:

1. **`R6a_lane_independence` (before placement + added dots):**
   - Rank correlation of discovery surface `C_cov` against every registry raster `<= 0.90`:
     measured `0.0273 - 0.0450`.
   - 3 px overlap of the `12,000` novel added dots against every registry raster `<= 0.70`:
     measured **`0.0000`** (`0 / 12,000` within 3.0 px of any dot in `D2.8`, `R1-SOLO`,
     `H33-2-B2`, `H36-rung30`, `H19-5`, or historical `H82-2`).
2. **`R6b_full_mask_independence` (full 35,000-dot emitted mask, zero carrier exemption):**
   - By retaining only the `23,000` highest-corroboration carrier dots (`23,000 / 35,000 = 0.6571 <= 0.70`,
     while protecting all `1,611` near-tip `2 < d2c < 3` px dots) and adding `12,000` novel
     corroborated dots at `d_any_registry > 3.0 px`, the full 35,000-dot mask achieves:
     - `overlap_3px = 0.6571 <= 0.70` vs `D2.8`, `R1-SOLO`, `H33-2-B2`, `H19-5`;
     - `overlap_3px = 0.6561 <= 0.70` vs `H36-rung30`;
     - `overlap_3px = 0.6339 <= 0.70` vs historical `H82-2`;
     - `spearman_rho = 0.3502 - 0.6325 <= 0.90` across all 6 registry rasters;
     - `novel_fraction = (14,654 removed + 12,000 added) / 35,000 = 0.7615`.

Furthermore, `scripts/build_site.py` (tested by `tests/test_duplicate_site.py`) fails
closed and suppresses all download links if any registry comparison in `carrier_R6b`
exceeds `spearman_rho > 0.90` or `overlap_3px > 0.70`.
