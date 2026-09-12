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
    structured = _extract_block(
        full_script,
        "const STRUCTURED_COMMON_FIELDS",
        "function _populateStructuredFields",
    )
    return detailsToText + "\n" + parseDetails + "\n" + escapeHtml + "\n" + structured


def _extract_block(full_script, start_marker, end_marker):
    start = full_script.index(start_marker)
    end = full_script.index(end_marker, start)
    return full_script[start:end]


_HARNESS = """
%s

const elements = {};
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
