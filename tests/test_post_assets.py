"""Tests for colocated post assets, chart data generation, and static redirects."""

from html.parser import HTMLParser
import json
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

MANIFEST = ROOT / "posts.json"
MIGRATED_POSTS = (
    "tigris-and-euphrates-scoring-rule",
    "on-sexuality-and-criminality",
    "why-anti-cyrillic-croats-attack-serbian-language",
    "finding-greener-alternatives-to-ap-chromatography-lab",
    "a-field-guide-to-interior-design-styles",
    "best-2-player-android-games",
    "pixel-10-pro-xl-case-choices",
    "mentor-collage",
    "two-person-agile-product-development-flowchart",
    "mailer-for-agnes-irwin-future-owl-fly-by",
    "let-it-grow-banner",
    "custom-content-management-system",
    "converting-my-book-of-the-churchs-year-into-a-coloring-book",
    "updating-biomass-controls-website",
    "e-commerce-site-for-kims-creations",
    "brandywine-oak-private-wealths-dynamic-content",
    "website-for-rose-river-way-studio",
    "montgomery-school-map",
    "corsage-removal-with-photoshop",
    "comptia-a-it-technician-certification",
)

SOCIAL_META_POSTS = (
    "a-field-guide-to-interior-design-styles",
    "best-2-player-android-games",
    "pixel-10-pro-xl-case-choices",
    "mentor-collage",
)

SITE_ORIGIN = "https://jacobstephens.net"

