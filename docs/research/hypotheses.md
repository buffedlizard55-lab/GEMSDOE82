# Preregistered candidate hypotheses

**State:** hypothesis design only; **none was run**. At the start of the review the checkout had no input rasters, cached feature stack, shared holdout evaluator, writer, or registry rasters. These are therefore not viable submissions and no expected gain below is a score or projection.

## Lane caveat

The parallel-run instructions say to stay within “the single method paragraph below,” but the request contains no distinct method paragraph. The candidate register below proposes one provisional lane—magnetic source-depth boundaries—for later validation. No placement or raster emission is authorized until the project owner’s lane is unambiguous and registry comparisons can be made. Current checkout contents are verified in `README.md`; the older site titles below are user-provided context and may not fully describe their implementations.

## Rank order

Ranking is qualitative, based on physical specificity and likely DTI value per engineering effort—not on measured performance. Every mechanism must be tested against the spatially blocked holdout with the shared evaluator and leakage canary before it can be called promising.

### Rank 1 — Magnetic source-depth boundary discontinuities

- **Layer(s):** The official `training_features.tif` band described as top-of-crustal magnetic-source depth estimate; total magnetic intensity (TMI), reduced-to-pole magnetic anomaly, and the supplied horizontal/vertical TMI gradients as independent corroboration.
- **Physical signature:** A scale-persistent, oriented edge in the source-depth estimate, retained only where the independent magnetic-field gradient supports a coherent contact. This is a depth-boundary/edge hypothesis, not “high magnetic anomaly = fault.”
- **Why it may find faults absent from USGS/INGENIOUS:** A basement step or concealed intrasedimentary fault may juxtapose magnetic units beneath alluvium, leaving a weak or absent surface scarp. The public fault catalogue is incomplete by the competition definition. USGS literature documents examples of aeromagnetic anomalies associated with faulted strata, but that does not establish that the same signature occurs in this AOI.
- **Difference from this repo and known history:** This checkout initially contained no transforms or model code. Compared with the supplied prior-result titles such as generic “topo-geophys-baseline-ridges” and “conj_alteration_mag,” the primary evidence here is the *source-depth estimate’s boundary*, not a topographic ridge, a broad anomaly, radiometric alteration, a mapped-fault extension, or a dot-sampling rule. The titles do not expose all prior feature choices; cross-repo novelty is provisional until the actual registry/source is audited.
- **Named non-fault mimic:** A lithologic contact, dike, or intrusive body can produce magnetic-source-depth and field-gradient boundaries without a fault. USGS explicitly cautions that aeromagnetic signatures reflect contrasts in magnetic properties; use the boundary as a hypothesis, not a geological label.
- **Expected DTI improvement / cost:** **Moderate potential, low confidence; low-to-medium implementation cost** if the cached stack already contains the required official bands. No numeric gain is projected.
- **New external data / viability:** None beyond the competition-provided feature raster. **Not locally viable yet** because that raster and the canonical cached stack are absent.
- **Pre-registered test:** Fit/normalize transforms using training folds only; score the depth band alone and each corroborating band alone on the spatial holdout before their combination. Run a feature-only AUC leakage canary. Generate no dots until the surface passes the duplicate-correlation and 3-pixel overlap gates.

### Rank 2 — Residual heat-flow anomalies aligned to independent structure

