"""Node.js-driven behavioral tests for the Web UI's canonical record deep
links (#838) and copy-link action (#839): the drawer-URL-sync helpers in
``lifetxt/web_assets_js_10.js``, the drawer-close URL cleanup in
``lifetxt/web_assets_js_12.js``, and the deep-link build/open/restore
helpers in ``lifetxt/web_assets_js_15.js``.

These functions implement no second record-detail UI or resolution engine:
they only decide which query parameter (``id`` -- the stable canonical
``id:``, or ``line`` as a fallback for id-less records) belongs in the URL
for a given record, and how to restore/close the drawer from that URL on
load, in-app navigation, and Back/Forward. Mirrors this project's
established "targeted Node.js run of the extracted function source"
verification style (tests/test_web_context_create_js.py).
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


def _extract_block(full_script, start_marker, end_marker):
    start = full_script.index(start_marker)
    end_anchor = full_script.index(end_marker, start)
    end = full_script.index("\n    }\n", end_anchor) + len("\n    }\n")
    return full_script[start:end]


def _extract_functions_under_test(full_script):
    url_sync = _extract_block(
        full_script, "function _drawerIdFor", "function syncDrawerUrlForItem"
    )
    close_drawer = _extract_block(
        full_script, "function closeDrawer", "function closeDrawer"
    )
    # openItemById/openItemByLine are deliberately NOT extracted here: the
    # harness stubs them via `global.openItemById =`/`global.openItemByLine
    # =` so syncDrawerFromUrl's own decision logic can be observed in
    # isolation. Including their real (async, api()-calling) bodies would
    # shadow those stubs, since a local function declaration in the same
    # snippet always wins over a `global.x` property for bare-identifier
    # lookups.
    share_and_restore = _extract_block(
        full_script, "function syncDrawerFromUrl", "function syncDrawerFromUrl"
    )
    build_link_start = full_script.index("function buildItemDeepLink")
    build_link_end_marker = (
        'function drawerShareLink() { copyItemDeepLink(drawerItem); }'
    )
    build_link_end = full_script.index(
        build_link_end_marker, build_link_start
    ) + len(build_link_end_marker)
    build_link = full_script[build_link_start:build_link_end]
    return "\n".join([url_sync, close_drawer, share_and_restore, build_link])


_HARNESS = """
%s

// ---- minimal DOM/global/URL stub for the functions under test ----
global.appConfig = { ids: { key: "id" } };
global.t = (s) => s;
const toasts = [];
global.showToast = (message, type) => { toasts.push({message, type}); };

let _href = "http://example.invalid/";
global.location = {
  get pathname() { return new URL(_href).pathname; },
  get search() { return new URL(_href).search; },
  get href() { return _href; },
  get origin() { return new URL(_href).origin; },
};
const historyLog = [];
global.history = {
  pushState: (_s, _t, url) => { historyLog.push(["push", url]); _href = new URL(url, _href).toString(); },
  replaceState: (_s, _t, url) => { historyLog.push(["replace", url]); _href = new URL(url, _href).toString(); },
};
global.URL = URL;
function query() { return new URLSearchParams(new URL(_href).search); }
global.query = query;

global.closeManagedModal = () => {};
global.openManagedModal = () => {};
global.document = { getElementById: () => null };
let drawerItem = null;
Object.defineProperty(global, "drawerItem", {
  get: () => drawerItem, set: (v) => { drawerItem = v; },
});

const opened = [];
global.openItemById = (id, urlMode) => { opened.push(["id", id, urlMode]); drawerItem = { id, line: null, details: {} }; };
global.openItemByLine = (line, urlMode) => { opened.push(["line", line, urlMode]); drawerItem = { line, details: {} }; };

let clipboardText = null;
let clipboardFails = false;
// Node itself defines a built-in, non-writable `navigator` global (Web
// Platform API compatibility), so `global.navigator = {...}` silently
// no-ops in sloppy mode instead of throwing. Patch the existing object's
// `clipboard` property in place rather than replacing the reference.
if (!global.navigator) global.navigator = {};
global.navigator.clipboard = {
  writeText: (text) => {
    if (clipboardFails) return Promise.reject(new Error("denied"));
    clipboardText = text;
    return Promise.resolve();
  },
};

