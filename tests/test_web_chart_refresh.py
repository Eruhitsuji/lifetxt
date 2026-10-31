"""Canonical chart identity survives translated labels (#1497)."""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class ChartRefreshTests(unittest.TestCase):
    def test_selected_type_group_redraw_and_errors_survive_translation(self):
        result = subprocess.run(
            [
                "node",
                str(ROOT / "tests/chart_refresh_probe.mjs"),
                str(ROOT / "lifetxt/web_assets_js_13.js"),
                str(ROOT / "lifetxt/web_assets_js_14.js"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"cases": 30, "initial": "tasks"}, json.loads(result.stdout))
