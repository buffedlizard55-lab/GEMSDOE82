# R2 measurement fix (gate v1.0 -> v1.1): root cause

## Symptom

`scripts/make_submission.py` (v1.0) reported `quads_pos=1/4` for the Exp3
candidate even though its pooled SGMC-FAR margin was +0.0096 and every
instrument agreed the candidate dominates the base.

## Root cause

The v1.0 script compared candidate per-quadrant FAR values against HAND-COPIED
base quadrant constants (`baseq = NW 0.09922, NE 0.09832, SW 0.11893,
SE 0.07420`). Those constants were copied from the wrong instrument run: they
are the v1 **SGMC-RAW** quadrant values for H33-2-B2, not SGMC-FAR values.

The true in-process SGMC-FAR base quadrants (receipt
`evidence/holdout_registry_v2.json`, re-verified in-process, deterministic
across recomputation) are:

| quadrant | TRUE base FAR | Exp1 | Exp3 |
| --- | --- | --- | --- |
| NW | 0.078047 | 0.078708 (+0.000661) | 0.080427 (+0.002380) |
| NE | 0.089993 | 0.090698 (+0.000705) | 0.097645 (+0.007652) |
| SW | 0.109712 | 0.110798 (+0.001086) | 0.116750 (+0.007038) |
| SE | 0.070076 | 0.070532 (+0.000456) | 0.088938 (+0.018862) |

Exp1: 4/4 positive. Exp3: 4/4 positive. R2 PASSES under correct measurement.

## Fix

v1.1 evaluates the base mask in-process with the same evaluator object
(`scripts/make_submission.py`); no constants are hand-copied anywhere.
A regression test (`tests/test_gate.py`) asserts the in-process base quadrants
match the pinned receipt to 1e-9.

## Why this was catchable

Pooled DTI improved while "every quadrant worsened" is mathematically
impossible here (removals were zero-FAR-credit by construction: FAR truth is a
subset of MID truth, and every removed dot had zero MID credit — so per-quadrant
TP is unchanged and FP falls, hence every quadrant DTI must rise). The
contradiction flagged the measurement bug, not a pipeline bug.
