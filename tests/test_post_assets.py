"""Tests for colocated post assets, chart data generation, and static redirects."""

from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTACCESS = ROOT / ".htaccess"
CHART_SCRIPT = ROOT / "posts" / "tigris-and-euphrates-scoring-rule" / "build_chart_data.py"
CHART_RESULTS = ROOT / "posts" / "tigris-and-euphrates-scoring-rule" / "sim_results.json"
TIGRIS_HTML = ROOT / "posts" / "tigris-and-euphrates-scoring-rule" / "index.html"

MIGRATED_POSTS = (
    "tigris-and-euphrates-scoring-rule",
    "on-sexuality-and-criminality",
    "why-anti-cyrillic-croats-attack-serbian-language",
    "finding-greener-alternatives-to-ap-chromatography-lab",
)

REMOVED_STATIC_DIRS = (
    "tigris-and-euphrates",
    "028f841bbba7a644da6d72d66abecd43",
    "0c7c64a5f5f92661d8d92a6d0700ad3d",
    "27752169223039ada5e361fffc255a03",
    "32975babe9834cd024e61a1765949d11",
    "4087dff12f43c8c90e67cfd39c185cdd",
    "48026830135942437af9f60db938d38c",
    "5b646d42c2bbc185b455bc4de1193c0a",
    "6344e9f96395a791b635f70f6077d13e",
    "71931b27e48aa0c824e29d669bcec443",
    "97ec2f2154fcdd3cacfbc20b04fbe0b8",
    "d25607e7a9ba260e44096fa7fea46552",
    "fbb4f4e111e598d6c9f9dbd47b218e5b",
)

EXPECTED_REDIRECTS = {
    "/static/tigris-and-euphrates/waterline-hero.jpg":
        "/posts/tigris-and-euphrates-scoring-rule/waterline-hero.jpg",
    "/static/tigris-and-euphrates/uruk-accounting-tablets.jpg":
        "/posts/tigris-and-euphrates-scoring-rule/uruk-accounting-tablets.jpg",
    "/static/tigris-and-euphrates/tigris_sim.py":
        "/posts/tigris-and-euphrates-scoring-rule/tigris_sim.py",
    "/static/tigris-and-euphrates/sim_results.json":
        "/posts/tigris-and-euphrates-scoring-rule/sim_results.json",
    "/static/tigris-and-euphrates/build_chart_data.py":
        "/posts/tigris-and-euphrates-scoring-rule/build_chart_data.py",
    "/static/028f841bbba7a644da6d72d66abecd43/SOC411-Syllabus.pdf":
        "/posts/on-sexuality-and-criminality/SOC411-Syllabus.pdf",
    "/static/0c7c64a5f5f92661d8d92a6d0700ad3d/Syllabus-SOC371.pdf":
        "/posts/why-anti-cyrillic-croats-attack-serbian-language/Syllabus-SOC371.pdf",
}

CHROMATOGRAPHY_MIGRATED_ASSETS = [
    ("27752169223039ada5e361fffc255a03", ("1bed9", "4e610", "7b64c"),
     "1-two-series-five-dev-chambers-dye-spinach.png"),
    ("4087dff12f43c8c90e67cfd39c185cdd", ("b4e2e", "993bf", "2be58"),
     "2-sharpie-chromatographs.png"),
    ("48026830135942437af9f60db938d38c", ("97cec", "4fe98", "79613", "94eb7"),
     "3-dye-mix-diluted-ethanol-chromatographs.png"),
    ("97ec2f2154fcdd3cacfbc20b04fbe0b8", ("b217e", "28aea", "1bda3", "bf0a7"),
     "4-black-ink-marker-chromatographs.png"),
    ("71931b27e48aa0c824e29d669bcec443", ("56022", "3ae48", "da63f", "f554a"),
     "5-marker-chromatographs.png"),
    ("32975babe9834cd024e61a1765949d11", ("34428", "799c6", "6a7c4", "eaec9"),
     "6-sharpie-pen-chromatographs.png"),
    ("d25607e7a9ba260e44096fa7fea46552", ("c6e1a", "e4c64", "704d3", "bd361"),
     "7-dye-mixes-red-blue-yel-chromatographs.png"),
    ("5b646d42c2bbc185b455bc4de1193c0a", ("853e8", "d6ba7", "225a5", "59727", "18c31"),
     "chromatography-research-notes-p1-copy.png"),
    ("6344e9f96395a791b635f70f6077d13e", ("a9fc9", "ca463", "8daf7", "1aaec"),
     "chromatography-research-notes-p2-copy.png"),
    ("fbb4f4e111e598d6c9f9dbd47b218e5b", ("e8a52", "0eb15", "50822", "31e07"),
     "chromatography-research-notes-p3-copy.png"),
]
for _hash_dir, _variants, _filename in CHROMATOGRAPHY_MIGRATED_ASSETS:
    _dest = f"/posts/finding-greener-alternatives-to-ap-chromatography-lab/{_filename}"
    for _variant in _variants:
        EXPECTED_REDIRECTS[f"/static/{_hash_dir}/{_variant}/{_filename}"] = _dest


