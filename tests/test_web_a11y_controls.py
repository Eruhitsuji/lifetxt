"""Regression coverage for main Web UI accessibility fixes (#1072).

* Icon-only header controls and Items filter controls expose accessible
  names independent of ``title``/``placeholder``.
* The workspace navigation is plain ``<nav>`` with ``aria-current="page"``
  instead of an invalid mixed ``tablist``/``tab`` structure.
* Row selection checkboxes and the Open-only checkbox get 44x44 CSS px
  effective touch targets without opening the record drawer.
"""

import json
import re
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


def _script():
    return re.search(r"<script>(.*)</script>", HTML_PAGE, re.S).group(1)


def _function(script, signature):
    start = script.index(signature)
    depth = 0
    for index in range(script.index("{", start), len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[start : index + 1]
    raise AssertionError(signature)


class AccessibleNameTests(unittest.TestCase):
    def test_icon_only_header_controls_have_aria_labels(self):
        for control_id, label in (
            ("dark-btn", "Toggle dark mode"),
            ("contrast-btn", "Toggle high-contrast theme"),
            ("motion-btn", "Toggle reduced motion"),
            ("density-btn", "Toggle compact density"),
            ("fullscreen-btn", "Toggle fullscreen"),
        ):
            tag = re.search(r'<button id="%s"[^>]*>' % control_id, HTML_PAGE).group(0)
            self.assertIn('aria-label="%s"' % label, tag)
        self.assertRegex(
            HTML_PAGE, r'onclick="openCmdk\(\)"[^>]*aria-label="Command palette"'
        )
        self.assertRegex(
            HTML_PAGE,
            r'onclick="openHelpModal\(\)"[^>]*aria-label="Keyboard shortcuts help"',
        )

    def test_items_filter_controls_have_programmatic_labels(self):
        for control_id in (
            "search",
            "kind",
            "sort",
            "order",
            "group-by",
            "limit",
            "saved-view-select",
            "area-select",
            "export-select",
        ):
            tag = re.search(r'<(?:input|select) id="%s"[^>]*>' % control_id, HTML_PAGE)
            self.assertIsNotNone(tag, control_id)
            self.assertRegex(tag.group(0), r'aria-label="[^"]+"', control_id)

    def test_new_label_strings_are_localized(self):
        self.assertIn('"Search items": "アイテムを検索"', HTML_PAGE)
        self.assertIn('"Select for bulk action": "一括操作の対象に選択"', HTML_PAGE)


class NavigationSemanticsTests(unittest.TestCase):
    def test_workspace_navigation_is_not_a_tablist(self):
        nav = re.search(
            r'<nav class="workspace-tabs header-workspace-tabs"[^>]*>', HTML_PAGE
        ).group(0)
        self.assertNotIn("tablist", nav)
        self.assertIn('aria-label="Views"', nav)
        script = _script()
        setup = _function(script, "function setupWorkspaceTabs(")
        self.assertNotIn('"tablist"', setup)
        sync = _function(script, "function syncViewTabs(")
        self.assertNotIn('"tab"', sync)
        self.assertNotIn("aria-selected", sync)
        self.assertNotIn("tabIndex", sync)


_NAV_HARNESS = r"""
function makeTab(view, label) {
  const attrs = {};
  return {
    dataset: {view},
    textContent: label,
    classList: {toggle() {}},
    setAttribute(k, v) { attrs[k] = String(v); },
    removeAttribute(k) { delete attrs[k]; },
    getAttribute(k) { return k in attrs ? attrs[k] : null; },
    getClientRects() { return [1]; },
    focus() { focused = this; },
  };
}
let focused = null;
let view = "";
function currentView() { return view; }
const tabs = [makeTab("today", "Today"), makeTab("", "Items"), makeTab("dashboard", "Dashboard")];
let navKeydown = null;
const nav = {
  removeAttribute() {},
  querySelectorAll() { return tabs; },
  addEventListener(type, fn) { if (type === "keydown") navKeydown = fn; },
};
const document = {
  querySelectorAll() { return tabs; },
  getElementById(id) { return id === "workspace-tabs" ? nav : null; },
  get activeElement() { return focused; },
};
"""


@unittest.skipUnless(shutil.which("node"), "node is required for Web JS behavior tests")
class NavigationBehaviorTests(unittest.TestCase):
    def _run(self, body):
        script = _script()
        source = (
            _NAV_HARNESS
            + _function(script, "function syncViewTabs(")
            + "\n"
            + _function(script, "function setupWorkspaceTabs(")
            + "\nconst out = {};\n"
            + body
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

    def test_active_view_uses_aria_current_only(self):
        out = self._run(
            'view = "dashboard"; syncViewTabs();'
            "out.current = tabs.map(t => t.getAttribute('aria-current'));"
            "out.roles = tabs.map(t => t.getAttribute('role'));"
            "out.selected = tabs.map(t => t.getAttribute('aria-selected'));"
        )
        self.assertEqual(out["current"], [None, None, "page"])
        self.assertEqual(out["roles"], [None, None, None])
        self.assertEqual(out["selected"], [None, None, None])

    def test_arrow_keys_still_move_between_views(self):
        out = self._run(
            "setupWorkspaceTabs(); focused = tabs[0];"
            'navKeydown({key: "ArrowRight", preventDefault() {}}); out.a = focused.textContent;'
            'navKeydown({key: "End", preventDefault() {}}); out.b = focused.textContent;'
            'navKeydown({key: "ArrowRight", preventDefault() {}}); out.c = focused.textContent;'
        )
        self.assertEqual(
            [out["a"], out["b"], out["c"]], ["Items", "Dashboard", "Today"]
        )


class TouchTargetTests(unittest.TestCase):
    def test_row_checkbox_hit_area_does_not_open_the_drawer(self):
        script = _script()
        self.assertIn(
            '<label class="item-check-hit"><input type="checkbox" class="item-check"',
            script,
        )
        self.assertIn('if (e.target.closest(".item-check-hit")) return;', script)
        self.assertIn(
            'node.querySelector(".item-check-hit").addEventListener("click"', script
        )

    def test_phone_and_touch_targets_are_44px(self):
        block = HTML_PAGE[
            HTML_PAGE.index("@media (pointer: coarse), (max-width: 680px)") :
        ]
        block = block[: block.index("\n    }\n")]
        self.assertIn(".item-check-hit { min-width: 44px; min-height: 44px; }", block)
        self.assertIn("label.inline { min-height: 44px; min-width: 44px;", block)

    def test_hidden_checkbox_contexts_also_hide_the_hit_area(self):
        self.assertIn(
            ".kiosk-mode .item-check, .kiosk-mode .item-check-hit"
            " { display: none !important; }",
            HTML_PAGE,
        )
        self.assertIn(".item-check, .item-check-hit { display: none; }", HTML_PAGE)


if __name__ == "__main__":
    unittest.main()
