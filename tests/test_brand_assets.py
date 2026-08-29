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


class BrandAssetTests(unittest.TestCase):
    def test_canonical_svg_assets_are_valid(self) -> None:
        names = {
            "lifetxt-symbol.svg",
            "lifetxt-symbol-monochrome.svg",
            "lifetxt-logo-horizontal.svg",
            "lifetxt-app-icon.svg",
            "lifetxt-favicon.svg",
        }
        for name in names:
            with self.subTest(name=name):
                root = ET.parse(BRAND / name).getroot()
                self.assertTrue(root.tag.endswith("svg"))
                self.assertIn("viewBox", root.attrib)

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

    def test_web_embeds_canonical_favicon_and_brand_mark(self) -> None:
        self.assertIn('data-lifetxt-brand="favicon"', HTML_PAGE)
        self.assertIn('data-lifetxt-brand="mark"', HTML_PAGE)
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
