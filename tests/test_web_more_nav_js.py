"""Regression coverage for the Web UI More navigation (#1068).

Opening an advanced view (one that lives under **More**) used to force the
``#nav-more`` disclosure open, which squeezed the primary tabs (Today / Items /
Dashboard / Create) into a narrow column. The More group now stays collapsed,
names the active advanced view in its summary ("More: Agenda"), and closes
after a destination is chosen, on Escape, or on an outside click.

The behavioral tests run the real navigation snippet extracted from the
assembled page against a small hand-rolled DOM, following the targeted
Node.js style already used by tests/test_web_drawer_edit_js.py.
"""

import json
import re
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE

_START = (
    "    // Keep advanced destinations discoverable without giving them equal first-"
)
_END_ANCHOR = (
    "if (_moreNav.open && !_moreNav.contains(event.target)) closeMoreNav(false);"
)


def _nav_snippet():
    script = re.search(r"<script>(.*)</script>", HTML_PAGE, re.S).group(1)
    start = script.index(_START)
    anchor = script.index(_END_ANCHOR, start)
    # The snippet ends with the closing of the document listener and the
    # surrounding ``if (_moreNav) { ... }`` block.
    end = script.index("    }\n", anchor) + len("    }\n")
    return script[start:end]


_HARNESS = r"""
function makeClassList() {
  const set = new Set();
  return {
    toggle(name, on) { if (on) set.add(name); else set.delete(name); },
    contains(name) { return set.has(name); },
  };
}
function makeEl(props) {
  const attrs = {};
  const listeners = {};
  const el = Object.assign({
    classList: makeClassList(),
    setAttribute(k, v) { attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null; },
    removeAttribute(k) { delete attrs[k]; },
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    dispatch(type, event) { (listeners[type] || []).forEach(fn => fn(event)); },
    focus() { focused = el.id; },
    closest() { return null; },
  }, props);
  return el;
}
let focused = "";
let view = "";
function currentView() { return view; }
function syncViewTabs() {}
const tabs = [
  {view: "agenda", label: "📅 Agenda"},
  {view: "messages", label: "💬 Messages"},
  {view: "matrix", label: "📊 Priority Matrix"},
].map(t => makeEl({dataset: {view: t.view}, textContent: t.label,
  closest(sel) { return sel === ".workspace-tab" ? this : null; }}));
const advanced = makeEl({id: "nav-advanced"});
const summary = makeEl({id: "nav-more-summary"});
const current = makeEl({id: "nav-more-current", textContent: "", hidden: true});
const outside = makeEl({id: "outside"});
const more = makeEl({
  id: "nav-more",
  open: false,
  querySelectorAll(sel) { return sel === ".workspace-tab[data-view]" ? tabs : []; },
  querySelector(sel) { return sel === ".nav-advanced" ? advanced : null; },
  contains(node) { return [more, summary, current, advanced, ...tabs].includes(node); },
});
const byId = {"nav-more": more, "nav-more-summary": summary, "nav-more-current": current, "nav-advanced": advanced};
const docListeners = {};
const document = {
  getElementById(id) { return byId[id] || null; },
  addEventListener(type, fn) { (docListeners[type] = docListeners[type] || []).push(fn); },
};
function snapshot() {
  return {
    open: more.open,
    current: current.textContent,
    currentHidden: current.hidden,
    summaryActive: summary.classList.contains("active"),
    ariaCurrent: summary.getAttribute("aria-current"),
    ariaExpanded: summary.getAttribute("aria-expanded"),
    focused,
  };
}
"""


