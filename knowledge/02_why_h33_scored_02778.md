# Why H33-2-B2 scored 0.2778 — and how lane 82 aims higher

## Short answer

H33-2-B2 is not a better *detector* than its parent — it is the same detector
with less *waste*. Its score comes from the metric's structure, not from new
geology: the organizer masks known catalogue faults out of scoring, so every
dot spent inside (or within kernel reach only of) the masked catalogue pays the
false-positive cost `α = 0.2` and can earn nothing. Deleting such dots raises
DTI mechanically. The D2.8 → R1 → B2 chain is three successive deletions of
exactly this waste (d≤1, then d≤2 px from the catalogue), each step gaining
about +0.0028 per 1,000 removed dots. The `-zeros` twin is the submittable one
because it makes the whole grid finite and in [0,1], which is what the portal
validator checks.

## The mechanism, precisely

1. **Masked mass is pure cost.** Scored domain = footprint minus catalogue.
   A dot at catalogue distance `d ≤ 1` px sits inside the masked region's
   kernel shadow: the only truth within 300 m is masked catalogue truth, so its
   live TP credit is ~0 while it adds exactly `α = 0.2` to the denominator.
2. **Each prune is a controlled experiment.** Byte-verified in this repo:
   `D2.8 & dist>1 == R1` pixel-exact (3,891 dots removed, +0.0108 reported);
   `R1 & dist>2 == B2` pixel-exact (2,545 removed, +0.0070 reported).
   No dots were added or moved — the ONLY mechanism is waste removal.
3. **Why `-zeros` and not `-nan`.** Both twins carry identical in-footprint
   dots. `-nan` matches the sample format (NaN outside) but trips strict
   `[0,1]` validators that reject NaN ("Predicted values must be in range
   [0,1]"). `-zeros` (0.0 outside, nodata=None) satisfies `0 ≤ v ≤ 1` on all
   12,279,160 cells. Same geology, portal-proof container.
4. **Why blanket B=3 was rejected by GEMSDOE32.** Dots at d==3 sit AT the kernel
   radius: they can still earn live credit from hidden truth at d∈{4,5,6}.
   Blanket deletion there is approximately break-even (measured LM margin
   +0.0013, safety 1.27 < 2.0). The prune franchise has diminishing returns —
   the next gains must be SELECTIVE.

## Can we score higher than 0.2778?

Yes, by two moves the blanket-prune franchise cannot make:

* **Selective surgery.** Of the 2,171 d==3 dots and 4,630 ring (d∈{4,5,6}) dots
  the base retains, delete only those with ZERO proxy credit AND no
  independent physical corroboration (lane-82 antislope/conjugate/radiometric
  surface). Keep corroborated flank dots as lottery tickets. Lane 82 removed
  2,063 dots at zero measured proxy cost (safety infinite).
* **Screened additions.** Add a SMALL number (1,500) of far-field dots at the
  most corroborated sites, each required to clear 2× the live bar on the proxy
  (measured 0.331 vs bar 0.0556 — 5.9×). Sizing caps the worst case: even if
  every added dot earned zero live credit, the file still ≈ holds 0.2778
  (projection scenarios on the site; projections, not scores).

The honest caveats: (a) no organizer receipt links the 0.2778 row to these
bytes (all attributions are OWNER-REPORTED); (b) the SGMC proxy covers only
part of the live hidden truth, so proxy margins are evidence, not promises;
(c) the live-anchored inversion assumes the chain's zero-credit mechanism,
which cross-checks to 0.2% but remains an assumption. The submission ships with
a machine-checked PROMOTED verdict (7-rule gate), full receipts, and a
duplicate/lane-disclosure card — inspection without human intervention.
