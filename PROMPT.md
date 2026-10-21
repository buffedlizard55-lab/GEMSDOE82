# Retained project prompt and operating brief

This file preserves the user's project brief so future sessions start from the same objective. The working README is the shorter executable summary. The following requirements are binding for this repository.

## Highest-urgency requirements

- Generate a **unique TIF submission** for the GEMS competition. Never copy a previous submission except for learning/education. Make it obvious whether the generated TIF is safe to download and whether it is actually promoted for contest upload.
- The inspection must run through this project and be validated without human intervention. The site must offer an easy download, an exact submission name, and a short note.
- Work line by line from official, trusted sources; provide links for manual review; flag irregularities; do not hallucinate; verify every calculation.
- Read this prompt at the start of every session.

## Parallel-run protocol

1. **Lane.** Work in a single method lane. Before placement and after final dot placement, compare the raster with the registry. If rank-correlation with any registry raster exceeds `0.90`, or if more than `70%` of dots fall within 3 px of a registry raster's dots, log a duplicate and stop.
2. **Reuse, do not rebuild.** Use the template's cached feature stack, `evaluate_holdout.py`, and `submission_writer.py`. Holdout means hide-and-recover: withhold whole fault segments with a buffer, derive catalogue-based features only from visible faults, mask visible faults pixel-exactly, and score pooled DTI with alpha `0.2`, beta `0.8`, and a 300 m triangular kernel. If a shared tool is wrong, fix it once in the template and report it; do not maintain a private fork.
3. **Label numbers.** Every performance number must be labelled either `HOLDOUT-DTI` with evaluator version, number of withheld positives, and 95% CI, or `ORGANIZER-CONFIRMED` copied from an organizer submission/leaderboard receipt. A projection is never written as a score.
4. **Leakage canary.** Test each feature alone on holdout before trusting it. AUC above `0.90` means leakage until proven otherwise.
5. **Run card.** End with one JSON card containing: hypothesis; mechanism; named non-fault process that could mimic it; holdout DTI and CI; correlation/overlap against registry; raster SHA-256; validator output (no NaN inside footprint, values in `[0,1]`, CRS/shape/transform match); submission name; note of at most 140 characters; verdict `promote` or `negative`.
6. **Budget.** Stop after `3` experiments or `2` hours. Do not pick submissions: promotion to a real slot is a separate selector step within the weekly cap on the submission page. Negative results are deliverables.

## User's scientific and product objective

Study the GEMS challenge and the highest result displayed on the GEMSDOE site:

- [GEMSDOE32 site](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)
- The site lists `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` with a mirror-displayed value of `0.2778`. Investigate why/how it could be high, distinguish a mirror claim from an organizer receipt, and determine whether a genuinely unique candidate can do better.
- The user also reported an earlier current high of `0.3195`; always re-check the official dynamic leaderboard rather than assuming that value is current.
- The final goal is to compete for a top leaderboard position, while remaining scientifically grounded and honest about the private test set.
- Think deeply about scientific discovery of geothermal-indicative faults and overlooked official/free data. Store research and verified sources for future sessions.
- Keep Arena values central: **Maximize P(Win)** and **Own the Outcome**.

Before implementation, generate 3–5 candidate geological hypotheses not already tried. For each, name the specific layers, physical signature, reason it should find a fault missing from the USGS/INGENIOUS catalogue rather than a mapped fault, and the difference from prior implementation. Rank expected DTI improvement and implementation cost. If new external data is required, name the free official source and check whether it is obtainable before calling the idea viable.

## Competition and source links

