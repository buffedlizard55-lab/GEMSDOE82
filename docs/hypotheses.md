# H82 hypotheses

The HTML version is the primary readable page: [hypotheses.html](hypotheses.html).

## Pre-run ranking

1. **H82-A — scale-commuting boundary triplet.** Layers: RTP magnetic, isostatic gravity, conductivity, basement depth, detrended elevation. Signature: robust gradient persistence at sigma 1/3/6 px, absolute sigma-3 Laplacian curvature, pairwise boundary orientation, weak-relief gate. Off-catalogue rationale: covered faults can juxtapose subsurface domains without a mapped scarp. Difference: not a catalogue-flank, ridge, tip, relay, or submodular rule.
2. **H82-B — signed curvature discordance.** Layers: RTP, gravity, basement depth, conductivity, detrended elevation. Signature: edge magnitude times signed Gaussian-Laplacian polarity dispersion with weak topographic curvature gate. Off-catalogue rationale: a blind juxtaposition can reverse contrast across independent physical fields while leaving weak surface relief. Difference: signed second-derivative disagreement, not a plain gradient or orientation vote.
3. **H82-C — strain saddle times cover edge.** Layers: geodetic shear, dilatation, second invariant, conductivity, basement depth. Signature: positive dilation/shear/invariant conjunction with coincident conductive and basement edges. Off-catalogue rationale: a damage-zone permeability signal may exist under cover. Difference: no earthquake-density head and not a plain conductive breach.
4. **H82-D — radiometric ratio curvature.** Layers: official GeoDAWN K/Th/U/TC plus magnetic edge. Signature: multi-scale ratio curvature and potential-field boundary offset. Requires the official USGS GeoDAWN release; verified obtainable at the [USGS page](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and), but deferred.
5. **H82-E — 1 m LiDAR directional roughness persistence.** Layers: official USGS 3DEP/GeoDAWN LiDAR and competition DEM links. Signature: directional roughness and scarplet persistence across scales with road/gully rejection. Deferred because the required cache was not in this three-run budget.

## Results

The exact three runs are in [`../evidence/experiments.json`](../evidence/experiments.json). Results are **HOLDOUT-DTI**, evaluator `gemsdoe82-pooled-hide-v1`, with `10730` withheld positive pixels and a spatial-block 95% CI:

| Candidate | DTI | 95% CI |
|---|---:|---:|
| H82-B | 0.013925211177605194 | [0.009949051706376702, 0.018292877858376997] |
| H82-C | 0.009445541067111691 | [0.005257452929155655, 0.014527875876734101] |
| H82-A | 0.009069309377073904 | [0.005783826625822374, 0.012703327615654068] |

These are not organizer scores and do not authorize a weekly slot. The best-of-three H82-B artifact is format-valid but the selector verdict is negative.
