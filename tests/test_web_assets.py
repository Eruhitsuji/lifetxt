"""Protect the packaged Web UI assembly and runtime rebinding contract."""

from __future__ import unicode_literals

import hashlib
import io
import os
import unittest
from importlib import resources

from lifetxt import web_assets, webapp


REVISION_BRIDGE_MARKER = "lifetxt-revision-contract-v1"
LEGACY_PRISTINE_GIT_BLOB_SHA = "9da1d4c4123b011e983ecf1f623d841b967bd9d4"
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


if __name__ == "__main__":
    unittest.main()
