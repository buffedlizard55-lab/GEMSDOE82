"""Fail closed when historical H82-2 final dots violate the user's duplicate rule."""
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
            self.assertIn('DO NOT SUBMIT', text)
            self.assertIn('Submission blocked', text)
            self.assertNotIn('href="downloads/gems82-h82-antislope-corroborated', text)
            self.assertNotIn("href='downloads/gems82-h82-antislope-corroborated", text)
            self.assertIn('href="downloads/gems82-h82-csam-dinkelbach-41200-20261021-zeros.tif"', text)
