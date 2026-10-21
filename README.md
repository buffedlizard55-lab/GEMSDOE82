# GEMSDOE82 — auditable GEMS fault-discovery and submission system

**Session state:** branch `arena/af816701-gemsdoe82` · working date `2026-10-21` UTC
**Competition:** [DOE GEMS Prize / DrivenData competition 306](https://www.drivendata.org/competitions/306/competition-doe-gems/)
**Scope:** one preregistered structural method lane, one shared hide-and-recover evaluator, one format-safe artifact. No submission slot was used.

> **Read this file and [`PROMPT.md`](PROMPT.md) before changing the project.** `PROMPT.md` retains the complete user brief and its operating constraints. This README is the executable summary and the public audit trail.

---

## ⬇ Download the generated TIF — status is explicit

### **DOWNLOAD OK: yes · FORMAT READY: yes · SUBMIT PROMOTION: no**

**[Download the single-band GeoTIFF](docs/downloads/gemsdoe82-h82b-signed-curvature-37654-20261021-d1727ccc21e9-SUBMIT.tif)**
**[Download the one-TIFF ZIP](docs/downloads/gemsdoe82-h82b-signed-curvature-37654-20261021-d1727ccc21e9-SUBMIT.zip)**
**[Open the byte-level validator receipt](docs/downloads/gemsdoe82-h82b-signed-curvature-37654-20261021-d1727ccc21e9-SUBMIT.json)**

This is a **unique, newly generated** candidate. It is safe to download and is structurally ready for the DrivenData upload form. **Do not upload both the TIF and ZIP.** The local selector is negative because no organizer receipt exists and the local holdout did not establish improvement over a current cross-repository incumbent. The project therefore does **not** recommend spending a weekly slot automatically. A local format pass is not a competition score or organizer acceptance.

| Submission form field | Paste this |
|---|---|
| **Unique name** | `GEMSDOE82-H82B-20261021` |
| **Note (108/140 characters)** | `H82-B signed curvature discordance; 37654 dots; HOLDOUT-DTI 0.01393 [0.00995,0.01829]; local validation only` |
| **TIF SHA-256** | `1deab2d36b9dd2b702bf1775fa3d0aad1ae5a4cd36617e0028aa9dfeb37a1036` |
| **Output** | one float32 band; `EPSG:32611`; shape `3730 × 3292`; 100 m; all cells finite; values in `[0,1]`; `37654` positive cells |

The **validator receipt** is the authority for the output bytes. It records `no_positive_on_catalogue`, no NaN/infinity, the all-cells range check, and exact CRS/shape/transform/bounds equality with `sample_submission.tif`. The all-finite, zero-outside export is intentional: the brief reported the portal error **“Predicted values must be in range [0, 1]”**; a nodata sentinel or NaN can trigger that class of failure. The official problem page still describes outside-footprint cells as null or NaN, so if the organizer gives a different instruction, follow the organizer and regenerate with the shared writer rather than editing bytes by hand.

**ORGANIZER-CONFIRMED:** the official leaderboard page read on 2026-10-21 displayed a public leader of `0.4413`. That is a leaderboard result, not this file's score. There is no organizer submission receipt in this repository for the generated file.

---

## Executive answer to the H33 question

The GEMSDOE32 page supplied in the brief displays a **mirror-reported** H33 value of `0.2778`; the page does not provide an organizer submission receipt or a hash-to-score crosswalk. This repository therefore does **not** call that value organizer-confirmed and does not use it as a training label. The official page currently shows an `ORGANIZER-CONFIRMED` public leader of `0.4413`, so the old `0.3195` comparison in the brief is stale.

What can be learned from the H33 bytes and its local receipt is conditional and useful:

1. **Mass is costly under the official metric.** DrivenData defines a distance-weighted Tversky index with `alpha = 0.2`, `beta = 0.8`, and a triangular kernel with 300 m support. Every emitted unit of probability incurs false-positive mass unless it earns nearby true-positive credit. A dense line or broad continuous field can spend mass repeatedly on already-covered neighbourhoods.
2. **Thinning can improve credit density.** The mirrored H33 artifact is a sparse binary field with `37654` positive cells and no positive cell on the mapped catalogue in the local audit. Removing redundant or catalogue-adjacent mass can raise precision under the asymmetric metric. This explains why a dotted/trimmed artifact could outperform a dense precursor **if** its remaining dots align with hidden expert faults; it does not prove the mirror's displayed value.
3. **A catalogue buffer is a risk trade-off, not a discovery.** Pruning near known traces avoids spending mass where the organizer's target is intended to reward new faults, but it can also remove real hidden faults that parallel or intersect known faults. A buffer must be tested on a spatial holdout rather than justified from a leaderboard number.
4. **The decisive missing evidence is the private test set.** Public catalogue hide-and-recover can test geometry and emission efficiency, but it cannot prove performance on the private expert-labelled new faults. The official challenge description explicitly says the initial labels are private and later expanded by expert review.

The conclusion is therefore: **the H33 mechanism is a plausible sparse-emission explanation, not an attribution or a verified score.** A higher score than the mirror display is possible in principle, but this session found no organizer-confirmed evidence that H82-B improves the official leaderboard. The correct deliverable is the valid, clearly labelled candidate plus a negative run card, not a fabricated score claim.

---

## Current experiment result — one JSON card, no hidden projections

The complete required card is [`evidence/run_card.json`](evidence/run_card.json). The primary result is:

```json
{
  "hypothesis": "H82-B signed multi-physics curvature discordance",
  "holdout_dti": {
    "evidence_class": "HOLDOUT-DTI",
    "evaluator_version": "gemsdoe82-pooled-hide-v1",
    "dti": 0.013925211177605194,
    "ci95": [0.009949051706376702, 0.018292877858376997],
    "withheld_positive_pixels": 10730
  },
  "registry_gate": {
    "surface_max_sampled_spearman": 0.05307039932280373,
    "surface_max_candidate_support_within_3px": 0.2294891427423567,
    "final_dots_max_sampled_spearman": 0.03683331529931281,
    "final_dots_max_candidate_dots_within_3px": 0.6726775375790088,
    "thresholds": {"rank_correlation_gt": 0.90, "candidate_dots_within_3px_gt": 0.70},
    "duplicate": false
  },
  "raster_sha256": "1deab2d36b9dd2b702bf1775fa3d0aad1ae5a4cd36617e0028aa9dfeb37a1036",
  "validator": "all checks passed; all cells finite and in [0,1]; CRS/shape/transform match",
  "verdict": "negative"
}
```

The numeric DTI and interval above are **HOLDOUT-DTI** from evaluator `gemsdoe82-pooled-hide-v1`, pooled over `10730` withheld catalogue-positive pixels and 159 spatial blocks with a 2,000-draw spatial-block bootstrap. They are not an organizer score, projection, or private-test estimate. The registry values are uniqueness diagnostics, not scores. The scanned inventory contains 48 locally available single-band rasters from the GEMSDOE32 and GEMSDOE70 public owner mirrors; it is explicitly **not organizer-complete**.

---

## What was implemented

- **Shared feature stack reader:** validates all 19 supplied bands, removes the documented float32 sentinel before calculations, and uses the finite mask of `sample_submission.tif` as the footprint.
- **Three preregistered candidates, exactly three experiments:** H82-A, H82-B, and H82-C. Results and canaries are in [`evidence/experiments.json`](evidence/experiments.json). H82-B was the best of those three by the frozen HOLDOUT-DTI instrument.
- **Leakage canary:** each candidate surface and each input layer used by that candidate was tested alone against withheld positives. The strongest H82-B canary was below the `0.90` stop threshold; details are in the experiment receipt.
- **Hide-and-recover holdout:** whole eight-connected catalogue components are withheld within four spatial quadrants; a 3-pixel collar is removed from the visible catalogue feature context; visible catalogue pixels are masked pixel-exactly; DTI terms are pooled before the ratio; 300 m triangular kernel, `alpha=0.2`, `beta=0.8`.
- **Fail-closed writer:** no clipping, filling, silent repair, or manual byte edits. It refuses NaN, infinity, sentinel values, out-of-range values, wrong grid metadata, positive mass outside the footprint, or positive mass on the mapped catalogue.
- **Uniqueness gate:** checks the surface before placement and the final dots after placement against the locally available registry. It stops with a duplicate status if rank correlation exceeds `0.90` or more than `70%` of candidate dots lie within 3 px of a registry raster.
- **GitHub Pages site:** [`docs/index.html`](docs/index.html) is the first page; [`docs/executive-summary.html`](docs/executive-summary.html) gives the exact no-manual-intervention submission workflow and distinguishes download validity, scientific promotion, and organizer acceptance.

### Reproduce from the cached public mirror

The official data tab redirects to login in this environment. If the user supplies the official files, set `GEMS_DATA_DIR` to that directory. Otherwise the autonomous public-mirror fetcher obtains pinned bytes into the ignored cache:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fetch_public_mirror_cache.py
GEMS_DATA_DIR="$PWD/.cache/gems_data/core" .venv/bin/python scripts/prepare_data.py
GEMS_DATA_DIR="$PWD/.cache/gems_data/core" .venv/bin/python scripts/run_experiments.py
GEMS_DATA_DIR="$PWD/.cache/gems_data/core" .venv/bin/python scripts/build_submission.py
```

The public mirror is useful for reproducibility but is not organizer authentication. The 19-band TIFF is intentionally ignored and is not committed. The generated submission and its receipts are committed because the user explicitly requested an easy download.

### Tests

```bash
.venv/bin/pytest
```

---

## Preregistered H82 hypotheses

The full table with layer names, physical signatures, off-catalogue rationale, novelty audit, cost, result, and external-data status is [`docs/hypotheses.md`](docs/hypotheses.md). In brief:

| Rank before the run | Candidate | Target | New relative to prior GEMSDOE lanes | Data status |
|---:|---|---|---|---|
| 1 | H82-A | cross-scale edge persistence + pairwise orientation + weak-relief gate | not a catalogue-flank, ridge, tip, relay, or submodular rule | supplied 19-band stack |
| 2 | H82-B | signed Laplacian-curvature polarity dispersion across magnetic/gravity/cover/MT | not a plain gradient or multi-physics orientation vote | supplied 19-band stack |
| 3 | H82-C | strain-saddle × conductive/basement edge | excludes the earlier earthquake-swarm head and uses a different conjunction | supplied 19-band stack |
| 4 | H82-D | radiometric ratio curvature plus potential-field edge mismatch | uses K/Th/U products not in the 19-band input | official USGS GeoDAWN DOI; deferred, obtainable but not run |
| 5 | H82-E | 1 m LiDAR directional roughness with multi-scale scarplet persistence | not run because the cache was not part of this validated three-experiment budget | official USGS 3DEP / competition DEM links; deferred |

The result ranking was H82-B, H82-C, H82-A by **HOLDOUT-DTI**. The pre-run ranking was a scientific priority order, not a post-hoc selection rule.

---

## Official, trusted sources and line-by-line verification

- [DrivenData competition overview](https://www.drivendata.org/competitions/306/competition-doe-gems/) — mission, data-download workflow, external-data licensing statement, and competition dates.
- [DrivenData problem description, page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) — fault-prediction task; provided magnetic, gravity, strain, seismic, topographic, conductivity and basement layers; distance-weighted Tversky equations; 300 m triangular kernel; submission format.
- [DrivenData data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) — access point. In this environment it was verified to redirect to login; no claim is made that a public mirror is organizer-authenticated.
- [Official DrivenData leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) — dynamic organizer page; the `0.4413` public-leader reading in this repo is **ORGANIZER-CONFIRMED** as a page snapshot, not a claim about this candidate.
- [GEMS official rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) — official competition governance, submission phases, eligibility, external-data requirements, and use of submitted predictions for expert review.
- [USGS GeoDAWN data release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) — official 2024 data release, DOI `10.5066/P93LGLVQ`, magnetic/radiometric survey provenance, airborne LiDAR coordination, CC0 statement.
- [GBCGE INGENIOUS project](https://gbcge.org/current-projects/ingenious/) — project goal, collaborators, and Great Basin geothermal exploration context.
- [DOE GDR submission 1391](https://gdr.openei.org/submissions/1391) — public INGENIOUS compilation, DOI `10.15121/1881483`, CC BY 4.0, and catalogued geophysical/geothermal resource families. It is a candidate source for deferred external-data work, not a hidden-label substitute.
- [EPSG:32611](https://epsg.io/32611) — WGS 84 / UTM zone 11N, metre units and official EPSG definition used for the output grid.
- [Organizer reference solution](https://github.com/drivendataorg/gems-prize-reference-solution) — official starting-point repository; it confirms that competition data must be placed locally and a GeoTIFF matching the format must be generated.

A source matrix, claims/limits, and the retrieval date are in [`docs/sources.md`](docs/sources.md) and [`registry/sources.json`](registry/sources.json). Irregularities are listed in [`docs/irregularities.html`](docs/irregularities.html) and [`registry/irregularities.json`](registry/irregularities.json).

---

## Limitations and next work

1. **Private truth is unavailable.** No local holdout can establish the private expert-test score. The generated candidate must not be described as higher-scoring without an organizer receipt.
2. **The public-mirror cache is not organizer-authenticated.** The official data page was login-walled here. The source hashes, commit IDs, and metadata are recorded for audit, but they do not replace competition authentication.
3. **The registry is incomplete.** The local surface/dot uniqueness scan covers only 48 rasters present in the two downloaded sibling repositories. It cannot clear deleted, private, uncommitted, or other-site rasters. It did not fire the prescribed thresholds.
4. **Catalogue holdout is a proxy.** Hiding known catalogue components tests recovery and emission mechanics, not newly discovered expert faults. Negative results are retained as deliverables.
5. **No external data was required for H82-B.** H82-D and H82-E require official-source ingestion and licensing checks before any future experiment. Do not add them outside the shared template or exceed the three-experiment/2-hour budget.
6. **Selector separation remains intentional.** This session generated a format-ready file but used zero weekly slots. A separate selector step must compare a current, audited holdout incumbent, check the complete registry, and make any real upload decision.

---

## Core values

### Maximize P(Win)

Every choice is treated as an experiment-design decision: preserve the scarce weekly slots, test a physically motivated mechanism, use the organizer metric rather than a convenient proxy, and stop on a negative result instead of optimizing a flattering number.

### Own the Outcome

The repository owns the end-to-end path: data provenance, feature construction, leakage canaries, holdout scoring, registry uniqueness, byte-level validation, the download link, the upload note, and the limitations. A valid file is not mislabeled as a winning file, and a negative result is not hidden.

---

## Repository map

- `src/gemsdoe82/feature_stack.py` — feature stack and H82 surfaces.
- `src/gemsdoe82/evaluate_holdout.py` — shared holdout and pooled DTI.
- `src/gemsdoe82/metric.py` — official metric implementation plus test oracle.
- `src/gemsdoe82/submission_writer.py` — fail-closed GeoTIFF/ZIP writer and validator.
- `scripts/fetch_public_mirror_cache.py` — pinned public-mirror fetch; never claims official authentication.
- `scripts/prepare_data.py` — input audit and manifest.
- `scripts/run_experiments.py` — exactly three preregistered experiments.
- `scripts/build_submission.py` — packages the selected-by-holdout candidate, without slot promotion.
- `scripts/registry_compare.py` — pre-placement and final-dots uniqueness gates.
- `docs/` — static GitHub Pages site, executive summary, research, sources, and download artifact.
- `evidence/` — machine-readable receipts and the final JSON run card.
- `registry/` — source, data, hypothesis, and irregularity records.

**Generated artifact policy:** raw competition features and caches remain ignored; the small, validated submission TIF, one-TIFF ZIP, receipts, and audit documents are retained because they are the requested deliverables.
