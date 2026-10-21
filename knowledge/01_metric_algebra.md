# The DTI metric and its exact decision algebra

Official source: [problem description, page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).
Known-fault masking: organizer clarification (DrivenData community thread 11516;
recorded via GEMSDOE32 — this sandbox cannot open community.drivendata.org).

## Definitions

Triangular kernel `k(d) = max(1 - d/R, 0)`, `R = 300 m = 3 px` at 100 m resolution.
With `T = TP_w`, `F = FP_w`, `G = |scored truth|`, `α = 0.2`, `β = 0.8`:

```
DTI = T / (T + αF + β(G - T)) = T / (α(T + F) + βG)
```

The second form is the useful one: with `S = T + F` (emitted mass inside the
scored domain) and `D = αS + βG` (denominator),

```
DTI = T / D,   D = αS + βG.
```

## Exact marginal rules (verified by brute force, tests/test_metric.py)

* **Addition.** Adding one unit dot with realised kernel credit `k` changes
  `dT = k`, `dF = 1 - k`, hence `dD = α` EXACTLY (independent of placement).
  The addition helps iff `k > α·s` where `s` is the current DTI.
  At `s = 0.2778`: every added dot must earn more than **τ = 0.05556**.
* **Removal.** Removing `dn` dots carrying `dS` credit helps iff
  `dS < α·s·dn`. Removing zero-credit mass ALWAYS helps (denominator falls,
  numerator fixed).
* **Correction note.** Some group notes quote the bar as `α·s/(1-α·s)`; that
  form does not follow from the metric (correct: `α·s`). At `s = 0.2708` the
  wrong form gives 0.05726 vs the correct 0.05416 — and the only lattice kernel
  weight in that window is the (2,2)-diagonal 0.05719, which the wrong form
  would reject. (First corrected in GEMSDOE32 IR-32-BAR-01; re-verified here.)

## Live-anchored inversion (CONDITIONAL on the owner-reported chain)

Pixel-exact verified: D2.8 (44,090 dots) → delete 3,891 dots at d≤1 px of the
catalogue → R1 (40,199) → delete 2,545 dots at d≤2 → H33-2-B2 (37,654).
Owner-reported scores: 0.2600 → 0.2708 → 0.2778.

Under the zero-live-credit flank-removal assumption (`T` fixed across the chain):

```
T_live ≈ 5,069 weighted TP units,  K_live ≈ 13,300 truth px,
D_live ≈ 18,247 at s = 0.2778,  mean live credit/dot ≈ 0.126.
```

Cross-check: the B=2 step then predicts 0.2784 vs reported 0.2778
(residual −0.0006 — the removed ring carried ≈0.0006 of credit, i.e. the
assumption holds to 0.2%). Implied live recall ≈ 38%.

Consequences for lane 82: removals are licensed when their conservative proxy
cost satisfies `cost < α·s·dn / 2` (safety ≥ 2); additions must clear
`τ = 0.0556` live, i.e. SGMC-measured `≥ 0.111` under a 50%-transfer
assumption (gate R5). Our additions measured **0.331/dot** — 5.9× the live bar.
