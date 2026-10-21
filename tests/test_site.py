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


def test_no_submission_badge_without_selector_receipt():
    auth = json.loads((ROOT / "registry" / "submission_authorization.json").read_text())
    html = (ROOT / "docs" / "index.html").read_text()
    assert auth["selected_for_submission"] is False
    assert "NOT SELECTED" in html
    assert "DO NOT SUBMIT" in html
    assert "inspection" in html.lower()


def test_selector_gate_fails_closed_and_binds_sha():
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.build_site import submission_authorized

    base = {"status": "AUTHORIZED", "selected_for_submission": True,
            "selector_receipt": "receipt-123", "authorized_sha256": "abc"}
    assert submission_authorized(base, "abc")
    assert not submission_authorized(base, "different")
    assert not submission_authorized({**base, "selector_receipt": None}, "abc")
    assert not submission_authorized({**base, "selected_for_submission": False}, "abc")
    assert not submission_authorized({**base, "duplicate_screen": {"verdict": "DUPLICATE"}}, "abc")


def test_numbers_trace_to_receipts():
    gate = json.loads((ROOT / "evidence" / "gate.json").read_text())
    html = (ROOT / "docs" / "index.html").read_text()
    far = gate["holdout"]["sgmc_far"]["pooled_dti"]
    assert f"{far:.6f}" in html
    assert f"{gate['receipts']['zeros']['emitted_positive_pixels']:,}" in html
    # A note may be used only after a separate selector authorization.
    ex = (ROOT / "docs" / "executive-summary.html").read_text()
    assert "no submission is authorized" in ex.lower()
    assert "selector receipt" in ex.lower()
    assert len(gate["submission_note"]) <= 140


def test_root_redirect():
    assert "docs/index.html" in (ROOT / "index.html").read_text()
