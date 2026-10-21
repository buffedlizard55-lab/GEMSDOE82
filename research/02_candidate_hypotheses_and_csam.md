# Five Novel Geological Hypotheses (`H82-A` through `H82-E`) & The `H82-CSAM` Architecture

## 1. Portfolio Audit of Prior GEMSDOE Hypotheses (`GEMSDOE19`–`GEMSDOE77`)

Before formulating new geological hypotheses for `GEMSDOE82`, we audited the code, run cards, and feature stores of prior GEMSDOE repositories:
- **`GEMSDOE19`–`GEMSDOE36` (`H19-5`, `D1.5`, `D2.8`, `H27-4`, `H33`, `H36-1`, `PINN`):** Multi-line topographic/geophysical heuristic ridges + Poisson-disk dotting + $d_{\text{cat}} > 2.0\text{ px}$ collar pruning (`0.1922 -> 0.2778` `ORGANIZER-CONFIRMED`).
- **`GEMSDOE57`–`GEMSDOE72`:** Fault-zone anisotropy, breakover ridges, and early gradient-boosted ensembles.
- **`GEMSDOE73` (`H73`):** Cross-deconfounded topographic-geophysical ridges and calibrated binary emitters.
- **`GEMSDOE74` (`H74-FZA`):** Fault-zone anisotropy and step-over bridge scoring.
- **`GEMSDOE75` (`H75-RFA`):** Range-front apron and topographic breakover morphology.
- **`GEMSDOE76` (`H76`):** Geophysical contact ridges and multi-scale strike continuation.
- **`GEMSDOE77` (`H77-VDS`, `H77-LIA`, `H82-TE`, `H85-EDTI`):** 98-channel zero-SGMC static physical store + 8 fold-visible continuation channels + Dinkelbach submodular allocation.

Across all prior repositories (`GEMSDOE19`–`GEMSDOE77`), **every static physical feature was evaluated vertically at pixel $(y, x)$ without accounting for the 3D listric/planar dip offset between subsurface hanging-wall geophysical anomalies and footwall surface fault scarps**, or the **down-slope groundwater advection of shallow thermal anomalies in alluvial fans**.

---

## 2. Five Novel Geological Hypotheses Ranked by Expected `HOLDOUT-DTI` Gain & Cost

