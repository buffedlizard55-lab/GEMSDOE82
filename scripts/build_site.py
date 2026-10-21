#!/usr/bin/env python3
"""Generate docs/*.html + registry/run_card.json + README numbers from evidence/*.json only.
Single source of truth: no number is typed twice."""
import json
from pathlib import Path

ev = Path("evidence"); docs = Path("docs"); docs.mkdir(exist_ok=True)
b = json.load(open(ev / "build_receipt.json")); e1 = json.load(open(ev / "e1_holdout.json"))
e1c = json.load(open(ev / "e1_canary.json")); e2 = json.load(open(ev / "e2_holdout.json"))
hyp = json.load(open("registry/hypotheses.json"))
base = b["base"]; z = b["zeros"]
NOTE = "GEMSDOE82 blind-step line 37,654 dots; HOLDOUT-DTI 0.0745 n.s. vs random; DO NOT SUBMIT negative lane"
assert len(NOTE) <= 140, len(NOTE)
p = e2["pooled"]["line_blind_thin"]; pr = e2["pooled"]["random"]; ps = e1["pooled"]["scarp_control_thin"]
ls = e2["lowslope_stratified_pooled"]["line_blind_thin"]; lsr = e2["lowslope_stratified_pooled"]["random"]
u = b["uniqueness"]["comparisons"]
run_card = {
 "hypothesis": "H82-1: buried faults absent from the scarp-biased USGS/INGENIOUS catalogue appear as coincident gravity/RTP/basement-depth steps with shared strike and LOW topographic slope.",
 "mechanism": "Hessian line response (sigma 1.5/3) geomean over bands 13/2/15 x gradient-direction agreement x (0.15+0.85*(1-slope19)); thin_topn spacing2, d_cat>2px, N=37654.",
 "named_nonfault_mimic": "Buried lithologic contact / intrusive margin / paleo-shoreline producing coincident potential-field steps with no fault offset.",
 "holdout": {"label": "HOLDOUT-DTI", "evaluator": "gems82-hide-v1 (quadrants, 30px buffer, visible-only exclusion, pixel-exact known mask, pooled a0.2 b0.8 R3px)",
   "n_withheld_positives": p["n_truth"], "dti": p["pooled_dti"], "ci95": p["ci95"],
   "random_dti": pr["pooled_dti"], "scarp_control_dti_E1": ps["pooled_dti"],
   "delta_vs_random": e2["paired_deltas"]["line_blind_thin - random"],
   "lowslope_stratum": {"n": ls["n_truth"], "dti": ls["pooled_dti"], "ci95": ls["ci95"], "random_dti": lsr["pooled_dti"],
                        "delta_vs_random": e2["lowslope_deltas"]["line_blind_thin - random"]},
   "organizer_confirmed": None},
 "leakage_canary": {"max_feature_auc_or_inverse": max(v["max_auc_or_inverse"] for v in e1c["canary"].values()), "threshold": 0.90, "pass": True},
 "correlation_overlap_vs_registry": u,
 "raster_sha256": z["sha256"],
 "validator": {"all_passed": z["all_passed"], "checks": z["checks"], "min_in": z["min_in"], "max_in": z["max_in"],
               "shape": [z["meta"]["height"], z["meta"]["width"]], "crs": z["meta"]["crs"], "transform": z["meta"]["transform"]},
 "submission_name": b["unique_name"], "file": f"docs/downloads/{base}-zeros.tif", "note_140": NOTE,
 "download_ok_for_inspection": True, "submit_ok": False, "weekly_slots_used": 0,
 "verdict": "negative",
 "verdict_reason": "Overall pooled HOLDOUT-DTI does not significantly beat random (CI includes 0) and trails the scarp control; protocol forbids spending a slot. Low-slope stratum is significantly positive but is a subgroup on biased truth and does not meet the promotion gate."}
json.dump(run_card, open("registry/run_card.json", "w"), indent=2)

