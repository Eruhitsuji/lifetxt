"""Node.js-driven behavioral tests for the Web UI's structured common-field
authoring JavaScript (#776): `renderStructuredFields`/`structuredFieldsForType`
/`_structuredDetails` in `lifetxt/web_assets_js_18.js`.

These functions are a presentation adapter only: they read/write the same
Details object the plain textarea already edits, so this suite confirms the
merge/round-trip behavior rather than any new authoritative data model.

Extracts the real assembled Web UI script from `lifetxt.web_assets.HTML_PAGE`
(the same source served to a browser) and drives it under Node with a small
DOM stub -- no headless browser dependency, matching this project's
established pattern (tests/test_beginner_authoring_mode_js.py). Skips
gracefully when `node` is not on PATH.
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
    detailsToText = _extract_block(
        full_script, "function detailsToText", "function parseDetails"
    )
    parseDetails = _extract_block(
        full_script, "function parseDetails", "function query"
    )
    escapeHtml = _extract_block(
        full_script, "function escapeHtml", "function jsLiteral"
    )
    statusStates = _extract_block(
        full_script,
        "function standardStatusStates",
        "function setupQuickPresencePicker",
    )
    structured = _extract_block(
        full_script,
        "const STRUCTURED_COMMON_FIELDS",
        "function _populateStructuredFields",
    )
    return (
        detailsToText
        + "\n"
        + parseDetails
        + "\n"
        + escapeHtml
        + "\n"
        + statusStates
        + "\n"
        + structured
    )


def _extract_block(full_script, start_marker, end_marker):
    start = full_script.index(start_marker)
    end = full_script.index(end_marker, start)
    return full_script[start:end]


_HARNESS = """
%s

const elements = {};
const appConfig = {status_states: ["available", "busy", "focus"]};
global.document = {
  getElementById: (id) => elements[id] || null,
};

const results = {};

// -- structuredFieldsForType ---------------------------------------------
results.task_fields = structuredFieldsForType("T").map(f => f.key);
results.event_fields = structuredFieldsForType("E").map(f => f.key);

// -- renderStructuredFields ------------------------------------------------
results.render_task_html = renderStructuredFields("edit", {due: ["2026-01-01"]}, "T");
results.render_escapes_hostile_value = renderStructuredFields("edit", {project: ['"><img>']}, "T");
results.render_standard_status = renderStructuredFields("edit", {state: ["busy"]}, "S");
results.render_custom_status = renderStructuredFields("edit", {state: ["Deep research"]}, "S");
results.render_non_status = renderStructuredFields("edit", {state: ["busy"]}, "T");

// -- _structuredDetails: input fields win over the textarea, blank clears --
elements["edit-details"] = {value: "due:2026-01-01\\nproject:old\\n"};
elements["edit-due"] = {value: "2099-12-31"};
elements["edit-project"] = {value: ""};
results.merge_overrides_and_clears = _structuredDetails("edit-details", "edit");

// -- comma-separated values become a repeated detail list ------------------
elements["edit-details"] = {value: ""};
elements["edit-tag"] = {value: "a, b ,c"};
results.comma_splits_into_list = _structuredDetails("edit-details", "edit");

// -- a field with no matching input element is left from the textarea ------
elements["edit-details"] = {value: "priority:high\\n"};
results.no_matching_input_preserved = _structuredDetails("edit-details", "edit");

// -- Status state selector: selected mode is authoritative ----------------
const stateSelect = {value: "focus"};
const customInput = {value: "Deep research"};
elements["edit-type"] = {value: "S"};
elements["structured-fields"] = {querySelector: selector =>
  selector === "[data-status-state-select]" ? stateSelect :
  selector === "[data-status-state-custom]" ? customInput : null};
elements["edit-details"] = {value: "state:busy\\nperson:self\\n"};
results.standard_precedence = _structuredDetails("edit-details", "edit");
stateSelect.value = "__custom__";
results.custom_precedence = _structuredDetails("edit-details", "edit");
customInput.value = "";
results.empty_custom = _structuredDetails("edit-details", "edit");

