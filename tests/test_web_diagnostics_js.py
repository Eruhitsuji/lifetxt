"""Behavior coverage for Web diagnostics location, navigation, and summary (#1073).

Diagnostics used to render only ``severity code: message``, with no way to
see which record or file they came from. They now show a location label
(``file:line[:column]`` or ``Line N``), mark diagnostics whose record is not
in the current filtered list, offer an **Open record** action that opens the
affected record without changing the filters, and collapse two or more
diagnostics behind a summary whose expand/collapse state survives reloads.

The tests run the real diagnostics snippet extracted from the assembled page
against a minimal DOM stub, following the Node.js style of
tests/test_web_more_nav_js.py.
"""

import json
import re
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE

_START = "    let renderedDiagnostics = [];"
_END = "    function safeMarkdownHtml("


def _diagnostics_snippet():
    script = re.search(r"<script>(.*)</script>", HTML_PAGE, re.S).group(1)
    start = script.index(_START)
    return script[start : script.index(_END, start)]


_HARNESS = r"""
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}
function t(s) { return s; }
let currentItems = [];
let apiItems = [];
let apiFails = false;
const toasts = [];
const opened = [];
const selected = [];
async function api(path) {
  if (apiFails) throw new Error("boom");
  return {items: apiItems, path};
}
function showToast(message, kind) { toasts.push([message, kind]); }
function selectItem(item) { selected.push(item.line); }
function openDrawer(item) { opened.push(item.line); }
let clickHandler = null;
const root = {
  innerHTML: "",
  _details: null,
  querySelector(sel) { return sel === "details.diagnostics-summary" ? this._details : null; },
  addEventListener(type, fn) { if (type === "click") clickHandler = fn; },
};
const document = { getElementById(id) { return id === "diagnostics" ? root : null; } };
function render(list) {
  renderDiagnostics(list);
  // Emulate the browser parsing the rendered <details> element.
  root._details = root.innerHTML.startsWith("<details")
    ? {open: /^<details[^>]* open/.test(root.innerHTML)}
    : null;
}
function clickOpen(index) {
  const button = {dataset: {diagnosticIndex: String(index)}};
  clickHandler({target: {closest: sel => sel === ".diagnostic-open" ? button : null}});
}
function settle() { return new Promise(resolve => setTimeout(resolve, 0)); }
"""

_W = {"severity": "warning", "code": "W103", "message": "done", "line": 2}


