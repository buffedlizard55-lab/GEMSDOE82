# Instrument licensing: what each holdout may and may not judge

## The three SGMC frames

| frame | truth | D2.8 → R1 → B2 ordering | licensed for |
| --- | --- | --- | --- |
| SGMC-FAR (PRIMARY) | SGMC faults with d(catalogue) > 6 px Euclidean, K=55,109 | 0.084594 → 0.085845 → 0.086683, TP exactly neutral (4,518.6 all three) | carrier surgery on `d2c ≥ 3.0`; screened far-field additions |
| SGMC-MID | d > 3 px Euclidean, K=62,122 | 0.094174 → 0.095295 → 0.095386 | ring (d∈{4,5,6}) decisions; no-loss gate |
| SGMC-RAW | >300 m Chebyshev, K=62,703 | 0.095282 → 0.096273 → 0.096060 (B2 step WRONG sign) | conservative secondary; no-loss gate |

The moat sweep (d > 3/4/5/6/8/10) reproduces both live orderings at every moat
≥ 3 Euclidean px and becomes exactly TP-neutral at moat ≥ 5. The phantom credit
that breaks SGMC-RAW lives in the d∈{4,5} truth band: SGMC geologic-map faults
extend into the catalogue flank, while the live hidden truth does not (the live
B=2 gain of +0.0070 ≈ the zero-credit prediction +0.0072 proves the flank dots
carried ~zero live credit). Mechanism: the scorer masks the catalogue, and
experts do not label "new" faults in the shadow of mapped ones.

## What SGMC-FAR may NOT judge: wholesale detector replacement

A fresh 37,654-dot emission from the H82-2.1 antislope surface alone scores
SGMC-FAR **0.1403** (vs base 0.0867) — yet CAT-HIDDEN **0.0030** (≈ random 0.0023).
SGMC faults are surface-expressed BY CONSTRUCTION (they were mapped from
surface geology), so a pure scarp detector over-scores on SGMC while dropping
near-catalogue tip coverage.

Therefore:
1. Dot selection in Exp1/Exp2/Exp3 must be **100% label-free and proxy-free**
   (never filtering dots by `sgmc_mid` or `sgmc_far` credit; see `IR-82-LEAK-01`).
2. All `1,611` near-catalogue tip dots (`2.0 < d2c < 3.0 px`) on the H33-2-B2
   carrier must be protected so `CAT-HIDDEN` never degrades (`+0.000141` in H82-3).
3. Retained carrier dots (`23,000`) plus strictly non-overlapping multi-physics
   additions (`12,000` at `d_any_registry > 3.0 px`, screened at `0.2647 >= 0.111`
   SGMC-FAR credit/dot) simultaneously respect the strict full-mask duplicate
   guard (`23,000 / 35,000 = 0.6571 <= 0.70`) and improve all four holdouts.

## CAT-HIDDEN: diagnostic + tip-protection verify

Whole-component hide-and-recover (4 quadrants × 2 draws, 15 px collar, visible
masked pixel-exactly, K=22,232 withheld) ranks the ascending live chain
0.0967 → 0.0305 → 0.0045 — strictly DESCENDING because hidden catalogue segments
sit adjacent to visible ones (`d2c < 3.0 px`). Once `d2c ≤ 2.0 px` is removed
(as in H33-2-B2), 100% of remaining near-tip credit lives in `2.0 < d2c < 3.0 px`.
Protecting those 1,611 dots in Lane H82-3 while reducing total emitted dots from
37,654 to 35,000 raises `CAT-HIDDEN` from `0.004515` to `0.004656 (+0.000141)`.

## Leakage canary (evidence/canary.json)

Each of the 6 surfaces (`h82_1`..`h82_6`) alone: AUC vs catalogue `0.489–0.542`,
vs SGMC-offcat `0.493–0.525` — no trip (trip bar `0.90`, max `0.5415`).
Pairwise surface `|rho| ≤ 0.431`. The detectors are label-free by construction
(they never open `labels.tif`) and the canary confirms no retrospective leakage path.
