# GEMSDOE82 — auditable GEMS submission research

> **Submission status: no competition-ready GeoTIFF is present in this repository. Do not download or submit a file from this repository as a prediction.** The checkout contains only this README; it has no competition rasters, cached feature stack, evaluator, writer, or validator. Creating a guessed raster or relabeling a constant raster as a model submission would be misleading and would not satisfy the competition's georeferencing or validation requirements.

## Project objective and operating brief

Build an auditable, reproducible workflow to investigate geothermal-system discovery in the GEMS competition; generate a single-band GeoTIFF in the organizer's exact submission grid; check it automatically for finite in-footprint values in `[0,1]`, correct CRS/shape/transform, and no registry duplication; and make the resulting file and its unique name/comment easy to identify and download. Improve the probability of a strong result through spatially blocked, leakage-aware validation rather than leaderboard chasing. Preserve negative findings and disclose limitations. Do not claim an official score without a submission receipt.

This brief captures the durable requirements of the project request. The original long-form request and its user-supplied historical score list remain in the conversation; the score list is not independently verified here. **Read this brief before each project session.** Core working values: maximize the probability of a scientifically defensible win, and own the outcome end-to-end.

### Non-negotiable experiment and reporting protocol

1. Define one method lane before work begins. Compare the candidate surface to all available registry rasters before placement and the final dots afterward. Stop and log as a duplicate if rank correlation exceeds `0.90` or more than `70%` of dots lie within 3 pixels of one registry raster. The supplied request refers to a “single method paragraph” but does not identify one; the lane therefore remains **unspecified** and must not be silently invented.
2. Reuse the shared cached feature stack and shared holdout evaluator/writer when available; do not create a private fork. Hold out whole fault segments with a buffer; derive catalogue features from visible faults only; mask visible faults pixel-exactly; evaluate pooled DTI with alpha `0.2`, beta `0.8`, and a 300 m triangular kernel. Verify these evaluator details against the actual shared implementation before reporting results.
3. Test each feature alone on holdout. Treat AUC above `0.90` as suspected leakage until investigated.
4. Label every numerical result either **HOLDOUT-DTI** (include evaluator version, withheld-positive count, and 95% CI) or **ORGANIZER-CONFIRMED** (copied from a submission receipt). Projections are not scores.
5. Limit exploration to three experiments or two hours, whichever comes first. A negative result is a deliverable. Do not select/promote a submission; the competition's selector and weekly cap are separate.
6. End each experiment report with a JSON run card: hypothesis, mechanism, named non-fault mimic, holdout DTI and CI, correlation/overlap versus registry, raster SHA-256, validator output (finite/no NaN in footprint, range `[0,1]`, CRS/shape/transform), submission name, note <=140 characters, verdict (`promote` or `negative`). If inputs prevent a field from being computed, use `null` and explain; never fabricate a value.

## Repository review (2026-10-21)

The working tree at review contained only `README.md` (11 bytes), with no source code, tests, data, website, raster artifacts, or pipeline. The branch was `arena/37895e49-gemsdoe82`, based on initial commit `fe13719`. Accordingly, this repository cannot yet reproduce the cited historical score, inspect any registry raster, compute a blocked holdout, or produce a compliant TIF. No prediction or score is claimed.

The user supplied a historical comparison in which the GEMSDOE32 entry `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` is said to score `0.2778`, and also supplied a newer leaderboard high of `0.3195` (elsewhere `0.4413`). These are **user-provided, unverified claims**, not HOLDOUT-DTI or ORGANIZER-CONFIRMED results. Their differing high-score values and dates are an irregularity that must be resolved from the current organizer leaderboard/receipts before comparison. A relative leaderboard score alone does not establish why a model worked or predict a better score.

## Candidate hypotheses for later testing (not validated; no submission slots)

These are research hypotheses, not reported discoveries. The current checkout has no layers or code, so “difference from this repository” means none is implemented here; user-provided prior results mention related families, so novelty versus the wider project network is **not established**. Do not proceed until the actual available feature bands and shared evaluator are inspected, the lane is defined, and registry similarity checks are possible.