| Rank | Hypothesis ID & Name | Competition & External Layers Used | Physical Signature / Mathematical Transform | Why It Catches Unmapped Faults Missed by USGS / INGENIOUS | How It Differs From All Prior GEMSDOE Implementations | Expected `HOLDOUT-DTI` Gain | Implementation Cost |
|---:|---|---|---|---|---|---:|---|
| **1 (Selected)** | **`H82-A` (`H82-CSAM`): Coupled Subsurface-to-Surface Up-Dip Advection & Upslope Plume Back-Projection** | `training_features.tif` (`Basement_15`, `CBA`, `CBA_HGM`, `Mag_RTP`, `Mag_RTP_HGM`, `MT_1km`–`MT_5km`, `TG_0_200`, `TG_200_400`, `Temp_100m`, `Elevation`, `Slope`), `lidar_scarp_100m.tif`, `dem_terrain_100m_f32.tif`, `audit_sources/*.tif` | Back-projects hanging-wall gravity, magnetic, and 1–5 km MT clay-cap gradients $250\text{ m}$ ($2.5\text{ px}$) up-dip along the unit pre-Tertiary basement climb vector $\hat{u}_{\text{up}}(x) = +\nabla B_{15}/\|\nabla B_{15}\|$ onto deconfounded surface scarps: $C_{\text{updip}}(x) = G_{\text{sub}}(x - 2.5\hat{u}_{\text{up}}(x))\cdot S_{\text{surf}}(x)$, and integrates with `H82-B`–`H82-E` + Dinkelbach 300 m submodular emitter | Dipping ($45^\circ\text{--}60^\circ$) basin-bounding normal faults offset dense basement and MT conductors 150–350 m down-dip in the hanging wall; USGS surface mapping misses eroded piedmont scarps, while vertical geophysical HGM peaks place dots 250 m too far into the basin | Prior repos (`GEMSDOE19`–`GEMSDOE77`) multiplied geophysical HGM and topographic slope at the **same pixel** $(y,x)$; `H82-A` is the first to perform explicit 2D Lagrangian up-dip vector back-advection along $\nabla B_{15}$ | **`+0.0683` vs `H33_fold_fair` (`+0.0034` static-only over 98-ch)** | Moderate (`~158 MB` 8-ch memmap + 8 stacker interactions) |
| **2** | **`H82-B`: Multi-Scale Potential-Field Tilt-Phase Congruency $\times$ Radiometric `K/Th` Alteration** | `CBA`, `CBA_HGM`, `Mag_RTP`, `Mag_RTP_HGM`, `K_pct`, `Th_ppm`, `U_ppm`, `acquisition_block_id_100m.tif` | Computes amplitude-invariant tilt angle $\theta_\sigma = \arctan(\text{Lap}_\sigma / (\|\nabla_\sigma\| + \varepsilon))$ across scales $\sigma \in \{1.5, 4.0\}\text{ px}$ for gravity and RTP magnetics, measures inter-scale phase congruency $\cos(\theta_{1.5} - \theta_{4.0})$, and couples with within-block deconfounded potassium/thorium (`K/Th`) adularia-illite alteration edges | Intrabasin and volcanic-tableland faults have weak absolute gravity/magnetic contrast (missed by raw HGM thresholds) but strong multi-scale tilt-phase alignment across depth scales and subtle K-metasomatism along fluid pathways | Prior repos used single-scale tilt or raw HGM products without inter-scale phase congruency $\cos(\theta_{1.5} - \theta_{4.0})$ or survey-block deconfounded radiometric coupling | **`+0.0018` to `+0.0028`** | Low (vectorized multi-scale Gaussian derivatives) |
| **3** | **`H82-C`: Cross-Branch Fluvial $\chi$-Disequilibrium & $k_{sn}$ Jump Across Tributary Divides** | `hydro_100m_f32.tif` (`flow_acc`, `twi`, `hand`, `stream_order`), `dem_terrain_100m_f32.tif` (`elev`, `slope`, `plan_curv`) | Approximates local normalized channel steepness $k_{sn} \approx \log(1 + \text{slope})\cdot (\text{flow\_acc})^{0.45}$, computes local drainage-divide saddle curvature vs valley-floor incision jump, and isolates strike-aligned knickzone alignments perpendicular to channels | Active blind normal faults in piedmont fans and relay ramps lack continuous 1 m LiDAR scarps due to rapid holocene aggradation, but create systematic knickzones and $\chi$/steepness jumps across adjacent tributary branches | Prior repos used scalar `twi`, `hand`, or `stream_order` at pixel $(y,x)$; none computed cross-divide $k_{sn}$ variance jumps paired with strike-normal channel alignment | **`+0.0012` to `+0.0020`** | Low (`scipy.ndimage` morphological saddle filters) |
| **4** | **`H82-D`: Upslope Hydraulic-Gradient Back-Advection of Lateral Alluvial Thermal Outflow Plumes** | `TG_0_200`, `TG_200_400`, `Temp_100m`, `Heatflow`, `Elevation`, `TWI`, `HAND` | Back-projects shallow thermal anomaly z-scores and horizontal thermal gradients $250\text{ m}$ ($2.5\text{ px}$) upslope along the smoothed topographic hydraulic head vector $\hat{u}_{\text{hyd}}(x) = +\nabla z_{\text{smooth}} / \|\nabla z_{\text{smooth}}\|$ onto range-front breakover hinges | Upwelling geothermal fluids along range-front faults mix with cold meteoric groundwater and flow 200–500 m laterally down alluvial fans before being sampled in shallow temperature-gradient (`TG_0_200`) boreholes | Prior repos evaluated `TG_0_200` and `Temp_100m` in-place, biasing thermal detections into valley-floor outflow plumes rather than the up-gradient fault conduit | **`+0.0015` to `+0.0024`** | Low (`map_coordinates` upslope advection) |
| **5** | **`H82-E`: Biharmonic Thin-Plate Basement Flexural Curvature $\|\nabla^4 B_{15}\|$ in Piedmont Regimes** | `Basement_15`, `Geod_2nd_inv`, `Geod_max_shear`, `Crust_15`, `Slope` | Computes the 4th-order biharmonic thin-plate bending operator $\nabla^4 B_{15} = \nabla^2(\nabla^2 B_{15})$ of the pre-Tertiary basement depth surface weighted by low surface slope ($\exp(-\text{slope}/6^\circ)$) and geodetic strain rate | Concealed master detachment and listric faults beneath thick Quaternary basin fill flex the overlying basement-alluvium interface at flexural hinge zones where elastic bending stress $\propto \nabla^2 B_{15}$ and shear force $\propto \nabla^3 B_{15}$ peak | Prior repos used 1st-order $\|\nabla B_{15}\|$ or 2nd-order $\nabla^2 B_{15}$; `H82-E` is the first to compute the 4th-order biharmonic flexural load operator $\|\nabla^4 B_{15}\|$ | **`+0.0014` to `+0.0022`** | Low (cascaded Laplacian filters) |

---

## 3. Mathematical Specification of the 8 Novel `H82-CSAM` Channels (`src/gems82/csam.py`)

In `GEMSDOE82`, we synthesize all five physical mechanisms (`H82-A` through `H82-E`) into an 8-channel static feature block (`CSAM_CHANNEL_NAMES` in `src/gems82/csam.py`, stored in `.cache/h82_csam/csam8_ch_fp.f32`) that augments the 98-channel zero-SGMC base physical store (`FE.STATIC_CHANNEL_NAMES`) and 8 fold-visible continuation channels (`FE.VISIBLE_CHANNEL_NAMES`):

