from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() not in {"a", "link"}:
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)


class SiteLinksTests(unittest.TestCase):
    def test_local_html_links_resolve(self):
        missing = []
        for html_path in sorted(DOCS.rglob("*.html")):
            parser = LinkCollector()
            parser.feed(html_path.read_text(encoding="utf-8"))
            for href in parser.links:
                parts = urlsplit(href)
                if not parts.path or parts.scheme or parts.netloc:
                    continue
                target = (html_path.parent / unquote(parts.path)).resolve()
                if not target.exists():
                    missing.append(f"{html_path.relative_to(ROOT)} -> {href}")
        self.assertEqual(missing, [], "Broken local links:\n" + "\n".join(missing))

    def test_all_pages_have_title_and_language(self):
        for html_path in DOCS.rglob("*.html"):
            content = html_path.read_text(encoding="utf-8")
            with self.subTest(page=html_path.relative_to(ROOT)):
                self.assertIn("<html lang=\"en\">", content)
                self.assertIn("<title>", content)


if __name__ == "__main__":
    unittest.main()
