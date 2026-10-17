"""Offline status regressions plus explicitly opted-in real engine checks."""

from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from contrib.browser_check_poc.engine_matrix import check_engine, matrix_passed


class BrowserEngineStatusTests(unittest.TestCase):
    def test_blocked_failed_empty_incomplete_and_mismatch_never_pass(self):
        good = {
            "engine": "firefox",
            "status": "passed",
            "cases": [{"match": True}] * 16,
        }
        self.assertTrue(matrix_passed({"engines": [good]}, ["firefox"]))
        for result in (
            [],
            [{**good, "status": "blocked"}],
            [{**good, "status": "failed"}],
            [{**good, "cases": []}],
            [{**good, "cases": [{"match": False}] * 16}],
        ):
            self.assertFalse(matrix_passed({"engines": result}, ["firefox"]))
        self.assertFalse(matrix_passed({"engines": [good]}, ["firefox", "webkit"]))
        self.assertFalse(matrix_passed({"engines": []}, []))

    def test_launch_page_and_acceptance_failure_remain_distinct(self):
        class DriverError(Exception):
            pass

        driver = SimpleNamespace(Error=DriverError, expect=Mock())
        pw = SimpleNamespace(firefox=Mock())
        pw.firefox.launch.side_effect = DriverError("Missing libgtk-4.so.1")
        result = check_engine(pw, "firefox", "http://127.0.0.1/", [], driver)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["missing_libraries"], ["libgtk-4.so.1"])
        for page_created in (False, True):
            browser = Mock(version="test-only")
            if page_created:
                browser.new_context.return_value.new_page.return_value.goto.side_effect = DriverError(
                    "acceptance failure"
                )
            else:
                browser.new_context.return_value.new_page.side_effect = DriverError(
                    "page unavailable"
                )
            pw.firefox.launch.side_effect = None
            pw.firefox.launch.return_value = browser
            with redirect_stderr(io.StringIO()):
                result = check_engine(pw, "firefox", "http://127.0.0.1/", [], driver)
            self.assertEqual(result["status"], "failed" if page_created else "blocked")
            browser.close.assert_called_once()

    def test_opt_in_real_engines(self):
        selected = os.environ.get("LIFETXT_BROWSER_ENGINES", "")
        required = os.environ.get("LIFETXT_REQUIRE_BROWSER_ENGINES") == "1"
        if not selected:
            if required:
                self.fail("Set LIFETXT_BROWSER_ENGINES=firefox,webkit")
            self.skipTest("Real Firefox/WebKit checks require explicit engine opt-in")
        engines = selected.split(",")
        try:
            from contrib.browser_check_poc.engine_matrix import run
            from contrib.browser_check_poc.build import SOURCE, build
            import playwright.sync_api  # noqa: F401
        except ImportError:
            if required:
                self.fail("Install optional Playwright and selected browsers")
            self.skipTest("Optional Playwright unavailable")
        if not (SOURCE / "node_modules/pyodide/package.json").is_file():
            if required:
                self.fail("Install pinned PoC runtime with npm ci")
            self.skipTest("Optional PoC runtime unavailable")
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            build(site)
            result = run(site, engines, Path(directory) / "evidence.json")
            self.assertTrue(matrix_passed(result, engines), result["engines"])