@unittest.skipUnless(shutil.which("node"), "node is required for Web JS behavior tests")
class MoreNavigationBehaviorTests(unittest.TestCase):
    def _run(self, steps):
        source = (
            _HARNESS
            + _nav_snippet()
            + "\nconst out = {};\n"
            + steps
            + "\nconsole.log(JSON.stringify(out));\n"
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

    def test_advanced_view_keeps_more_collapsed_and_names_the_view(self):
        out = self._run('view = "agenda"; syncViewTabs(); out.s = snapshot();')["s"]
        self.assertFalse(out["open"])
        self.assertEqual(out["current"], "Agenda")
        self.assertFalse(out["currentHidden"])
        self.assertTrue(out["summaryActive"])
        self.assertEqual(out["ariaCurrent"], "page")
        self.assertEqual(out["ariaExpanded"], "false")

    def test_multi_word_label_strips_only_the_icon(self):
        out = self._run('view = "matrix"; syncViewTabs(); out.s = snapshot();')["s"]
        self.assertEqual(out["current"], "Priority Matrix")

    def test_primary_view_clears_the_active_indication(self):
        out = self._run(
            'view = "messages"; syncViewTabs(); view = "today"; syncViewTabs(); out.s = snapshot();'
        )["s"]
        self.assertFalse(out["open"])
        self.assertEqual(out["current"], "")
        self.assertTrue(out["currentHidden"])
        self.assertFalse(out["summaryActive"])
        self.assertIsNone(out["ariaCurrent"])

    def test_explicit_open_is_not_overridden_by_navigation_sync(self):
        out = self._run(
            'view = "agenda"; more.open = true; syncViewTabs(); out.s = snapshot();'
        )["s"]
        self.assertTrue(out["open"])
        self.assertEqual(out["ariaExpanded"], "true")
        self.assertEqual(out["current"], "Agenda")

    def test_choosing_a_destination_closes_more(self):
        out = self._run(
            'more.open = true; advanced.dispatch("click", {target: tabs[1]}); out.s = snapshot();'
        )["s"]
        self.assertFalse(out["open"])

    def test_escape_closes_more_and_returns_focus_to_summary(self):
        out = self._run(
            "more.open = true; let prevented = false;"
            'more.dispatch("keydown", {key: "Escape", preventDefault() { prevented = true; }, stopPropagation() {}});'
            "out.s = snapshot(); out.prevented = prevented;"
        )
        self.assertFalse(out["s"]["open"])
        self.assertEqual(out["s"]["focused"], "nav-more-summary")
        self.assertTrue(out["prevented"])

    def test_escape_when_closed_is_left_to_the_global_handler(self):
        out = self._run(
            "let prevented = false;"
            'more.dispatch("keydown", {key: "Escape", preventDefault() { prevented = true; }, stopPropagation() {}});'
            "out.prevented = prevented;"
        )
        self.assertFalse(out["prevented"])

    def test_outside_click_closes_but_inside_click_does_not(self):
        out = self._run(
            "more.open = true; docListeners.click.forEach(fn => fn({target: summary})); out.inside = more.open;"
            "docListeners.click.forEach(fn => fn({target: outside})); out.outside = more.open;"
        )
        self.assertTrue(out["inside"])
        self.assertFalse(out["outside"])


class MoreNavigationMarkupTests(unittest.TestCase):
    def test_summary_has_a_current_view_slot(self):
        summary = re.search(
            r'<summary id="nav-more-summary"[^>]*>(.*?)</summary>', HTML_PAGE, re.S
        ).group(1)
        self.assertIn('id="nav-more-current"', summary)
        self.assertIn("hidden", summary)

    def test_auto_expand_of_more_is_gone(self):
        self.assertNotIn("advanced.has(currentView())) more.open = true", HTML_PAGE)

    def test_desktop_more_is_an_overlay_dropdown(self):
        block = HTML_PAGE[HTML_PAGE.index("@media (min-width: 681px)") :]
        block = block[: block.index("\n    }\n")]
        self.assertIn(".header-workspace-tabs > .nav-more { position: static; }", block)
        self.assertIn("position: absolute;", block)
        self.assertIn(
            ".header-workspace-tabs > .nav-primary { flex-wrap: nowrap; }", block
        )

    def test_phone_open_more_gets_its_own_row(self):
        self.assertIn(
            ".header-workspace-tabs:has(> .nav-more[open]) { flex-wrap: wrap; }",
            HTML_PAGE,
        )
        self.assertIn(
            ".header-workspace-tabs > .nav-more[open] { flex: 1 1 100%; min-width: 0; }",
            HTML_PAGE,
        )


if __name__ == "__main__":
    unittest.main()
