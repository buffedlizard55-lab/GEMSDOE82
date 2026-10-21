# GEMSDOE82 — auditable fault discovery for the DOE GEMS Prize

> **Submission status: NOT READY.** This checkout has no competition rasters, cached feature stack, shared holdout evaluator/writer, or candidate GeoTIFF. **There is no file here that is safe to upload.** Do not spend a competition slot on an unvalidated or synthetic raster. The submission button will remain disabled until the run card and validator both pass.
>
> [Executive summary & exact submission steps](docs/executive-summary.html) · [Research hypotheses](docs/hypotheses.html) · [Official-source ledger](docs/sources.html) · [Irregularities](docs/irregularities.html) · [Three-pass review log](docs/review-log.md)

## Permanent project prompt — read before every project session

This is the working charter distilled from the full project request. Re-read it before researching, coding, reviewing, or proposing any change; update the status and evidence links when facts change.

### Mission

Build a reproducible, auditable system to identify **previously unmapped geological faults** in the DOE GEMS / GeoDAWN region, and—only after scientific and format validation—produce a unique, single-band GeoTIFF that can be submitted to DrivenData competition 306. The competition labels faults that are indicative of geothermal resources; the target is **fault presence**, not geothermal vents themselves. A high score is a means to the goal, not evidence of a verified geological discovery.

### Non-negotiable experiment and submission protocol

1. **One scientific lane per run.** The original parallel-run instruction refers to a “single method paragraph below,” but no standalone lane paragraph was supplied. Until an owner-authored lane is explicitly available, use the preregistered magnetic-source-depth-boundary hypothesis in `docs/research/hypotheses.md` only as a *provisional candidate*; do not place or emit dots. Before placement and on any final raster, compare rank-correlation and 3-pixel dot overlap against every available registry raster. If Spearman correlation is greater than 0.90 or more than 70% of dots lie within 3 pixels of one registry raster, log a duplicate and stop.
2. **Reuse shared tooling; do not fork it.** Use the template’s cached feature stack, `evaluate_holdout.py`, and `submission_writer.py`. This checkout does not contain them. Do not create a private replacement; first locate the canonical template and its pinned version. If a shared tool is defective, fix it in that template and report the upstream change.
3. **Withhold whole fault segments, with a spatial buffer.** Derive catalogue-based features only from visible faults; hide visible faults pixel-exactly; score pooled distance-weighted Tversky using α=0.2, β=0.8, and the 300 m triangular kernel. Record the evaluator version, withheld-positive count, and 95% confidence interval for every **HOLDOUT-DTI** result.
4. **Leakage canary.** Score each feature alone on the holdout before trusting a combination. AUC above 0.90 is leakage until it is explained and disproved.
5. **Evidence labels.** A numerical project score may be written only as **HOLDOUT-DTI** (with evaluator version, withheld positives, 95% CI) or **ORGANIZER-CONFIRMED** (copied from a submission-page receipt). A projection is never a score. Public leaderboard readings are external context, not this project’s result or an artifact receipt.
6. **Run card and budget.** End each experiment with one JSON card containing hypothesis, mechanism, a named non-fault mimic, holdout DTI and CI, registry correlation/overlap, raster SHA-256, validator results, submission name and a note ≤140 characters, and verdict `promote` or `negative`. Negative results are deliverables. Stop after three experiments or two hours. Do not select or submit a candidate; promotion to a real slot is a separate selector step governed by the submission page’s current weekly cap.
7. **Unique file and no false readiness.** Never reuse a previous submission raster as the deliverable. Learning from earlier methods is allowed, but the final raster must be newly generated from the selected method and data, carry a digest and validation receipt, and be visibly labelled “OK TO SUBMIT” only after every gate passes. The official format page requires a single-band float32 GeoTIFF, EPSG:32611, 100 m resolution, matching bounds/grid, values in [0,1], and null/NaN outside the data bounds. Also validate every value the portal may inspect; do not assume that NaN or a nodata sentinel is accepted by the upload form.
8. **Line-by-line source review.** Use official, free sources for any third-party data; record the exact source, license/terms, retrieval status, checksum and transformation. Link claims to primary sources. Flag conflicts, access limits, and any evidence that cannot be reproduced.

### Core Values

**Maximize P(Win)**

> “Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

**Own the Outcome**

> We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Applied here: protect submission slots, do not misrepresent unverified scores, and treat a blocked or negative experiment as useful evidence rather than papering over missing data.

## Current verified state (2026-10-21)