const results = {};

// -- syncDrawerUrlForItem: opening a record by id sets ?id= -----------------
_href = "http://example.invalid/";
syncDrawerUrlForItem({ id: "task-001", line: 5 }, "push");
results.push_id_url = _href;
results.push_id_mode = historyLog[historyLog.length - 1][0];

// -- an id-less item falls back to ?line= ------------------------------------
_href = "http://example.invalid/";
syncDrawerUrlForItem({ line: 7, details: {} }, "push");
results.push_line_url = _href;

// -- urlMode "replace" never pushes a new history entry ----------------------
historyLog.length = 0;
_href = "http://example.invalid/";
syncDrawerUrlForItem({ id: "task-002", line: 1 }, "replace");
results.replace_mode = historyLog[historyLog.length - 1][0];

// -- urlMode "none" never touches the URL at all ------------------------------
_href = "http://example.invalid/?id=unrelated";
historyLog.length = 0;
syncDrawerUrlForItem({ id: "task-003", line: 1 }, "none");
results.none_mode_url = _href;
results.none_mode_no_history_calls = historyLog.length === 0;

// -- re-opening the already-current id is a no-op (no duplicate push) --------
_href = "http://example.invalid/?id=task-004";
historyLog.length = 0;
syncDrawerUrlForItem({ id: "task-004", line: 1 }, "push");
results.already_current_no_history_calls = historyLog.length === 0;

// -- closeDrawer removes id/line and never pushes a new entry ----------------
_href = "http://example.invalid/?id=task-005&preset=urgent";
drawerItem = { id: "task-005" };
historyLog.length = 0;
closeDrawer();
results.close_url = _href;
results.close_mode = historyLog[historyLog.length - 1][0];
results.close_drawer_item_cleared = drawerItem === null;

// -- closeDrawer("none") leaves the URL untouched (popstate restore) --------
_href = "http://example.invalid/";
historyLog.length = 0;
drawerItem = { id: "x" };
closeDrawer("none");
results.close_none_no_history_calls = historyLog.length === 0;

// -- buildItemDeepLink: canonical id wins over the line number ---------------
_href = "http://example.invalid/?theme=dark";
results.deep_link_id = buildItemDeepLink({ id: "task-006", line: 3 });
results.deep_link_id_preserves_unrelated_param = results.deep_link_id.url.includes("theme=dark");

// -- buildItemDeepLink: id-less item falls back to line ----------------------
results.deep_link_line = buildItemDeepLink({ line: 42, details: {} });

// -- buildItemDeepLink: no line, no id -> null -------------------------------
results.deep_link_none = buildItemDeepLink({ details: {} });

// -- copyItemDeepLink: success path writes the URL and announces it ---------
clipboardText = null; clipboardFails = false; toasts.length = 0;
copyItemDeepLink({ id: "task-007", line: 9 });
results.copy_success_toast_type = null; // filled after the microtask below

// -- copyItemDeepLink: no item selected fails immediately, no clipboard call -
toasts.length = 0;
copyItemDeepLink(null);
results.copy_no_item_toast = toasts[toasts.length - 1];

// -- syncDrawerFromUrl: ?id= reopens by id when not already showing it ------
_href = "http://example.invalid/?id=task-008";
opened.length = 0;
drawerItem = null;
syncDrawerFromUrl();
results.restore_by_id = opened[opened.length - 1];

// -- syncDrawerFromUrl: matching id already shown -> no reopen --------------
_href = "http://example.invalid/?id=task-009";
opened.length = 0;
drawerItem = { id: "task-009", details: {} };
syncDrawerFromUrl();
results.restore_already_shown_no_reopen = opened.length === 0;

// -- syncDrawerFromUrl: ?line= reopens by line -------------------------------
_href = "http://example.invalid/?line=12";
opened.length = 0;
drawerItem = null;
syncDrawerFromUrl();
results.restore_by_line = opened[opened.length - 1];

