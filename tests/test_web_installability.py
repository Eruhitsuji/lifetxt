"""Installability metadata coverage for the online-only Quick Capture app."""

import json
import struct
import unittest
from importlib import resources
from pathlib import Path

from lifetxt import web_assets, webapp


BRAND = Path(__file__).resolve().parents[1] / "assets" / "brand"


class WebInstallabilityResourceTests(unittest.TestCase):
    def setUp(self):
        self.package = resources.files("lifetxt")
        self.manifest = json.loads(
            self.package.joinpath("web_app_manifest.json").read_text(encoding="utf-8")
        )

    def test_manifest_launches_capture_as_a_scoped_standalone_app(self):
        self.assertEqual("/capture", self.manifest["id"])
        self.assertEqual("/capture", self.manifest["start_url"])
        self.assertEqual("/", self.manifest["scope"])
        self.assertEqual("standalone", self.manifest["display"])
        self.assertEqual("#27343d", self.manifest["theme_color"])
        self.assertEqual("#f4f7f5", self.manifest["background_color"])

    def test_manifest_icons_are_packaged_pngs_with_declared_dimensions(self):
        icons = {icon["sizes"]: icon for icon in self.manifest["icons"]}
        self.assertEqual({"192x192", "512x512"}, set(icons))
        for dimensions, icon in icons.items():
            size = int(dimensions.split("x", 1)[0])
            data = self.package.joinpath("web_icon_%d.png" % size).read_bytes()
            self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])
            self.assertEqual((size, size), struct.unpack(">II", data[16:24]))
            self.assertEqual("image/png", icon["type"])
            self.assertEqual("any", icon["purpose"])

        touch_icon = self.package.joinpath("web_icon_180.png").read_bytes()
        self.assertEqual((180, 180), struct.unpack(">II", touch_icon[16:24]))

    def test_brand_svg_is_the_existing_favicon_source(self):
        svg = self.package.joinpath("web_icon.svg").read_text(encoding="utf-8")
        self.assertEqual(svg, web_assets._BRAND_FAVICON_SVG)
        self.assertEqual(
            svg, (BRAND / "lifetxt-favicon.svg").read_text(encoding="utf-8")
        )
        self.assertIn('data-lifetxt-geometry="v3"', svg)

    def test_packaged_icons_reuse_canonical_brand_derivatives(self):
        for packaged, canonical in (
            ("web_icon_180.png", "apple-touch-icon-180.png"),
            ("web_icon_192.png", "pwa-icon-192.png"),
            ("web_icon_512.png", "pwa-icon-512.png"),
        ):
            self.assertEqual(
                self.package.joinpath(packaged).read_bytes(),
                (BRAND / canonical).read_bytes(),
            )


class WebInstallabilityRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise unittest.SkipTest("web extras unavailable") from exc
        cls.client = TestClient(webapp.create_app(paths=[]))

    def test_manifest_and_every_declared_icon_are_served_without_caching(self):
        response = self.client.get("/manifest.webmanifest")
        self.assertEqual(200, response.status_code)
        self.assertEqual("application/manifest+json", response.headers["content-type"])
        self.assertEqual("no-store", response.headers["cache-control"])
        manifest = response.json()
        for icon in manifest["icons"]:
            icon_response = self.client.get(icon["src"])
            self.assertEqual(200, icon_response.status_code, icon["src"])
            self.assertEqual("image/png", icon_response.headers["content-type"])
            self.assertEqual("no-store", icon_response.headers["cache-control"])

    def test_capture_shell_links_manifest_and_ios_metadata(self):
        response = self.client.get("/capture")
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        for fragment in (
            '<meta name="theme-color" content="#27343d">',
            '<meta name="apple-mobile-web-app-capable" content="yes">',
            '<meta name="apple-mobile-web-app-title" content="life.txt">',
            '<link rel="manifest" href="/manifest.webmanifest">',
            'rel="apple-touch-icon" sizes="180x180"',
        ):
            self.assertIn(fragment, response.text)

    def test_unknown_icon_size_is_not_served(self):
        self.assertEqual(
            404, self.client.get("/assets/lifetxt-icon-256.png").status_code
        )

    def test_no_offline_worker_or_cache_is_introduced(self):
        self.assertNotIn("navigator.serviceWorker", webapp.HTML_PAGE)
        self.assertNotIn("service_worker", webapp.HTML_PAGE)


if __name__ == "__main__":
    unittest.main()
