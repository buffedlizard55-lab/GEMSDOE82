"""Fail closed when historical final dots violate the user's duplicate rule."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DuplicateSiteTest(unittest.TestCase):
    def test_no_submit_link_for_duplicate(self):
        gate = json.loads((ROOT / 'evidence/gate.json').read_text())
        carrier = gate['duplicate_guard']['carrier_R6b']
        self.assertTrue(any(v['spearman_rho'] > .90 or v['overlap_3px'] > .70
                            for v in carrier.values()))
        for page in ('index.html', 'executive-summary.html'):
            text = (ROOT / 'docs' / page).read_text()
            self.assertIn('DO NOT SUBMIT' if page == 'index.html' else 'Submission blocked', text)
            self.assertNotIn('href="downloads/', text)
            self.assertNotIn("href='downloads/", text)
