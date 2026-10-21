from datetime import datetime, timezone
import unittest

from scripts.refresh_competition_feed import (
    DATA_URL,
    LEADERBOARD_URL,
    refresh_feed,
)


class RefreshFeedTests(unittest.TestCase):
    def test_public_leaderboard_and_login_redirect_are_reported_without_scores(self):
        html_by_url = {
            LEADERBOARD_URL: """<!doctype html><html><head><title>GEMS Prize Challenge - Leaderboard</title></head>
            <body><h1>Leaderboard</h1><table><tr><th>Rank</th><th>Participant</th></tr>
            <tr><td>#1</td><td>Example team</td></tr></table></body></html>""",
            DATA_URL: "<html><head><title>Login</title></head><body><h1>Login</h1></body></html>",
        }
        final_urls = {
            LEADERBOARD_URL: LEADERBOARD_URL,
            DATA_URL: "https://www.drivendata.org/accounts/login/?next=/competitions/306/competition-doe-gems/data/",
        }

        def fake_fetch(url):
            return {"status": "http_ok", "final_url": final_urls[url], "html": html_by_url[url]}

        feed = refresh_feed(
            fetch=fake_fetch,
            now=datetime(2026, 10, 21, tzinfo=timezone.utc),
        )
        self.assertEqual(feed["leaderboard"]["access_status"], "public_leaderboard_reachable")
        self.assertTrue(feed["leaderboard"]["table_rows_present"])
        self.assertEqual(feed["competition_data"]["access_status"], "login_required")
        self.assertFalse(feed["competition_data"]["authenticated"])
        self.assertFalse(feed["leaderboard"]["score_values_copied"])
        self.assertNotIn("score", feed["leaderboard"])
        self.assertTrue(feed["observed_at_utc"].endswith("Z"))

    def test_unreachable_sources_are_recorded_as_unavailable(self):
        feed = refresh_feed(
            fetch=lambda url: {"status": "unreachable", "final_url": None, "html": ""},
            now=datetime(2026, 10, 21, tzinfo=timezone.utc),
        )
        self.assertEqual(feed["leaderboard"]["access_status"], "unreachable")
        self.assertEqual(feed["competition_data"]["access_status"], "unreachable")
        self.assertFalse(feed["leaderboard"]["score_values_copied"])


if __name__ == "__main__":
    unittest.main()
