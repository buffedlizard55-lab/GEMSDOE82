"""Site integrity: every download link resolves; badge matches gate; no stale numbers."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_download_links_resolve():
    html = (ROOT / "docs" / "index.html").read_text()
    hrefs = re.findall(r'href="(downloads/[^"]+)"', html)
    assert hrefs, "no download links found"
    for h in hrefs:
        assert (ROOT / "docs" / h).exists(), h


def test_badge_matches_gate():
    gate = json.loads((ROOT / "evidence" / "gate.json").read_text())
    html = (ROOT / "docs" / "index.html").read_text()
    assert gate["verdict"] in html
    assert gate["slug"] in html
    assert gate["raster_sha256_zeros"] in html


def test_numbers_trace_to_receipts():
    gate = json.loads((ROOT / "evidence" / "gate.json").read_text())
    html = (ROOT / "docs" / "index.html").read_text()
    far = gate["holdout"]["sgmc_far"]["pooled_dti"]
    assert f"{far:.6f}" in html
    assert f"{gate['receipts']['zeros']['emitted_positive_pixels']:,}" in html
    # executive summary carries the exact submission note
    ex = (ROOT / "docs" / "executive-summary.html").read_text()
    assert gate["submission_note"] in ex
    assert len(gate["submission_note"]) <= 140


def test_root_redirect():
    assert "docs/index.html" in (ROOT / "index.html").read_text()
