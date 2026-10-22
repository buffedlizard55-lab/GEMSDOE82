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

## 2026-10-21 merge amendment (two tracks, one repo)

A lane session (H82-2 antislope-corroborated) was merged alongside the
canonical-track position. Both stand; the owner decides between them
(IR-82-MERGE-01):

- Canonical track (H82-0 prereg, H82-1 blindstep negative): unchanged policy —
  `docs/canon/`, `registry/run_card.json`, `research/h82-blindstep/`,
  `docs/review-log.md`. Do not edit the archived canon pages.
- Lane H82-2: mirror-verified submission track — `src/gems82/`, lane `scripts/`,
  `evidence/`, `knowledge/`, generated `docs/` pages (index, executive-summary,
  hypotheses, research, leaderboard, lanes, sources), `docs/downloads/`.
  `docs/irregularities.html` is a static merged file (both tracks).
- ABSOLUTE RULES for lane pages: never write `docs/data/feed.json` (owned by
  the refresh-feed workflow) or `docs/data/run_card.json` (byte-synced from
  `registry/run_card.json`); never link outside `docs/` from any `docs/*.html`;
  every generated page keeps `<html lang="en">` + `<title>`; lane hypotheses
  are H82-2.1…H82-2.5 (H82-1 is the blindstep lane).
- CI deploys `docs/` on push to main and runs BOTH suites: `python -m unittest
  discover` (canonical) and `python -m pytest tests/` (lane). Keep both green.
