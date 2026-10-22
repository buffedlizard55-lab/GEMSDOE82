# Session prompt (read every time we work on this project)

> This file preserves the standing brief verbatim-ish so every session builds on
> the same base. Shorthand: `[links]` = the URL lists in the original message
> (competition, leaderboard, reference solution, USGS, GBCGE, EPSG, Tversky,
> NLR rules PDF, Dropbox data links, GDR 1391); the full per-site score ledger
> lives in `registry/leaderboard_history.jsonl` + `docs/leaderboard.html`.

Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A
PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION. BUT WE MUST
GENERATE A UNIQUE TIF SUBMISSION. IT MUST BE OBVIOUS WHETHER IT IS OK TO
DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the
prompt. Read the entire prompt. A lot of sites mention inspection only and a
human inspector, but the inspection needs to be done through the project and
needs to be validated for submission without human intervention.

PARALLEL-RUN PROTOCOL — read first. This session is one of several running from
this same prompt.

1. LANE. Your lane is the single method paragraph below. Stay inside it. If
   your raster's rank-correlation with any registry raster exceeds [0.90], or
   more than [70%] of your dots fall within 3 px of one registry raster's dots,
   you have drifted into another lane: log it as a duplicate and stop. Check
   this on the surface before placement AND on the final dots.
2. REUSE, DON'T REBUILD. Use the template's cached feature stack,
   evaluate_holdout.py and submission_writer.py. Holdout = hide-and-recover:
   withhold whole fault segments with a buffer, derive every catalogue-based
   feature only from the visible faults, mask visible faults pixel-exactly,
   score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared
   tool is wrong, fix it once in the template and report it; never keep a
   private fork.
3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld
   positives, 95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page
   receipt). A projection is never written as a score.
4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any
   result. AUC above [0.90] means leakage until proven otherwise.
5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault
   process that could mimic it; holdout DTI + CI; correlation/overlap vs
   registry; raster sha256; validator output (no NaN inside the footprint,
   values in [0,1], CRS/shape/transform match); submission name + note of at
   most 140 characters; verdict promote / negative. Negative results are
   deliverables.
6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions:
   promotion to a real slot is a separate selector step, within the weekly cap
   shown on the submission page.

STUDY the `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778` result (top of
the group ledger at session start; live site GEMSDOE32). Why and how did this
get the highest score, and can we generate a submission scoring higher than
0.2778? Answer with PhD-level judgement, then generate a UNIQUE TIF submission
unlike any within the GEMSDOE sites. Verify working line by line, no
hallucinations. (Prompt also cites public-leaderboard snapshots 0.3195/DARD and
0.4413 — CONTRADICTORY; see IR-82-LB-01.)

Before implementing, generate 3–5 candidate geological hypotheses we haven't
tried yet (layers; physical signature/transform; why it catches a
catalogue-missing fault; how it differs from repo prior art). Rank by expected
DTI improvement and implementation cost. Validate the top candidate on the
spatially-blocked holdout BEFORE touching a weekly slot. If a candidate needs
new external data, name the specific free official source and check
obtainability before calling it viable.

Work line by line verifying from official verified trusted sources, provide
links for manual review. No manual input; work autonomously. Flag
irregularities. No hallucinations.

Think outside the box but grounded in proper scientific research; be contrarian
but smart. Deep research + critical thinking → new hypotheses. Store knowledge
from official verified sources for reuse.

Submission portal lesson: a past download failed with "Predicted values must be
in range [0, 1]" — the shipped file must make that error structurally
impossible. Provide a unique file name + short comment for the submission form.
Create an executive-summary subpage explaining exactly how to submit.

Site: clean, user-friendly GitHub Pages UI with all relevant information + official
verified links. Keep Core Values central: Maximize P(Win); Own the Outcome.

Limitations/access: no DrivenData auth in sandbox (data login-walled) → use free
publicly available official/verified sources only. Blocker note from prior
sessions: data placement via download script into data/ + prepare step.

Run the task through 3 passes (implement+verify; bug/edge review+fix; final
re-check vs request). Then open a PR and merge it. Suggest next work +
limitations.
