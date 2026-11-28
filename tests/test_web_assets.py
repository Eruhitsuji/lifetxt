"""Protect the packaged Web UI assembly and runtime rebinding contract."""

from __future__ import unicode_literals

import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from importlib import resources

from lifetxt import web_assets, webapp


REVISION_BRIDGE_MARKER = "lifetxt-revision-contract-v1"
# #1490 moves the existing Drawer rules outside the split .focus-check rule.
# Keep the exact assembled page checksum gate in sync with reviewed asset changes.
# Calculated using _CSS_RESOURCE_NAMES / _JS_RESOURCE_NAMES assembly order,
# before brand injection (CSS 06/07 precede 05).
LEGACY_PRISTINE_GIT_BLOB_SHA = "3c63d3a6a0222a07875f29f3ea56b4ccc7a0ff43"
WEBAPP_SOURCE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lifetxt", "webapp.py"
)


def _git_blob_sha(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


class WebAssetExtractionTests(unittest.TestCase):
    def test_asset_module_holds_the_page(self):
        self.assertTrue(web_assets.HTML_PAGE.startswith("<!doctype html>"))
        self.assertTrue(web_assets.HTML_PAGE.endswith("</html>"))
        self.assertIn("/api/temporal-thread/", web_assets.HTML_PAGE)
        self.assertIn("consistencyWarnings", web_assets.HTML_PAGE)

    def test_surface_navigation_links_are_explicit(self):
        nav = re.search(
            r'<nav class="workspace-tabs header-workspace-tabs"[^>]*>(.*?)</nav>',
            web_assets.HTML_PAGE,
            re.DOTALL,
        ).group(1)
        primary = re.search(
            r'<div class="nav-primary"[^>]*>(.*?)</div>', nav, re.DOTALL
        ).group(1)
        more = re.search(
            r'<div class="nav-advanced"[^>]*>(.*?)</div>', nav, re.DOTALL
        ).group(1)
        self.assertNotIn('href="/procedures"', primary)
        self.assertIn('href="/procedures"', more)
        self.assertIn('data-i18n="Procedures"', more)
        self.assertNotIn('href="/planner"', primary)
        self.assertNotIn('href="/capture"', primary)
        self.assertNotIn('href="/state"', primary)
        self.assertIn('href="/state"', more)
        self.assertIn('href="/desk"', more)
        self.assertNotIn('href="/desk"', primary)
        self.assertIn('data-i18n="Quick Status"', more)
        self.assertRegex(
            more,
            r'<a class="workspace-tab surface-link" href="/planner"><span class="nav-feature-title">'
            r'<span aria-hidden="true">📓</span> '
            r'<span data-i18n="Planner">Planner</span></span>',
        )
        self.assertRegex(
            more,
            r'<a class="workspace-tab surface-link" href="/capture"><span class="nav-feature-title">'
            r'<span aria-hidden="true">⚡</span> '
            r'<span data-i18n="Quick Capture">Quick Capture</span></span>',
        )
        groups = re.findall(
            r'<section class="nav-feature-group".*?</section>', more, re.S
        )
        self.assertEqual(len(groups), 5)
        destinations = re.findall(r'(?:data-view|href)="([^"]+)"', more)
        self.assertEqual(len(destinations), 20)
        self.assertEqual(len(set(destinations)), 20)
        self.assertEqual(more.count('class="nav-feature-description"'), 20)
        for destination in (
            'data-view="agenda"',
            'data-view="calendar"',
            'href="/planner"',
        ):
            self.assertIn(destination, groups[0])
        self.assertIn('href="/"', web_assets.PLANNER_HTML_PAGE)
        self.assertIn('class="capture-back" href="/"', web_assets.HTML_PAGE)

    def test_more_navigation_links_share_surface_control_styling(self):
        self.assertIn(".surface-link", web_assets.HTML_PAGE)
        self.assertIn('data-status="__active__"', web_assets.HTML_PAGE)
        self.assertIn("setActiveStatusFilter", web_assets.HTML_PAGE)

    def test_items_filters_apply_without_discarding_pending_controls(self):
        for expected in (
            'search?.addEventListener("input", schedule)',
            'search?.addEventListener("keydown"',
            'control.addEventListener("change", () => loadItems())',
            'limit?.addEventListener("keydown"',
            "let itemsLoadGeneration = 0",
            "if (generation !== itemsLoadGeneration) return;",
            "updateUrlFromControls();\n      const params = query();",
        ):
            self.assertIn(expected, web_assets.HTML_PAGE)
        self.assertNotIn(
            '<button onclick="loadItems()">Apply</button>', web_assets.HTML_PAGE
        )

    def test_split_resources_assemble_the_legacy_pristine_page(self):
        package = resources.files("lifetxt")
        template = package.joinpath("web_assets.html").read_text(encoding="utf-8")
        self.assertEqual(template.count(web_assets._STYLE_MARKER), 1)
        self.assertEqual(template.count(web_assets._SCRIPT_MARKER), 1)

        styles = package.joinpath("web_tokens.css").read_text(
            encoding="utf-8"
        ) + "".join(
            package.joinpath(name).read_text(encoding="utf-8")
            for name in web_assets._CSS_RESOURCE_NAMES
        )
        script = "".join(
            package.joinpath(name).read_text(encoding="utf-8")
            for name in web_assets._JS_RESOURCE_NAMES
        )
        assembled = template.replace(web_assets._STYLE_MARKER, styles).replace(
            web_assets._SCRIPT_MARKER, script
        )
        self.assertEqual(
            _git_blob_sha(assembled.encode("utf-8")),
            LEGACY_PRISTINE_GIT_BLOB_SHA,
        )
        self.assertEqual(
            web_assets.HTML_PAGE, web_assets._apply_brand_assets(assembled)
        )

    def test_packaged_fragment_resources_exist(self):
        package = resources.files("lifetxt")
        names = web_assets._CSS_RESOURCE_NAMES + web_assets._JS_RESOURCE_NAMES
        self.assertTrue(names)
        for name in names:
            resource = package.joinpath(name)
            self.assertTrue(resource.is_file(), name)
            self.assertTrue(resource.read_bytes(), name)

    def test_shell_no_longer_embeds_full_css_or_script(self):
        shell = (
            resources.files("lifetxt")
            .joinpath("web_assets.html")
            .read_text(encoding="utf-8")
        )
        self.assertIn(web_assets._STYLE_MARKER, shell)
        self.assertIn(web_assets._SCRIPT_MARKER, shell)
        self.assertLess(len(shell), len(web_assets.HTML_PAGE) // 2)

    def test_webapp_still_exposes_the_name(self):
        self.assertTrue(hasattr(webapp, "HTML_PAGE"))
        self.assertIn("</html>", webapp.HTML_PAGE)

    def test_surface_runtime_still_rebinds_webapp_html_page(self):
        self.assertIn(REVISION_BRIDGE_MARKER, webapp.HTML_PAGE)

    def test_asset_module_keeps_the_pristine_value(self):
        self.assertNotIn(REVISION_BRIDGE_MARKER, web_assets.HTML_PAGE)

    def test_route_serves_what_webapp_exposes(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest(
                "web extras unavailable, so the served page cannot be checked"
            )
        from unittest.mock import patch

        info = {"version": "1.0.4.3", "git_commit": "a" * 40}
        with patch("lifetxt.webapp.snapshot_runtime_build_info", return_value=info):
            client = TestClient(webapp.create_app(paths=[]))
        expected = webapp.HTML_PAGE.replace(
            "__LIFETXT_RUNTIME_VERSION__", info["version"]
        ).replace("__LIFETXT_RUNTIME_COMMIT__", info["git_commit"])
        for path in ("/", "/capture"):
            response = client.get(path)
            self.assertEqual(expected.encode("utf-8"), response.content)
            self.assertEqual("no-store", response.headers.get("cache-control"))
            self.assertNotIn(b"__LIFETXT_RUNTIME_", response.content)
            self.assertIn(REVISION_BRIDGE_MARKER.encode("utf-8"), response.content)

    def test_runtime_html_escapes_identity_and_handles_unavailable_git(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest("web extras unavailable")

        from unittest.mock import patch

        info = {"version": "<script>alert(1)</script>", "git_commit": None}
        with patch("lifetxt.webapp.snapshot_runtime_build_info", return_value=info):
            client = TestClient(webapp.create_app(paths=[]))
        body = client.get("/").text
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)
        self.assertNotIn('<dd id="runtime-build-version" data-no-i18n><script>', body)
        self.assertIn('<dd id="runtime-build-commit" data-no-i18n>—</dd>', body)
        self.assertNotIn("__LIFETXT_RUNTIME_", body)

    def test_literal_is_not_back_in_webapp(self):
        with io.open(WEBAPP_SOURCE, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn('HTML_PAGE = r"""', source)
        self.assertIn("from .web_assets import HTML_PAGE", source)
        self.assertIn('headers={"Cache-Control": "no-store"}', source)

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_assembled_script_has_no_syntax_error(self):
        # Every JS fragment concatenates into one shared-scope <script>, so
        # a name collision (e.g. a `const` redeclaring an earlier `function`)
        # in any one fragment is a fatal SyntaxError for the whole page.
        # Nothing else in this suite parses the assembled script as
        # JavaScript, so this is the one guard that would catch it.
        match = re.search(r"<script>(.*)</script>", web_assets.HTML_PAGE, re.S)
        self.assertIsNotNone(match)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(match.group(1))
            script_path = handle.name
        try:
            proc = subprocess.run(
                ["node", "--check", script_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            os.unlink(script_path)
        self.assertEqual(0, proc.returncode, proc.stderr or proc.stdout)

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_due_indicators_use_workspace_calendar_days(self):
        def extract(start, end):
            source = web_assets.HTML_PAGE
            offset = source.index(start)
            return source[offset : source.index(end, offset)]

        source = "\n".join(
            [
                extract(
                    "function _isoDateOnlyUTC(", "function buildRelativeTimeBadge("
                ),
                extract("function dueSoonDays(", "function renderSummary("),
                extract("function buildDueRelLabel(", "// ── progress: presentation"),
                extract("function agendaCountdownLabel(", "function guidedEmptyState("),
                extract(
                    "function agendaDueSoonClass(", "// ── Notification permission"
                ),
                extract("function updateAgendaOverdueBadge(", "// ── Stats summary"),
            ]
        )
        harness = r"""
const assert = require("node:assert/strict");
const appConfig = {today: "2026-03-07", web: {due_soon_days: 2}};
const badge = {style: {}};
const document = {getElementById: () => badge};
const escapeHtml = text => text;
const task = (due, status = "[ ]") => ({details: {due: [due]}, status});
for (const [due, days, state, label] of [
  ["2026-03-06", -1, "overdue", "1d overdue"],
  ["2026-03-07", 0, "due-soon", "due today"],
  ["2026-03-07T00:15:00+09:00", 0, "due-soon", "due today"],
  ["2026-03-09", 2, "due-soon", "in 2d"],
  ["2026-03-10", 3, "", "in 3d"],
]) {
  const item = task(due);
  assert.equal(workspaceCalendarDayDifference(due), days);
  assert.equal(itemDueSoonClass(item), state);
  assert.equal(agendaDueSoonClass(item), state);
  assert.ok(buildDueRelLabel(item).includes(">" + label + "<"));
}
assert.equal(relativeTime("2026-03-08"), "tomorrow");
assert.equal(workspaceCalendarDayDifference("2026-02-30"), null);
assert.equal(itemDueSoonClass(task("")), "");
for (const status of ["[x]", "[-]"]) {
  assert.equal(itemDueSoonClass(task("2026-03-06", status)), "");
  assert.equal(buildDueRelLabel(task("2026-03-06", status)), "");
}
assert.match(
  agendaCountdownLabel({when: "2026-03-06", occurrence_start: "2026-03-07"}),
  /due-soon.*>today</,
);
updateAgendaOverdueBadge([
  {when: "2026-03-06", status: "[ ]", matches: [{}, {}]},
  {when: "2026-03-07", status: "[ ]"},
  {when: "2026-03-06", status: "[x]"},
  {when: "2026-02-30", status: "[ ]"},
]);
assert.equal(badge.textContent, "1");
updateAgendaOverdueBadge([]);
assert.equal(badge.style.display, "none");
"""
        for zone in ("America/Los_Angeles", "Asia/Tokyo"):
            with self.subTest(zone=zone):
                result = subprocess.run(
                    ["node", "-e", source + harness],
                    env={**os.environ, "TZ": zone},
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()


class Issue1386RegressionTests(unittest.TestCase):
    def test_saved_filters_retry_hidden_attribute_is_honored(self):
        from lifetxt import web_assets

        css = web_assets.HTML_PAGE
        self.assertIn("#saved-filters-retry[hidden] { display: none; }", css)

    def test_date_formatting_follows_ui_language_not_browser_locale(self):
        from lifetxt import web_assets

        page = web_assets.HTML_PAGE
        self.assertIn("function uiLocale()", page)
        self.assertNotRegex(page, r"toLocale(?:Date|Time)String\(undefined")
        self.assertNotIn("Intl.DateTimeFormat(undefined", page)
