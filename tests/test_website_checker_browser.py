"""Opt-in real product-checker smoke. Missing prerequisites never establish a pass."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

from scripts.build_website_checker import ROOT, build


class WebsiteCheckerBrowserTests(unittest.TestCase):
    def test_focused_chromium(self):
        required = os.environ.get("LIFETXT_REQUIRE_WEBSITE_CHECKER") == "1"
        executable = Path(os.environ.get("LIFETXT_BROWSER_BIN", "/missing-chromium"))
        available = (
            executable.is_file()
            and importlib.util.find_spec("playwright") is not None
            and (
                ROOT / "contrib/browser_check_poc/node_modules/pyodide/pyodide.asm.wasm"
            ).is_file()
        )
        if not available:
            if required:
                self.fail(
                    "Product checker requires pinned runtime, Playwright and LIFETXT_BROWSER_BIN"
                )
            self.skipTest(
                "Product checker browser not requested/available; no acceptance inferred"
            )
        from scripts.probe_website_checker import run

        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            build(site)
            result = run(site, executable, Path(directory) / "evidence.json")
            self.assertEqual(result["acceptance"], "passed_focused_only")
