"""Browser regression for content-sized Kiosk rows (#1455)."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(
    shutil.which("node") and os.path.isfile(os.environ.get("LIFETXT_BROWSER_BIN", "")),
    "Node and LIFETXT_BROWSER_BIN required",
)
class KioskLayoutTests(unittest.TestCase):
    def test_long_cards_fit_and_last_row_is_reachable(self):
        with tempfile.TemporaryDirectory() as directory:
            html = Path(directory) / "page.html"
            html.write_text(HTML_PAGE, encoding="utf-8")
            result = subprocess.run(
                [
                    "node",
                    str(Path(__file__).with_name("browser_kiosk_layout_probe.mjs")),
                    os.environ["LIFETXT_BROWSER_BIN"],
                    str(html),
                ],
                capture_output=True,
                text=True,
                timeout=90,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(24, len(json.loads(result.stdout)["viewports"]))
