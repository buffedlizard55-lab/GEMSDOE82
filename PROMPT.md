# Standing brief — read first, every session (operative excerpt of the commissioning prompt)

> Maximize P(Win). Own the Outcome. Every weekly slot is an experiment, not a lottery ticket.

1. **Unique TIF, obvious clearance.** Generate a UNIQUE submission GeoTIFF (never copy prior
   pixels; prior rasters only for learning/comparison). At the top of the site/README it must be
   obvious whether the file is OK to download and whether it is OK to submit. Inspection is
   automated through this project (validator + holdout + uniqueness) — no human inspector.
2. **Parallel-run protocol.** Stay in lane (H82-1 here): surface Spearman >0.90 or >70% dots
   within 3px of a registry raster = duplicate, stop. Reuse shared metric/holdout/writer logic;
   holdout = hide-and-recover with buffer, visible-only catalogue features, pixel-exact known
   mask, pooled DTI (alpha 0.2 beta 0.8, 300m triangular). Label every number HOLDOUT-DTI
   (evaluator, n withheld, CI) or ORGANIZER-CONFIRMED (portal receipt only). Leakage canary:
   feature-alone AUC >0.90 = leakage until proven otherwise. End with one JSON run card.
   Budget: 3 experiments / 2 hours. Promotion to a slot is a separate selector step.
3. **Beat-the-best question.** Study why H33-2-B2 (brief: 0.2778) leads the group and whether a
   higher score is reachable; answer at PhD level, then build a distinct lane. Leaderboard
   figures in the brief conflict (0.4413 / 0.3195) — verify live, never assert unverified.
4. **Hypotheses first.** 3-5 untried geological hypotheses (layers, signature, why off-catalogue,
   novelty), ranked by expected DTI/cost. Validate top candidate on spatially-blocked holdout
   before any slot. External data only if free/official/obtainable (verify obtainability).
5. **Portal correctness.** Fix "Predicted values must be in range [0, 1]" (sentinel + nodata tag).
   Unique name + short note (<=140 chars in run card). Executive-summary subpage explaining
   exactly how to submit. GitHub Pages site, clean UI, official links, line-by-line verification,
   flag irregularities, no hallucinations, multiple passes, PR + merge, list limitations/next steps.
