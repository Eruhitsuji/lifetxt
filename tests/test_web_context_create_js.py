"""Node.js-driven behavioral tests for the Web UI's context-aware
related-item creation (#770): ``newItemWithContext``/``drawerCreateRelated``/
``newRelatedItemFromProject`` in ``lifetxt/web_assets_js_05.js``.

These functions never implement a second create/mutation engine: they only
populate the plain-text ``edit-details`` textarea the existing ``newItem()``/
``saveItem()`` flow already reads, before the user reviews and presses
Create. This mirrors this project's established "targeted Node.js run of
the extracted function source" verification style
(tests/test_beginner_authoring_mode_js.py) rather than booting a full
browser under Node.
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


def _extract_functions_under_test(full_script):
    start = full_script.index("function newItem()")
    end_anchor = full_script.index("function drawerCreateRelated")
    end = full_script.index("\n    }\n", end_anchor) + len("\n    }\n")
    return full_script[start:end]


_HARNESS = """
%s

// ---- minimal DOM/global stub for the functions under test ----
const elements = {};
function makeField(initial) {
  return { value: initial, textContent: "", disabled: false };
}
for (const id of [
  "editor-heading", "edit-status", "edit-type", "edit-title", "edit-details",
  "save-button", "delete-button", "editor-note",
]) {
  elements[id] = makeField("");
}
global.document = {
  getElementById: (id) => elements[id] || null,
};
global.openEditorModal = () => { global._openedModal = true; };
global.ensureBeginnerProfileVocabulary = () => {};
global.refreshAuthoringModeOptions = () => {};
global.renderItems = () => {};
global.setEditorDisabled = (disabled) => { for (const id of ["edit-status","edit-type","edit-title","edit-details","save-button"]) elements[id].disabled = disabled; };
global.currentItems = [];
const toasts = [];
global.showToast = (message, type) => { toasts.push({message, type}); };
let drawerClosed = false;
global.closeDrawer = () => { drawerClosed = true; };
global.appConfig = { ids: { key: "id" } };
let promptResponse = "related";
global.prompt = (message, defaultValue) => promptResponse;

const results = {};

// -- newItemWithContext: project only --------------------------------------
newItemWithContext({ project: "lifetxt" });
results.project_only_details = elements["edit-details"].value;
results.project_only_note = elements["editor-note"].textContent;

// -- newItemWithContext: relation only --------------------------------------
elements["edit-details"].value = "";
elements["editor-note"].textContent = "";
newItemWithContext({ relationField: "related", relationTarget: "t2" });
results.relation_only_details = elements["edit-details"].value;

// -- newItemWithContext: combined project + relation ------------------------
elements["edit-details"].value = "";
newItemWithContext({ project: "lifetxt", relationField: "parent", relationTarget: "t2" });
results.combined_details = elements["edit-details"].value;

// -- newItemWithContext: no context leaves the normal create form unchanged -
elements["edit-details"].value = "should-be-cleared";
elements["editor-note"].textContent = "stale";
newItemWithContext({});
results.no_context_details = elements["edit-details"].value;
results.no_context_note = elements["editor-note"].textContent;

// -- newRelatedItemFromProject -----------------------------------------------
elements["edit-details"].value = "";
newRelatedItemFromProject("research");
results.project_button_details = elements["edit-details"].value;
newRelatedItemFromProject("");
results.project_button_noop_details = elements["edit-details"].value; // unchanged by the empty call

// -- drawerCreateRelated: no drawer item -------------------------------------
global.drawerItem = null;
drawerCreateRelated();
results.no_item_toast = toasts[toasts.length - 1];

// -- drawerCreateRelated: item with no id -------------------------------------
toasts.length = 0;
global.drawerItem = { title: "No ID item", details: {} };
drawerCreateRelated();
results.no_id_toast = toasts[toasts.length - 1];