// -- switching modes changes visibility/authority without clearing text ----
const modeInput = {value: "Keep me", disabled: false, required: false, setAttribute: () => {}};
const modeRow = {hidden: false};
const modeSelect = {value: "busy"};
const modeContainer = {querySelector: selector =>
  selector === "[data-status-state-select]" ? modeSelect :
  selector === "[data-status-state-custom]" ? modeInput :
  selector === "[data-status-state-custom-row]" ? modeRow : null};
syncStatusStateMode(modeContainer);
results.standard_mode = {value: modeInput.value, hidden: modeRow.hidden, disabled: modeInput.disabled, required: modeInput.required};
modeSelect.value = "__custom__";
syncStatusStateMode(modeContainer);
results.custom_mode = {value: modeInput.value, hidden: modeRow.hidden, disabled: modeInput.disabled, required: modeInput.required};

console.log(JSON.stringify(results));
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class StructuredFieldAuthoringJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        full_script = _extract_script()
        functions = _extract_functions_under_test(full_script)
        harness = _HARNESS % functions
        proc = subprocess.run(
            ["node", "-e", harness],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)
        cls.results = json.loads(proc.stdout)

    def test_fields_are_scoped_by_item_type(self):
        # due/priority/progress are Task-relevant but not Event-relevant;
        # project/tag apply to any kind (types: null).
        self.assertIn("due", self.results["task_fields"])
        self.assertIn("priority", self.results["task_fields"])
        self.assertNotIn("due", self.results["event_fields"])
        self.assertIn("on", self.results["event_fields"])
        self.assertIn("project", self.results["event_fields"])

    def test_render_produces_one_labeled_input_per_applicable_field(self):
        html = self.results["render_task_html"]
        self.assertIn('id="edit-due"', html)
        self.assertIn('value="2026-01-01"', html)
        self.assertIn('data-structured-key="due"', html)

    def test_render_escapes_a_hostile_detail_value(self):
        html = self.results["render_escapes_hostile_value"]
        self.assertNotIn("<img>", html)
        self.assertIn("&lt;img&gt;", html)

    def test_status_render_selects_standard_or_custom_and_is_type_scoped(self):
        standard = self.results["render_standard_status"]
        custom = self.results["render_custom_status"]
        self.assertIn('value="busy" selected', standard)
        self.assertIn('value="__custom__" selected', custom)
        self.assertIn('value="Deep research"', custom)
        self.assertNotIn("data-status-state-fields", self.results["render_non_status"])

    def test_status_standard_and_custom_precedence_is_deterministic(self):
        self.assertEqual(["focus"], self.results["standard_precedence"]["state"])
        self.assertEqual(["Deep research"], self.results["custom_precedence"]["state"])
        self.assertNotIn("state", self.results["empty_custom"])

    def test_switching_modes_preserves_custom_text_and_updates_validation(self):
        self.assertEqual("Keep me", self.results["standard_mode"]["value"])
        self.assertTrue(self.results["standard_mode"]["hidden"])
        self.assertTrue(self.results["standard_mode"]["disabled"])
        self.assertFalse(self.results["standard_mode"]["required"])
        self.assertEqual("Keep me", self.results["custom_mode"]["value"])
        self.assertFalse(self.results["custom_mode"]["hidden"])
        self.assertFalse(self.results["custom_mode"]["disabled"])
        self.assertTrue(self.results["custom_mode"]["required"])

    def test_input_value_overrides_the_textarea_and_blank_clears_the_key(self):
        details = self.results["merge_overrides_and_clears"]
        self.assertEqual(["2099-12-31"], details["due"])
        self.assertNotIn("project", details)

    def test_comma_separated_input_becomes_a_repeated_detail_list(self):
        details = self.results["comma_splits_into_list"]
        self.assertEqual(["a", "b", "c"], details["tag"])

    def test_a_field_with_no_input_element_is_preserved_from_the_textarea(self):
        # priority is a recognized structured field, but this fixture never
        # rendered an #edit-priority input for it (no such element exists);
        # the textarea's own value must not be silently dropped.
        details = self.results["no_matching_input_preserved"]
        self.assertEqual(["high"], details["priority"])


if __name__ == "__main__":
    unittest.main()
