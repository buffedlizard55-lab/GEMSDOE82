# Three-pass implementation review

**Review date:** 2026-10-21. This log records what was implemented, what each pass found, and what remains blocked. It is not a scientific experiment or a score report.

## Pass 1 — implement the useful work available

- Inspected the entire initial tracked checkout: it contained only `README.md`.
- Read the official GEMS problem page, about page, leaderboard and data tab. The data tab redirected the unauthenticated request to login; no training package or template grid was available.
- Read the linked public GEMSDOE32 build metadata. It labels the cited H33 artifact unscored and its projected value a model, not a score; no submission-page receipt was in the reviewed repository.
- Added the permanent README charter, official source ledger, four ranked hypotheses, score-attribution review, irregularity log, machine-readable negative run card, and explicit local data placement notes.
- Built a responsive GitHub Pages site with an executive-summary submission guide. Its download control is disabled and says not to submit because there is no candidate file.
- Added non-invasive readiness diagnostics, a score-free official-source status feed, a scheduled Pages-refresh workflow, and standard-library unit tests. No model, evaluator, writer, data or TIFF was copied or rebuilt.

## Pass 2 — audit assumptions, bugs and unsafe wording

- **Source URL defect found and corrected:** the first Nevada geologic-map URL tried in the draft returned HTTP 404. The official USGS state-geology listing was then read and its Nevada `NV.zip` listing confirmed. The correction and the remaining file/AOI limitations are recorded as IR-82-11.
- **Readiness semantics tightened:** an early diagnostic used “ready” labels based on file presence and an assumed cache manifest. It was changed to accept only an explicitly supplied cache path and now reports asset presence separately; `submit_ready` is always false because the diagnostic cannot validate a model or portal upload.
- **Upload-format provenance clarified:** the public problem page specifies GeoTIFF; ZIP acceptance is attributed to the form text quoted in the user request and must be checked in the logged-in form at upload time.
- **Score classes tightened:** public leaderboard context is kept separate from project results and receipts. No projection or user-supplied group value is written as a score.
- **Data-source limits surfaced:** the USGS heat-flow, 3DEP, GeoDAWN, Nevada geology and earthquake sources are described as official listings/docs where checked, not as downloaded or aligned feature inputs.

## Pass 3 — final requirement and regression check

- At the end of this pass, confirmed there was no TIFF, submission download, canonical holdout result, confidence interval, leakage-canary result, correlation/overlap result, or organizer receipt in this branch. No canonical experiment or competition slot was spent.
- Ran `python -m unittest discover -v`: all seven local unit tests passed, including readiness fail-closed behavior, feed parsing without scores, and local site-link validation.
- Ran Python byte-compilation for the scripts/tests, parsed each JSON registry/feed file, checked the run-card note length and negative disposition, ran `git diff --check`, and smoke-tested the static site over HTTP. The site pages and feed returned successfully.
- Re-read the top-level README against the task: it makes non-readiness obvious, records the missing lane paragraph and required shared tools, captures the requested Core Values, links sources, and explains the upload process. The executive summary says plainly that there is no file to download or submit.
- **Final verdict: negative / blocked.** Generating a synthetic or copied TIFF would violate the uniqueness, shared-tool, holdout and duplicate-screening rules. The only safe next scientific step is to obtain the authorized competition package and canonical shared template, then run the preregistered top candidate through the exact holdout and registry gates.

## Post-pass merged-branch remediation

A concurrent PR #3 was merged to `main` after the pass-3 review. It added a downloadable TIFF, local experiment receipts, and private evaluator/writer code; its fetcher sourced the feature/label rasters from public sibling-repository mirrors because the official data page required login. The canonical shared tools and organizer-authorized inputs were still absent, and the scanned registry was explicitly incomplete. Under the standing protocol, those local metrics and the file's format/uniqueness claims are **not accepted**. PR #3's changes were reverted on this branch in commit `a489d79`; the TIFF, ZIP and receipts are no longer in the checkout. The associated Pages run failed at its test step before deployment. This remediation used no organizer submission slot. See IR-82-12.

## Deployment smoke test and correction

After PR #4, a fetch of the public site exposed a run-card link that escaped the project-site prefix and targeted a file outside the published `docs/` artifact. The site now links to `docs/data/run_card.json`; `scripts/sync_site_run_card.py` copies the canonical registry card into that published location, and link tests fail on paths that escape the Pages artifact. PR #5's workflow completed successfully, including sync, tests, upload, and deploy; all eight local tests pass.

A further cache-busted request to the registered root URL returned the repository README, while `/docs/` rendered the intended site. The Pages API still reports legacy `main:/`; changing the Pages build type through the available API returned HTTP 403. A root `index.html` redirect with a fallback link to `docs/` is now included so the registered URL can reach the site without a settings change. The root-redirect guard adds a ninth local test. **Root redirect behavior still requires post-merge verification; until then, `/docs/` is the verified public site path.**

## Reproducible local checks

```bash
python -m unittest discover -v
python -m py_compile scripts/check_readiness.py scripts/refresh_competition_feed.py scripts/sync_site_run_card.py tests/test_readiness.py tests/test_refresh_feed.py tests/test_site_links.py
python scripts/sync_site_run_card.py
python scripts/check_readiness.py
```

The readiness command returns a nonzero status while required assets are absent; this is expected and is not a score or model failure. The public-feed refresh uses no authentication and never downloads competition data or copies leaderboard score values.