// -- syncDrawerFromUrl: no id/line param closes an open drawer silently -----
// closeDrawer is a real, locally-declared function in the extracted
// snippet (not a spy-able global), so observe its effect instead: the
// modal actually closes and it must not touch browser history (mode
// "none").
_href = "http://example.invalid/";
historyLog.length = 0;
let modalCloseCalls = 0;
global.closeManagedModal = () => { modalCloseCalls += 1; };
drawerItem = { id: "task-010" };
syncDrawerFromUrl();
results.restore_closes_when_no_param = modalCloseCalls === 1 && historyLog.length === 0;
results.restore_close_drawer_item_cleared = drawerItem === null;

Promise.resolve().then(() => {
  results.copy_success_url = clipboardText;
  results.copy_success_toast = toasts.find(x => x.message && x.message.includes("Link copied"));
  process.stdout.write(JSON.stringify(results));
});
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class DeepLinkJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        full_script = _extract_script()
        cls.snippet = _extract_functions_under_test(full_script)

    def _run(self):
        script = _HARNESS % self.snippet
        proc = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_opening_a_record_by_id_sets_the_id_query_parameter(self):
        results = self._run()
        self.assertIn("id=task-001", results["push_id_url"])
        self.assertNotIn("line=", results["push_id_url"])
        self.assertEqual("push", results["push_id_mode"])

    def test_id_less_item_falls_back_to_line(self):
        results = self._run()
        self.assertIn("line=7", results["push_line_url"])

    def test_replace_mode_never_pushes(self):
        results = self._run()
        self.assertEqual("replace", results["replace_mode"])

    def test_none_mode_never_touches_the_url(self):
        results = self._run()
        self.assertEqual("http://example.invalid/?id=unrelated", results["none_mode_url"])
        self.assertTrue(results["none_mode_no_history_calls"])

    def test_reopening_the_already_current_id_is_a_no_op(self):
        results = self._run()
        self.assertTrue(results["already_current_no_history_calls"])

    def test_close_drawer_removes_id_and_line_but_preserves_other_params(self):
        results = self._run()
        self.assertNotIn("id=", results["close_url"])
        self.assertIn("preset=urgent", results["close_url"])
        self.assertEqual("replace", results["close_mode"])
        self.assertTrue(results["close_drawer_item_cleared"])

    def test_close_drawer_none_mode_does_not_touch_history(self):
        results = self._run()
        self.assertTrue(results["close_none_no_history_calls"])

    def test_deep_link_prefers_canonical_id_and_preserves_other_params(self):
        results = self._run()
        self.assertIn("id=task-006", results["deep_link_id"]["url"])
        self.assertNotIn("line=", results["deep_link_id"]["url"])
        self.assertTrue(results["deep_link_id_preserves_unrelated_param"])
        self.assertEqual("id=task-006", results["deep_link_id"]["label"])

    def test_deep_link_falls_back_to_line_for_id_less_items(self):
        results = self._run()
        self.assertIn("line=42", results["deep_link_line"]["url"])
        self.assertEqual("line=42", results["deep_link_line"]["label"])

    def test_deep_link_is_null_with_no_id_and_no_line(self):
        results = self._run()
        self.assertIsNone(results["deep_link_none"])

    def test_copy_deep_link_with_no_selection_fails_without_touching_clipboard(self):
        results = self._run()
        self.assertEqual("error", results["copy_no_item_toast"]["type"])

    def test_copy_deep_link_success_writes_the_url_and_announces_it(self):
        results = self._run()
        self.assertIn("id=task-007", results["copy_success_url"])
        self.assertIsNotNone(results["copy_success_toast"])

    def test_restore_from_url_reopens_by_id_without_pushing_history(self):
        results = self._run()
        self.assertEqual(["id", "task-008", "none"], results["restore_by_id"])

    def test_restore_from_url_is_a_no_op_when_the_matching_id_is_already_shown(self):
        results = self._run()
        self.assertTrue(results["restore_already_shown_no_reopen"])

    def test_restore_from_url_reopens_by_line(self):
        results = self._run()
        self.assertEqual(["line", 12, "none"], results["restore_by_line"])

    def test_restore_from_url_closes_an_open_drawer_silently_when_no_param(self):
        results = self._run()
        self.assertTrue(results["restore_closes_when_no_param"])
        self.assertTrue(results["restore_close_drawer_item_cleared"])
