from __future__ import annotations

import base64
import re
import struct
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from lifetxt.web_assets import HTML_PAGE


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"

BASE_SVG_NAMES = {
    "lifetxt-symbol.svg",
    "lifetxt-symbol-monochrome.svg",
    "lifetxt-logo-horizontal.svg",
    "lifetxt-app-icon.svg",
    "lifetxt-favicon.svg",
    "lifetxt-maskable-icon.svg",
}
APP_SURFACE_SVG_NAMES = {
    "lifetxt-app-icon.svg",
    "lifetxt-favicon.svg",
    "lifetxt-maskable-icon.svg",
}
EXPECTED_NOTEBOOK_PATH = (
    "M150 84H291L339 132V364C339 384 327 396 307 396H150"
    "C130 396 118 384 118 364V116C118 96 130 84 150 84Z"
)
EXPECTED_FOLD_PATH = "M291 84V116C291 126 297 132 307 132H339Z"
EXPECTED_LEAF_LEFT_PATH = (
    "M335 348C306 352 284 334 281 305C310 303 333 320 339 342"
    "C340 346 339 347 335 348Z"
)
EXPECTED_SYMBOL_BOUNDS = (118, 84, 394, 420)
EXPECTED_NOTEBOOK_BOUNDS = (118, 84, 339, 396)
A4_HEIGHT_WIDTH_RATIO = 297 / 210
GRAPHITE = "#27343D"
WHITE = "#FFFFFF"
FOLD_MIST = "#C8D7D9"


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"{path} is not a PNG")
    return struct.unpack(">II", data[16:24])


def _ico_sizes(path: Path) -> set[tuple[int, int]]:
    data = path.read_bytes()
    reserved, image_type, count = struct.unpack("<HHH", data[:6])
    if (reserved, image_type) != (0, 1):
        raise AssertionError(f"{path} is not an ICO")
    sizes: set[tuple[int, int]] = set()
    for index in range(count):
        offset = 6 + index * 16
        width, height = data[offset], data[offset + 1]
        sizes.add((256 if width == 0 else width, 256 if height == 0 else height))
    return sizes


def _geometry_parts(path: Path) -> dict[str, tuple[str, tuple[tuple[str, str], ...]]]:
    root = ET.parse(path).getroot()
    parts: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {}
    for element in root.iter():
        name = element.attrib.get("data-lifetxt-part")
        if not name:
            continue
        geometry = tuple(
            sorted(
                (key, value)
                for key, value in element.attrib.items()
                if key
                not in {
                    "data-lifetxt-part",
                    "fill",
                    "color",
                    "opacity",
                    "mask",
                }
            )
        )
        parts[name] = (element.tag.rsplit("}", 1)[-1], geometry)
    return parts


def _part(root: ET.Element, name: str) -> ET.Element:
    for element in root.iter():
        if element.attrib.get("data-lifetxt-part") == name:
            return element
    raise AssertionError(f"missing data-lifetxt-part={name!r}")


