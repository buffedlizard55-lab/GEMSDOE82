# Local registry rasters for duplicate screening

Place prior/registry rasters here only as comparison inputs, never as the candidate deliverable. Keep a metadata manifest with each source name, SHA-256, provenance, grid metadata, and permission/receipt status. Do not commit large rasters; they are local-only and ignored by `.gitignore`.

Before candidate placement and again on final dots, compare every candidate surface against every registry raster. If a rank-correlation exceeds 0.90 or more than 70% of candidate dots fall within 3 pixels of a registry raster’s dots, record a duplicate and stop. This directory is empty in the current checkout, so the gate cannot run.
