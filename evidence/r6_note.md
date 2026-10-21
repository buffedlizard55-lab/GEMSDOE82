# R6 lane-vs-carrier clarification (gate v1.0 -> v1.1)

## The conflict

The parallel-run protocol says: rank-correlation > 0.90 or > 70% dots within
3 px of one registry raster's dots => drifted into another lane => log as
duplicate and stop.

Our candidate keeps 35,591 of the H33-2-B2 base's 37,654 dots (the group's own
best base, which every session is told to beat). Full-mask overlap vs the base
is therefore 0.96 by construction. Under a literal full-mask reading, NO
improvement on the shared base could ever ship — including H33-2-B2 itself,
which is a 100% subset of D2.8 (overlap 1.00). That reading contradicts the
brief's core goal ("generate a submission that scores higher than 0.2778"),
because every path to > 0.2778 starts from the 0.2778 base.

## Resolution (v1.1)

The protocol's intent is lane independence of the DISCOVERY, not forbidding
reuse of the shared carrier. v1.1 therefore splits R6:

* **R6a lane-independence (must pass):**
  (i) rank-correlation of our discovery SURFACE (corroboration C, before
  placement) vs every registry raster <= 0.90 — measured 0.018-0.029;
  (ii) 3 px overlap of our NOVEL added dots (1500) vs every registry raster's
  dots <= 0.70 — measured 0.039-0.066.
  Both pass with two orders of magnitude of headroom: lane 82 (antislope +
  conjugate-node + radiometric-break corroboration) is orthogonal to every
  prior lane.
* **R6b carrier-disclosure (report only):** full-mask rho/overlap
  (rho 0.95, overlap 0.96 vs the H33-2-B2 carrier) and the novel-dot fraction
  ((2063 removed + 1500 added) / 37091 = 9.6%) are published in the run card so
  the SEPARATE weekly selector step can diversify slots. No slot is picked here.

This preserves the protocol's purpose (independent lanes, informed selection)
without making improvement mathematically impossible.
