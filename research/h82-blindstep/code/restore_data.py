#!/usr/bin/env python3
"""Verify restored competition mirrors against registry/data_manifest.json (fail-closed).
Fetch on an unrestricted machine:
  git clone --depth 1 --filter=blob:none --sparse https://github.com/buffedlizard55-lab/GEMSDOE /tmp/G0
  (cd /tmp/G0 && git sparse-checkout set data/bridge)
  cat /tmp/G0/data/bridge/gems-geodawn-numerical-features.tif.part-00* > data/training_features.tif
  git clone --depth 1 --filter=blob:none --sparse https://github.com/buffedlizard55-lab/GEMSDOE24 /tmp/G24
  (cd /tmp/G24 && git sparse-checkout set data/bridge)
  cp /tmp/G24/data/bridge/{labels,sample_submission,existing_faults}.tif data/
Then run this script. No DrivenData credentials are used or needed."""
import hashlib, json, sys
from pathlib import Path
m = json.load(open("registry/data_manifest.json")); ok = True
for f in m["files"]:
    p = Path(f["dest"]); h = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING"
    good = h == f["sha256"] and p.stat().st_size == f["bytes"] if p.exists() else False
    ok &= good; print(("PASS " if good else "FAIL ") + f["id"] + " " + h[:16])
sys.exit(0 if ok else 1)
