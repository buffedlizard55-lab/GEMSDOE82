# Lane-82 science: why antislope scarps + TMI magnetic tilt + the mimic list

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
step gradient AGAINST the regional slope) is the primary detector where 1 m
LiDAR exists, because its background population excludes the largest confound
class by construction.

## Solving the 24.63% missing-LiDAR gap (H82-2.6 + coverage-aware fusion)

USGS 3DEP 1 m LiDAR covers `75.37%` of the competition footprint (`3,894,768 /
5,167,373` pixels), leaving `24.63%` (`1,272,605` pixels — including `45.8%`
of the NE quadrant) with `valid_lidar == 0`. Zero-filling missing LiDAR creates
an acquisition-boundary confound (`IR-82-LIDAR-01`). Lane H82-3 adds
**H82-2.6 (`h82_6_magnetic_tilt`)** from GeoDAWN `TMI_up150` (`99.94%` footprint
coverage): the zero-contours and ridge crests of `arctan2(-∇²TMI, |∇_h TMI|)`
weighted by `|∇_h TMI|` map sub-vertical basement susceptibility steps and
magnetite-destructed hydrothermal fault zones directly beneath basin fill and
across the non-LiDAR eastern/northeastern corridors. Combining LiDAR +
radiometrics + TMI + thermal where `valid_lidar > 0` and radiometrics + TMI +
thermal where `valid_lidar == 0` with stratum-wise quantile normalisation
(`coverage_aware_corroboration()`) eliminates the coverage bias completely.

## Why it should catch faults missing from the catalogue

Mapped catalogue faults are the large throughgoing structures with 100 m-scale
expression. Antislope scarplets at 1 m resolution and TMI/radiometric gradient
ridges reveal the complementary population: young distributed antithetic/graben
faults in piedmonts and fans, relay ramps between mapped segments, and blind
faults under alluvial cover whose sub-meter surface creep or basement
susceptibility step is invisible to traditional airphoto compilation.

## The named non-fault mimics (one per hypothesis)

| hypothesis | mimic | mitigation in the operator |
| --- | --- | --- |
| H82-2.1 antislope lineament | sackung/landslide headscarps; dip-slope benches | strike-agreement vote (faults are straight over 100s of m; slumps are arcuate) + channel-bank suppression (low `cross_max`) + NMS crest (thin lines, not alcoves) |
| H82-2.2 radiometric break | lithologic contacts (K/Th contrasts with no fault) | gradient-NMS (thin edges) + fusion (an isolated contact rarely coincides with antislope or TMI fabric) |
| H82-2.3 valley deflection | axial playas, meander cutoffs, fan-head trenches | 7 px straightness vote; playa/meander curvature fails it |
| H82-2.4 conjugate intersection | dendritic drainage junctions | scarp-relief weighting (junctions on flat fans score ~0) |
| H82-2.5 thermal halo | lateral outflow plumes, shallow mixing | per-site MAX of three independent geothermometers (disagreement = mixing, down-weighted) + short IDW length (L=20 px) |
| H82-2.6 TMI tilt/H-grad ridge | unfaulted plutonic/volcanic dike margins or flow edges | Laplace-tilt × horizontal-gradient NMS crest + co-registration with radiometric and LiDAR fabric in `C_cov` |

## References (background; operators are our own)

* Faulds & Hinz (2015) — Great Basin geothermal systems concentrate at fault
  terminations, stepovers, and relay ramps (structural-setting rationale).
* Siler et al. (2019) — fault-intersection permeability (H82-2.4 rationale).
* Miller & Singh (1994) — potential-field tilt-angle phase filter (H82-2.6 rationale).
* Fournier & Potter — quartz/chalcedony geothermometers (H82-2.5 estimators).
* USGS GeoDAWN release, DOI 10.5066/P93LGLVQ (radiometric/magnetic source).
* GDR 1391, DOI 10.15121/1881483, CC BY 4.0 (spring-chemistry source).