- **Layer(s):** USGS Great Basin background conductive heat-flow maps and geothermal-well residuals from the [USGS heat-flow data release](https://www.usgs.gov/data/heat-flow-maps-and-supporting-data-great-basin-usa), paired with the competition’s magnetic-source-depth or gravity-boundary surface.
- **Physical signature:** A compact heat-flow residual (well departure from background conductive flow) near a structural edge, rather than simply ranking broad high-heat-flow areas. This tries to distinguish local fluid advection from regional thermal background.
- **Why it may find faults absent from USGS/INGENIOUS:** Localized fluid circulation can mark a permeable fault that lacks a well-mapped surface trace. The heat-flow data release contains residual information intended to express departures from estimated background conditions; this is a candidate signal, not proof that an individual residual is fault controlled.
- **Difference from this repo and known history:** No heat-flow raster or point input exists in the current checkout. The user-provided result titles mention hydro-conduit, radon, and geothermal/thermal ideas, so this candidate is not certified globally novel; its specific residual-plus-independent-structural-edge test is the distinction to audit.
- **Named non-fault mimic:** Groundwater advection, local thermal conductivity, well-depth/measurement error, and spatially uneven well sampling can create a residual without a fault trace.
- **Expected DTI improvement / cost:** **Low-to-moderate potential, low confidence; high cost** because new data must be acquired, inspected, spatially joined and compared with the competition grid.
- **Specific free official source / availability check:** USGS Great Basin heat-flow release, DOI [10.5066/P9BZPVUC](https://doi.org/10.5066/P9BZPVUC), which its official catalog identifies as public domain/CC0. The official source is discoverable; the files, grid resolution and AOI overlap were **not** downloaded or checked here. It is therefore **not viable for a submission yet**.

### Rank 3 — Lithology-conditioned magnetic-edge residual

- **Layer(s):** Competition magnetic source-depth/TMI-gradient layers plus geologic-unit polygons from the USGS [Nevada geologic map data](https://mrdata.usgs.gov/geology/state/) or USGS [State Geologic Map Compilation](https://www.sciencebase.gov/catalog/item/5888bf4fe4b05ccb964bab9d). Use polygon lithology only; do not use mapped fault lines as prediction features.
- **Physical signature:** Estimate whether a magnetic edge is already explained by an ordinary mapped lithologic-unit boundary, then test the residual edge signal for persistence/linearity. A boundary unexplained by the polygon map may be a concealed structure; a boundary coincident with a contact is ambiguous, not automatically discarded.
- **Why it may find faults absent from USGS/INGENIOUS:** A concealed fault may juxtapose units or create a magnetic contact where a generalized surface map has no fault trace. Explicitly modeling mapped lithology can also remove some non-fault magnetic edges and free emission budget for less obvious structures.
- **Difference from this repo and known history:** Nothing is implemented in this checkout. This differs from the supplied `h18-4-usgs-geologic-map-faults-gap` title by using mapped *rock-unit polygons as a confounder model*, not gaps between mapped fault lines. Because an earlier map-based experiment exists, this candidate has **high duplication/implementation-overlap risk** and needs an audit before implementation.
- **Named non-fault mimic:** A true fault may coincide with a lithologic boundary; coarse or outdated polygons may misrepresent the contact. Conversely, intrusive contacts, stratigraphic boundaries and map-scale generalization can leave residual edges.
- **Expected DTI improvement / cost:** **Low-to-moderate potential, low confidence; medium-to-high cost** due reprojection, scale/lineage review and an external polygon input.
- **Specific free official source / availability check:** The official [USGS state-geology listing](https://mrdata.usgs.gov/geology/state/) lists a Nevada `NV.zip` Shapefile + CSV download at `https://mrdata.usgs.gov/geology/state/shp/NV.zip`; it also links the [SGMC release](https://www.sciencebase.gov/catalog/item/5888bf4fe4b05ccb964bab9d). The listing is reachable, but the file bytes, AOI coverage, scale suitability and raster alignment were not checked here. **Not viable yet.**

### Rank 4 — Fault-localized strain-rate change points

- **Layer(s):** Competition dilatation rate, shear-strain rate and second invariant of the strain-rate tensor, with magnetic source-depth boundaries used only as independent context.
- **Physical signature:** Spatially compact changes in shear/dilatation and a co-located strain-rate ridge/edge, rather than a regional maximum or a generic multi-band score. Avoid inventing vector orientation if the supplied bands are scalars.
- **Why it may find faults absent from USGS/INGENIOUS:** Active or recently active faults can localize crustal deformation before a clearly mappable surface expression develops. A test on withheld complete segments would determine whether the provided strain fields resolve that scale.
- **Difference from this repo and known history:** No implementation exists in this checkout. It uses the geodetic strain fields as the primary mechanism, not topographic scarps, channel lineaments, magnetic magnitude, or catalogue-tip continuation. Prior broad “geophysics” titles could contain strain; exact novelty is unverified.
- **Named non-fault mimic:** Smooth regional tectonic loading, volcanic inflation, interpolation artifacts, or a spatially varying geodetic network can produce apparent strain-rate gradients.
- **Expected DTI improvement / cost:** **Low and uncertain; low-to-medium cost** from the supplied feature stack. It is ranked last because broad strain fields may not resolve individual fault traces at the target raster scale.
- **New external data / viability:** None beyond the competition feature raster. **Not locally viable yet** because the feature stack is missing.

## Evaluation gates (not run)

1. **Inputs first:** locate the canonical template; verify its feature cache, pinned evaluator, writer, label mask and sample-grid receipt. None is in this checkout.
2. **Leakage canary:** one feature at a time, with all feature transforms learned within the training fold; investigate any AUC above 0.90 before combining features.
3. **Hide-and-recover:** withhold whole fault segments plus a buffer; derive catalogue-based features only from visible segments; mask those visible pixels exactly; score pooled DTI using the organizer’s metric. Report evaluator version, number of withheld positives and 95% CI.
4. **No cherry-picking:** compare against the current best *holdout* using the same evaluator and split. The historical organizer leaderboard is not a holdout comparator.
5. **Uniqueness before and after placement:** compare the candidate surface to each registry raster by rank-correlation and the fraction of final dots within 3 px. If either protocol threshold is crossed, log it as a duplicate and stop.
6. **Emission/format:** only after the candidate beats the current holdout best may the separate selector consider a slot. Validate values in [0,1], footprint masking, CRS, shape and transform against the official template; record SHA-256. No such evaluation or emission occurred in this review.

## Primary sources

- [DrivenData problem description and feature descriptions](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [USGS aeromagnetic anomalies over faulted strata](https://www.usgs.gov/publications/aeromagnetic-anomalies-over-faulted-strata) — evidence from another region, not proof for GeoDAWN.
- [USGS Great Basin heat-flow release](https://www.usgs.gov/data/heat-flow-maps-and-supporting-data-great-basin-usa)
- [USGS state-geology listing (Nevada NV.zip available)](https://mrdata.usgs.gov/geology/state/)
- [USGS State Geologic Map Compilation](https://www.sciencebase.gov/catalog/item/5888bf4fe4b05ccb964bab9d)