@unittest.skipUnless(shutil.which("node"), "node is required for Web JS behavior tests")
class DiagnosticsBehaviorTests(unittest.TestCase):
    def _run(self, steps):
        source = (
            _HARNESS
            + _diagnostics_snippet()
            + "\n(async () => {\nconst out = {};\n"
            + steps
            + "\nconsole.log(JSON.stringify(out));\n})();\n"
        )
        result = subprocess.run(
            ["node", "-e", source],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def _render(self, diagnostics, items=(), extra=""):
        return self._run(
            f"currentItems = {json.dumps(list(items))};"
            f"render({json.dumps(diagnostics)}); {extra} out.html = root.innerHTML;"
        )

    def test_empty_list_renders_nothing(self):
        self.assertEqual(self._render([])["html"], "")

    def test_single_diagnostic_has_line_label_and_open_action_without_summary(self):
        html = self._render([_W], items=[{"line": 2, "source": ""}])["html"]
        self.assertNotIn("<details", html)
        self.assertIn(
            '<span class="diagnostic-location" title="Line 2">Line 2</span>', html
        )
        self.assertIn('data-diagnostic-index="0"', html)
        self.assertNotIn("diagnostic-hidden", html)

    def test_record_outside_current_filter_is_marked(self):
        html = self._render([_W], items=[{"line": 9, "source": ""}])["html"]
        self.assertIn("Not shown by the current filter", html)

    def test_source_basename_handles_posix_and_windows_paths(self):
        diags = [
            dict(_W, source="/srv/data/work.life.txt", line=4, column=7),
            dict(_W, source="C:\\Users\\me\\home.life.txt", line=1),
        ]
        html = self._render(diags)["html"]
        self.assertIn(">work.life.txt:4:7</span>", html)
        self.assertIn('title="/srv/data/work.life.txt:4"', html)
        self.assertIn(">home.life.txt:1</span>", html)

    def test_same_line_in_another_source_is_not_a_match(self):
        diag = dict(_W, source="/a/one.life.txt")
        html = self._render([diag], items=[{"line": 2, "source": "/a/two.life.txt"}])[
            "html"
        ]
        self.assertIn("diagnostic-hidden", html)

    def test_missing_line_has_no_location_or_action(self):
        diag = {"severity": "error", "code": "E001", "message": "bad"}
        html = self._render([diag])["html"]
        self.assertNotIn("diagnostic-location", html)
        self.assertNotIn("diagnostic-open", html)
        self.assertIn('<div class="diagnostic">', html)

    def test_untrusted_text_is_escaped(self):
        diag = {
            "severity": "warning",
            "code": "W1",
            "message": '<img src=x onerror="alert(1)">&',
            "source": '/p/"<b>.life.txt',
            "line": 3,
            "hint": "<script>x</script>",
        }
        html = self._render([diag])["html"]
        self.assertNotIn("<img", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>", html)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;", html)
        self.assertIn(
            '<div class="diagnostic-hint">&lt;script&gt;x&lt;/script&gt;</div>', html
        )

    def test_two_or_more_collapse_into_summary_with_counts(self):
        diags = [
            _W,
            dict(_W, line=3),
            {"severity": "error", "code": "E1", "message": "x", "line": 1},
        ]
        html = self._render(diags)["html"]
        self.assertTrue(html.startswith('<details class="diagnostics-summary" open>'))
        self.assertIn("Diagnostics (3)", html)
        self.assertIn('<span class="diagnostic-count error">Errors: 1</span>', html)
        self.assertIn('<span class="diagnostic-count warning">Warnings: 2</span>', html)

    def test_warnings_only_summary_starts_collapsed(self):
        html = self._render([_W, dict(_W, line=3)])["html"]
        self.assertTrue(html.startswith('<details class="diagnostics-summary">'))
        self.assertNotIn("Errors:", html)

    def test_user_expand_choice_survives_rerender(self):
        out = self._run(
            f"render({json.dumps([_W, dict(_W, line=3)])}); root._details.open = true;"
            f"render({json.dumps([_W, dict(_W, line=4)])}); out.html = root.innerHTML;"
        )
        self.assertTrue(
            out["html"].startswith('<details class="diagnostics-summary" open>')
        )

    def test_open_record_uses_current_items_without_api(self):
        out = self._run(
            f'currentItems = [{{"line": 2, "source": ""}}]; apiFails = true;'
            f"render({json.dumps([_W])}); clickOpen(0); await settle();"
            "out.opened = opened; out.selected = selected; out.toasts = toasts;"
        )
        self.assertEqual(out["opened"], [2])
        self.assertEqual(out["selected"], [2])
        self.assertEqual(out["toasts"], [])

    def test_open_record_hidden_by_filter_falls_back_to_unfiltered_list(self):
        diag = dict(_W, source="/d/b.life.txt", line=1)
        out = self._run(
            'currentItems = []; apiItems = [{"line": 1, "source": "/d/a.life.txt"}, {"line": 1, "source": "/d/b.life.txt"}];'
            f"render({json.dumps([diag])}); clickOpen(0); await settle();"
            "out.opened = opened; out.toasts = toasts;"
        )
        self.assertEqual(out["opened"], [1])
        self.assertEqual(out["toasts"], [])

    def test_unmatched_location_reports_a_toast(self):
        out = self._run(
            f"apiItems = []; render({json.dumps([_W])}); clickOpen(0); await settle();"
            "out.opened = opened; out.toasts = toasts;"
        )
        self.assertEqual(out["opened"], [])
        self.assertEqual(out["toasts"], [["No record found at Line 2", "error"]])

    def test_api_failure_reports_a_toast(self):
        out = self._run(
            f"apiFails = true; render({json.dumps([_W])}); clickOpen(0); await settle();"
            "out.opened = opened; out.toasts = toasts;"
        )
        self.assertEqual(out["opened"], [])
        self.assertEqual(out["toasts"], [["Could not load the record: boom", "error"]])


class DiagnosticsI18nTests(unittest.TestCase):
    def test_new_labels_have_japanese_entries(self):
        for key in (
            "Diagnostics",
            "Open record",
            "Not shown by the current filter",
            "No record found at",
            "Could not load the record",
            "Errors",
            "Warnings",
        ):
            self.assertRegex(HTML_PAGE, rf'"{re.escape(key)}": "[^"]+"', key)


if __name__ == "__main__":
    unittest.main()
