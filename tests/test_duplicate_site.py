"""Verify fail-closed duplicate blocking on historical H82-2 and strict full-mask independence on H82-3 & H82-CSAM."""
import copy
import json
import unittest
from pathlib import Path

from scripts.build_site import is_full_mask_duplicate, render_entry_pages

ROOT = Path(__file__).resolve().parents[1]


class DuplicateSiteTest(unittest.TestCase):
    def test_active_gate_passes_strict_full_mask_duplicate_rule(self):
        gate = json.loads((ROOT / "evidence/gate.json").read_text())
        self.assertFalse(is_full_mask_duplicate(gate))
        for ref, v in gate["duplicate_guard"]["carrier_R6b"].items():
            self.assertLessEqual(v["spearman_rho"], 0.90, ref)
            self.assertLessEqual(v["overlap_3px"], 0.70, ref)
            self.assertFalse(v["duplicate"], ref)
        for ref, v in gate["duplicate_guard"]["lane_R6a"].items():
            self.assertLessEqual(v["surface_rho"], 0.90, ref)
            self.assertLessEqual(v["added_overlap_3px"], 0.70, ref)
            self.assertFalse(v["duplicate"], ref)

    def test_no_submit_link_for_duplicate(self):
        auth = json.loads((ROOT / "registry/submission_authorization.json").read_text())
        blocked = auth["blocked_historical_candidates"]["H82-2_antislope_corroborated"]
        self.assertGreater(blocked["final_dot_spearman_rho"], 0.90)
        self.assertGreater(blocked["final_dots_within_3px"], 0.70)
        for page in ("index.html", "executive-summary.html"):
            text = (ROOT / "docs" / page).read_text()
            self.assertIn("DO NOT SUBMIT", text)
            self.assertIn("Submission blocked", text)
            self.assertNotIn('href="downloads/gems82-h82-antislope-corroborated', text)
            self.assertNotIn("href='downloads/gems82-h82-antislope-corroborated", text)
            self.assertIn('href="downloads/gems82-h82-csam-dinkelbach-41200-20261021-zeros.tif"', text)
            self.assertIn('href="downloads/gems82-h82-3-covaware-corroborated-35000-20261021T233000Z-32cbf138-zeros.tif"', text)

    def test_render_entry_pages_fails_closed_when_full_mask_exceeds_threshold(self):
        gate = copy.deepcopy(json.loads((ROOT / "evidence/gate.json").read_text()))
        gate["duplicate_guard"]["carrier_R6b"]["h33-2-b2-37654"] = {
            "spearman_rho": 0.9522129193117653,
            "overlap_3px": 0.9611496050254779,
            "duplicate": True,
        }
        self.assertTrue(is_full_mask_duplicate(gate))
        idx_html, exec_html = render_entry_pages(gate)
        self.assertIn("DO NOT SUBMIT", idx_html)
        self.assertIn("Submission blocked", exec_html)
        self.assertNotIn('href="downloads/', idx_html)
        self.assertNotIn('href="downloads/', exec_html)


if __name__ == "__main__":
    unittest.main()