class BrandAssetTests(unittest.TestCase):
    def test_canonical_svg_assets_are_valid(self) -> None:
        for name in BASE_SVG_NAMES:
            with self.subTest(name=name):
                root = ET.parse(BRAND / name).getroot()
                self.assertTrue(root.tag.endswith("svg"))
                expected_viewbox = (
                    "0 0 920 240"
                    if name == "lifetxt-logo-horizontal.svg"
                    else "0 0 512 512"
                )
                self.assertEqual(root.attrib.get("viewBox"), expected_viewbox)
                self.assertEqual(root.attrib.get("data-lifetxt-geometry"), "v3")

    def test_all_variants_reuse_the_same_base_geometry(self) -> None:
        reference = _geometry_parts(BRAND / "lifetxt-symbol.svg")
        self.assertEqual(reference["notebook"][1], (("d", EXPECTED_NOTEBOOK_PATH),))
        self.assertEqual(reference["fold"][1], (("d", EXPECTED_FOLD_PATH),))
        self.assertEqual(reference["leaf-left"][1], (("d", EXPECTED_LEAF_LEFT_PATH),))
        for name in BASE_SVG_NAMES - {"lifetxt-symbol.svg"}:
            with self.subTest(name=name):
                self.assertEqual(_geometry_parts(BRAND / name), reference)

    def test_geometry_contract_is_centered_a4_proportioned_and_safe(self) -> None:
        sx0, sy0, sx1, sy1 = EXPECTED_SYMBOL_BOUNDS
        nx0, ny0, nx1, ny1 = EXPECTED_NOTEBOOK_BOUNDS
        self.assertEqual((sx0 + sx1) / 2, 256)
        self.assertLess(abs((sy0 + sy1) / 2 - 256), 8)
        ratio = (ny1 - ny0) / (nx1 - nx0)
        self.assertAlmostEqual(ratio, A4_HEIGHT_WIDTH_RATIO, delta=0.01)
        self.assertGreaterEqual(min(sx0, sy0, 512 - sx1, 512 - sy1), 84)

    def test_sprout_overlaps_notebook_with_negative_space_separator(self) -> None:
        notebook_right = EXPECTED_NOTEBOOK_BOUNDS[2]
        leaf_left_min_x = 281
        self.assertLess(leaf_left_min_x, notebook_right - 40)
        for name in BASE_SVG_NAMES:
            with self.subTest(name=name):
                root = ET.parse(BRAND / name).getroot()
                separator_paths = [
                    element
                    for element in root.iter()
                    if element.tag.endswith("path")
                    and element.attrib.get("stroke-width") == "12"
                    and "data-lifetxt-part" not in element.attrib
                ]
                self.assertGreaterEqual(len(separator_paths), 3)

    def test_app_surface_fold_contrasts_with_tile_and_page(self) -> None:
        for name in APP_SURFACE_SVG_NAMES:
            with self.subTest(name=name):
                root = ET.parse(BRAND / name).getroot()
                fold = _part(root, "fold")
                self.assertEqual(fold.attrib.get("fill"), FOLD_MIST)
                self.assertNotEqual(fold.attrib.get("fill"), GRAPHITE)
                self.assertNotEqual(fold.attrib.get("fill"), WHITE)
        self.assertIn(FOLD_MIST, HTML_PAGE)

    def test_base_geometry_uses_fills_not_fragile_strokes(self) -> None:
        for name in BASE_SVG_NAMES:
            with self.subTest(name=name):
                root = ET.parse(BRAND / name).getroot()
                for element in root.iter():
                    if element.attrib.get("data-lifetxt-part"):
                        self.assertNotIn("stroke", element.attrib)
                        self.assertNotIn("stroke-width", element.attrib)

    def test_raster_derivatives_have_expected_dimensions(self) -> None:
        expected = {
            "lifetxt-app-icon-1024.png": (1024, 1024),
            "favicon-32.png": (32, 32),
            "apple-touch-icon-180.png": (180, 180),
            "pwa-icon-192.png": (192, 192),
            "pwa-icon-512.png": (512, 512),
            "pwa-maskable-512.png": (512, 512),
            "desktop/src-tauri/icons/icon.png": (512, 512),
        }
        for relative, size in expected.items():
            path = ROOT / relative if "/" in relative else BRAND / relative
            with self.subTest(path=relative):
                self.assertEqual(_png_size(path), size)

    def test_desktop_ico_contains_standard_sizes(self) -> None:
        sizes = _ico_sizes(ROOT / "desktop" / "src-tauri" / "icons" / "icon.ico")
        self.assertTrue({(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes)

    def test_desktop_png_matches_canonical_512_derivative(self) -> None:
        desktop = ROOT / "desktop" / "src-tauri" / "icons" / "icon.png"
        self.assertEqual(desktop.read_bytes(), (BRAND / "pwa-icon-512.png").read_bytes())

    def test_web_embeds_canonical_favicon_and_base_geometry(self) -> None:
        self.assertIn('data-lifetxt-brand="favicon"', HTML_PAGE)
        self.assertIn('data-lifetxt-brand="mark"', HTML_PAGE)
        self.assertIn('data-lifetxt-geometry="v3"', HTML_PAGE)
        match = re.search(
            r'data-lifetxt-brand="favicon"[^>]+href="data:image/svg\+xml;base64,([^"]+)"',
            HTML_PAGE,
        )
        self.assertIsNotNone(match)
        embedded = base64.b64decode(match.group(1)).decode("utf-8")
        canonical = (BRAND / "lifetxt-favicon.svg").read_text(encoding="utf-8")
        self.assertEqual(embedded, canonical)


if __name__ == "__main__":
    unittest.main()
