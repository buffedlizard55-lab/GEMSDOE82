# H82-1 blind-fault lane — NEGATIVE research record (session arena/d0d8912f)

**Status: NOT READY / DO NOT SUBMIT** (consistent with repo README and IR-82-12). This folder is
an evidence record only. The candidate GeoTIFF binaries are **withheld from main** per the repo's
canonical-data/tool policy (this session restored sha256-pinned sibling mirrors and used a
clean-room local evaluator/writer, not the canonical template). Audit digests of the withheld
file: zeros sha256 `cfd9a3279f24f4dbf48225f4ed9d5df188053a0a1d0024a91129ea6af7761307`
(210,235 B, 37,654 dots) — see `build_receipt.json`. Do not retrieve/submit it as a candidate.

Results (HOLDOUT-DTI, local evaluator `gems82-hide-v1`, 57,407 withheld, 50px-block bootstrap):
E2 line-blind 0.0745 [0.0693,0.0799] vs random 0.0693 (n.s.), scarp control (E1) 0.0779;
low-slope stratum 0.0748 vs random 0.0556 (Δ+0.0190 [+0.0099,+0.0281]). Canary max AUC 0.544.
Uniqueness vs H33-2-B2/dotted: rho~0.007, overlap~20%. Verdict: negative. Full card: run_card.json.
Next science (main session): adjudicate low-slope signal on off-catalogue truth with canonical tooling; H82-3.
