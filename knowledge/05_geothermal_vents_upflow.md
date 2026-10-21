# Geothermal vents + upflow evidence in the footprint (measured, GDR 1391)

Source: [GDR 1391](https://gdr.openei.org/submissions/1391) (DOI 10.15121/1881483,
CC BY 4.0), files already on disk and sha256-pinned. All counts below were
computed from those files in this session (see command log); `dist_known_fault_px`
is label-derived and is NEVER used as a model input.

## Volcanic vents (gdr_volcanic_vents_in_footprint.csv)

* 21 vents in the footprint: 20 basalt, 1 rhyolite (row 1505, col 390).
* Three spatial clusters: NW cluster (rows ~370–471, cols ~2282–2358, 10 vents),
  central cluster (rows ~1182–1419, cols ~385–1022, 8 vents), southern pair +
  singletons (rows 2964–3226).
* Relevance: Quaternary basalt vents mark crustal-scale permeability; rhyolite
  marks evolved magmatic heat. A vent WITHOUT a nearby mapped fault implies a
  blind feeder structure — the canonical catalogue-missing fault. Lane 82 does
  not emit on vents directly (21 points cannot support a lineament operator);
  they corroborate the H82-5 thermal halo instead.

## Well/spring chemistry (gdr_wellspring_in_footprint.csv)

* 27,092 rows in footprint; 1,247 sites with ≥1 geothermometer reading;
  **180 sites with T_reservoir > 150 °C** (per-site max of quartz/chalcedony/
  cation estimators); max measured `temp_c` 296.54 °C.
* H82-5 turns the 1,247 measured reservoir temperatures into an IDW halo
  (L=20 px, k=8, σ=3). Holdout screen at matched budget: SGMC-FAR 0.0397
  (below base) — a halo is not a lineament, so H82-5 was DOCUMENTED, not
  shipped. Its role in future work: gate additions (already-hot corridors get
  priority), not emission.

## Quaternary fault traces (gdr_qfaults_traces.csv)

* INGENIOUS Quaternary fault-trace attributes (slip rate, recency, slip sense,
  centroid row/col). Unused by lane 82 (trace attributes, not a raster);
  filed as future corroboration (slip-rate-weighted priors).

## Bottom line for the competition

Surface heat (vents, >150 °C reservoirs) proves deep permeability exists at
sites where the 100 m catalogue may show nothing. The winning use is not
"emit on heat" (halos score ~0.04) but "emit lineaments, corroborate with
heat" — the fusion lane 82 ships.