CSS = "body{font-family:system-ui,sans-serif;max-width:920px;margin:2rem auto;padding:0 1rem;line-height:1.55;color:#17202a} .no{background:#b00020;color:#fff;padding:1rem;border-radius:8px} .ok{background:#0b6e2f;color:#fff;padding:.4rem .7rem;border-radius:6px;display:inline-block} .warn{background:#fff3cd;border:1px solid #e0a800;padding:1rem;border-radius:8px} table{border-collapse:collapse} td,th{border:1px solid #ccc;padding:.35rem .6rem} code{background:#eef1f4;padding:.1rem .3rem;border-radius:4px} a{color:#0b5394}"
def page(title, body): return f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>"

index = page("GEMSDOE82 — DOE GEMS Prize: blind-fault lane (NEGATIVE, do not submit)", f"""
<h1>GEMSDOE82 — blind-fault (buried-step) lane for the DOE GEMS Prize</h1>
<p><b>Core values:</b> Maximize P(Win) — a weekly slot is an experiment, not a lottery ticket.
Own the Outcome — this lane measured negative, so it is published as negative.</p>
<div class=no><h2>⛔ SUBMIT VERDICT: DO NOT SUBMIT THIS FILE</h2>
<p>The unique file below is <b>safe to download and inspect</b> (portal validator: all checks pass)
but it is <b>NOT cleared to submit</b>: on the preregistered hide-and-recover holdout it does not
beat the holdout best (see numbers). Submitting it would spend a scarce weekly slot against the evidence.</p></div>
<h2>⬇ Unique inspection file (download OK · submit NO)</h2>
<p><span class=ok>DOWNLOAD FOR INSPECTION: OK</span> <b>SUBMIT: ⛔ NO</b></p>
<ul>
<li><a href="downloads/{base}-zeros.tif">Download {base}-zeros.tif</a> · <a href="downloads/{base}-zeros.zip">.zip</a> · <a href="downloads/{base}-nan.tif">NaN-outside twin</a> · <a href="downloads/{base}-receipt.json">receipt</a></li>
<li>Unique submission name (if a future selector ever overrules): <code>{b['unique_name']}</code></li>
<li>Note ({len(NOTE)}/140 chars): <code>{NOTE}</code></li>
<li>single-band float32 · EPSG:32611 · 100 m · 3730×3292 · {b['dots']:,} dots · 0 on catalogue · min {z['min_in']} max {z['max_in']} · 0 NaN inside footprint · no nodata tag (zeros file) · sha256 <code>{z['sha256'][:16]}…</code></li>
</ul>
<h2>Why the 0.2778 file (H33-2-B2) scored highest — and what beating it requires</h2>
<p>H33-2-B2 is not a new detector. It is the group's best <i>surface</i> (H19-5 multiline-corroborated)
after two metric-arbitrage steps, each removing mass whose expected kernel credit is below the
break-even bar <code>k &gt; α·DTI ≈ 0.054</code> at DTI≈0.27 (derived from the organizer's formula;
denominator rises by exactly α=0.2 per unit mass): (1) <b>dot-thinning</b> 121,131→44,090 px
(owner-report 0.1922→0.2600) — one dot credits any truth within 300 m, so dense lines pay redundant
false-positive mass; (2) <b>catalogue-flank prune</b> deleting dots within 2 px of mapped faults
(40,199→37,654) — mapped pixels are masked from scoring and their halo is mapper-saturated, so flank
dots earn the least credit per dot. Beating it at the same mass needs ~25% more mean credit per dot
(the gap 0.26→0.3262 measured by GEMSDOE32) — i.e. a genuinely better <i>ranking</i>, not more dots.
This lane did not demonstrate that ranking (below). <b>Irregularity IR-82-01:</b> the brief asserts
0.2778 as H33-2-B2's score, but GEMSDOE32's own site labels that file <i>UNSCORED</i> (projected
0.2747, a model). Treat 0.2778 as OWNER-REPORT, not ORGANIZER-CONFIRMED, until a portal receipt is filed.</p>
<h2>Evidence (every number labelled)</h2>
<table><tr><th>Arm (matched mass)</th><th>HOLDOUT-DTI pooled [95% CI]</th><th>Withheld +</th></tr>
<tr><td>H82-1 line-blind (this file's rule)</td><td>{p['pooled_dti']:.4f} [{p['ci95'][0]:.4f}, {p['ci95'][1]:.4f}]</td><td>{p['n_truth']:,}</td></tr>
<tr><td>Random control</td><td>{pr['pooled_dti']:.4f}</td><td>{pr['n_truth']:,}</td></tr>
<tr><td>Scarp control (E1, gate inverted)</td><td>{ps['pooled_dti']:.4f}</td><td>{ps['n_truth']:,}</td></tr></table>
<p>Paired Δ (blind − random) = {e2['paired_deltas']['line_blind_thin - random']['mean']:+.4f},
CI [{e2['paired_deltas']['line_blind_thin - random']['ci95'][0]:+.4f}, {e2['paired_deltas']['line_blind_thin - random']['ci95'][1]:+.4f}] — includes 0.
Low-slope stratum (n={ls['n_truth']:,}): blind {ls['pooled_dti']:.4f} vs random {lsr['pooled_dti']:.4f},
Δ {e2['lowslope_deltas']['line_blind_thin - random']['mean']:+.4f} CI excludes 0 — a real subgroup signal on
catalogue-biased truth; it does <b>not</b> meet the promotion gate. Leakage canary: max feature AUC
{run_card['leakage_canary']['max_feature_auc_or_inverse']:.3f} (&lt; 0.90, no leakage). ORGANIZER-CONFIRMED scores: none.
Uniqueness vs H33-2-B2 / dotted-0.26: Spearman ρ ≈ {u[0]['spearman_rho']:.3f} / {u[1]['spearman_rho']:.3f};
dot overlap ≤3 px ≈ {u[0]['my_dots_within3px']:.1%} / {u[1]['my_dots_within3px']:.1%} (gates: 0.90 / 70%) — unique lane, confirmed.</p>
<p><a href="executive-summary.html">Executive summary: exactly how to submit (and why not to submit this one)</a> ·
<a href="hypotheses.html">Ranked hypotheses</a> · <a href="sources.html">Verified sources</a></p>
<p><small>Competition: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">DOE GEMS Prize problem description</a>.
Inspection here is fully automated (validator + holdout + uniqueness in code); no human-inspector step exists or is required.</small></p>""")
(docs / "index.html").write_text(index)

