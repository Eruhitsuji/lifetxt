"""Installability and navigation contracts for online-only Web surfaces."""

import json
import struct
import unittest
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path

from lifetxt import web_assets, webapp


BRAND = Path(__file__).resolve().parents[1] / "assets" / "brand"


class _Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        self.elements.append((tag, dict(attributes)))


class StateInstallabilityResourceTests(unittest.TestCase):
    def test_separate_manifest_has_stable_identity_and_no_new_permissions(self):
        raw = web_assets.web_resource_bytes("state_app_manifest.json")
        manifest = json.loads(raw)
        self.assertEqual("/state", manifest["id"])
        self.assertEqual("/state", manifest["start_url"])
        self.assertEqual("/", manifest["scope"])
        self.assertEqual("standalone", manifest["display"])
        self.assertEqual("State", manifest["short_name"])
        self.assertEqual("life.txt State", manifest["name"])
        self.assertEqual("#f5f6f2", manifest["background_color"])
        planner = json.loads(web_assets.web_resource_bytes("planner_app_manifest.json"))
        self.assertEqual(planner["icons"], manifest["icons"])
        self.assertEqual(planner["theme_color"], manifest["theme_color"])
        self.assertEqual(
            {
                "id",
                "name",
                "short_name",
                "description",
                "start_url",
                "scope",
                "display",
                "background_color",
                "theme_color",
                "icons",
            },
            set(manifest),
        )
        self.assertIn(
            '"state_app_manifest.json"',
            (BRAND.parents[1] / "pyproject.toml").read_text(encoding="utf-8"),
        )

    def test_state_links_own_manifest_touch_icon_and_full_web_return(self):
        elements = _Elements(web_assets.STATE_HTML_PAGE).elements
        manifests = [
            a["href"]
            for tag, a in elements
            if tag == "link" and a.get("rel") == "manifest"
        ]
        self.assertEqual(["/state.webmanifest"], manifests)
        self.assertTrue(
            any(
                tag == "link"
                and a.get("rel") == "apple-touch-icon"
                and a.get("href") == "/assets/lifetxt-icon-180.png"
                for tag, a in elements
            )
        )
        self.assertTrue(
            any(
                tag == "meta"
                and a.get("name") == "apple-mobile-web-app-title"
                and a.get("content") == "State"
                for tag, a in elements
            )
        )
        self.assertTrue(
            any(
                tag == "a" and a.get("href") == "/" and a.get("data-i18n") == "web"
                for tag, a in elements
            )
        )
        self.assertNotIn("navigator.serviceWorker", web_assets.STATE_HTML_PAGE)
        self.assertNotIn("caches.open", web_assets.STATE_HTML_PAGE)

    def test_more_navigation_uses_links_without_replacing_status_team_tabs(self):
        html = web_assets.HTML_PAGE
        more = html.split('id="nav-advanced"', 1)[1].split("</details>", 1)[0]
        elements = _Elements(more).elements
        for route in ("/state", "/capture", "/planner"):
            links = [a for tag, a in elements if tag == "a" and a.get("href") == route]
            self.assertEqual(1, len(links), route)
            self.assertEqual("workspace-tab surface-link", links[0]["class"])
            self.assertNotIn("onclick", links[0])
            self.assertNotIn("role", links[0])
            self.assertNotIn("tabindex", links[0])
        for view in ("status", "team"):
            self.assertTrue(
                any(
                    tag == "button"
                    and a.get("data-view") == view
                    and a.get("onclick") == f"switchWorkspace('{view}')"
                    for tag, a in elements
                )
            )
        self.assertIn('data-i18n="Quick Status"', more)
        self.assertIn('<span lang="en">State</span>', more)


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

    def test_state_manifest_and_icons_keep_auth_no_store_and_other_app_identities(self):
        from fastapi.testclient import TestClient

        with TestClient(
            webapp.create_app(paths=[], config={"api": {"token": "install-test"}})
        ) as client:
            auth = {"Authorization": "Bearer install-test"}
            # The existing public root shell is intentionally exempt, not /state.
            self.assertEqual(200, client.get("/").status_code)
            for route in (
                "/capture",
                "/planner",
                "/state",
                "/state.webmanifest",
                "/assets/lifetxt-icon-180.png",
                "/assets/lifetxt-icon-192.png",
                "/assets/lifetxt-icon-512.png",
            ):
                self.assertEqual(401, client.get(route).status_code, route)
                self.assertEqual(
                    401,
                    client.get(
                        route, headers={"Authorization": "Bearer wrong"}
                    ).status_code,
                    route,
                )
                response = client.get(route, headers=auth)
                self.assertEqual(200, response.status_code, route)
                self.assertEqual("no-store", response.headers["cache-control"], route)
            response = client.get("/state.webmanifest", headers=auth)
            self.assertEqual(
                "application/manifest+json", response.headers["content-type"]
            )
            self.assertEqual(
                web_assets.web_resource_bytes("state_app_manifest.json"),
                response.content,
            )
            for route, expected in (
                ("/manifest.webmanifest", "/capture"),
                ("/planner.webmanifest", "/planner"),
                ("/state.webmanifest", "/state"),
            ):
                manifest = client.get(route, headers=auth).json()
                self.assertEqual(expected, manifest["id"])
                self.assertEqual(expected, manifest["start_url"])
                for icon in manifest["icons"]:
                    icon_response = client.get(icon["src"], headers=auth)
                    self.assertEqual(200, icon_response.status_code)
                    self.assertEqual("image/png", icon_response.headers["content-type"])
                    self.assertEqual("no-store", icon_response.headers["cache-control"])

    def test_readonly_state_still_has_install_metadata_and_menu_link(self):
        from fastapi.testclient import TestClient

        with TestClient(webapp.create_app(paths=[], read_only=True)) as client:
            self.assertEqual(200, client.get("/state.webmanifest").status_code)
            self.assertIn('href="/state.webmanifest"', client.get("/state").text)
            for route in ("/", "/capture"):
                self.assertIn('href="/state"', client.get(route).text)
            self.assertTrue(client.get("/api/health").json()["read_only"])

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