- At the start of this review, the tracked project consisted only of this README. There was no `data/`, `scripts/`, `src/`, evaluator, writer, feature cache, test suite, site, run card, registry raster, or TIFF to inspect.
- The competition data page redirects an unauthenticated browser to DrivenData login. No training package was available in this checkout. The linked competition data tab remains the required source; this project does not bypass its access control.
- The public GEMSDOE32 repository’s `registry/submission_build.json` describes its H33-2-B2 raster as an emission created by removing candidates close to the mapped catalogue, and explicitly labels that artifact **UNSCORED** with its live value described as a projection. It contains no submission-page receipt for the result quoted in the request. The reported GEMSDOE32 value therefore remains unverified here; it is not a promotion baseline.
- The current official public leaderboard page was checked on this date. Its top public row agrees with the earlier, higher figure in the prompt, not the later lower figure. This is external public-leaderboard context only, not a submission-page receipt for a GEMSDOE82 artifact and not a GEMSDOE82 score. See the live [leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).
- The full GEMS contract and access caveat are recorded in [`docs/sources.md`](docs/sources.md). The decision not to create a TIFF is deliberate: without the training/features raster, labels, template grid, cached stack, shared evaluator/writer and registry rasters, any output would be synthetic, unvalidated, and unsafe to submit.
- A concurrent merged PR briefly added a candidate TIFF and local metrics from public sibling-repository mirrors using a private evaluator/writer. That PR was reverted because it violated the canonical-data/tool protocol; its artifact and claims are not accepted and must not be retrieved from history. See [`IR-82-12`](docs/irregularities.html) and the post-pass section of [`docs/review-log.md`](docs/review-log.md).

## Why the cited GEMSDOE32 result is not yet an explanation

The “zeros” suffix in the public GEMSDOE32 artifact name does **not** establish that the prediction is an all-zero raster. The repository’s own build manifest describes a sparse, nonzero candidate emission with zeros used outside its prediction footprint. The stated construction removes points close to the known catalogue from a prior emission, which is a plausible way to reduce false-positive mass while retaining predictions farther from mapped faults. That mechanism could help under a distance-weighted metric, but it does not prove the score or explain causality. The public repository marks the artifact unscored and has no organizer receipt for it. See [`docs/research/score-review.md`](docs/research/score-review.md).

## Submission contract and upload guidance

The official [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) specifies a distance-weighted Tversky score (α=0.2, β=0.8, 300 m triangular-kernel support) and the GeoTIFF grid/format requirements. The [executive summary](docs/executive-summary.html) explains the upload steps and current stop condition. The old portal error, “Predicted values must be in range [0, 1],” cannot be diagnosed without the rejected file: likely causes include any in-array value below 0 or above 1, but NaN/nodata handling must be checked against the official template and validator rather than guessed.

## Suggested start-of-session checklist

1. Read this charter and `docs/irregularities.html`.
2. Run `python scripts/check_readiness.py` and inspect the JSON output.
3. Locate the canonical template and verify its cached feature stack, holdout evaluator and writer versions; do not copy them into a private fork.
4. Obtain the authorized competition data package through the official data page, then verify its files against the template manifest. Do not use a previous submission as training truth or as a replacement for the sample template.
5. Reconcile the current leaderboard and any quoted team result against official pages and submission receipts. Keep external leaderboard context separate from HOLDOUT-DTI results.
6. Preregister at most three experiments, run the leakage canary and duplicate gate, and complete the JSON card. Do not use a submission slot unless a separate selector authorizes it.

## Official references

- [GEMS Prize — problem description, metric, data and submission format](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [GEMS Prize — about the sponsor, data and task](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/)
- [Competition data page](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) — login required for the data package.
- [Official reference solution](https://github.com/drivendataorg/gems-prize-reference-solution)
- [USGS GeoDAWN data release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)
- [USGS ScienceBase GeoDAWN catalog item](https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7)
- [USGS 3DEP 1 m DEM collection](https://data.usgs.gov/datacatalog/data/USGS:77ae0551-c61e-4979-aedd-d797abdcde0e)
- [USGS ComCat / FDSN earthquake catalog API](https://earthquake.usgs.gov/fdsnws/event/1/)
- [EPSG:32611](https://epsg.io/32611)

---

**Repository rule:** no score, result, source, or submit-ready state is promoted from a hypothesis, leaderboard title, filename, or projection. It requires reproducible evidence and a permanent link.
## Parallel-session research record (2026-10-21, arena/d0d8912f) — negative, no artifact

A parallel session tested lane **H82-1** (buried-fault potential-field step × anti-scarp gate)
using sha256-pinned sibling mirrors and a clean-room local evaluator. Consistent with IR-82-12,
its GeoTIFF is **withheld from main** and its tooling is **not canonical**. Evidence only:
[`research/h82-blindstep/`](research/h82-blindstep/) — HOLDOUT-DTI (local `gems82-hide-v1`,
57,407 withheld) 0.0745 vs random 0.0693 (n.s. overall; low-slope subgroup +0.019 significant).
Verdict **negative**; submission status above (**NOT READY**) is unchanged. Slots used: 0.
