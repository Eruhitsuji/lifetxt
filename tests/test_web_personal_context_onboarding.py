import json
import shutil
import subprocess
import unittest
from importlib import resources

from lifetxt import web_assets


class WebPersonalContextOnboardingTests(unittest.TestCase):
    def setUp(self):
        package = resources.files("lifetxt")
        self.html = package.joinpath("web_assets.html").read_text(encoding="utf-8")
        self.js = package.joinpath("web_assets_js_19.js").read_text(encoding="utf-8")
        self.css = package.joinpath("web_assets_css_06.css").read_text(encoding="utf-8")

    def test_page_is_discoverable_without_displacing_primary_navigation(self):
        primary = self.html.split('<details class="nav-more"', 1)[0]
        advanced = self.html.split('<details class="nav-more"', 1)[1]
        self.assertNotIn('data-view="context"', primary)
        self.assertIn('data-view="context"', advanced)
        self.assertIn('data-page="context"', self.html)
        self.assertIn('aria-labelledby="personal-context-heading"', self.html)

    def test_ui_uses_projection_preview_and_authoritative_item_write_routes(self):
        self.assertIn("api(`/api/personal-context", self.js)
        self.assertIn("?include_stale=true", self.js)
        self.assertIn("loadMorePersonalContext", self.js)
        self.assertIn('id="personal-context-load-more"', self.html)
        self.assertIn("reconfirmPersonalContext", self.js)
        self.assertIn("Still correct", self.js)
        self.assertIn('api("/api/personal-context/preview"', self.js)
        self.assertIn('api("/api/items"', self.js)
        self.assertNotIn("/api/personal-context/save", self.js)
        self.assertIn("personalContextReadOnly", self.js)
        self.assertIn("remainingRecords", self.js)
        self.assertIn("currentness_counts", self.js)
        self.assertIn("personal-context-stale-badge", self.js)
        self.assertIn('label: "Other context"', self.js)
        self.assertIn('id="personal-context-include-stale"', self.html)
        self.assertIn('id="personal-context-bulk-toolbar"', self.html)
        self.assertIn("bulkReviewPersonalContext", self.js)
        self.assertIn("/api/personal-context/bulk-review", self.js)

    def test_responsive_and_accessible_contract_is_present(self):
        for width in (760, 430):
            self.assertIn("@media (max-width: %dpx)" % width, self.css)
        self.assertIn("min-height: 44px", self.css)
        self.assertIn(".personal-context-stale-badge", self.css)
        self.assertIn('aria-live="assertive"', self.html)
        self.assertIn('role="status"', self.html)
        self.assertIn(
            '"Personal Context": "パーソナルコンテキスト"', web_assets.HTML_PAGE
        )

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_sequential_save_stops_at_failure_and_retains_unsaved_records(self):
        start = self.js.index("    async function savePersonalContextRecords")
        end = self.js.index("\n    function replacePersonalContextFacts", start)
        function_source = self.js[start:end]
        records = [
            {"domain": "profile", "fact": "one", "payload": {"title": "one"}},
            {"domain": "goal", "fact": "two", "payload": {"title": "two"}},
            {"domain": "skill", "fact": "three", "payload": {"title": "three"}},
        ]
        script = f"""
{function_source}
const records = {json.dumps(records)};
const calls = [];
savePersonalContextRecords(records, async payload => {{
  calls.push(payload.title);
  if (payload.title === "two") throw new Error("disk full");
}}).then(() => process.exit(2)).catch(error => {{
  process.stdout.write(JSON.stringify({{
    calls, savedCount: error.savedCount,
    remaining: error.remainingRecords.map(row => row.fact),
  }}));
}});
"""
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=20
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            {"calls": ["one", "two"], "savedCount": 1, "remaining": ["two", "three"]},
            json.loads(result.stdout),
        )

    def test_new_fragments_are_packaged(self):
        self.assertIn("web_assets_css_06.css", web_assets._CSS_RESOURCE_NAMES)
        self.assertIn("web_assets_js_19.js", web_assets._JS_RESOURCE_NAMES)
        self.assertIn("Personal Context onboarding", web_assets.HTML_PAGE)


if __name__ == "__main__":
    unittest.main()
