"""Protect the packaged Web UI assembly and runtime rebinding contract."""

from __future__ import unicode_literals

import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from importlib import resources

from lifetxt import web_assets, webapp


REVISION_BRIDGE_MARKER = "lifetxt-revision-contract-v1"
LEGACY_PRISTINE_GIT_BLOB_SHA = "032369997c5e2ccf0bd40b4a33dfcc1d13555d5c"
WEBAPP_SOURCE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lifetxt", "webapp.py"
)


def _git_blob_sha(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


class WebAssetExtractionTests(unittest.TestCase):
    def test_asset_module_holds_the_page(self):
        self.assertTrue(web_assets.HTML_PAGE.startswith("<!doctype html>"))
        self.assertTrue(web_assets.HTML_PAGE.endswith("</html>"))
        self.assertIn("/api/temporal-thread/", web_assets.HTML_PAGE)
        self.assertIn("consistencyWarnings", web_assets.HTML_PAGE)

    def test_split_resources_assemble_the_legacy_pristine_page(self):
        package = resources.files("lifetxt")
        template = package.joinpath("web_assets.html").read_text(encoding="utf-8")
        self.assertEqual(template.count(web_assets._STYLE_MARKER), 1)
        self.assertEqual(template.count(web_assets._SCRIPT_MARKER), 1)

        styles = "".join(
            package.joinpath(name).read_text(encoding="utf-8")
            for name in web_assets._CSS_RESOURCE_NAMES
        )
        script = "".join(
            package.joinpath(name).read_text(encoding="utf-8")
            for name in web_assets._JS_RESOURCE_NAMES
        )
        assembled = template.replace(web_assets._STYLE_MARKER, styles).replace(
            web_assets._SCRIPT_MARKER, script
        )
        self.assertEqual(
            _git_blob_sha(assembled.encode("utf-8")),
            LEGACY_PRISTINE_GIT_BLOB_SHA,
        )
        self.assertEqual(
            web_assets.HTML_PAGE, web_assets._apply_brand_assets(assembled)
        )

    def test_packaged_fragment_resources_exist(self):
        package = resources.files("lifetxt")
        names = web_assets._CSS_RESOURCE_NAMES + web_assets._JS_RESOURCE_NAMES
        self.assertTrue(names)
        for name in names:
            resource = package.joinpath(name)
            self.assertTrue(resource.is_file(), name)
            self.assertTrue(resource.read_bytes(), name)

    def test_shell_no_longer_embeds_full_css_or_script(self):
        shell = (
            resources.files("lifetxt")
            .joinpath("web_assets.html")
            .read_text(encoding="utf-8")
        )
        self.assertIn(web_assets._STYLE_MARKER, shell)
        self.assertIn(web_assets._SCRIPT_MARKER, shell)
        self.assertLess(len(shell), len(web_assets.HTML_PAGE) // 2)

    def test_webapp_still_exposes_the_name(self):
        self.assertTrue(hasattr(webapp, "HTML_PAGE"))
        self.assertIn("</html>", webapp.HTML_PAGE)

    def test_surface_runtime_still_rebinds_webapp_html_page(self):
        self.assertIn(REVISION_BRIDGE_MARKER, webapp.HTML_PAGE)

    def test_asset_module_keeps_the_pristine_value(self):
        self.assertNotIn(REVISION_BRIDGE_MARKER, web_assets.HTML_PAGE)

    def test_route_serves_what_webapp_exposes(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest(
                "web extras unavailable, so the served page cannot be checked"
            )
        client = TestClient(webapp.create_app(paths=[]))
        body = client.get("/").content
        self.assertEqual(webapp.HTML_PAGE.encode("utf-8"), body)

    def test_literal_is_not_back_in_webapp(self):
        with io.open(WEBAPP_SOURCE, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn('HTML_PAGE = r"""', source)
        self.assertIn("from .web_assets import HTML_PAGE", source)

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_assembled_script_has_no_syntax_error(self):
        # Every JS fragment concatenates into one shared-scope <script>, so
        # a name collision (e.g. a `const` redeclaring an earlier `function`)
        # in any one fragment is a fatal SyntaxError for the whole page.
        # Nothing else in this suite parses the assembled script as
        # JavaScript, so this is the one guard that would catch it.
        match = re.search(r"<script>(.*)</script>", web_assets.HTML_PAGE, re.S)
        self.assertIsNotNone(match)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(match.group(1))
            script_path = handle.name
        try:
            proc = subprocess.run(
                ["node", "--check", script_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            os.unlink(script_path)
        self.assertEqual(0, proc.returncode, proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
