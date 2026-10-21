"""Gate regression: base holdout numbers pinned to the receipt (IR-82-R2-01).

Requires data/ (skipped if absent). Guards against hand-copied-constant bugs:
the base mask evaluated in-process must reproduce evidence/holdout_registry_v2.json.
"""
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not Path("data/registry/h33-2-b2-37654-nan.tif").exists(),
    reason="data/ not fetched (bash scripts/fetch_data.sh)")

from gems82 import grid as G
from gems82 import holdout as H


def test_base_quadrants_match_receipt():
    ctx = H.load_holdout_context("data")
    base = G.read_binary_mask("data/registry/h33-2-b2-37654-nan.tif")
    r = H.evaluate_sgmc_far(base, ctx)
    rec = json.loads(Path("evidence/holdout_registry_v2.json").read_text())
    row = next(x for x in rec["results"] if "h33" in x["name"])
    assert r["pooled_dti"] == pytest.approx(row["sgmc_far"]["pooled_dti"], abs=1e-9)
    assert r["tp"] == pytest.approx(row["sgmc_far"]["tp"], abs=1e-6)
    for q in ("NW", "NE", "SW", "SE"):
        assert r["per_quadrant"][q] == pytest.approx(
            row["sgmc_far"]["per_quadrant"][q], abs=1e-9)


def test_moat_reproduces_live_ordering():
    # The instrument license: SGMC-FAR must rank d28 < r1 < b2 (TP-neutral steps).
    ctx = H.load_holdout_context("data")
    ds = {}
    for k, f in (("d28", "data/registry/d28-44090-nan.tif"),
                 ("r1", "data/registry/r1-solo-40199-nan.tif"),
                 ("b2", "data/registry/h33-2-b2-37654-nan.tif")):
        ds[k] = H.evaluate_sgmc_far(G.read_binary_mask(f), ctx)
    assert ds["d28"]["pooled_dti"] < ds["r1"]["pooled_dti"] < ds["b2"]["pooled_dti"]
    assert ds["d28"]["tp"] == pytest.approx(ds["b2"]["tp"], abs=1e-6)