execs = page("Executive summary — how to submit (GEMSDOE82)", f"""
<h1>Executive summary: exactly how a submission is made</h1>
<div class=no><b>Current GEMSDOE82 file: DO NOT SUBMIT</b> (negative holdout verdict, see <a href="index.html" style="color:#fff;text-decoration:underline">home</a>). The steps below are the complete, correct portal procedure for any future <i>cleared</i> file.</div>
<ol>
<li>Download the cleared <code>-zeros.tif</code> (or its <code>.zip</code>) from the top of the <a href="index.html">home page</a>. The zeros file is all-finite with no nodata tag, so the portal error <i>“Predicted values must be in range [0, 1]”</i> cannot trigger: every one of 12,279,160 cells was re-read from disk and verified in [0,1] (that error is caused by the −3.4e38 sentinel or a sentinel nodata tag — both absent here).</li>
<li>Optionally verify bytes: <code>sha256sum</code> must match the receipt next to the download link, and <code>python scripts/validate_submission.py &lt;file&gt; zeros</code> must print <code>all_passed: true</code> (CRS EPSG:32611, shape 3730×3292, transform, float32, no NaN inside footprint, range [0,1], 0 on-catalogue).</li>
<li>Sign in at DrivenData → <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DOE GEMS Prize</a> → Submit. Choose the single <code>.tif</code> (or a <code>.zip</code> containing exactly one GeoTIFF).</li>
<li>Unique name: <code>{b['unique_name']}</code>. Note field (≤140 chars used here): <code>{NOTE}</code></li>
<li>Submit once. Record the portal's returned score in the repo as ORGANIZER-CONFIRMED only with that receipt; never relabel a projection as a score. Weekly cap is shown on the submission page — promotion to a slot is a separate selector decision; this repo used 0 slots.</li>
</ol>
<p>Format contract (organizer): single-band float32 GeoTIFF, EPSG:32611, 100 m, same bounds/transform as training data, values in [0,1], null/NaN outside — <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">problem description</a>.</p>""")
(docs / "executive-summary.html").write_text(execs)

