# Forensic review of the cited GEMSDOE32 result

## Finding

The high value cited for `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` is **not independently confirmed by the evidence available in this checkout**. The linked public GEMSDOE32 source repository’s [`registry/submission_build.json`](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/registry/submission_build.json) explicitly says that no organizer score exists for that artifact and labels the live-board value in its note as a projection/model, not a score. The current GEMSDOE82 checkout contains no submission-page receipt, no copy of that raster, and no competition data with which to reproduce it.

Accordingly, the cited figure is not used as a `HOLDOUT-DTI` result, an `ORGANIZER-CONFIRMED` result, or the current holdout best. If a later DrivenData receipt exists outside the linked repository, it is not represented in the material reviewed here.

## What the source repository says the raster does

The GEMSDOE32 public build manifest describes H33-2-B2 as a **sparse, nonzero emission** derived by pruning candidate pixels near the mapped catalogue from an earlier emission. Its `-zeros` suffix refers to the outside-fill convention in that repository’s documentation; it does not mean the entire raster predicts absence. The manifest also records that the artifact has no candidates on the mapped catalogue. These are claims in a public owner-maintained manifest, not measurements recomputed from the artifact bytes in this checkout.

The plausible mechanism is selective precision control: pruning near-catalogue candidates can reduce false-positive mass when those candidates do not correspond to the hidden truth, while retaining farther candidate traces that might overlap unmapped structures. This is a **hypothesis**, not a causal result. It can also reduce recall if true hidden faults lie close to known faults, and any apparent advantage can be due to chance or repeated tuning against the public test set.

## Why a single reported score cannot establish causality

The official [metric description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) uses a triangular distance kernel with 300 m support and weights false negatives more heavily than false positives (α=0.2, β=0.8). Thus a prediction near a hidden fault can receive more credit than a distant one, while an emission far from truth still incurs a false-positive penalty. A sparse mask might improve the precision/recall balance, but only a pinned, spatially blocked hide-and-recover evaluation can separate a genuine effect from test-set luck, leakage, or leaderboard overfitting.

The public GEMSDOE32 README itself describes a particular catalogue-flank pruning rule and states that its artifact was unscored. The quoted high value may represent a later event, a different file, or a record not included in that repository. Without a submission-page receipt binding the file digest to an organizer score, choosing among those explanations would be speculation.

## Official leaderboard context

The public [DrivenData leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) was read on 2026-10-21. It shows a current top entry consistent with the earlier figure in the prompt and higher than the later lower figure. This is external public-leaderboard context, not a receipt for the GEMSDOE32 file or for this project. The page is dynamic; use the live link for the current board.

## Answer: can this project beat the cited result?

No defensible prediction is possible from this checkout. It has no input rasters, labels, feature cache, shared evaluator/writer, registry raster collection, holdout result, or validated candidate. An unvalidated TIFF would not answer the question and could consume a limited submission opportunity. The correct current verdict is **negative / blocked**, with no submission slot spent.

The first admissible next result is a new, non-duplicate candidate that beats the current *holdout* best under the required evaluator, includes the specified confidence interval and leakage/overlap tests, and is written by the canonical shared writer. It must then pass the actual organizer format checks and carry a submission-page receipt before any external score is reported.
