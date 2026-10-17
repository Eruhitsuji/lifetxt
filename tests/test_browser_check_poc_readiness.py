"""Evidence failures must stay visible; actual measurements require opt-in."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from contrib.browser_check_poc.adapter import check_text
from contrib.browser_check_poc.readiness_probe import (
    PROFILES,
    REPEATS,
    boundary_text,
    measurement_passed,
)


class BrowserReadinessTests(unittest.TestCase):
    def test_public_corpus_keeps_invalid_examples_and_accounts_for_utf8_limit(self):
        from contrib.browser_check_poc.example_corpus import collect_examples

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "valid.txt").write_text('[ ] T "Synthetic"')
            (root / "invalid.txt").write_text("invalid synthetic record")
            (root / "large.txt").write_text("あ" * 22000, encoding="utf-8")
            fixtures, excluded = collect_examples(root)
            self.assertEqual(len(fixtures), 2)
            self.assertEqual({f["expected"]["valid"] for f in fixtures}, {True, False})
            self.assertEqual([e["name"] for e in excluded], ["large.txt"])
            self.assertEqual(excluded[0]["bytes"], 66000)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                collect_examples(Path(directory))

    def test_exact_boundary_fixture_is_valid_and_next_byte_is_refused(self):
        text = boundary_text()
        self.assertEqual(len(text.encode()), 65536)
        self.assertTrue(check_text(text)["valid"])
        with self.assertRaises(ValueError):
            check_text(text + "x")

    def test_partial_blocked_or_failed_evidence_never_passes(self):
        profile = {
            "status": "passed",
            "boundary_bytes": 65536,
            "repeat_matches": REPEATS,
            "diagnostic_limit": 100,
            "diagnostics_truncated": True,
            "warm_no_http": True,
            "oversize_refused": True,
            "cancel_restart": True,
            "storage_empty": True,
            "network_bounded": True,
            "ax_semantics": True,
        }
        good = {
            "status": "passed",
            "physical_device": False,
            "profiles": [{**profile, "name": p[0]} for p in PROFILES],
        }
        self.assertTrue(measurement_passed(good))
        for status in ("blocked", "failed", "not tested"):
            broken = copy.deepcopy(good)
            broken["status"] = status
            self.assertFalse(measurement_passed(broken))
        for key in profile:
            broken = copy.deepcopy(good)
            del broken["profiles"][0][key]
            self.assertFalse(measurement_passed(broken), key)
        for profiles in ([], good["profiles"][:1], good["profiles"][::-1]):
            self.assertFalse(measurement_passed({**good, "profiles": profiles}))
        self.assertFalse(measurement_passed({**good, "physical_device": True}))

    def test_optional_actual_measurements(self):
        required = os.environ.get("LIFETXT_REQUIRE_READINESS") == "1"
        if os.environ.get("LIFETXT_RUN_READINESS") != "1":
            if required:
                self.fail("Set LIFETXT_RUN_READINESS=1")
            self.skipTest("Explicit opt-in needed for paced browser measurements")
        from contrib.browser_check_poc.build import SOURCE, build

        executable = os.environ.get("LIFETXT_BROWSER_BIN", "")
        try:
            import playwright.sync_api  # noqa: F401

            available = (
                Path(executable).is_file()
                and (SOURCE / "node_modules/pyodide/package.json").is_file()
            )
        except ImportError:
            available = False
        if not available:
            if required:
                self.fail(
                    "Install optional Playwright, Chromium and pinned PoC runtime"
                )
            self.skipTest("Optional browser/runtime tooling unavailable")
        from contrib.browser_check_poc.readiness_probe import run

        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            output = Path(directory) / "evidence.json"
            build(site)
            result = run(site, Path(executable), output)
            self.assertTrue(measurement_passed(result), result)
            self.assertEqual(json.loads(output.read_text()), result)
