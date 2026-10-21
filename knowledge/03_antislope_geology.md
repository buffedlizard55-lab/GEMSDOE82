# Lane-82 science: why antislope scarps + the mimic list

## The core observation

In extensional Basin-and-Range terrain, a scarp that faces UPHILL cannot be
fluvial: streams, terrace risers, and channel banks always step DOWN-slope.
An uphill-facing step at 1–10 m scale is one of three things:

1. a normal-fault scarp (range-front, antithetic, or graben-bounding);
2. a gravitational headscarp (landslide, sackung / deep-seated gravitational
   slope deformation);
3. a resistant-bed bench (lithologic, dip-slope controlled).

The group's 1 m LiDAR stacks were previously used as generic slope-excess
composites (`0.45·ex_max + 0.35·step_max + 0.20·downface_max`), which are
dominated by downhill-facing steps — i.e. by exactly the fluvial/terrace
population. Lane 82 inverts the priority: the `upface_max` channel (band-passed
step gradient AGAINST the regional slope) is the primary detector, because its
background population excludes the largest confound class by construction.

## Why it should catch faults missing from the catalogue

Mapped catalogue faults are the large throughgoing structures with 100 m-scale
expression. Antislope scarplets at 1 m resolution reveal the complementary
population: young distributed antithetic/graben faults in piedmonts and fans,
relay ramps between mapped segments, and blind faults under thin cover whose
sub-meter surface creep still warps the 1 m DEM. These are precisely the faults
a 100 m-grid expert compilation misses.

## The named non-fault mimics (one per hypothesis)

| hypothesis | mimic | mitigation in the operator |
| --- | --- | --- |
| H82-1 antislope lineament | sackung/landslide headscarps; dip-slope benches | strike-agreement vote (faults are straight over 100s of m; slumps are arcuate) + channel-bank suppression (low `cross_max`) + NMS crest (thin lines, not alcoves) |
| H82-2 radiometric break | lithologic contacts (K/Th contrasts with no fault) | gradient-NMS (thin edges) + fusion (an isolated contact rarely coincides with antislope fabric); contacts are reported, not hidden |
| H82-3 valley deflection | axial playas, meander cutoffs, fan-head trenches | 7 px straightness vote; playa/meander curvature fails it |
| H82-4 conjugate intersection | dendritic drainage junctions | scarp-relief weighting (junctions on flat fans score ~0) |
| H82-5 thermal halo | lateral outflow plumes, shallow mixing | per-site MAX of three independent geothermometers (disagreement = mixing, down-weighted) + short IDW length (L=20 px) |

Residual risk (stated, not hidden): sackung in high-relief ranges produces
straight uphill-facing scarps that pass every gate above. A relief-mask
ablation is filed as next work; the shipped candidate mitigates by fusion
(sackung rarely coincides with radiometric breaks) and by small addition sizing.

## References (background; operators are our own)

* Faulds & Hinz (2015) — Great Basin geothermal systems concentrate at fault
  terminations, stepovers, and relay ramps (structural-setting rationale).
* Siler et al. (2019) — fault-intersection permeability (H82-4 rationale).
* Fournier & Potter — quartz/chalcedony geothermometers (H82-5 estimators).
* USGS GeoDAWN release, DOI 10.5066/P93LGLVQ (radiometric/magnetic source).
* GDR 1391, DOI 10.15121/1881483, CC BY 4.0 (spring-chemistry source).
