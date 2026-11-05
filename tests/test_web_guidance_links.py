"""Theme-safe guidance links (#1526)."""

import re
import unittest
from lifetxt.web_assets import HTML_PAGE
from tests.test_web_kiosk_theme import contrast


class GuidanceLinkTests(unittest.TestCase):
    def test_guidance_links_use_theme_text_and_underlines(self):
        for selector in (
            ".personal-context-next a",
            ".personal-context-next a:visited",
            ".backup-guidance a",
            ".backup-guidance a:visited",
        ):
            rules = [
                body
                for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", HTML_PAGE)
                if selector in [s.strip() for s in selectors.split(",")]
            ]
            self.assertTrue(
                any(
                    "color: var(--ink)" in body and "text-decoration: underline" in body
                    for body in rules
                ),
                selector,
            )

    def test_theme_text_contrast_on_guidance_surfaces(self):
        base = dict(
            re.findall(
                r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})",
                re.search(r":root\s*\{([^}]+)\}", HTML_PAGE).group(1),
            )
        )
        dark = re.search(r'\[data-theme="dark"\]\s*\{([^}]+)\}', HTML_PAGE).group(1)
        for selector in (
            ":root",
            '[data-theme="dark"]',
            '[data-contrast="high"]',
            '[data-contrast="high"][data-theme="dark"]',
        ):
            values = base.copy()
            if 'theme="dark"' in selector:
                values.update(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", dark))
            values.update(
                re.findall(
                    r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})",
                    re.search(re.escape(selector) + r"\s*\{([^}]+)\}", HTML_PAGE).group(
                        1
                    ),
                )
            )
            for surface in ("--panel", "--soft", "--panel-2"):
                self.assertGreaterEqual(
                    contrast(values["--ink"], values[surface]), 4.5, (selector, surface)
                )