REMOVED_STATIC_DIRS = (
    "tigris-and-euphrates",
    "stewardgoods",
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

STEWARDGOODS_MIGRATED_ASSETS = {
    "a-field-guide-to-interior-design-styles": (
        "interior-design-styles/art-deco.jpg",
        "interior-design-styles/art-nouveau.jpg",
        "interior-design-styles/arts-and-crafts.jpg",
        "interior-design-styles/bohemian.jpg",
        "interior-design-styles/boho-mountain.jpg",
        "interior-design-styles/british-colonial.jpg",
        "interior-design-styles/brutalist.jpg",
        "interior-design-styles/coastal.jpg",
        "interior-design-styles/contemporary.jpg",
        "interior-design-styles/cottage.jpg",
        "interior-design-styles/eclectic.jpg",
        "interior-design-styles/english-country.jpg",
        "interior-design-styles/french-baroque.jpg",
        "interior-design-styles/french-country.jpg",
        "interior-design-styles/hollywood-glam.jpg",
        "interior-design-styles/industrial.jpg",
        "interior-design-styles/international.jpg",
        "interior-design-styles/japandi.jpg",
        "interior-design-styles/maximalist.jpg",
        "interior-design-styles/mediterranean.jpg",
        "interior-design-styles/mid-century-modern.jpg",
        "interior-design-styles/minimalist.jpg",
        "interior-design-styles/modern-farmhouse.jpg",
        "interior-design-styles/modern.jpg",
        "interior-design-styles/organic-modern.jpg",
        "interior-design-styles/rustic.jpg",
        "interior-design-styles/scandinavian.jpg",
        "interior-design-styles/shabby-chic.jpg",
        "interior-design-styles/southwest.jpg",
        "interior-design-styles/traditional.jpg",
        "interior-design-styles/transitional.jpg",
        "interior-design-styles/tuscan.jpg",
        "interior-design-styles/victorian.jpg",
    ),
    "best-2-player-android-games": (
        "best-2-player-android-games.jpg",
        "two-player-android-games/bombsquad.jpg",
        "two-player-android-games/bounden.jpg",
        "two-player-android-games/dual.jpg",
        "two-player-android-games/duel-otters.jpg",
        "two-player-android-games/jaipur.jpg",
        "two-player-android-games/keep-talking.jpg",
        "two-player-android-games/polytopia.jpg",
        "two-player-android-games/seven-wonders-duel-tldr.jpg",
        "two-player-android-games/seven-wonders-duel.jpg",
        "two-player-android-games/spaceteam-screenshot.png",
        "two-player-android-games/star-realms.jpg",
        "two-player-android-games/the-past-within.jpg",
        "two-player-android-games/tick-tock.jpg",
    ),
    "pixel-10-pro-xl-case-choices": (
        "pixel-10-pro-xl-case-choices.png",
        "pixel-cases/bellroy-mag-wallet.jpg",
        "pixel-cases/casebus-harper-purple-1.jpg",
        "pixel-cases/casebus-harper-purple-2.jpg",
        "pixel-cases/casebus-harper-purple-3.jpg",
        "pixel-cases/google-pixelsnap-case-jade.jpg",
        "pixel-cases/google-pixelsnap-case-lineup.jpg",
        "pixel-cases/google-pixelsnap-case-moonstone.jpg",
        "pixel-cases/google-pixelsnap-case-obsidian.jpg",
        "pixel-cases/google-pixelsnap-case-porcelain.jpg",
        "pixel-cases/snakehive-metro-wallet-black.jpg",
        "pixel-cases/snakehive-metro-wallet.jpg",
        "pixel-cases/torro-pixel-10-pro-xl-wallet.jpg",
    ),
    "mentor-collage": ("mentor-collage.jpg",),
    "two-person-agile-product-development-flowchart": (
        "ProductDevelopmentFlowchart-TwoPerson-v1.pdf",
        "agile-flowchart-highres.png",
    ),
    "mailer-for-agnes-irwin-future-owl-fly-by": ("agnes-irwin-mailer.jpg",),
    "let-it-grow-banner": ("let-it-grow-banner.jpg",),
    "custom-content-management-system": ("artifact-management-tool.png",),
    "converting-my-book-of-the-churchs-year-into-a-coloring-book": (
        "churchs-year-coloring.jpg",
        "churchs-year-original.jpg",
    ),
    "updating-biomass-controls-website": ("biomass-homepage.png",),
    "e-commerce-site-for-kims-creations": ("kims-creations-product-page.png",),
    "brandywine-oak-private-wealths-dynamic-content": (
        "brandywine-oak-homepage-after.png",
        "brandywine-oak-homepage-before.png",
        "brandywine-oak-scroll-after.png",
        "brandywine-oak-scroll-before.png",
    ),
    "website-for-rose-river-way-studio": (
        "rose-river-way-new.png",
        "rose-river-way-old.png",
    ),
    "montgomery-school-map": ("montgomery-school-map.jpg",),
    "corsage-removal-with-photoshop": (
        "corsage-after.jpg",
        "corsage-before.jpg",
    ),
    "comptia-a-it-technician-certification": ("comptia-a-plus.png",),
}
for _slug, _assets in STEWARDGOODS_MIGRATED_ASSETS.items():
    for _rel in _assets:
        EXPECTED_REDIRECTS[f"/static/stewardgoods/{_rel}"] = f"/posts/{_slug}/{Path(_rel).name}"

REMOVED_UNREFERENCED_STEWARDGOODS = (
    "/static/stewardgoods/CertificateOfCompletion_Become-a-DevOps-Engineer.pdf",
    "/static/stewardgoods/JacobStephens-CompTIA-A-plus-certificate.pdf",
    "/static/stewardgoods/agile-flowchart.jpg",
    "/static/stewardgoods/pixel-cases/casebus-harper-1.jpg",
    "/static/stewardgoods/pixel-cases/casebus-harper-2.jpg",
    "/static/stewardgoods/pixel-cases/casebus-harper-3.jpg",
    "/static/stewardgoods/pixel-cases/casebus-harper-4.jpg",
    "/static/stewardgoods/pixel-cases/casebus-harper-5.jpg",
    "/static/stewardgoods/pixel-cases/google-pixelsnap-case.jpg",
    "/static/stewardgoods/pixel-cases/snakehive-metro-wallet-black-open.jpg",
)


class LinkExtractor(HTMLParser):
    """Collect asset src/href URLs and social image meta URLs from authored HTML."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.urls = []
        self.social_images = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        for name, value in attrs:
            if name in ("src", "href") and value:
                self.urls.append(value)
        if tag == "meta":
            key = (attr_map.get("property") or attr_map.get("name") or "").lower()
            content = attr_map.get("content")
            if key in ("og:image", "twitter:image") and content:
                self.social_images.append(content)


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
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for post in manifest["posts"]:
            slug = post["slug"]
            with self.subTest(registered_slug=slug):
                html_path = ROOT / "posts" / slug / "index.html"
                self.assertNotIn("/static/", html_path.read_text(encoding="utf-8"))

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

                if slug in SOCIAL_META_POSTS:
                    self.assertEqual(len(extractor.social_images), 2, f"{slug}: expected og:image and twitter:image")
                expected_meta_prefix = f"{SITE_ORIGIN}{prefix}"
                for meta_url in extractor.social_images:
                    self.assertTrue(
                        meta_url.startswith(expected_meta_prefix),
                        f"{slug}: social image {meta_url!r} must start with {expected_meta_prefix!r}",
                    )
                    rel = meta_url.removeprefix(f"{SITE_ORIGIN}/")
                    self.assertTrue((ROOT / rel).is_file(), f"missing social image asset: {rel}")

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

        for old_path in REMOVED_UNREFERENCED_STEWARDGOODS:
            with self.subTest(unreferenced_path=old_path):
                self.assertIsNone(resolve_redirect(rules, old_path))


if __name__ == "__main__":
    unittest.main()
