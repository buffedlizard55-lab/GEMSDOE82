#!/usr/bin/env bash
# Fetch competition + mirror data from pinned GitHub refs into data/.
# Everything is an owner mirror of a DrivenData/GDR/USGS file (login-walled or
# egress-blocked from some sandboxes); sha256 pins live in
# registry/data_manifest.json and are verified by scripts/verify_data.py.
#
# Usage: bash scripts/fetch_data.sh [data_dir]   (default: data/)
set -euo pipefail
DATA_DIR="${1:-data}"
mkdir -p "$DATA_DIR/external"

have() { command -v "$1" >/dev/null 2>&1; }

fetch_file() { # repo, ref, remote_path, local_path
  local repo="$1" ref="$2" remote="$3" local="$4"
  if [ -f "$local" ]; then echo "exists: $local"; return 0; fi
  mkdir -p "$(dirname "$local")"
  echo "fetch: $repo@$ref:$remote -> $local"
  if have gh; then
    gh api "repos/$repo/contents/$remote?ref=$ref" -q .content 2>/dev/null | base64 -d > "$local" \
      || git archive --remote="https://github.com/$repo.git" "$ref" "$remote" | tar -x -O "$remote" > "$local"
  else
    git archive --remote="https://github.com/$repo.git" "$ref" "$remote" | tar -x -O "$remote" > "$local"
  fi
}

G24_REPO="buffedlizard55-lab/GEMSDOE24"
G24_REF="07345ea0604953d7efb858d9cfbc21e20c7aca0b"
G32_REPO="buffedlizard55-lab/GEMSDOE32"
G32_REF="f62038b54dcb7767d4d997f80b033cdc3d42bef9"
G28_REPO="buffedlizard55-lab/GEMSDOE28"
G28_REF="84d99d7479bbd8e02deba4e8217c7b73d111eaeb"

# core grids (small)
fetch_file "$G24_REPO" "$G24_REF" "data/bridge/labels.tif"            "$DATA_DIR/labels.tif"
fetch_file "$G24_REPO" "$G24_REF" "data/bridge/sample_submission.tif" "$DATA_DIR/sample_submission.tif"
fetch_file "$G24_REPO" "$G24_REF" "data/bridge/existing_faults.tif"   "$DATA_DIR/existing_faults.tif"
# proxy truth + externals
fetch_file "$G24_REPO" "$G24_REF" "data/external/derived_sgmc_faults_100m_u8.tif" "$DATA_DIR/external/derived_sgmc_faults_100m_u8.tif"
fetch_file "$G24_REPO" "$G24_REF" "data/external/gdr_wellspring_in_footprint.csv" "$DATA_DIR/external/gdr_wellspring_in_footprint.csv"
fetch_file "$G24_REPO" "$G24_REF" "data/external/gdr_qfaults_traces.csv"          "$DATA_DIR/external/gdr_qfaults_traces.csv"
fetch_file "$G24_REPO" "$G24_REF" "data/external/gdr_volcanic_vents_in_footprint.csv" "$DATA_DIR/external/gdr_volcanic_vents_in_footprint.csv"
fetch_file "$G24_REPO" "$G24_REF" "data/external/lidar_scarp_features_u8.tif"  "$DATA_DIR/external/lidar_scarp_features_u8.tif"
fetch_file "$G24_REPO" "$G24_REF" "data/external/geodawn_rad_u8.tif"           "$DATA_DIR/external/geodawn_rad_u8.tif"
fetch_file "$G24_REPO" "$G24_REF" "data/external/geodawn_extensions_u8.tif"    "$DATA_DIR/external/geodawn_extensions_u8.tif"
fetch_file "$G24_REPO" "$G24_REF" "data/external/lidar_scarp_features.json"   "$DATA_DIR/external/lidar_scarp_features.json"
fetch_file "$G24_REPO" "$G24_REF" "data/external/geodawn_rad.json"            "$DATA_DIR/external/geodawn_rad.json"
fetch_file "$G24_REPO" "$G24_REF" "data/external/geodawn_extensions.json"     "$DATA_DIR/external/geodawn_extensions.json"
# registry rasters for the duplicate guard (small downloads)
mkdir -p "$DATA_DIR/registry"
fetch_file "$G32_REPO" "$G32_REF" "docs/downloads/gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif" \
  "$DATA_DIR/registry/d28-44090-nan.tif"
fetch_file "$G28_REPO" "$G28_REF" "docs/downloads/gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan.tif" \
  "$DATA_DIR/registry/r1-solo-40199-nan.tif"
fetch_file "$G32_REPO" "$G32_REF" "docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-nan.tif" \
  "$DATA_DIR/registry/h33-2-b2-37654-nan.tif"

echo "done. Verifying pins..."
python3 scripts/verify_data.py --data-dir "$DATA_DIR"
