# Competition data placement

The official competition data tab requires a DrivenData login and was not accessible without authentication in this checkout. Do not try to bypass that gate. After obtaining the authorized package through the official page, place the files here using the accepted names below, then run `python scripts/check_readiness.py`.

| Purpose | Accepted filename from the project request |
|---|---|
| Numerical feature stack | `training_features.tif` or `gems-geodawn-numerical-features.tif` |
| Fault labels / existing faults | `labels.tif` or `existing_faults.tif` |
| Official sample grid/template | `sample_submission.tif` or `example_submission.tif` |
| Optional 1 m DEM index | `1m_DEM_links.csv` or `digital_elevation_model_links.json` |

**Do not commit competition rasters, DEM tiles, credentials, or large derived caches.** Keep their checksums and provenance in the registry. This file does not authorize the use of unverified GitHub mirrors in place of organizer data.

This checkout intentionally does not include `download_competition_data.sh`, `prepare_data.py`, `evaluate_holdout.py`, or `submission_writer.py`; inventing replacements would violate the project’s “reuse the shared template” rule. Locate and pin the canonical template before preparing data or running an experiment.