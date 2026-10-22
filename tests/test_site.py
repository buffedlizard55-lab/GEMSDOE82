"""Site integrity: authorized H82-CSAM is downloadable while duplicate H82-2 remains blocked."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_authorized_csam_download_and_blocked_duplicate():
    auth = json.loads((ROOT / "registry" / "submission_authorization.json").read_text())
    assert auth["selected_for_submission"] is True
    assert auth["status"] == "AUTHORIZED"
    assert auth["authorized_filename"] == "gems82-h82-csam-dinkelbach-41200-20261021-zeros.tif"
    assert auth["authorized_sha256"] == "18bdf3f4eb021b0b2a45aca2627d9c81c656d366618cc9f39f413f2163e01767"
    assert auth["duplicate_screen"]["final_dot_spearman_rho"] <= 0.90
    assert auth["duplicate_screen"]["final_dots_within_3px"] <= 0.70

    for name in ("index.html", "executive-summary.html"):
        html = (ROOT / "docs" / name).read_text()
        assert "gems82-h82-csam-dinkelbach-41200-20261021-zeros.tif" in html
        assert 'href="downloads/gems82-h82-antislope-corroborated' not in html
        assert "DO NOT SUBMIT" in html
        assert "Submission blocked" in html


def test_selector_receipt_bound_on_entry_pages():
    auth = json.loads((ROOT / "registry" / "submission_authorization.json").read_text())
    html = (ROOT / "docs" / "index.html").read_text()
    assert auth["selector_receipt"] in html
    assert auth["authorized_sha256"] in html
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
    blocked = auth["blocked_historical_candidates"]["H82-2_antislope_corroborated"]
    assert blocked["final_dot_spearman_rho"] > 0.90
    assert blocked["final_dots_within_3px"] > 0.70
    idx = (ROOT / "docs" / "index.html").read_text()
    ex = (ROOT / "docs" / "executive-summary.html").read_text()
    assert "0.9522" in idx
    assert "96.1%" in idx
    assert "DO NOT SUBMIT" in ex and "Submission blocked" in ex


def test_root_and_docs_portal_synced():
    assert (ROOT / "index.html").read_text() == (ROOT / "docs" / "index.html").read_text()
    assert (ROOT / "executive-summary.html").read_text() == (ROOT / "docs" / "executive-summary.html").read_text()