- [Competition overview](https://www.drivendata.org/competitions/306/competition-doe-gems/)
- [Problem description page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [About page 968](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/)
- [Competition data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
- [Official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
- [Official rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
- [Organizer reference solution](https://github.com/drivendataorg/gems-prize-reference-solution)
- [USGS GeoDAWN](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)
- [GBCGE INGENIOUS](https://gbcge.org/current-projects/ingenious/)
- [DOE GDR 1391](https://gdr.openei.org/submissions/1391)
- [EPSG:32611](https://epsg.io/32611)
- [Tversky index background](https://en.wikipedia.org/wiki/Tversky_index)
- [GEMS rules/data PDF mirror](https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&st=wz4kofki&dl=0)
- [Example submission mirror](https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0)
- [Existing faults mirror](https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0)
- [GeoDAWN numerical features mirror](https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0)
- [DEM link PDF mirror](https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&st=srhhir10&dl=0)

The official data page redirected to login during this session. The project must not claim that a public owner mirror is organizer-authenticated. The autonomous fetcher may use pinned public GitHub mirrors for reproducibility, with hashes and provenance clearly recorded.

## Prior site results to audit, not copy

The user supplied these sibling pages/results as a research registry. They are historical context, not permission to copy an output:

- [GEMSDOE32](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html): H33 H33-2-B2 mirror display `0.2778`.
- [GEMSDOE](https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html): `0.1563`.
- [6GEMSDOE](https://buffedlizard55-lab.github.io/6GEMSDOE/): `0.0286`.
- [GEMSDOE3](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html): `0.1193`, `0.0830`, `0.1152`.
- [GEMSDOE2](https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html): `0.1560`.
- [GEMSDOE4](https://buffedlizard55-lab.github.io/GEMSDOE4/): `0.0343`.
- [5GEMSDOE](https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html): `0.1563`.
- [7GEMSDOE](https://buffedlizard55-lab.github.io/7GEMSDOE/): `0.1461`.
- [8GEMSDOE](https://buffedlizard55-lab.github.io/8GEMSDOE/): `0.1563`.
- [GEMSDOE9](https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html): `0.0107`.
- [11GEMSDOE](https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html): `0.0202`.
- [12GEMSDOE](https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html): `0.1294`.
- [15GEMSDOE](https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html): `0.0782`.
- [14GEMSDOE](https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html): `0.0020`.
- [17GEMSDOE](https://buffedlizard55-lab.github.io/17GEMSDOE/): `0.0187`.
- [18GEMSDOE](https://buffedlizard55-lab.github.io/18GEMSDOE/): `0.0297`.
- [19GEMSDOE](https://buffedlizard55-lab.github.io/19GEMSDOE/docs/index.html): `0.1894`, `0.1922`.
- [GEMSDOE10](https://buffedlizard55-lab.github.io/GEMSDOE10/): `0.0461`, `0.0921`, `0.1280`, `0.1839`.
- [13GEMSDOE](https://buffedlizard55-lab.github.io/13GEMSDOE/): `0.0904`.
- [16GEMSDOE](https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html): `0.1855`, `0.0976`, `0.0360`.
- [GEMSDOE21](https://buffedlizard55-lab.github.io/GEMSDOE21/): `0.1894`.
- [20GEMSDOE](https://buffedlizard55-lab.github.io/20GEMSDOE/docs/index.html): `0.1890`, `0.1859`.
- [GEMSDOE22](https://buffedlizard55-lab.github.io/GEMSDOE22/docs/index.html): `0.1002`, `0.0748`.
- [GEMSDOE23](https://buffedlizard55-lab.github.io/GEMSDOE23/): `0.1352`.
- [GEMSDOE24](https://buffedlizard55-lab.github.io/GEMSDOE24/): `0.2477`.
- [GEMSDOE25](https://buffedlizard55-lab.github.io/GEMSDOE25/): `0.2600`.
- [GEMSDOE26](https://buffedlizard55-lab.github.io/GEMSDOE26/): `0.1223`.
- [GEMSDOE27](https://buffedlizard55-lab.github.io/GEMSDOE27/): `0.2449`.
- [GEMSDOE30](https://buffedlizard55-lab.github.io/GEMSDOE30/): `0.2600`.
- [GEMSDOE31](https://buffedlizard55-lab.github.io/GEMSDOE31/docs/): `0.2708`.
- [GEMSDOE33](https://buffedlizard55-lab.github.io/GEMSDOE33/): `0.2632`.
- [GEMSDOE34](https://buffedlizard55-lab.github.io/GEMSDOE34/docs/index.html): `0.0778`.
- [GEMSDOE35](https://buffedlizard55-lab.github.io/GEMSDOE35/docs/index.html): `0.0418`.
- [GEMSDOE36](https://buffedlizard55-lab.github.io/GEMSDOE36/docs/): `0.2750`.
- [GEMSDOE37](https://buffedlizard55-lab.github.io/GEMSDOE37/): `0.1193`.
- [GEMSDOE38](https://buffedlizard55-lab.github.io/GEMSDOE38/docs/index.html): `0.0763`.
- [GEMSDOE40](https://buffedlizard55-lab.github.io/GEMSDOE40/docs/index.html): `0.0355`, `0.0397`, `0.0984`.
- [GEMSDOE41](https://buffedlizard55-lab.github.io/GEMSDOE41/docs/index.html): `0.0245`.
- [GEMSDOE42](https://buffedlizard55-lab.github.io/GEMSDOE42/docs/index.html): `0.0581`.
- [GEMSDOE43](https://buffedlizard55-lab.github.io/GEMSDOE43/docs/index.html): `0.0424`.
- [GEMSDOE44](https://buffedlizard55-lab.github.io/GEMSDOE44/docs/): `0.0715`.
- [GEMSDOE45](https://buffedlizard55-lab.github.io/GEMSDOE45/): `0.0106`.
- [GEMSDOE46](https://buffedlizard55-lab.github.io/GEMSDOE46/): `0.1589`, `0.0843`.
- [GEMSDOE47](https://buffedlizard55-lab.github.io/GEMSDOE47/): `0.0430`.
- [GEMSDOE48](https://buffedlizard55-lab.github.io/GEMSDOE48/docs/index.html): `0.2296`.
- [GEMSDOE49](https://buffedlizard55-lab.github.io/GEMSDOE49/): `0.2376`.
- [GEMSDOE50](https://buffedlizard55-lab.github.io/GEMSDOE50/): `0.0764`.
- [GEMSDOE51](https://buffedlizard55-lab.github.io/GEMSDOE51/): `0.1047`.
- [GEMSDOE52](https://buffedlizard55-lab.github.io/GEMSDOE52/): `0.0856`.
- [GEMSDOE53](https://buffedlizard55-lab.github.io/GEMSDOE53/docs/index.html): `0.0159`.
- [GEMSDOE54](https://buffedlizard55-lab.github.io/GEMSDOE54/docs/): `0.0449`.
- [55GEMSDOE](https://buffedlizard55-lab.github.io/55GEMSDOE/docs/index.html): `0.0290`.
- [56GEMSDOE](https://buffedlizard55-lab.github.io/56GEMSDOE/docs/index.html): `0.0658`.
- [57GEMSDOE](https://buffedlizard55-lab.github.io/57GEMSDOE/docs/index.html): `0.0254`.
- [58GEMSDOE](https://buffedlizard55-lab.github.io/58GEMSDOE/docs/index.html): `0.0180`.
- [59GEMSDOE](https://buffedlizard55-lab.github.io/59GEMSDOE/docs/index.html): `0.0499`.
- [60GEMSDOE](https://buffedlizard55-lab.github.io/60GEMSDOE/docs/index.html): `0.0351`.
- [61GEMSDOE](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/index.html): `0.0009`, `0.0751`.
- [62GEMSDOE](https://buffedlizard55-lab.github.io/62GEMSDOE/): `0.0000`.
- [GEMSDOE63](https://buffedlizard55-lab.github.io/GEMSDOE63/): `0.2303`.
- [GEMSDOE64](https://buffedlizard55-lab.github.io/GEMSDOE64/): `0.0383`.
- [GEMSDOE65](https://buffedlizard55-lab.github.io/GEMSDOE65/docs/index.html): `0.0431`.
- [GEMSDOE66](https://buffedlizard55-lab.github.io/GEMSDOE66/docs/index.html): `0.1152`.
- [GEMSDOE67](https://buffedlizard55-lab.github.io/GEMSDOE67/): `0.0356`, `0.1426`.
- [GEMSDOE68](https://buffedlizard55-lab.github.io/GEMSDOE68/): `0.0437`.
- [GEMSDOE69](https://buffedlizard55-lab.github.io/GEMSDOE69/): `0.0053`.
- [GEMSDOE70](https://buffedlizard55-lab.github.io/GEMSDOE70/): `0.2478`.
- [GEMSDOE71](https://buffedlizard55-lab.github.io/GEMSDOE71/): `0.0558`.
- [GEMSDOE72](https://buffedlizard55-lab.github.io/GEMSDOE72/): `0.0492`.
- [GEMSDOE73](https://buffedlizard55-lab.github.io/GEMSDOE73/), [74](https://buffedlizard55-lab.github.io/GEMSDOE74/), [75](https://buffedlizard55-lab.github.io/GEMSDOE75/), [76](https://buffedlizard55-lab.github.io/GEMSDOE76/), [77](https://buffedlizard55-lab.github.io/GEMSDOE77/), [78](https://buffedlizard55-lab.github.io/GEMSDOE78/), [79](https://buffedlizard55-lab.github.io/GEMSDOE79/), [80](https://buffedlizard55-lab.github.io/GEMSDOE80/), [81](https://buffedlizard55-lab.github.io/GEMSDOE81/), [82](https://buffedlizard55-lab.github.io/GEMSDOE82/), [83](https://buffedlizard55-lab.github.io/GEMSDOE83/): no result was supplied for the blank pages in the brief.

These values are retained as user/owner research context. They must not be silently converted into organizer-confirmed labels. The official leaderboard and official receipts control score claims.

## Submission and site requirements

- Site first page must make the download and status obvious.
- Explain exactly how to upload one `.tif` or a `.zip` containing one `.tif`, how to paste the unique name and note, and why not to upload both.
- Validate `float32`, one band, CRS/shape/transform/bounds, finite values, range `[0,1]`, no sentinel, and footprint handling.
- Include executive summary, research, hypotheses, sources, irregularities, and machine-readable receipts.
- Make all checks autonomous; no manual inspection is required to decide format validity.
- Run three review passes: implementation, bug/edge-case review, and final requirements review.
- Create a GitHub Pages site and, after local verification, create a pull request from the fixed Arena branch and merge that PR using the explicit PR number. Never rename or switch the Arena branch.

## Core Values

**Maximize P(Win):** use the official metric, preserve scarce slots, pre-register hypotheses, and select only after spatial validation.
**Own the Outcome:** carry data provenance, research, modeling, validation, delivery, limitations, and negative results end to end.