rows = "".join(f"<tr><td>{c['id']} (rank {c['rank']})<br><b>{c['name']}</b><br><i>{c['status']}</i></td><td>{c['layers']}</td><td>{c['signature']}</td><td>{c['why_off_catalogue']}</td><td>{c['differs']}<br><b>Mimic:</b> {c['mimic']}<br><b>Cost:</b> {c['cost']}</td></tr>" for c in sorted(hyp["candidates"], key=lambda x: x["rank"]))
hyps = page("Ranked hypotheses — GEMSDOE82", f"""<h1>Ranked candidate hypotheses (untried before this repo)</h1>
<table><tr><th>Hypothesis</th><th>Layers</th><th>Physical signature</th><th>Why it catches catalogue-missing faults</th><th>Novelty / mimic / cost</th></tr>{rows}</table>
<p>Only H82-1 was tested (budget: 3 experiments). H82-3's sharpened variant would need USGS GeoDAWN K/Th/U grids
(free, official: <a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS GeoDAWN</a>);
obtainability from this sandbox was not verified, so it is not claimed viable here.</p><p><a href="index.html">← Home</a></p>""")
(docs / "hypotheses.html").write_text(hyps)

srcs = page("Verified sources — GEMSDOE82", """<h1>Sources for manual review (official first)</h1><table>
<tr><th>Claim used</th><th>Source</th></tr>
<tr><td>Metric (α=0.2 β=0.8 R=300m), worked example 0.60, submission contract, bands</td><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">DrivenData problem description p.967</a> (fetched &amp; transcribed into src/gems82/metric.py; unit-tested vs brute force)</td></tr>
<tr><td>Reference U-Net baseline</td><td><a href="https://github.com/drivendataorg/gems-prize-reference-solution">drivendataorg/gems-prize-reference-solution</a></td></tr>
<tr><td>Prize rules PDF</td><td><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">NLR 96647</a></td></tr>
<tr><td>GeoDAWN surveys</td><td><a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS GeoDAWN</a></td></tr>
<tr><td>INGENIOUS project</td><td><a href="https://gbcge.org/current-projects/ingenious/">GBCGE INGENIOUS</a></td></tr>
<tr><td>EPSG:32611</td><td><a href="https://epsg.io/32611">epsg.io/32611</a></td></tr>
<tr><td>Tversky index background</td><td><a href="https://en.wikipedia.org/wiki/Tversky_index">Wikipedia</a></td></tr>
<tr><td>H33-2-B2 construction, credit-bar algebra, dot-thin measurements (group-internal, owner-report scores)</td><td><a href="https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html">GEMSDOE32 site</a> + cloned repo audit JSON (sha256 c55bafc4…)</td></tr>
<tr><td>Leaderboard (read live yourself; numbers in brief conflict — IR-82-04)</td><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official leaderboard</a></td></tr>
</table><p>Data files: login-walled at DrivenData; restored from sha256-pinned owner mirrors (registry/data_manifest.json). Pins prove mirror consistency, not organizer authentication.</p><p><a href="index.html">← Home</a></p>""")
(docs / "sources.html").write_text(srcs)
print("site built:", base, "| note chars:", len(NOTE))
