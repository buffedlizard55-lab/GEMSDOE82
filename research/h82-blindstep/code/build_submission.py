#!/usr/bin/env python3
"""E3/build: unique GEMSDOE82 TIF from validated in-lane rule (line_blind + thin spacing2,
d_cat>2px, N=37654 matched mass). Writes zeros-primary + nan twin + zip + receipts + uniqueness."""
import hashlib, json, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
sys.path.insert(0, "src")
from gems82 import grid, emission, uniqueness
from scipy.ndimage import distance_transform_edt

foot, prof = grid.load_template("data/sample_submission.tif")
labels = grid.load_labels("data/labels.tif", foot)
S = np.load(".cache/s_line_blind.npy")
allowed, dcat = emission.allowed_mask(foot, labels, buffer_px=2)
dots = emission.thin_topn(S, allowed, 37654, spacing=2)
n = int(dots.sum()); print(f"dots={n} on_cat={int((dots&labels).sum())} min_dcat={float(dcat[dots].min())}")
assert n == 37654 and int((dots & labels).sum()) == 0
digest8 = hashlib.sha256(np.packbits(dots)).hexdigest()[:8]
ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
base = f"gems82-blindstep-line-37654-{ts}-{digest8}"
outdir = Path("docs/downloads"); outdir.mkdir(parents=True, exist_ok=True)
zp = grid.write_submission(dots.astype(np.float32), foot, prof, outdir / f"{base}-zeros.tif", "zeros")
np_ = grid.write_submission(dots.astype(np.float32), foot, prof, outdir / f"{base}-nan.tif", "nan")
rz = grid.validate(zp, foot, labels, "zeros"); rn = grid.validate(np_, foot, labels, "nan")
zipp = outdir / f"{base}-zeros.zip"
with zipfile.ZipFile(zipp, "w", zipfile.ZIP_DEFLATED) as z: z.write(zp, arcname=zp.name)
reg = ["/tmp/inspect/GEMSDOE32/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif",
       "/tmp/inspect/GEMSDOE32/docs/downloads/gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"]
reg = [p for p in reg if Path(p).exists()]
uniq = uniqueness.check(S, dots, reg, foot)
receipt = dict(base=base, unique_name="GEMSDOE82-BLINDSTEP-LINE-37654", zeros=rz, nan=rn,
               zip=dict(file=zipp.name, sha256=grid.sha256_file(zipp), bytes=zipp.stat().st_size),
               uniqueness=uniq, dots=n, surface="s_line_blind (H82-1 Hessian-line blind step)",
               emission="thin_topn spacing=2, allowed d_cat>2px, N=37654")
json.dump(receipt, open(outdir / f"{base}-receipt.json", "w"), indent=2)
json.dump(receipt, open("evidence/build_receipt.json", "w"), indent=2)
print(json.dumps({k: receipt[k] for k in ("base","dots")}, indent=2))
print("zeros sha", rz["sha256"], rz["bytes"], "checks", rz["all_passed"])
print("UNIQ", json.dumps(uniq, indent=2))
