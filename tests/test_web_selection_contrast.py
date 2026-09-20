import unittest
from importlib import resources

from lifetxt import web_assets


class WebSelectionContrastTests(unittest.TestCase):
    def test_selection_styles_are_loaded_last(self):
        self.assertEqual(web_assets._CSS_RESOURCE_NAMES[-1], "web_assets_css_05.css")
        css = resources.files("lifetxt").joinpath("web_assets_css_05.css").read_text(encoding="utf-8")
        self.assertIn(css, web_assets.HTML_PAGE)

    def test_selection_styles_use_neutral_theme_tokens(self):
        css = resources.files("lifetxt").joinpath("web_assets_css_05.css").read_text(encoding="utf-8")
        self.assertIn("--selection-bg: #e5e7eb;", css)
        self.assertIn("--selection-fg: var(--ink);", css)
        self.assertIn("--selection-bg: #374151;", css)
        self.assertIn("background: var(--selection-bg);", css)
        self.assertIn("color: var(--selection-fg);", css)
        self.assertNotIn("var(--accent-soft)", css)


if __name__ == "__main__":
    unittest.main()
