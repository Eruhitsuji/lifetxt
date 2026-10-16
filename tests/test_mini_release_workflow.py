"""Regression: Mini's old publisher cannot bypass the central approval gate."""

import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class MiniReleaseWorkflowTests(unittest.TestCase):
    def test_old_tag_and_manual_publisher_is_retired(self):
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/lifetxt-mini-release.yml").read_text()
        )
        self.assertEqual({"workflow_call"}, set(workflow[True]))
        self.assertEqual({"contents": "read"}, workflow["permissions"])
        result = subprocess.run(
            ["bash", "-c", workflow["jobs"]["retired"]["steps"][0]["run"]],
            capture_output=True,
            timeout=5,
        )
        self.assertNotEqual(0, result.returncode)

    def test_mini_preflight_retains_native_and_conformance_checks(self):
        text = (ROOT / ".github/workflows/release-preflight-mini.yml").read_text()
        self.assertIn("release_preflight_mini.py build", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("gh release", text)