// -- drawerCreateRelated: happy path, default "related" ----------------------
toasts.length = 0;
drawerClosed = false;
elements["edit-details"].value = "";
global.drawerItem = { id: "t9", title: "Selected item", details: { project: ["work"] } };
promptResponse = "related";
drawerCreateRelated();
results.drawer_related_details = elements["edit-details"].value;
results.drawer_related_closed = drawerClosed;

// -- drawerCreateRelated: explicit "parent" choice ----------------------------
elements["edit-details"].value = "";
promptResponse = "parent";
drawerCreateRelated();
results.drawer_parent_details = elements["edit-details"].value;

// -- drawerCreateRelated: user cancels the prompt (null) -- no creation opened
toasts.length = 0;
elements["edit-details"].value = "unchanged";
global._openedModal = false;
promptResponse = null;
drawerCreateRelated();
results.cancel_details_unchanged = elements["edit-details"].value;
results.cancel_opened_modal = global._openedModal;

// -- drawerCreateRelated: invalid relation choice fails visibly, no silent rebind
toasts.length = 0;
elements["edit-details"].value = "unchanged2";
promptResponse = "bogus";
drawerCreateRelated();
results.invalid_relation_toast = toasts[toasts.length - 1];
results.invalid_relation_details_unchanged = elements["edit-details"].value;

process.stdout.write(JSON.stringify(results));
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class ContextAwareCreateJsTests(unittest.TestCase):
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

    def test_project_context_is_prefilled_and_visible(self):
        results = self._run()
        self.assertEqual("project:lifetxt", results["project_only_details"])
        self.assertIn("prefilled", results["project_only_note"])

    def test_relation_context_is_prefilled(self):
        results = self._run()
        self.assertEqual("related:t2", results["relation_only_details"])

    def test_combined_project_and_relation_context(self):
        results = self._run()
        lines = results["combined_details"].split("\n")
        self.assertIn("project:lifetxt", lines)
        self.assertIn("parent:t2", lines)

    def test_no_context_leaves_normal_create_unchanged(self):
        results = self._run()
        self.assertEqual("", results["no_context_details"])
        self.assertNotIn("prefilled", results["no_context_note"])

    def test_project_dashboard_button_prefills_project(self):
        results = self._run()
        self.assertEqual("project:research", results["project_button_details"])
        # Calling with an empty/falsy project is a deliberate no-op: it must
        # never clear or corrupt whatever the editor already holds.
        self.assertEqual(
            results["project_button_details"], results["project_button_noop_details"]
        )

    def test_no_drawer_item_fails_visibly(self):
        results = self._run()
        self.assertEqual("error", results["no_item_toast"]["type"])

    def test_missing_id_fails_visibly_rather_than_guessing(self):
        results = self._run()
        self.assertEqual("error", results["no_id_toast"]["type"])
        self.assertIn("id", results["no_id_toast"]["message"])

    def test_happy_path_prefills_relation_and_inherited_project(self):
        results = self._run()
        lines = results["drawer_related_details"].split("\n")
        self.assertIn("related:t9", lines)
        self.assertIn("project:work", lines)
        self.assertTrue(results["drawer_related_closed"])

    def test_explicit_parent_relation_choice_is_honored(self):
        results = self._run()
        self.assertIn("parent:t9", results["drawer_parent_details"].split("\n"))

    def test_cancelling_the_prompt_does_not_open_or_mutate_anything(self):
        results = self._run()
        self.assertEqual("unchanged", results["cancel_details_unchanged"])
        self.assertFalse(results["cancel_opened_modal"])

    def test_invalid_relation_choice_fails_visibly_no_silent_rebind(self):
        results = self._run()
        self.assertEqual("error", results["invalid_relation_toast"]["type"])
        self.assertIn("bogus", results["invalid_relation_toast"]["message"])
        self.assertEqual("unchanged2", results["invalid_relation_details_unchanged"])


if __name__ == "__main__":
    unittest.main()
