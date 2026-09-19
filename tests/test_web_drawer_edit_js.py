"""Behavioral regression coverage for the Web record-detail drawer's Edit
action (#850).

The drawer editor (``drawerEdit``/``drawerSaveEdit``/``drawerCancelEdit`` in
``lifetxt/web_assets_js_12.js``) calls ``renderStructuredFields()``,
``_structuredDetails()``, and ``syncStatusStateMode()`` (structured
common-key authoring, #776) and ``showActionableError()`` (#798) directly by
name, from top-level code. Those functions used to be declared *inside* the
``loadConfig().then(() => { ... })`` callback in
``lifetxt/web_assets_js_17.js``/``lifetxt/web_assets_js_18.js`` -- a nested
function scope with no lexical visibility from outside it -- so clicking
Edit threw an uncaught ``ReferenceError`` while building the edit form's
HTML, before ``drawer-body.innerHTML`` was ever assigned. The drawer
silently kept showing the read-only Overview content instead of an editable
form. Reproduced live against a real running server with a real headless
browser before the fix (see the pull request for the transcript); this
module gives it an automated regression test.

Two independent things are checked:

* :class:`ScopeRegressionGuardTests` is a narrow, purely textual guard
  against reverting exactly this fix (moving the affected declarations back
  inside the ``loadConfig().then()`` callback). It does not require a JS
  parser -- it is not a general "detect any accidental closure nesting"
  check, only a targeted regression gate for this bug.
* :class:`DrawerEditInteractionTests` drives the *real* extracted
  ``drawerEdit``/``drawerSaveEdit``/``drawerCancelEdit`` functions plus their
  real structured-field/actionable-error dependencies against a small
  hand-rolled DOM (mirroring this project's established
  "targeted Node.js run of the extracted function source" verification
  style, e.g. tests/test_web_context_create_js.py), covering the actual
  ``openDrawer -> Edit -> change fields -> Save -> updated detail``
  interaction rather than only the underlying helper functions in
  isolation.
"""

import json
import re
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


def _extract_script():
    match = re.search(r"<script>(.*)</script>", HTML_PAGE, re.S)
    assert match is not None
    return match.group(1)


def _extract_statement(full_script, start_marker, end_marker):
    start = full_script.index(start_marker)
    end = full_script.index(end_marker, start) + len(end_marker)
    return full_script[start:end]


