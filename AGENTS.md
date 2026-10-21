# Project-specific instructions

Before each session or project change, read the canonical project charter and current evidence in this order:

1. `README.md`
2. `docs/irregularities.html` and `docs/review-log.md`
3. `docs/research/hypotheses.md` and `docs/research/score-review.md`
4. `docs/sources.md`
5. `registry/run_card.json` and `docs/data/feed.json`

Use `docs/` as the canonical GitHub Pages site. Do not add a competing root site or a second run-card/source/hypothesis registry. Root `index.html` is an intentional redirect/fallback for the legacy Pages configuration.

Work only on the active Arena branch. Do not copy, retrieve from Git history, or submit a previous candidate TIFF. Do not use the `research/h82-blindstep/code/` local experiment as a substitute for the canonical shared evaluator or writer; the review log marks that lane as non-canonical and negative. The cached feature stack, official competition inputs, shared `evaluate_holdout.py`/`submission_writer.py`, and registry rasters are still missing; do not invent replacements or report a submit-ready file.

The parallel-run request's standalone method-lane paragraph was absent. Treat any lane in the repository as provisional unless this session's lane is explicitly authorized. Do not emit dots or a raster without the lane, whole-segment buffered holdout, feature-only leakage canary, both registry duplicate screens, and validator evidence required by `README.md`. A readiness diagnostic is not scientific validation. Preserve negative/blocked evidence and never convert public leaderboard context or a projection into an `ORGANIZER-CONFIRMED` score.