| Rank (prior) | Candidate; layers and target signature | Why it might find an uncatalogued fault | Key non-fault mimic | Difference / cost / validation status |
|---|---|---|---|---|
| 1 (most promising, low-to-medium cost) | Multi-scale DEM curvature-transition concordance: DEM-derived profile/plan curvature plus a scale-space ridge/edge response; target persistent, spatially coherent slope-break edges, not raw elevation highs. | A previously unmapped structure could produce a geomorphic break even where the existing fault layer has a gap. Scale persistence and segment-level holdout are intended to reject catalog interpolation. | Lithologic contacts, drainage incision, landslide scarps, roads/terraces. | No code/layers here. Distinct from a single-scale scarp/topographic-ridge score in principle, but related to the user's cited many DEM/scarp/ridge methods; broad-network uniqueness and holdout performance unproven. Requires DEM in the cached stack; test each transform alone, then one preregistered combination. |
| 2 | Magnetic analytic-signal amplitude and directional edge coherence: magnetic grid (and derivatives); target edges persistent across directions/scales. | A buried basement discontinuity may be expressed in magnetic gradients without appearing in surface fault catalogs. | Intrusive contacts, remanent magnetization, survey seams, cultural magnetic sources. | No magnetic data or implementation in checkout. Potentially overlaps user-cited geophysics/radiometric work; verify exact bands. Medium cost; only viable if magnetic bands are available in the existing stack and holdout can test it without leakage. |
| 3 | Radiometric eTh/eU/K log-ratio boundaries with topographic residualization: radiometric bands plus DEM; target a coherent geochemical boundary aligned with independent structural edge evidence. | Fault-controlled permeability or alteration can redistribute radioelements near a structure omitted from the fault catalog. | Bedrock composition, soil moisture/cover, weathering, flight-line artifacts. | No radiometric bands here. User cites prior radiometric experiments, so this is not demonstrably new. Medium/high cost; viable only with stack bands and artifact controls. |
| 4 | DEM flow-network discontinuity: DEM-derived drainage deflection/concavity anomalies; target repeated aligned channel offsets or abrupt knickzone patterns, not lineament density alone. | Distributed structural deformation can perturb drainage outside mapped traces. | Lithologic contrasts, incision history, glacial/landslide processes, DEM artifacts. | No DEM/flow tools here; likely conceptually overlaps the user's earlier geomorphic/ridge hypotheses. Medium/high cost and high confounding; only test if DEM resolution and spatial holdout support it. |

**Ranking is a prior for experiment order, not evidence that any candidate improves DTI.** Under the requested leakage canary and whole-segment holdout, candidate 1 is the first *testable in principle*, but it cannot currently be validated. No candidate is promoted and no submission slot should be spent.

## Data, references, and access limits

- Competition overview/rules (organizer): <https://www.drivendata.org/competitions/306/competition-doe-gems/> — login-gated competition resources may be needed.
- Competition problem description: <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>.
- Competition about page: <https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/>.
- Organizer data page: <https://www.drivendata.org/competitions/306/competition-doe-gems/data/>. The request reports that downloads redirect to login; this checkout has no credentials or data. Do not attempt to bypass access controls.
- Organizer reference solution: <https://github.com/drivendataorg/gems-prize-reference-solution>.
- DOE/GDR project submission cited by the request: <https://gdr.openei.org/submissions/1391>.
- USGS GeoDawn survey record cited by the request: <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>.
- EPSG:32611 reference: <https://epsg.io/32611> (verify the actual sample-submission metadata rather than assuming this CRS).
- Submission guidance PDF cited in the request: <https://docs.nlr.gov/docs/fy26osti/96647.pdf>.

The above are links supplied for source review; this repository review did not retrieve or line-by-line verify their contents. The Dropbox URLs in the request are user-provided file links and are not treated as authoritative or downloaded. Obtain data only through authorized official competition access or a verified official public source, and record provenance, license, checksum, and grid metadata.

## What must be available before a valid submission can be built

1. Authorized competition inputs, including sample submission grid, labels/feature rasters, and any permitted DEM/feature data; record their checksums and metadata.
2. The shared cached feature stack, `evaluate_holdout.py`, and `submission_writer.py` (the request names these, but none exist in this checkout). Confirm versions and tests rather than recreating them privately.
3. Registry submission rasters or an auditable registry manifest for correlation/3-pixel overlap screening.
4. An implemented blocked holdout and bootstrap/appropriate 95% interval, with segment buffers and exact masking verified by tests.
5. Automatic GeoTIFF validation against the actual sample submission (single band, CRS, shape, transform, footprint, finite values and `[0,1]` range); then an easily accessible artifact with a unique name and <=140-character note.
6. Organizer login/receipt for any official result. Never present a local holdout estimate as an official leaderboard result.

### Submission instructions for a future verified artifact

Only when a validated GeoTIFF is actually present: download the artifact explicitly marked **VALIDATED — READY TO SUBMIT**, then open the DrivenData competition's **New submission** page, choose the single-band `.tif` file, enter its unique submission name and short note, review the competition rules, and submit. The organizer requires the prediction grid to match the submission format and values to be in `[0,1]`. The present repository has no such file, so **there is nothing safe to download or submit yet**.

## Next actions and limitations

1. Add/obtain authorized competition data and the shared tools; run their preparation step and inspect every resulting file's metadata.
2. Inspect official competition criteria and sample grid; resolve the contradictory high-score claims from current organizer evidence.
3. Define the missing lane paragraph and registry inventory before experimentation.
4. Run the three-experiment/two-hour protocol; begin with the candidate 1 feature-only leakage canaries, then the preregistered blocked holdout if valid.
5. Generate a TIF only after it beats the current holdout best under the same evaluator and passes all duplicate and submission-format checks. This is a gate, not a promise of beating any organizer score.

Current blockers: data absent; DrivenData authorization absent; evaluator/writer/cache absent; registry rasters absent; lane unspecified; no independent access to competition receipts. The requested autonomous end-to-end submission is not possible without these gated/private inputs. Do not fabricate data, scores, source verification, or submission artifacts.
