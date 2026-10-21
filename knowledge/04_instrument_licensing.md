# Instrument licensing: what each holdout may and may not judge

## The three SGMC frames

| frame | truth | D2.8 → R1 → B2 ordering | licensed for |
| --- | --- | --- | --- |
| SGMC-FAR (PRIMARY) | SGMC faults with d(catalogue) > 6 px Euclidean, K=55,109 | 0.084594 → 0.085845 → 0.086683, TP exactly neutral (4,518.6 all three) | flank surgery on a fixed carrier; small screened far-field additions |
| SGMC-MID | d > 3 px Euclidean, K=62,122 | 0.094174 → 0.095295 → 0.095386 | ring (d∈{4,5,6}) decisions; no-loss gate |
| SGMC-RAW | >300 m Chebyshev, K=62,703 | 0.095282 → 0.096273 → 0.096060 (B2 step WRONG sign) | conservative secondary; no-loss gate |

The moat sweep (d > 3/4/5/6/8/10) reproduces both live orderings at every moat
≥ 3 Euclidean px and becomes exactly TP-neutral at moat ≥ 5. The phantom credit
that breaks SGMC-RAW lives in the d∈{4,5} truth band: SGMC geologic-map faults
extend into the catalogue flank, while the live hidden truth does not (the live
B=2 gain of +0.0070 ≈ the zero-credit prediction +0.0072 proves the flank dots
carried ~zero live credit). Mechanism: the scorer masks the catalogue, and
experts do not label "new" faults in the shadow of mapped ones.

## What SGMC-FAR may NOT judge: detector choice

A fresh 37,654-dot emission from the H82-2.1 antislope surface scores SGMC-FAR
**0.1403** (vs base 0.0867) — yet CAT-HIDDEN **0.0030** (≈ random 0.0023).
SGMC faults are surface-expressed BY CONSTRUCTION (they were mapped from
surface geology), so any scarp detector over-scores on SGMC while the live
hidden faults (expert-known but compilation-missing, many blind) need not.
This is the same failure GEMSDOE32 measured for its LiDAR scarplet vote
(H33-C below random on catalogue-hidden) and the same lesson as IR-33-LM-01
(a proxy ranking a variant at 0.44 that the live record refutes).

Therefore: SGMC-FAR is licensed ONLY for (a) TP-neutral-style surgery
evaluated as pooled margin + 4/4 quadrant consistency, and (b) small additions
screened at ≥2× the live bar with capped sizing. Wholesale emission replacement
ranked by SGMC-FAR would be gaming our own instrument. The shipped candidate
(96% shared carrier + 9.6% novel content) respects this license.

## CAT-HIDDEN: diagnostic only

Whole-component hide-and-recover (4 quadrants × 2 draws, 15 px collar, visible
masked pixel-exactly, K=22,232 withheld) ranks the ascending live chain
0.0967 → 0.0305 → 0.0045 — strictly DESCENDING. It is anti-monotone vs live on
emission questions because hidden segments sit adjacent to visible ones, so
flank mass that live calls waste, CAT-HIDDEN calls credit. Reported for
transparency, never gated on, never projected from.

## Leakage canary (evidence/canary.json)

Each surface alone: AUC vs catalogue 0.49–0.54, vs SGMC-offcat 0.49–0.53 —
no trip (trip bar 0.90). Pairwise surface |rho| ≤ 0.43. The detectors are
label-free by construction (they never open labels.tif) and the canary confirms
no retrospective leakage path.
