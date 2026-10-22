import tempfile
import unittest
from pathlib import Path

from scripts.check_readiness import inspect_root


class ReadinessTests(unittest.TestCase):
    def test_empty_checkout_is_blocked_not_falsely_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            report = inspect_root(Path(temp))
        self.assertFalse(report["holdout_assets_present"])
        self.assertFalse(report["candidate_stage_assets_present"])
        self.assertFalse(report["writer_assets_present"])
        self.assertFalse(report["submit_ready"])
        self.assertEqual(report["inputs"]["features"]["status"], "missing")
        self.assertEqual(report["shared_tools"]["evaluate_holdout.py"]["status"], "missing")
        self.assertEqual(report["cached_feature_stack"]["status"], "missing_or_unspecified")
        self.assertFalse(report["cached_feature_stack"]["explicit_path_supplied"])

    def test_explicit_but_missing_cache_path_does_not_unlock_holdout(self):
        with tempfile.TemporaryDirectory() as temp:
            report = inspect_root(Path(temp), feature_cache_path="missing-cache.npz")
        self.assertFalse(report["holdout_assets_present"])
        self.assertEqual(report["cached_feature_stack"]["status"], "missing_or_unspecified")
        self.assertTrue(report["cached_feature_stack"]["explicit_path_supplied"])

    def test_nonempty_explicit_cache_is_detected_but_other_missing_assets_still_block(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = root / "shared-cache.bin"
            cache.write_bytes(b"cached feature stack placeholder")
            report = inspect_root(root, feature_cache_path=str(cache))
        self.assertEqual(report["cached_feature_stack"]["status"], "present")
        self.assertFalse(report["holdout_assets_present"])
        self.assertFalse(report["writer_assets_present"])
        self.assertFalse(report["submit_ready"])


if __name__ == "__main__":
    unittest.main()
