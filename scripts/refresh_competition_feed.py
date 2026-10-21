#!/usr/bin/env python3
"""Refresh a public-source status feed without copying leaderboard scores or secrets.

This script probes only the public DrivenData leaderboard and the competition data
page. It does not authenticate, download competition data, or produce a submission.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LEADERBOARD_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
DATA_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/data/"
LOGIN_MARKER = "/accounts/login/"


class _PageProbe(HTMLParser):
    """Collect only page title, headings, and whether a data table is present."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self._in_title = False
        self._in_heading = False
        self._row_cells = 0
        self._rows_with_cells = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True
        elif tag.lower() in {"h1", "h2"}:
            self._in_heading = True
        elif tag.lower() == "tr":
            self._row_cells = 0
        elif tag.lower() in {"td", "th"}:
            self._row_cells += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        elif tag.lower() in {"h1", "h2"}:
            self._in_heading = False
        elif tag.lower() == "tr" and self._row_cells:
            self._rows_with_cells += 1
            self._row_cells = 0

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        if self._in_heading:
            self.heading_parts.append(text)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def headings(self) -> str:
        return " ".join(self.heading_parts).strip()


def _probe_html(html: str) -> dict[str, object]:
    parser = _PageProbe()
    parser.feed(html)
    return {
        "title": parser.title,
        "headings": parser.headings,
        "has_table_rows": parser._rows_with_cells > 0,
    }


def fetch_html(url: str, timeout: int = 20) -> dict[str, object]:
    """Fetch a public page, following ordinary redirects and returning no credentials."""
    request = Request(
        url,
        headers={"User-Agent": "GEMSDOE82-public-source-status/1.0", "Accept": "text/html"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {
                "status": "http_ok",
                "final_url": response.geturl(),
                "html": body,
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"status": f"http_{exc.code}", "final_url": exc.geturl(), "html": body}
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "status": "unreachable",
            "final_url": None,
            "html": "",
            "error_type": type(exc).__name__,
        }


def _public_page_record(url: str, result: dict[str, object], label: str) -> dict[str, object]:
    html = str(result.get("html", ""))
    info = _probe_html(html)
    status = str(result.get("status", "unknown"))
    final_url = result.get("final_url")
    return {
        "source_url": url,
        "status": status,
        "final_url": final_url,
        "page_title": info["title"] or None,
        "heading_present": label.lower() in str(info["headings"]).lower(),
        "table_rows_present": info["has_table_rows"],
        "score_values_copied": False,
        "note": "Public page probe only; no project score or submission receipt is inferred.",
    }


def refresh_feed(
    fetch: Callable[[str], dict[str, object]] = fetch_html,
    now: datetime | None = None,
) -> dict[str, object]:
    """Create a score-free status feed for the public leaderboard and data-page gate."""
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    observed_at = observed_at.astimezone(timezone.utc)

    leaderboard_result = fetch(LEADERBOARD_URL)
    data_result = fetch(DATA_URL)
    leaderboard = _public_page_record(LEADERBOARD_URL, leaderboard_result, "leaderboard")
    data_page = _public_page_record(DATA_URL, data_result, "login")

    final_data_url = str(data_page.get("final_url") or "")
    data_html_info = _probe_html(str(data_result.get("html", "")))
    if LOGIN_MARKER in final_data_url or "login" in str(data_html_info["title"]).lower():
        data_page["access_status"] = "login_required"
    elif data_page["status"] == "unreachable":
        data_page["access_status"] = "unreachable"
    else:
        data_page["access_status"] = "response_received_access_not_verified"
    data_page["authenticated"] = False
    data_page["credentials_used"] = False

    if leaderboard["status"] == "http_ok" and (
        leaderboard["heading_present"] or "leaderboard" in str(leaderboard["page_title"]).lower()
    ):
        leaderboard["access_status"] = "public_leaderboard_reachable"
    elif leaderboard["status"] == "unreachable":
        leaderboard["access_status"] = "unreachable"
    else:
        leaderboard["access_status"] = "unexpected_response"

    return {
        "schema_version": "1.0",
        "observed_at_utc": observed_at.isoformat().replace("+00:00", "Z"),
        "feed_scope": "Public-source availability only. No competition labels, private data, scores, or submission receipts are included.",
        "leaderboard": leaderboard,
        "competition_data": data_page,
        "project": {
            "status": "no_submit_ready_tiff",
            "run_card": "../../registry/run_card.json",
            "sources_ledger": "../sources.md",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/data/feed.json"),
        help="JSON feed destination (default: docs/data/feed.json)",
    )
    args = parser.parse_args()
    feed = refresh_feed()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(feed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(feed, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
