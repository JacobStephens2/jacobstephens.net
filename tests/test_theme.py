"""Check the single-include theme contract on every page using site styles."""

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from urllib.parse import urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
INLINE_THEME = re.compile(
    r"data-theme|prefers-color-scheme|colorScheme|theme-color|theme-toggle|['\"]theme['\"]"
)


class PageHead(HTMLParser):
    def __init__(self, page, text):
        super().__init__(convert_charrefs=True)
        self.page = page
        self.in_head = False
        self.tags = []
        self.scripts = []
        self.script = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.in_head = True
        entry = (tag, dict(attrs), self.in_head)
        self.tags.append(entry)
        if tag == "script":
            self.script = {"index": len(self.tags) - 1, "attrs": dict(attrs), "text": ""}
            self.scripts.append(self.script)

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        if tag == "script":
            self.script = None

    def handle_data(self, data):
        if self.script is not None:
            self.script["text"] += data

    def asset_path(self, value):
        return urlsplit(urljoin("/" + self.page.as_posix(), value or "")).path

    def stylesheets(self):
        return [(index, attrs) for index, (tag, attrs, _) in enumerate(self.tags)
                if tag == "link" and "stylesheet" in attrs.get("rel", "").lower().split()]

    def uses_site_styles(self):
        return any(self.asset_path(attrs.get("href")) == "/styles/style.css"
                   for _, attrs in self.stylesheets())


class ThemeWiring(unittest.TestCase):
    def test_all_styled_pages_use_one_synchronous_head_include(self):
        styled = []
        for page in sorted(ROOT.rglob("*.html")):
            relative = page.relative_to(ROOT)
            if any(part.startswith(".") for part in relative.parts):
                continue
            parsed = PageHead(relative, page.read_text(encoding="utf-8"))
            if parsed.uses_site_styles():
                styled.append(parsed)
        self.assertTrue(styled, "No pages using the shared stylesheet were found")

        for parsed in styled:
            with self.subTest(page=parsed.page.as_posix()):
                includes = [script for script in parsed.scripts
                            if parsed.asset_path(script["attrs"].get("src")) == "/styles/theme.js"]
                self.assertEqual(len(includes), 1, "Use exactly one shared theme include")
                include = includes[0]
                attrs = include["attrs"]
                self.assertTrue(parsed.tags[include["index"]][2], "Theme must load in head")
                self.assertNotIn("defer", attrs, "Theme must execute synchronously")
                self.assertNotIn("async", attrs, "Theme must execute synchronously")
                self.assertIn(attrs.get("type", "").lower(),
                              ("", "text/javascript", "application/javascript"),
                              "Theme must be a classic script")
                charset = [index for index, (tag, meta, in_head) in enumerate(parsed.tags)
                           if tag == "meta" and in_head and "charset" in meta]
                viewport = [index for index, (tag, meta, in_head) in enumerate(parsed.tags)
                            if tag == "meta" and in_head and meta.get("name", "").lower() == "viewport"]
                self.assertTrue(charset, "Keep charset metadata before the theme include")
                self.assertTrue(viewport, "Keep viewport metadata before the theme include")
                self.assertLess(max(charset + viewport), include["index"])
                self.assertLess(include["index"], min(index for index, _ in parsed.stylesheets()))
                for script in parsed.scripts:
                    if "src" not in script["attrs"]:
                        self.assertIsNone(INLINE_THEME.search(script["text"]),
                                          "Keep theme preference logic in styles/theme.js")


if __name__ == "__main__":
    unittest.main()
