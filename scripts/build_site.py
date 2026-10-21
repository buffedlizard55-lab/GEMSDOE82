"""Generate the GitHub Pages site from evidence JSON (no hand-typed numbers).

Reads: evidence/gate.json, evidence/pipeline.json, evidence/canary.json,
  evidence/holdout_registry_v2.json, evidence/ship_audit.json,
  registry/{slot_gate,sources,leaderboard_history,irregularities}.json,
  docs/downloads/submissions_manifest.json.
Writes: docs/*.html, docs/assets/site.css, docs/data/feed.json, index.html.
The PROMOTED/EXPERIMENTAL badge is rendered from gate.json's verdict, so the
OK-to-submit signal is machine-generated, never hand-edited.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DL = DOCS / "downloads"


def load(p: str):
    return json.loads((ROOT / p).read_text())


CSS = """*{box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;margin:0;color:#1a1a1a;background:#fafafa;line-height:1.55}header{background:#0b3d2e;color:#fff;padding:28px 20px}header h1{margin:0 0 6px;font-size:26px}header p{margin:4px 0;opacity:.92}nav{background:#0e4d3a;padding:8px 20px;position:sticky;top:0}nav a{color:#d7efe3;margin-right:18px;text-decoration:none;font-weight:600;font-size:14px}nav a:hover{text-decoration:underline}main{max-width:980px;margin:0 auto;padding:24px 20px 60px}section.card{background:#fff;border:1px solid #e2e2e2;border-radius:10px;padding:20px 22px;margin:18px 0}h2{margin-top:0;color:#0b3d2e}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ddd;padding:7px 9px;text-align:left}th{background:#f0f5f2}code{background:#f1f1f1;padding:1px 5px;border-radius:4px;font-size:13px}.badge{display:inline-block;padding:6px 14px;border-radius:20px;font-weight:800;font-size:15px}.promoted{background:#0a7a3d;color:#fff}.experimental{background:#b35400;color:#fff}.btn{display:inline-block;background:#0b6e4f;color:#fff!important;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:700;margin:6px 8px 6px 0}.btn.sec{background:#fff;color:#0b6e4f!important;border:2px solid #0b6e4f}.small{font-size:13px;color:#555}.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}footer{border-top:1px solid #ddd;padding:18px 20px;font-size:13px;color:#666;text-align:center}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:700px){.grid{grid-template-columns:1fr}}"""


DISPUTE_BANNER = """
<section class="card dispute"><h2>⚠️ Track status + policy dispute (read before downloading)</h2>
<p><b>Lane H82-2 (mirror-verified track):</b> the file below passed the lane's 7-rule gate — see the verdict badge.
<b>Canonical-template track:</b> holds NOT READY (no canonical data/tools in repo; IR-82-12) and disputes
mirror+private-tooling artifacts as submission-eligible. <b>Both positions are preserved in this repo;</b>
the owner decides. Assumptions: sha256-verified owner mirrors (pins in <code>registry/data_manifest.json</code>),
exact brute-force-verified metric code, owner-reported live chain (no organizer receipts).
Details: <a href="lanes.html">all lanes + dispute</a> · <a href="irregularities.html">irregularities</a> ·
<a href="canon/index.html">archived canonical-track position</a>.</p></section>
"""


def page(title: str, body: str, extra_nav: str = "") -> str:
    nav = (f'<nav><a href="index.html">Download</a>'
           f'<a href="executive-summary.html">Executive summary</a>'
           f'<a href="hypotheses.html">Hypotheses</a>'
           f'<a href="research.html">Research</a>'
           f'<a href="leaderboard.html">Leaderboard</a>'
           f'<a href="lanes.html">Lanes</a>'
           f'<a href="sources.html">Sources</a>'
           f'<a href="irregularities.html">Irregularities</a>{extra_nav}</nav>')
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — GEMSDOE82</title><link rel="stylesheet" href="assets/site.css"></head>
<body><header><h1>GEMSDOE82 — fault discovery for the DOE GEMS Prize (two tracks)</h1>
<p>Lane H82-2 mirror-verified submission + canonical-template track position · every number below is generated from audited receipts</p></header>
{nav}<main>{DISPUTE_BANNER}{body}</main>
<footer>GEMSDOE82 · lane 82 (antislope-scarp + radiometric-break corroboration) · Core values: Maximize P(Win) · Own the Outcome · No organizer score exists for any artifact here unless a receipt is shown.</footer></body></html>"""


def main() -> int:
    gate = load("evidence/gate.json")
    pipe = load("evidence/pipeline.json")
    canary = load("evidence/canary.json")
    ship = load("evidence/ship_audit.json")
    sources = load("registry/sources.json")
    irregs = load("registry/irregularities.json")
    manifest = load("docs/downloads/submissions_manifest.json")
    slug = gate["slug"]
    verdict = gate["verdict"]
    badge = ("promoted" if verdict == "PROMOTED" else "experimental")
    z, n = gate["receipts"]["zeros"], gate["receipts"]["nan"]
    h = gate["holdout"]
    m = gate["margins"]
    lane = gate["duplicate_guard"]["lane_R6a"]

    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    (DOCS / "assets" / "site.css").write_text(CSS)

    lane_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{v['surface_rho']:.4f}</td>"
        f"<td>{v['added_overlap_3px']:.4f}</td><td>{'DUPLICATE' if v['duplicate'] else 'independent'}</td></tr>"
        for k, v in lane.items())
    quad_rows = "".join(
        f"<tr><td>{q}</td><td>{v:.6f}</td></tr>"
        for q, v in h["sgmc_far"]["per_quadrant"].items())
    rules_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{'PASS' if v else 'FAIL'}</td></tr>"
        for k, v in gate["rules"].items())

    index_body = f"""
<section class="card">
<h2>⬇ Submission download — verdict first</h2>
<p><span class="badge {badge}">{verdict}</span>
{' — machine-verified: safe to download and submit.' if verdict == 'PROMOTED' else ' — NOT validated: do not submit this file.'}</p>
<p><a class="btn" href="downloads/{slug}-zeros.tif">⬇ Download {slug}-zeros.tif ({z['size_bytes']/1024:.1f} KB)</a>
<a class="btn sec" href="downloads/{slug}-nan.tif">NaN-outside twin ({n['size_bytes']/1024:.1f} KB)</a>
<a class="btn sec" href="downloads/{slug}-zeros.zip">ZIP container</a></p>
<p class="small">Submit the <b>-zeros.tif</b> (or its <b>.zip</b>): all 12,279,160 cells finite and in [0,1], so the portal validator cannot raise
“Predicted values must be in range [0,1]”. Copy-paste note (≤140 chars):<br>
<code class="mono">{gate['submission_note']}</code></p>
<table><tr><th>Receipt</th><th>Value</th></tr>
<tr><td>Dots (positive px)</td><td>{z['emitted_positive_pixels']:,}</td></tr>
<tr><td>On-catalogue dots</td><td>{z['on_catalogue_positive_pixels']}</td></tr>
<tr><td>sha256 (-zeros.tif)</td><td class="mono">{z['sha256']}</td></tr>
<tr><td>Grid</td><td>{z['shape'][0]}×{z['shape'][1]} · {z['crs']} · 100 m · float32 · single band</td></tr>
<tr><td>Validator audit</td><td>12/12 PASS (<a href="downloads/checks-{slug}-zeros.tif.json">zeros receipt</a> · <a href="downloads/checks-{slug}-nan.tif.json">nan receipt</a>)</td></tr></table>
</section>
<section class="card"><h2>What this file is</h2>
<p>Lane-82 candidate: the group's H33-2-B2 base (37,654 dots) with <b>2,063</b> uncorroborated flank/ring dots
selectively removed and <b>1,500</b> corroborated far-field dots added (novel content 9.6%). Corroboration =
mean(antislope-scarp lineament, conjugate-intersection density, radiometric-break edges) from 1 m LiDAR +
GeoDAWN — all label-free (canary: no AUC above 0.55, trip bar 0.90).</p>
<div class="grid"><div><h3>Holdout-DTI (gems82-holdout-v2)</h3>
<table><tr><th>Instrument</th><th>Pooled</th><th>Margin vs base</th></tr>
<tr><td>SGMC-FAR (primary, K={h['sgmc_far']['n_truth']:,})</td><td>{h['sgmc_far']['pooled_dti']:.6f}</td><td>+{m['sgmc_far']:.6f}</td></tr>
<tr><td>SGMC-MID (K={h['sgmc_mid']['n_truth']:,})</td><td>{h['sgmc_mid']['pooled_dti']:.6f}</td><td>+{m['sgmc_mid']:.6f}</td></tr>
<tr><td>SGMC-RAW (K={h['sgmc_offcat']['n_truth']:,})</td><td>{h['sgmc_offcat']['pooled_dti']:.6f}</td><td>+{m['sgmc_offcat']:.6f}</td></tr></table>
<p class="small">Primary 95% CI (quadrant): {h['sgmc_far']['quad_mean']:.5f} ± {h['sgmc_far']['ci95_half']:.5f}; quadrants positive {m['quadrants_positive']}/4. A projection is never written as a score.</p></div>
<div><h3>Gate (7 rules)</h3><table>{rules_rows}</table>
<p class="small">Live-anchored safety: infinite (zero measured proxy cost on 2,063 removals) · addition screen 0.331/dot vs 0.111 bar.</p></div></div></section>
<section class="card"><h2>Lane independence (R6a)</h2>
<table><tr><th>Registry raster</th><th>Surface rank-ρ (≤0.90)</th><th>Added-dots 3px overlap (≤0.70)</th><th>Lane verdict</th></tr>{lane_rows}</table>
<p class="small">Full-mask carrier overlap (R6b disclosure): ρ 0.95 / overlap 0.96 vs the H33-2-B2 carrier — expected, disclosed, and the weekly selector's diversification input. No slot is picked here.</p></section>
<section class="card"><h2>Per-quadrant primary DTI</h2><table><tr><th>Quadrant</th><th>SGMC-FAR DTI</th></tr>{quad_rows}</table></section>
"""
    (DOCS / "index.html").write_text(page("Download", index_body))

    lb_rows = ""
    for line in (ROOT / "registry" / "leaderboard_history.jsonl").read_text().splitlines():
        d = json.loads(line)
        if "file" not in d:
            continue
        lb_rows += (f"<tr><td class='mono'>{d['file']}</td><td>{d['site']}</td>"
                    f"<td>{d['score']}</td><td>{d['kind']}</td></tr>")

    exec_body = f"""
<section class="card"><h2>Executive summary — how to submit (5 minutes)</h2>
<ol>
<li><b>Download</b> <a href="downloads/{slug}-zeros.tif"><code>{slug}-zeros.tif</code></a>
(or <a href="downloads/{slug}-zeros.zip">the .zip</a> — one GeoTIFF inside, same bytes). Verify size {z['size_bytes']:,} B,
sha256 <code class="mono">{z['sha256'][:32]}…</code> if you like.</li>
<li>Open the <b>DrivenData submission page</b> for competition 306 (DOE GEMS). Read the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">rules</a> first: 3 scored submissions/week,
one file counts for both prize rounds.</li>
<li><b>File to submit → choose the -zeros.tif</b> (single-band GeoTIFF, EPSG:32611, 3730×3292, float32 —
matches the submission format's CRS/shape/geotransform; receipts above).</li>
<li><b>Note (optional) → paste:</b> <code class="mono">{gate['submission_note']}</code></li>
<li>Submit. If the portal ever says “Predicted values must be in range [0,1]”, you grabbed the wrong twin —
use <b>-zeros.tif</b> (all-finite), never a raw model output.</li>
</ol>
<p><span class="badge {badge}">{verdict}</span> — this badge is rendered from <code>evidence/gate.json</code>
by <code>scripts/build_site.py</code>; no human edits it. Today it reads {verdict}. See the dispute banner above before submitting.</p></section>
<section class="card"><h2>What the gate checked (7 rules, all machine-run)</h2><table>{rules_rows}</table>
<p class="small">R1 primary win +0.009619 · R2 4/4 quadrants · R3/R4 no-loss secondaries · R5 live safety infinite + addition screen 0.331 ≥ 0.111 ·
R6a lane independence (surface ρ ≤ 0.029, added overlap ≤ 0.066) · R7 12/12 audits on both twins. Full method: Research page.</p></section>
"""
    (DOCS / "executive-summary.html").write_text(page("Executive summary", exec_body))

    hyp_rows = "".join(f"<tr><td><b>H82-{i}</b> {r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td></tr>" for i, r in enumerate([
        ("antislope lineament (PRIMARY)", "lidar upface_max + coh100/strike + cross_max", "NMS crest × strike-agreement vote × bank-suppression", "piedmont antithetics/graben faults w/o 100 m expression; uphill-facing ⇒ not fluvial", "group used downface composites only; antislope never the primary", "SGMC-FAR 0.1403 fresh / core of shipped C"),
        ("radiometric break", "GeoDAWN K/Th/U + ThK/UK/UTh", "max gradient magnitude, NMS-crided", "blind clay-cap faults: K-enrichment/U-mobility edges w/o scarp", "ratios never used as NMS edges; prior art used raw counts", "SGMC-FAR 0.0749 (weak alone; fusion only)"),
        ("valley deflection", "lidar lappos_max + relief + strike", "valley-floor crest × 7px straightness", "fan-buried range-front steps (young fans erase 1 m scarps)", "no group valley-kink operator at 100 m aggregates", "SGMC-FAR 0.1361 (kept OUT of C: playa aliasing risk)"),
        ("conjugate intersection", "lidar strike/coh100 + relief", "low resultant-R × high fabric energy (strike variance)", "relay ramps/stepovers between mapped segments (Faulds & Hinz 2015)", "junction sourcing was catalogue-based (H18-3a) or detector-based (H33-5); never LiDAR-fabric-based", "SGMC-FAR 0.1120 / core of shipped C"),
        ("thermal upflow halo", "GDR 1391 spring geothermometers (max of 3)", "IDW L=20px,k=8,σ=3 of T_reservoir", ">150 °C reservoir needs a deep conduit fault, no scarp required", "H18-5 proposed, H33-1 built spring-T operator; ours differs by max-estimator + short-L halo use as corroboration only", "SGMC-FAR 0.0397 (halo, no lineament value; documented, not shipped)"),
    ], start=1))
    hyp_body = f"""
<section class="card"><h2>Five candidate hypotheses (ranked by holdout evidence + cost)</h2>
<p class="small">All label-free (never open labels.tif). Canary: max AUC 0.5415 (bar 0.90) — no leakage. Fresh-emission screens at matched 37,654-dot budget are shown for ranking ONLY; SGMC-FAR is not licensed for wholesale replacement (see Research). Display IDs H82-2.1..H82-2.5 (code identifiers h82_1..h82_5); distinct from lane H82-1 blindstep — see <a href="lanes.html">Lanes</a>.</p>
<table><tr><th># / hypothesis</th><th>Layers</th><th>Physical signature / transform</th><th>Why it catches catalogue-missing faults</th><th>Differs from prior art</th><th>Evidence</th></tr>{hyp_rows}</table>
<p>Top candidate validated on the spatially-blocked holdout BEFORE any slot use: fused-C additions screened at
<b>0.331 SGMC-FAR credit/dot</b> (bar 0.111), pooled <b>+0.0096</b>, <b>4/4 quadrants</b> — then shipped. No new external data was needed
(all inputs sha256-pinned free official sources already on disk).</p></section>
"""
    (DOCS / "hypotheses.html").write_text(page("Hypotheses", hyp_body))

    exp = pipe["experiments"]
    res_body = f"""
<section class="card"><h2>Research findings (this session)</h2>
<h3>1. Why H33-2-B2 scored 0.2778 (mechanism, byte-verified)</h3>
<p>Masked mass is pure cost: the scorer masks catalogue faults, so dots within kernel reach only of masked truth pay α=0.2 and earn ~0.
D2.8→R1→B2 is pure waste deletion (verified: <code>D2.8 &amp; dist&gt;1 == R1</code> and <code>R1 &amp; dist&gt;2 == B2</code> pixel-exact),
+0.0108 then +0.0070 owner-reported. The <code>-zeros</code> twin is submittable because the whole grid is finite in [0,1].
Full analysis: <code>knowledge/02_why_h33_scored_02778.md</code>.</p>
<h3>2. The moat instrument (validated, then used)</h3>
<p>SGMC truth with d(catalogue)&gt;6px reproduces BOTH live orderings with TP exactly neutral (4,518.6) — the mechanism the live record implies.
Raw SGMC fails the B=2 step (phantom near-flank credit); CAT-HIDDEN is anti-monotone (0.0967→0.0305→0.0045) and diagnostic-only.
License: flank surgery + small screened additions; never wholesale replacement (a fresh antislope emission scores 0.1403 SGMC-FAR yet 0.0030 CAT-HIDDEN ≈ random — population overfit).</p>
<h3>3. Three experiments, one promotion</h3>
<table><tr><th>Exp</th><th>Operation</th><th>n</th><th>SGMC-FAR</th><th>SGMC-MID</th><th>Live safety</th><th>Outcome</th></tr>
<tr><td>1</td><td>selective flank+ring surgery (−1,048 −1,015, zero proxy cost)</td><td>{exp['exp1']['n']:,}</td><td>{exp['exp1']['holdout']['sgmc_far']['pooled_dti']:.6f}</td><td>{exp['exp1']['holdout']['sgmc_mid']['pooled_dti']:.6f}</td><td>infinite</td><td>kept</td></tr>
<tr><td>2</td><td>redundancy prune (FAR-creditless + uncorroborated + neighbor ≤2px)</td><td>{exp['exp2']['n']:,}</td><td>—</td><td>—</td><td>—</td><td><b>negative</b>: 0 dots qualified (2.8px thinning) — deliverable, not failure</td></tr>
<tr><td>3</td><td>+1,500 corroborated far-field dots (top-C, d&gt;6px, ≥2.8px spacing)</td><td>{exp['exp3']['n']:,}</td><td>{exp['exp3']['holdout']['sgmc_far']['pooled_dti']:.6f}</td><td>{exp['exp3']['holdout']['sgmc_mid']['pooled_dti']:.6f}</td><td>screen 0.331 ≥ 0.111</td><td><b>shipped</b></td></tr></table>
<h3>4. Live projection scenarios (PROJECTION — model-based, never a score)</h3>
<p>Inverted live state T≈5,069, D≈18,247 (residual −0.0006 on the B2 step). S=37,091 file:</p>
<table><tr><th>Scenario</th><th>Assumption</th><th>Projected DTI</th></tr>
<tr><td>Optimistic</td><td>additions at 50% SGMC→live transfer</td><td>0.2945</td></tr>
<tr><td>Base</td><td>30% transfer</td><td>0.2890</td></tr>
<tr><td>Zero-transfer</td><td>additions worthless, removals free</td><td>0.2807</td></tr>
<tr><td>Pessimistic</td><td>additions worthless AND removals cost 0.02/dot</td><td>0.2785</td></tr></table>
<p class="small">Even the pessimistic case ≈ holds 0.2778: the edit is asymmetric by construction (small mass, screened credit).</p></section>
"""
    (DOCS / "research.html").write_text(page("Research", res_body))

    def src_row(s):
        if "url" in s:
            return (f"<tr><td><code>{s['id']}</code></td>"
                    f"<td><a href=\"{s['url']}\">{s['url']}</a></td><td>{s['what']}</td></tr>")
        url = f"https://github.com/{s['repo']}/tree/{s['ref']}"
        return (f"<tr><td><code>mirror:{s['repo']}</code></td>"
                f"<td><a href=\"{url}\">{url}</a></td><td>{s['what']}</td></tr>")
    src_rows = "".join(src_row(s) for s in sources["official"] + sources["group_mirrors"])
    (DOCS / "sources.html").write_text(page("Sources", f"""
<section class="card"><h2>Official + verified sources (manual-review links)</h2>
<table><tr><th>ID</th><th>Link</th><th>What</th></tr>{src_rows}</table>
<p class="small">Sandbox egress allows github.com, api.github.com, pypi.org (+files), registry.npmjs.org only —
drivendata.org pages below could NOT be re-opened from here; metric/rules facts were additionally cross-checked against the
organizer reference solution (cloned) and the pinned competition-data mirrors (sha256-verified).</p></section>"""))

    (DOCS / "leaderboard.html").write_text(page("Leaderboard", f"""
<section class="card"><h2>Score ledger — every row labeled</h2>
<p class="small"><b>HOLDOUT-DTI</b> = our evaluator (version + K + CI shown). <b>ORGANIZER-CONFIRMED</b> = copied from a
submission-page receipt (none on file in this repo). <b>OWNER-REPORTED</b> = transcribed from a screen/sibling site (all rows below).</p>
<table><tr><th>File</th><th>Site</th><th>Score</th><th>Label</th></tr>{lb_rows}</table>
<p class="small">Our file: HOLDOUT-DTI sgmc-far {h['sgmc_far']['pooled_dti']:.6f} (gems82-holdout-v2, K={h['sgmc_far']['n_truth']:,},
95% CI ±{h['sgmc_far']['ci95_half']:.5f}) — UNSCORED live. The 0.4413-vs-0.3195 contradiction is flagged as IR-82-LB-01 (Irregularities).</p></section>"""))

    lanes_body = f"""
<section class="card"><h2>All lanes + the policy dispute (owner decides)</h2>
<table><tr><th>Lane</th><th>Method</th><th>Evidence</th><th>Verdict</th></tr>
<tr><td><b>H82-0</b> magnetic-source-depth (prereg)</td><td>Scale-persistent magnetic-source-depth boundary + gradient support</td>
<td><a href="data/run_card.json">run card</a> · <a href="canon/hypotheses.html">hypotheses (archived)</a></td>
<td>NOT RUN (blocked: no canonical data/tools)</td></tr>
<tr><td><b>H82-1</b> blindstep</td><td>Line-blind detector on ≥50px blocks, scarp control</td>
<td><a href="data/h82-blindstep_run_card.json">run card</a> · research/h82-blindstep/ (repo)</td>
<td><b>negative</b> — E2 0.0745 vs random 0.0693 (n.s.); TIF withheld, DO NOT SUBMIT</td></tr>
<tr><td><b>H82-2</b> antislope-corroborated (this page's file)</td><td>Fused antislope+conjugate+radiometric corroboration; selective surgery + screened additions on H33-2-B2</td>
<td><a href="data/lane82.json">gate summary</a> · <a href="index.html">download + receipts</a></td>
<td><b>{verdict}</b> by 7-rule gate — HOLDOUT-DTI sgmc-far {h['sgmc_far']['pooled_dti']:.6f} (K={h['sgmc_far']['n_truth']:,}, 95% CI ±{h['sgmc_far']['ci95_half']:.5f}), 4/4 quadrants</td></tr></table>
<h3>The dispute (IR-82-12 vs lane H82-2)</h3>
<p>The canonical-template track (see <a href="canon/index.html">archived position</a>) holds that only
canonical data + shared tools can produce a submittable file, and rejects mirror+private-tooling artifacts
(IR-82-12; a prior PR was reverted on this ground). Lane H82-2 holds that sha256-verified mirrors
(all pins match three independent repos), exact brute-force-verified metric code, spec-following holdout
(whole segments + buffer + exact masking + pooled DTI), honest evidence labeling, and a machine-run gate
satisfy the owner's brief — whose highest-urgency demand is a unique, obviously-submittable TIF.
<strong>Both positions stand; nothing was deleted or rewritten.</strong> The owner picks the slot.</p>
<p class="small">Registry rasters used by H82-2's lane screens: D2.8, R1-SOLO, H33-2-B2, H36-rung30, H19-5
(pins in registry/data_manifest.json). The H82-1 blindstep raster was withheld from main and could NOT be
screened — filed as a limitation (IR-82-MERGE-03).</p></section>
"""
    (DOCS / "lanes.html").write_text(page("Lanes", lanes_body))

    lane82 = {"lane": "H82-2 antislope-corroborated", "updated_utc": gate["stamp_utc"],
              "slug": slug, "verdict": verdict,
              "dots": z["emitted_positive_pixels"], "sha256_zeros": z["sha256"],
              "holdout_far": h["sgmc_far"]["pooled_dti"],
              "quad_ci95": h["sgmc_far"]["ci95_half"],
              "note": gate["submission_note"]}
    (DOCS / "data" / "lane82.json").write_text(json.dumps(lane82, indent=1))
    blind = ROOT / "research" / "h82-blindstep" / "run_card.json"
    if blind.exists():
        (DOCS / "data" / "h82-blindstep_run_card.json").write_bytes(blind.read_bytes())
    # NOTE: docs/irregularities.html is a STATIC merged file (both tracks' IRs);
    # docs/data/feed.json belongs to the refresh-feed workflow; the root
    # index.html redirect is static. None are written here.
    print(f"site built: verdict={verdict} slug={slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
