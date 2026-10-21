#!/usr/bin/env python3
"""Fetch the reproducibility cache from public GitHub mirrors.

This is deliberately not described as the official DrivenData download: the
competition data page redirects to login in this environment.  The mirror
commits and SHA-256 values below are pinned so that a run is reproducible, but
mirror integrity is not organizer authentication.  The cache is git-ignored
because the 19-band feature TIFF is about 419 MB.
"""
from __future__ import annotations

import hashlib
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".cache" / "gems_data" / "core"
RAW = ROOT / ".cache" / "gems_data" / "raw"

FEATURE_REPO = "GEMSDOE"
FEATURE_REF = "c0c06ac82178f26b94fce3397036ef8f12a2f3a0"
AUX_REPO = "GEMSDOE24"
AUX_REF = "07345ea0604953d7efb858d9cfbc21e20c7aca0b"
FEATURE_PARTS = [
    (f"data/bridge/gems-geodawn-numerical-features.tif.part-{i:03d}", RAW / f"part-{i:03d}")
    for i in range(5)
]
EXPECTED = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
    "existing_faults.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_members(repo: str, ref: str, wanted: dict[str, Path]) -> None:
    url = f"https://codeload.github.com/buffedlizard55-lab/{repo}/tar.gz/{ref}"
    request = urllib.request.Request(url, headers={"User-Agent": "GEMSDOE82-reproducibility-fetch"})
    with urllib.request.urlopen(request, timeout=600) as response:
        with tarfile.open(fileobj=response, mode="r|gz") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                relative = member.name.split("/", 1)[-1]
                if relative not in wanted:
                    continue
                target = wanted[relative]
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError(f"Unable to read {member.name}")
                temporary = target.with_suffix(target.suffix + ".tmp")
                with temporary.open("wb") as destination:
                    while True:
                        block = source.read(1 << 20)
                        if not block:
                            break
                        destination.write(block)
                temporary.replace(target)


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    wanted_features = {source: target for source, target in FEATURE_PARTS if not target.exists()}
    if wanted_features:
        print(f"Fetching {len(wanted_features)} feature parts from {FEATURE_REPO}@{FEATURE_REF[:12]}")
        fetch_members(FEATURE_REPO, FEATURE_REF, wanted_features)
    feature_path = DEST / "training_features.tif"
    if not feature_path.exists() or feature_path.stat().st_size != sum(p.stat().st_size for _, p in FEATURE_PARTS):
        temporary = feature_path.with_suffix(".tif.tmp")
        with temporary.open("wb") as output:
            for _, part in FEATURE_PARTS:
                if not part.exists():
                    raise FileNotFoundError(part)
                with part.open("rb") as source:
                    while block := source.read(1 << 20):
                        output.write(block)
        temporary.replace(feature_path)

    needed_aux = {
        "data/bridge/sample_submission.tif": DEST / "sample_submission.tif",
        "data/bridge/existing_faults.tif": DEST / "existing_faults.tif",
        "data/bridge/labels.tif": DEST / "labels.tif",
    }
    missing_aux = {source: path for source, path in needed_aux.items() if not path.exists()}
    if missing_aux:
        print(f"Fetching {len(missing_aux)} template/label rasters from {AUX_REPO}@{AUX_REF[:12]}")
        fetch_members(AUX_REPO, AUX_REF, missing_aux)

    # Some mirrors do not need to expose a second labels copy; the competition
    # label raster is byte-identical to existing_faults in the pinned mirror.
    if not (DEST / "labels.tif").exists():
        (DEST / "existing_faults.tif").replace(DEST / "labels.tif")
    for name, expected in EXPECTED.items():
        path = DEST / name
        if not path.exists():
            raise FileNotFoundError(path)
        got = sha256(path)
        if got != expected:
            raise RuntimeError(f"SHA-256 mismatch for {name}: {got} != {expected}")
        print(f"OK {name} {got}")
    print(f"Cache ready at {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
