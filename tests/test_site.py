"""Site integrity: unapproved/duplicate candidates cannot be downloaded or submitted."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_tiff_download_links_without_authorization():
    auth = json.loads((ROOT / "registry" / "submission_authorization.json").read_text())
    assert auth["selected_for_submission"] is False
    for name in ("index.html", "executive-summary.html"):
        html = (ROOT / "docs" / name).read_text()
        assert 'href="downloads/' not in html
        assert "DO NOT SUBMIT" in html or "Submission blocked" in html


def test_no_submission_badge_without_selector_receipt():
    auth = json.loads((ROOT / "registry" / "submission_authorization.json").read_text())
    html = (ROOT / "docs" / "index.html").read_text()
    assert auth["selected_for_submission"] is False
    assert "DO NOT SUBMIT" in html
    assert "duplicate" in html.lower()


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


def test_duplicate_evidence_and_blocked_submission_are_visible():
    auth = json.loads((ROOT / "registry" / "submission_authorization.json").read_text())
    lanes = (ROOT / "docs" / "lanes.html").read_text()
    ex = (ROOT / "docs" / "executive-summary.html").read_text()
    assert f"{auth['duplicate_screen']['final_dot_spearman_rho']:.4f}" in (ROOT / "docs" / "index.html").read_text() or "0.952" in (ROOT / "docs" / "index.html").read_text()
    assert "96.1%" in (ROOT / "docs" / "index.html").read_text()
    assert "DO NOT SUBMIT" in ex or "Submission blocked" in ex
    assert "selector receipt" in lanes.lower() or "selector authorization" in lanes.lower()


def test_root_redirect():
    assert "docs/index.html" in (ROOT / "index.html").read_text()
