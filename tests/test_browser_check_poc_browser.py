"""Optional real-browser PoC acceptance (#1360), separate from fake DOM tests."""

import json
import os
from pathlib import Path
import tempfile
import unittest


class BrowserCheckRealBrowserTests(unittest.TestCase):
    def test_real_http_worker_privacy_and_failure_matrix(self):
        from contrib.browser_check_poc.build import SOURCE, build

        required = os.environ.get("LIFETXT_REQUIRE_BROWSER_CHECK") == "1"
        missing = None
        if not (SOURCE / "node_modules/pyodide/package.json").is_file():
            missing = "Run npm ci in the isolated PoC to install the pinned runtime"
        executable = os.environ.get("LIFETXT_BROWSER_BIN")
        if not executable or not Path(executable).is_file():
            missing = "Set LIFETXT_BROWSER_BIN to a local Chromium executable"
        try:
            import playwright.sync_api  # noqa: F401
        except ImportError:
            missing = "Optional Playwright unavailable"
        if missing:
            if required:
                self.fail(missing)
            self.skipTest(missing)
        from contrib.browser_check_poc.browser_probe import run

        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            result = Path(directory) / "evidence.json"
            build(site)
            run(site, Path(executable), result)
            evidence = json.loads(result.read_text())
            self.assertTrue(all(c["match"] for c in evidence["cases"]))
            self.assertEqual(len(evidence["cases"]), 16)
            self.assertTrue(evidence["offline_warm_check"])
            self.assertTrue(evidence["csp_inline_script_blocked"])