class LinkExtractor(HTMLParser):
    """Collect src and href values from authored HTML."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.urls = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("src", "href") and value:
                self.urls.append(value)


def parse_301_rewrite_rules(htaccess_text):
    """Parse unconditional 301 RewriteRule directives from root .htaccess."""
    rules = []
    previous_line = ""
    for raw_line in htaccess_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            previous_line = line
            continue
        match = re.match(r"^RewriteRule\s+(\S+)\s+(\S+)\s+\[([^\]]+)\]$", line)
        if match and not previous_line.startswith("RewriteCond"):
            pattern, target, flags = match.groups()
            flag_set = {f.strip() for f in flags.split(",")}
            if "R=301" in flag_set and "L" in flag_set:
                rules.append((re.compile(pattern), target))
        previous_line = line
    return rules


def resolve_redirect(rules, url_path):
    """Simulate Apache per-directory RewriteRule matching on a root-relative path."""
    rel_path = url_path.lstrip("/")
    for regex, target in rules:
        match = regex.search(rel_path)
        if match:
            return re.sub(
                r"\$(\d+)",
                lambda m: match.group(int(m.group(1))) or "",
                target,
            )
    return None


class PostAssetColocationTests(unittest.TestCase):
    def test_build_chart_data_check_and_rewrite_from_colocated_dir(self):
        self.assertTrue(CHART_SCRIPT.is_file(), f"missing {CHART_SCRIPT}")
        result = subprocess.run(
            [sys.executable, str(CHART_SCRIPT), "--check"],
            cwd=str(CHART_SCRIPT.parent),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            post_dir = tmp_root / "posts" / "tigris-and-euphrates-scoring-rule"
            post_dir.mkdir(parents=True)
            script = post_dir / "build_chart_data.py"
            shutil.copyfile(CHART_SCRIPT, script)
            shutil.copyfile(CHART_RESULTS, post_dir / "sim_results.json")
            original_html = TIGRIS_HTML.read_text(encoding="utf-8")
            stale_html = original_html.replace("bag: 0.3725", "bag: 0.9999", 1)
            self.assertNotEqual(stale_html, original_html)
            (post_dir / "index.html").write_text(stale_html, encoding="utf-8")

            stale = subprocess.run(
                [sys.executable, str(script), "--check"],
                cwd=str(tmp_root),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("STALE:", stale.stderr)

            rebuilt = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(post_dir),
                capture_output=True,
                text=True,
            )
            self.assertEqual(rebuilt.returncode, 0, rebuilt.stdout + rebuilt.stderr)
            self.assertEqual((post_dir / "index.html").read_text(encoding="utf-8"), original_html)

            clean = subprocess.run(
                [sys.executable, str(script), "--check"],
                cwd=str(post_dir),
                capture_output=True,
                text=True,
            )
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)

    def test_migrated_posts_use_colocated_assets_and_remove_old_static_dirs(self):
        for slug in MIGRATED_POSTS:
            with self.subTest(slug=slug):
                html_path = ROOT / "posts" / slug / "index.html"
                text = html_path.read_text(encoding="utf-8")
                self.assertNotIn("/static/", text)
                extractor = LinkExtractor(text)
                prefix = f"/posts/{slug}/"
                colocated = [url for url in extractor.urls if url.startswith(prefix) and not url.endswith("/")]
                self.assertTrue(colocated, f"{slug}: expected colocated asset links under {prefix}")
                for url in colocated:
                    rel = url.lstrip("/")
                    self.assertTrue((ROOT / rel).is_file(), f"missing colocated asset: {rel}")

        for dir_name in REMOVED_STATIC_DIRS:
            with self.subTest(static_dir=dir_name):
                self.assertFalse((ROOT / "static" / dir_name).exists())

    def test_htaccess_301_redirects_cover_migrated_static_paths(self):
        rules = parse_301_rewrite_rules(HTACCESS.read_text(encoding="utf-8"))
        for old_path, expected_target in EXPECTED_REDIRECTS.items():
            with self.subTest(old_path=old_path):
                actual_target = resolve_redirect(rules, old_path)
                self.assertEqual(actual_target, expected_target)
                self.assertTrue((ROOT / expected_target.lstrip("/")).is_file())

        self.assertIsNone(
            resolve_redirect(rules, "/static/stewardgoods/pixel-cases/bellroy-mag-wallet.jpg")
        )


if __name__ == "__main__":
    unittest.main()
