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
    def test_local_html_links_resolve_inside_pages_artifact(self):
        missing = []
        for html_path in sorted(DOCS.rglob("*.html")):
            parser = LinkCollector()
            parser.feed(html_path.read_text(encoding="utf-8"))
            for href in parser.links:
                parts = urlsplit(href)
                if not parts.path or parts.scheme or parts.netloc:
                    continue
                target = (html_path.parent / unquote(parts.path)).resolve()
                try:
                    target.relative_to(DOCS.resolve())
                except ValueError:
                    missing.append(f"{html_path.relative_to(ROOT)} -> {href} escapes the Pages artifact")
                    continue
                if not target.exists():
                    missing.append(f"{html_path.relative_to(ROOT)} -> {href}")
        self.assertEqual(missing, [], "Broken local links:\n" + "\n".join(missing))

    def test_pages_run_card_copy_matches_canonical_registry_card(self):
        canonical = ROOT / "registry" / "run_card.json"
        published = DOCS / "data" / "run_card.json"
        self.assertTrue(published.is_file(), "run card must be included in the Pages artifact")
        self.assertEqual(published.read_bytes(), canonical.read_bytes())

    def test_public_repository_root_matches_docs_site(self):
        root_page = ROOT / "index.html"
        content = root_page.read_text(encoding="utf-8")
        self.assertIn("<html lang=\"en\">", content)
        self.assertIn("gems82-h82-csam-dinkelbach-41200-20261021-zeros.tif", content)
        self.assertTrue((ROOT / "docs" / "index.html").is_file())
        self.assertEqual(root_page.read_bytes(), (ROOT / "docs" / "index.html").read_bytes())

    def test_all_pages_have_title_and_language(self):
        for html_path in DOCS.rglob("*.html"):
            content = html_path.read_text(encoding="utf-8")
            with self.subTest(page=html_path.relative_to(ROOT)):
                self.assertIn("<html lang=\"en\">", content)
                self.assertIn("<title>", content)


if __name__ == "__main__":
    unittest.main()
