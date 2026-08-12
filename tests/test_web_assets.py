"""The Web page asset lives outside webapp.py but still reaches the browser.

Extracting a 9,000-line literal is only safe if the two things that were true
before are still true: what `webapp` exposes is the bridged page, and what the
route serves is that same value. Neither was covered by a test before #82, so a
broken extraction would have shown up as a working suite and a browser that
silently stopped sending `If-Match`.
"""

from __future__ import unicode_literals

import io
import os
import unittest
from importlib import resources

from lifetxt import web_assets, webapp


REVISION_BRIDGE_MARKER = "lifetxt-revision-contract-v1"
WEBAPP_SOURCE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lifetxt", "webapp.py"
)


class WebAssetExtractionTests(unittest.TestCase):
    def test_asset_module_holds_the_page(self):
        self.assertTrue(web_assets.HTML_PAGE.startswith("<!doctype html>"))
        self.assertIn("</html>", web_assets.HTML_PAGE)

    def test_webapp_still_exposes_the_name(self):
        """Ten call sites read `webapp.HTML_PAGE`; the re-export must hold."""
        self.assertTrue(hasattr(webapp, "HTML_PAGE"))
        self.assertIn("</html>", webapp.HTML_PAGE)

    def test_surface_runtime_still_rebinds_webapp_html_page(self):
        """`surface_runtime` replaces `webapp.HTML_PAGE` to add the revision bridge.

        The rebinding targets the module attribute, so an extraction that made
        the name a re-export of an immutable constant elsewhere, or that moved
        the read to the asset module, would drop the bridge without failing.
        """
        self.assertIn(REVISION_BRIDGE_MARKER, webapp.HTML_PAGE)

    def test_asset_module_keeps_the_pristine_value(self):
        """The bridge is applied to what `webapp` exposes, not to the source."""
        self.assertNotIn(REVISION_BRIDGE_MARKER, web_assets.HTML_PAGE)

    def test_packaged_resource_matches_pristine_value(self):
        resource = resources.files("lifetxt").joinpath("web_assets.html")
        self.assertEqual(web_assets.HTML_PAGE.encode("utf-8"), resource.read_bytes())

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
        """Guard against re-inlining, which is the failure this slice undoes."""
        with io.open(WEBAPP_SOURCE, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn('HTML_PAGE = r"""', source)
        self.assertIn("from .web_assets import HTML_PAGE", source)


if __name__ == "__main__":
    unittest.main()