def _extract_function(full_script, signature):
    """Extract one self-contained ``function NAME(...) { ... }`` statement
    by brace-matching from its signature, regardless of what (if anything)
    encloses it in the real source. This is deliberately name-based, not
    scope-aware -- see the module docstring for why that limits what this
    style of extraction alone can prove."""
    start = full_script.index(signature)
    # Skip past the parameter list first (paren-matching), since a default
    # parameter value such as `options = {}` contains its own balanced
    # brace pair before the function body's own opening brace even begins.
    paren_depth = 0
    i = full_script.index("(", start)
    while True:
        ch = full_script[i]
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
            if paren_depth == 0:
                break
        i += 1
    depth = 0
    i = full_script.index("{", i)
    while True:
        ch = full_script[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return full_script[start : i + 1]
        i += 1


class ScopeRegressionGuardTests(unittest.TestCase):
    """A targeted, zero-dependency guard against reverting the #850 fix by
    moving these declarations back inside the ``loadConfig().then()``
    callback they were extracted from."""

    @classmethod
    def setUpClass(cls):
        cls.script = _extract_script()

    def test_structured_field_and_actionable_error_helpers_precede_load_config_then(
        self,
    ):
        then_pos = self.script.index("loadConfig().then(() => {")
        for signature in (
            "function structuredFieldsForType(",
            "function renderStructuredFields(",
            "function renderStatusStateField(",
            "function syncStatusStateMode(",
            "function _structuredDetails(",
            "function actionableErrorText(",
            "function showActionableError(",
            "function renderActionableError(",
        ):
            with self.subTest(signature=signature):
                pos = self.script.index(signature)
                self.assertLess(
                    pos,
                    then_pos,
                    f"{signature.strip('(')} must be declared before "
                    "loadConfig().then(...) so it stays reachable from "
                    "top-level code such as drawerEdit() in "
                    "web_assets_js_12.js (#850)",
                )

    def test_each_helper_is_declared_exactly_once(self):
        # A stray leftover copy inside the then-callback (a half-applied
        # revert) would satisfy the "declared before" check above via its
        # first occurrence while still shadowing nothing -- but a second,
        # nested copy is itself a sign of a broken revert/merge.
        for signature in (
            "function renderStructuredFields(",
            "function _structuredDetails(",
            "function syncStatusStateMode(",
            "function showActionableError(",
        ):
            with self.subTest(signature=signature):
                self.assertEqual(1, self.script.count(signature))


_HARNESS = r"""
%s

// ---- minimal DOM stub sufficient to drive the extracted functions ----
function decodeEntities(s) {
  return String(s)
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'");
}
const VOID_TAGS = new Set(["input", "br", "hr", "img", "meta", "link"]);
const idRegistry = {};
function registerId(id, el) { if (id) idRegistry[id] = el; }
function unregisterTree(el) {
  if (!el) return;
  if (el.id && idRegistry[el.id] === el) delete idRegistry[el.id];
  for (const c of el.children) unregisterTree(c);
}
function parseAttrs(str) {
  const attrs = {};
  const re = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)(?:\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
  let m;
  while ((m = re.exec(str || ""))) {
    const name = m[1];
    const raw = m[3] !== undefined ? m[3] : m[4] !== undefined ? m[4] : m[5] !== undefined ? m[5] : "";
    attrs[name] = m[2] === undefined ? "" : decodeEntities(raw);
  }
  return attrs;
}
class FakeElement {
  constructor(tag) {
    this.tagName = String(tag || "div").toUpperCase();
    this.id = "";
    this._attrs = {};
    this.children = [];
    this.parentNode = null;
    this._value = undefined;
    this.textContent = "";
    this.disabled = false;
    this.required = false;
    this.hidden = false;
    this.style = {};
    this.dataset = {};
    this._listeners = {};
    this._innerHTML = "";
  }
  get value() {
    if (this._value !== undefined) return this._value;
    if (this.tagName === "SELECT") {
      const selected = this.children.find(c => c.tagName === "OPTION" && "selected" in c._attrs);
      const chosen = selected || this.children.find(c => c.tagName === "OPTION");
      if (!chosen) return "";
      return chosen._attrs.value !== undefined ? chosen._attrs.value : chosen.textContent;
    }
    if (this.tagName === "TEXTAREA") return this.textContent;
    return this._attrs.value !== undefined ? this._attrs.value : "";
  }
  set value(v) { this._value = v; }
  getAttribute(name) { return this._attrs[name]; }
  setAttribute(name, value) { this._attrs[name] = value; if (name === "id") { this.id = value; registerId(value, this); } }
  hasAttribute(name) { return name in this._attrs; }
  addEventListener(type, fn) { (this._listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) {
    const list = this._listeners[type];
    if (list) this._listeners[type] = list.filter(f => f !== fn);
  }
  dispatchEvent(evt) {
    evt.target = evt.target || this;
    for (const fn of (this._listeners[evt.type] || [])) fn(evt);
    return true;
  }
  matches(selector) { return matchesSimpleSelector(this, selector); }
  closest(selector) {
    let el = this;
    while (el) { if (matchesSimpleSelector(el, selector)) return el; el = el.parentNode; }
    return null;
  }
  querySelector(selector) { return findDescendants(this, selector)[0] || null; }
  querySelectorAll(selector) { return findDescendants(this, selector); }
  focus() { this._focused = true; }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(html) {
    unregisterTree({children: this.children});
    this._innerHTML = html;
    this.children = parseHTML(html, this);
  }
}
function matchesSimpleSelector(el, selector) {
  const sel = String(selector || "").trim();
  const attrMatch = /^\[([a-zA-Z0-9_-]+)(?:=(.*))?\]$/.exec(sel);
  if (attrMatch) {
    const [, name, rawValue] = attrMatch;
    if (!(name in el._attrs)) return false;
    if (rawValue === undefined) return true;
    const expected = rawValue.replace(/^["']|["']$/g, "");
    return el._attrs[name] === expected;
  }
  if (sel.startsWith("#")) return el.id === sel.slice(1);
  return el.tagName === sel.toUpperCase();
}
function findDescendants(root, selector) {
  const out = [];
  const walk = el => {
    for (const c of el.children) {
      if (matchesSimpleSelector(c, selector)) out.push(c);
      walk(c);
    }
  };
  walk(root);
  return out;
}
function parseHTML(html, parentHint) {
  const root = new FakeElement("root");
  const stack = [root];
  const tagRe = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:[^<>"']|"[^"]*"|'[^']*')*?)\/?>/g;
  let lastIndex = 0;
  let m;
  while ((m = tagRe.exec(html))) {
    const textBefore = html.slice(lastIndex, m.index);
    if (textBefore) stack[stack.length - 1].textContent += decodeEntities(textBefore);
    lastIndex = tagRe.lastIndex;
    const closing = m[1] === "/";
    const tagName = m[2].toUpperCase();
    if (closing) {
      for (let i = stack.length - 1; i >= 1; i--) {
        if (stack[i].tagName === tagName) { stack.length = i; break; }
      }
      continue;
    }
    const selfClosing = /\/\s*$/.test(m[0].slice(0, -1)) || VOID_TAGS.has(tagName.toLowerCase());
    const el = new FakeElement(tagName);
    el._attrs = parseAttrs(m[3]);
    if (el._attrs.id) { el.id = el._attrs.id; registerId(el._attrs.id, el); }
    for (const k of Object.keys(el._attrs)) {
      if (k.startsWith("data-")) {
        const camel = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        el.dataset[camel] = el._attrs[k];
      }
    }
    el.disabled = "disabled" in el._attrs;
    el.required = "required" in el._attrs;
    el.hidden = "hidden" in el._attrs;
    const parent = stack[stack.length - 1];
    el.parentNode = parent === root ? (parentHint || null) : parent;
    parent.children.push(el);
    if (!selfClosing) stack.push(el);
  }
  const trailing = html.slice(lastIndex);
  if (trailing) stack[stack.length - 1].textContent += decodeEntities(trailing);
  return root.children;
}

global.document = { getElementById: id => idRegistry[id] || null };
global.appConfig = { ids: { key: "id" } };
global.t = value => value;
let toasts = [];
global.showToast = (message, type, duration) => { toasts.push({message, type, duration}); };
let apiCalls = [];
let apiImpl = async () => ({});
global.api = async (path, options) => {
  apiCalls.push({ path, method: options && options.method, body: options && options.body ? JSON.parse(options.body) : null });
  return apiImpl(path, options);
};
let currentItems = [];
global.currentItems = currentItems;
let refreshCalls = 0;
global.refreshAll = async () => { refreshCalls += 1; };
let openedDrawerItems = [];
global.openDrawer = item => { openedDrawerItems.push(item); };
global.setupCompletion = () => {};

const drawerHeadBtns = new FakeElement("div");
registerId("drawer-head-btns", drawerHeadBtns);
const drawerBody = new FakeElement("div");
registerId("drawer-body", drawerBody);
const toastContainer = new FakeElement("div");
registerId("toast-container", toastContainer);

let drawerItem = null;
let drawerEditing = false;
Object.defineProperty(global, "drawerItem", { get: () => drawerItem, set: v => { drawerItem = v; } });
Object.defineProperty(global, "drawerEditing", { get: () => drawerEditing, set: v => { drawerEditing = v; } });

const results = {};

function fillDrawerEditField(id, value) {
  const el = document.getElementById(id);
  el.value = value;
}

// -- Edit on an ordinary editable Task record ---------------------------
drawerItem = { line: 1, editable: true, status: "[ ]", type: "T", title: "Buy milk", details: { project: ["home"], priority: ["normal"] } };
drawerEdit();
results.head_btns_after_edit = drawerHeadBtns.innerHTML;
results.title_input_exists = !!document.getElementById("drawer-edit-title");
results.title_input_value = document.getElementById("drawer-edit-title")?.value;
results.status_select_exists = !!document.getElementById("drawer-edit-status");
results.due_field_exists = !!document.getElementById("drawer-edit-due");
results.project_field_value = document.getElementById("drawer-edit-project")?.value;
results.priority_field_value = document.getElementById("drawer-edit-priority")?.value;

// -- Change title + structured field, then Save --------------------------
fillDrawerEditField("drawer-edit-title", "Buy milk and eggs");
fillDrawerEditField("drawer-edit-due", "2026-03-03");
apiCalls = []; toasts = []; refreshCalls = 0; openedDrawerItems = [];
currentItems.push({ line: 1, editable: true, title: "Buy milk and eggs" });
await drawerSaveEdit();
results.save_call = apiCalls[0];
results.save_toast = toasts[0];
results.save_reopened = openedDrawerItems[0];
results.refresh_calls_after_save = refreshCalls;

// -- Custom/raw detail keys survive a save that only touches structured fields --
drawerItem = { line: 2, editable: true, status: "[ ]", type: "T", title: "Write report", details: { due: ["2026-01-01"], custom_key: ["kept"] } };
drawerEdit();
apiCalls = [];
await drawerSaveEdit();
results.custom_detail_preserved = apiCalls[0].body.details.custom_key;

// -- Type S: standard vs custom status/presence value ---------------------
drawerItem = { line: 3, editable: true, status: "[ ]", type: "S", title: "Focus", details: { state: ["working"] } };
global.standardStatusStates = () => ["working", "available", "busy"];
global.statusStateLabel = s => s;
drawerEdit();
results.status_state_select_exists = !!document.getElementById("drawer-edit-status-state");
results.status_state_select_value = document.getElementById("drawer-edit-status-state")?.value;
results.status_state_custom_hidden = document.getElementById("drawer-edit-structured-fields")?.querySelector("[data-status-state-custom-row]")?.hidden;
apiCalls = [];
await drawerSaveEdit();
results.standard_state_payload = apiCalls[0].body.details.state;

// custom mode: select "Custom..." and type a value
document.getElementById("drawer-edit-status-state").value = "__custom__";
document.getElementById("drawer-edit-status-state-custom").value = "in a meeting";
apiCalls = [];
await drawerSaveEdit();
results.custom_state_payload = apiCalls[0].body.details.state;

// -- Cancel: no mutation, drawer reopens on the original item -------------
drawerItem = { line: 4, editable: true, status: "[ ]", type: "T", title: "Cancel me", details: {} };
apiCalls = []; openedDrawerItems = [];
drawerEdit();
fillDrawerEditField("drawer-edit-title", "Should not be saved");
drawerCancelEdit();
results.cancel_made_no_api_call = apiCalls.length === 0;
results.cancel_reopened_original = openedDrawerItems[0] === drawerItem;
results.cancel_cleared_editing_flag = drawerEditing === false;

// -- Read-only record: Edit refuses and never touches drawer-body --------
drawerBody.innerHTML = "<div>original overview</div>";
drawerItem = { line: 5, editable: false, status: "[ ]", type: "T", title: "Read only", details: {} };
toasts = [];
drawerEdit();
results.readonly_refused_toast = toasts[0];
results.readonly_body_unchanged = drawerBody.innerHTML;

// -- Missing title fails loudly before any API call -----------------------
drawerItem = { line: 6, editable: true, status: "[ ]", type: "T", title: "Needs title", details: {} };
drawerEdit();
fillDrawerEditField("drawer-edit-title", "   ");
apiCalls = []; toasts = [];
await drawerSaveEdit();
results.missing_title_no_api_call = apiCalls.length === 0;
results.missing_title_toast = toasts[0];

process.stdout.write(JSON.stringify(results));
"""


class DrawerEditInteractionTests(unittest.TestCase):
    """Drives the real ``drawerEdit``/``drawerSaveEdit``/``drawerCancelEdit``
    against a small hand-rolled DOM, exercising the actual dynamic element
    IDs the drawer editor creates rather than the underlying structured-
    authoring helpers in isolation."""

    @classmethod
    def setUpClass(cls):
        full_script = _extract_script()
        pieces = [
            _extract_function(full_script, "function structuredFieldsForType("),
            _extract_function(full_script, "function renderStructuredFields("),
            _extract_function(full_script, "function renderStatusStateField("),
            _extract_function(full_script, "function syncStatusStateMode("),
            _extract_function(full_script, "function _structuredDetails("),
            _extract_function(full_script, "function actionableErrorText("),
            _extract_function(full_script, "function showActionableError("),
            _extract_function(full_script, "function renderActionableError("),
            _extract_function(full_script, "function escapeHtml("),
            _extract_function(full_script, "function jsLiteral("),
            _extract_function(full_script, "function detailsToText("),
            _extract_function(full_script, "function parseDetails("),
            _extract_statement(
                full_script, "const STRUCTURED_COMMON_FIELDS = [", "\n    ];"
            ),
            _extract_function(full_script, "function drawerEdit("),
            _extract_function(full_script, "function drawerCancelEdit("),
            _extract_function(full_script, "async function drawerSaveEdit("),
        ]
        cls.snippet = "\n".join(pieces)

    def _run(self):
        script = "async function main() {\n%s\n}\nmain();" % (_HARNESS % self.snippet)
        proc = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_edit_renders_an_editable_form_with_the_current_values(self):
        results = self._run()
        self.assertIn("Save", results["head_btns_after_edit"])
        self.assertIn("Cancel", results["head_btns_after_edit"])
        self.assertTrue(results["title_input_exists"])
        self.assertEqual("Buy milk", results["title_input_value"])
        self.assertTrue(results["status_select_exists"])
        self.assertTrue(results["due_field_exists"])
        self.assertEqual("home", results["project_field_value"])
        self.assertEqual("normal", results["priority_field_value"])

    def test_save_sends_one_put_with_the_edited_title_and_structured_field(self):
        results = self._run()
        call = results["save_call"]
        self.assertEqual("/api/items/1", call["path"])
        self.assertEqual("PUT", call["method"])
        self.assertEqual("Buy milk and eggs", call["body"]["title"])
        self.assertEqual(["2026-03-03"], call["body"]["details"]["due"])
        self.assertEqual("success", results["save_toast"]["type"])
        self.assertEqual(1, results["refresh_calls_after_save"])
        self.assertEqual(1, results["save_reopened"]["line"])

    def test_custom_detail_key_is_preserved_across_a_structured_field_edit(self):
        results = self._run()
        self.assertEqual(["kept"], results["custom_detail_preserved"])

    def test_status_type_standard_and_custom_state_round_trip(self):
        results = self._run()
        self.assertTrue(results["status_state_select_exists"])
        self.assertEqual("working", results["status_state_select_value"])
        self.assertTrue(results["status_state_custom_hidden"])
        self.assertEqual(["working"], results["standard_state_payload"])
        self.assertEqual(["in a meeting"], results["custom_state_payload"])

    def test_cancel_makes_no_api_call_and_reopens_the_original_record(self):
        results = self._run()
        self.assertTrue(results["cancel_made_no_api_call"])
        self.assertTrue(results["cancel_reopened_original"])
        self.assertTrue(results["cancel_cleared_editing_flag"])

    def test_read_only_record_refuses_edit_and_leaves_the_drawer_untouched(self):
        results = self._run()
        self.assertEqual("warning", results["readonly_refused_toast"]["type"])
        self.assertEqual("<div>original overview</div>", results["readonly_body_unchanged"])

    def test_blank_title_fails_loudly_before_any_save_request(self):
        results = self._run()
        self.assertTrue(results["missing_title_no_api_call"])
        self.assertEqual("warning", results["missing_title_toast"]["type"])


if __name__ == "__main__":
    unittest.main()
