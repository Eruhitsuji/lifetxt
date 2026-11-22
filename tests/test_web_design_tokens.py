"""Guard the shared Web design tokens (#1703-#1707, parent #1386)."""

import re
import unittest
from importlib import resources

from lifetxt import web_assets

PAGES = {
    "web_desk.css": web_assets.DESK_HTML_PAGE,
    "web_planner.css": web_assets.PLANNER_HTML_PAGE,
    "web_state.css": web_assets.STATE_HTML_PAGE,
}
# A hex colour used as a declaration value (after ':' or inside a gradient list).
HEX_VALUE = re.compile(r"[:,(\s]#[0-9a-fA-F]{3,8}\b(?=\s*[;,)}!]|\s*$)")
REQUIRED = (
    "--bg",
    "--panel",
    "--ink",
    "--muted",
    "--line",
    "--accent",
    "--danger",
    "--warn",
    "--ok",
    "--info",
    "--violet",
    "--r-md",
    "--shadow-2",
)


def _css(name):
    text = resources.files("lifetxt").joinpath(name).read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


class DesignTokenTests(unittest.TestCase):
    def test_tokens_define_required_names_for_light_and_dark(self):
        css = _css("web_tokens.css")
        for name in REQUIRED:
            self.assertIn(name + ":", css)
        self.assertIn("prefers-color-scheme:dark", css)
        self.assertIn(":root[data-theme=dark]", css)
        self.assertIn(":root[data-theme=light]", css)

    def test_page_css_has_no_hardcoded_hex_colours(self):
        for name in PAGES:
            hits = HEX_VALUE.findall(_css(name))
            self.assertEqual(hits, [], "%s must use shared tokens: %s" % (name, hits))

    def test_pages_embed_tokens_before_page_css(self):
        for name, page in PAGES.items():
            self.assertIn("--hero-a", page)
            self.assertLess(page.index("--danger-soft"), page.index("box-sizing"), name)


if __name__ == "__main__":
    unittest.main()
