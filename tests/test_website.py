"""Public-site artifact and link safety acceptance checks for #1351."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.build_website import BRAND, ROOT, build
from scripts.check_website import Document, check


class WebsiteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "lifetxt"
        build(self.output)

    def test_complete_project_site_reuses_brand_and_accepted_example(self):
        self.assertEqual(check(self.output), [])
        for name in BRAND:
            self.assertEqual(
                (self.output / "assets" / name).read_bytes(),
                (ROOT / "assets/brand" / name).read_bytes(),
            )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "lifetxt",
                "check",
                str(self.output / "example.txt"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # The upload tree never contains configuration, source copy, or real records.
        self.assertFalse(
            any(p.suffix in (".py", ".json", ".md") for p in self.output.rglob("*"))
        )
        self.assertFalse((self.output / "README.md").exists())
        self.assertFalse((self.output / "content.json").exists())

    def test_english_default_preserves_language_routes_and_deep_switches(self):
        base = "https://eruhitsuji.github.io/lifetxt/"
        root = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertEqual(Document(root).lang, "en")
        self.assertIn('<h1 id="page-title">Your life record. In your hands.</h1>', root)
        self.assertIn(f'<meta property="og:url" content="{base}">', root)
        self.assertIn('href="./ja/" lang="ja" hreflang="ja"', root)
        self.assertIn('href="en/get-started.html"', root)
        self.assertIn('href="en/" aria-current="page"', root)
        self.assertEqual(Document(root).canonical, [base])
        for lang, other in (("ja", "en"), ("en", "ja")):
            home = Document((self.output / lang / "index.html").read_text())
            self.assertEqual(home.lang, lang)
            self.assertEqual(home.canonical, [base + lang + "/"])
            self.assertEqual(home.alternates["x-default"], base)
            deep = (self.output / lang / "features.html").read_text()
            self.assertIn(f'href="../{other}/features.html" lang="{other}"', deep)
            self.assertEqual(
                Document(deep).alternates["x-default"], base + "en/features.html"
            )
        self.assertEqual(check(self.output), [])

    def test_wrong_default_or_localized_language_is_reported(self):
        for relative, before, after in (
            ("index.html", "en", "ja"),
            ("en/features.html", "en", "ja"),
            ("ja/features.html", "ja", "en"),
        ):
            with self.subTest(relative=relative):
                file = self.output / relative
                original = file.read_text()
                file.write_text(
                    original.replace(
                        f'<html lang="{before}">', f'<html lang="{after}">'
                    )
                )
                self.assertIn(f"{relative}: wrong page language", check(self.output))
                file.write_text(original)

    def test_broken_link_fragment_and_unsafe_content_are_reported(self):
        file = self.output / "ja/index.html"
        file.write_text(
            file.read_text(encoding="utf-8")
            + '<a href="missing.html">missing</a><a href="#missing">fragment</a>'
            + '<script src="https://example.com/tracker.js"></script>'
            + '<img src="../assets/lifetxt-symbol.svg">',
            encoding="utf-8",
        )
        errors = "\n".join(check(self.output))
        for expected in (
            "missing link",
            "missing fragment",
            "forbidden active",
            "missing alt",
        ):
            self.assertIn(expected, errors)

    def test_wrong_project_path_language_or_metadata_is_reported(self):
        file = self.output / "en/features.html"
        file.write_text(
            file.read_text(encoding="utf-8")
            .replace('href="../style.css"', 'href="/style.css"')
            .replace('hreflang="ja"', 'hreflang="de"')
            .replace('rel="canonical"', 'rel="wrong"'),
            encoding="utf-8",
        )
        errors = "\n".join(check(self.output))
        for expected in (
            "escapes project prefix",
            "wrong canonical",
            "wrong language alternates",
        ):
            self.assertIn(expected, errors)

    def test_future_domain_and_nested_path(self):
        for base in ("https://example.com/", "https://example.com/a/b/"):
            with self.subTest(base=base), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "site"
                build(output, base)
                self.assertEqual(check(output, base), [])

    def test_build_never_overwrites_or_writes_into_sources(self):
        sentinel = self.output / "sentinel"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            build(self.output)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        for path in (ROOT / "website/output", ROOT / "assets/output"):
            with self.assertRaises(ValueError):
                build(path)
        for base in (
            "http://example.com/",
            "https://example.com/?x=1",
            "https://user:secret@example.com/",
        ):
            with self.subTest(base=base), self.assertRaises(ValueError):
                build(Path(self.directory.name) / "bad", base)