1. **`csam_updip_grav_scarp`** (`Canary symmetric AUC = 0.574660`):
   Up-dip ($2.5\text{ px} = 250\text{ m}$ along $+\nabla B_{15} / \|\nabla B_{15}\|$) back-projected `CBA_HGM` gravity gradient $\times$ road/mine-deconfounded surface scarp strength.
2. **`csam_updip_mag_scarp`** (`Canary symmetric AUC = 0.533264`):
   Up-dip ($2.5\text{ px}$ along $+\nabla B_{15} / \|\nabla B_{15}\|$) back-projected `Mag_RTP_HGM` magnetic gradient $\times$ road/mine-deconfounded surface scarp strength.
3. **`csam_updip_claycap_sinter`** (`Canary symmetric AUC = 0.546014`):
   Up-dip ($2.5\text{ px}$ along $+\nabla B_{15} / \|\nabla B_{15}\|$) 1–2 km vs 4–5 km magnetotelluric (`MT`) clay-cap vertical contrast $\times$ surface hydrothermal alteration index (`K/Th` + `Geochem`).
4. **`csam_upgrad_thermal_source`** (`Canary symmetric AUC = 0.542204`):
   Upslope ($2.5\text{ px}$ along $+\nabla z_{\text{smooth}} / \|\nabla z_{\text{smooth}}\|$) back-projected shallow thermal anomaly (`TG_0_200`, `TG_200_400`, `Temp_100m`, `Heatflow`) $\times$ range-front breakover hinge index.
5. **`csam_basement_flex_hinge`** (`Canary symmetric AUC = 0.548251`):
   Biharmonic thin-plate basement flexural curvature $\log(1 + |\nabla^4 B_{15}|) \times \log(1 + \|\nabla B_{15}\|) \times \exp(-\text{slope}/6^\circ)$ in low-slope piedmont/basin terrain.
6. **`csam_chi_divide_diseq`** (`Canary symmetric AUC = 0.516840`):
   Cross-branch fluvial $\chi$ / steepness ($k_{sn}$) disequilibrium jump across local drainage divides (`src/gems82/csam.py`).
7. **`csam_transtens_valve_index`** (`Canary symmetric AUC = 0.558648`):
   Transtensional releasing-bend fault-valve dilation index (`Geod_2nd_inv` $\times$ `Geod_max_shear` $\times$ deep 3–5 km MT conductivity ascent $\times$ up-dip gravity step).
8. **`csam_phase_congruency_edge`** (`Canary symmetric AUC = 0.517462`):
   Multi-scale ($\sigma \in \{1.5, 4.0\}\text{ px}$) gravity + RTP magnetic tilt-angle phase congruency $\cos(\theta_{1.5} - \theta_{4.0}) \times$ within-block `K/Th` alteration edge.

---

## 4. Named Non-Fault Mimic Processes & Physical Deconfounding Rules

Every geophysical or geomorphic proxy has non-fault geological mimics that generate false positives if left unconditioned:
- **Mimic 1: Coalescent Alluvial Fan Aprons & Pleistocene Lake Lahontan Shoreline Beach Ridges.**
  Shoreline berms and fan-toe aprons produce subtle topographic steps in low-slope basins (`slope <= 5 deg`) without basement offset.
  *Deconfounding:* `csam_updip_grav_scarp`, `csam_updip_mag_scarp`, and `csam_basement_flex_hinge` require coupled pre-Tertiary basement flexure ($\nabla B_{15}, \nabla^4 B_{15}$) and up-dip potential-field steps, which vanish on superficial lacustrine beach ridges.
- **Mimic 2: 1 m LiDAR Acquisition Block Boundaries & Survey Quantization Seams.**
  The 1 m LiDAR mosaic covers `77.8%` of the footprint across heterogeneous survey blocks (`acquisition_block_id_100m.tif`), creating linear step artifacts along survey tile boundaries.
  *Deconfounding:* All LiDAR and radiometric channels undergo within-block percentile normalization plus explicit distance-to-tile-boundary (`lidar_1m_tile_boundary_dist_km`) conditioning.
- **Mimic 3: Road Cuts, Railroad Grades, Open-Pit Mine Benches & Steep Unfaulted Flank Canyons.**
  Highway cuts (`tiger_road_distance_m.tif`), mine benches (`blm_closed_claim_distance_m.tif`), and steep V-shaped erosional canyons mimic fault scarps.
  *Deconfounding:* Scarp features are multiplicatively damped within $250\text{ m}$ of TIGER roads and BLM mine claims (`lidar_step_deconf_road_mine`), and projected into the local structural strike frame $(u_2, v_2)$ so cross-strike drainage canyons ($\perp$ to strike) are vetoed.
