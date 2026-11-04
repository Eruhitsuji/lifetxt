"""Kiosk surface colors follow the shared theme (#1518)."""

import re
import unittest

from lifetxt.web_assets import HTML_PAGE


def contrast(a, b):
    def luminance(color):
        channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [
            c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            for c in channels
        ]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    values = sorted((luminance(a), luminance(b)))
    return (values[1] + 0.05) / (values[0] + 0.05)


class KioskThemeTests(unittest.TestCase):
    def test_kiosk_uses_theme_surfaces_and_readable_text(self):
        for selector, expected in (
            (".kiosk-mode", ("background: var(--bg)", "color: var(--ink)")),
            (".kiosk-mode .item", ("background: var(--panel)", "var(--line-strong)")),
            (".kiosk-mode .item .title", ("color: var(--ink)",)),
            (".kiosk-mode .item .meta", ("color: var(--muted)",)),
        ):
            rule = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", HTML_PAGE).group(
                1
            )
            for declaration in expected:
                self.assertIn(declaration, rule)
        for selector in (
            ":root",
            '[data-theme="dark"]',
            '[data-contrast="high"]',
            '[data-contrast="high"][data-theme="dark"]',
        ):
            rules = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", HTML_PAGE).group(
                1
            )
            base = re.search(r":root\s*\{([^}]+)\}", HTML_PAGE).group(1)
            dark = re.search(r'\[data-theme="dark"\]\s*\{([^}]+)\}', HTML_PAGE).group(1)
            values = dict(
                re.findall(
                    r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})",
                    base + (dark if "dark" in selector else "") + rules,
                )
            )
            for foreground in ("--ink", "--muted"):
                for background in ("--bg", "--panel"):
                    self.assertGreaterEqual(
                        contrast(values[foreground], values[background]),
                        4.5,
                        (selector, foreground, background),
                    )
