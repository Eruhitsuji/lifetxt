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
        full_script, "function editorDetailValue", "function parseDetails"
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
    # STRUCTURED_COMMON_FIELDS/structuredFieldsForType/renderStructuredFields/
    # renderStatusStateField/syncStatusStateMode/_structuredDetails are
    # declared at true top level (#850), separately from
    # _populateStructuredFields/refreshStructuredFields (which stay inside
    # the loadConfig().then() callback), so they can no longer be pulled out
    # as one contiguous span the way they could when everything sat next to
    # each other in the same function scope. Extract each self-contained
    # declaration by name instead.
    structured_const = _extract_const(
        full_script, "const STRUCTURED_COMMON_FIELDS = [", "\n    ];"
    )
    structured_fns = "\n".join(
        _extract_function(full_script, signature)
        for signature in (
            "function structuredFieldsForType(",
            "function renderStructuredFields(",
            "function renderStatusStateField(",
            "function syncStatusStateMode(",
            "function _structuredDetails(",
        )
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
        + structured_const
        + "\n"
        + structured_fns
    )


def _extract_block(full_script, start_marker, end_marker):
    start = full_script.index(start_marker)
    end = full_script.index(end_marker, start)
    return full_script[start:end]


def _extract_const(full_script, start_marker, end_marker):
    start = full_script.index(start_marker)
    end = full_script.index(end_marker, start) + len(end_marker)
    return full_script[start:end]


def _extract_function(full_script, signature):
    """Extract one self-contained ``function NAME(...) { ... }`` statement
    by brace-matching from its signature, wherever it lives in the real
    source."""
    start = full_script.index(signature)
    # Skip past the parameter list first (paren-matching): a default
    # parameter value such as `options = {}` would otherwise look like the
    # function body's own (immediately self-closing) opening brace.
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


_HARNESS = """
%s

const elements = {};
const appConfig = {status_states: ["available", "busy", "focus", "meeting", "away", "commuting", "working", "offline", "sleeping"]};
const jaStateLabels = {
  available: "対応可能", busy: "取り込み中", focus: "集中", meeting: "会議中",
  away: "離席中", commuting: "移動中", working: "作業中",
  offline: "オフライン", sleeping: "睡眠中",
};
const t = value => value.startsWith("Status state: ") ? (jaStateLabels[value.slice(14)] || value) : value;
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
results.render_ui_word_custom_status = renderStructuredFields("edit", {state: ["review"]}, "S");
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

// Habit guidance: optional fields, verbatim punctuation and raw round trip.
const habit = {habit_cue: ["After breakfast, before work", "After lunch"], habit_minimum: ['"><img>']};
results.habit_editor = renderStructuredFields("edit", habit, "H");
results.habit_read_only = renderStructuredFields("edit", habit, "H", true);
results.habit_drawer = renderStructuredFields("drawer-edit", habit, "H");
elements["edit-details"].value = detailsToText({...habit, done: ["2026-01-01"]});
elements["edit-habit_cue"] = {value: habit.habit_cue.join(", ")};
elements["edit-habit_minimum"] = {value: "Read, then review one word"};
results.habit_merge = _structuredDetails("edit-details", "edit");
elements["edit-habit_cue"].value = "";
results.habit_cleared = _structuredDetails("edit-details", "edit");
delete elements["edit-habit_cue"];
delete elements["edit-habit_minimum"];

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

const jsonDetails = parseDetails(`tag:json<< ["a","b"] >>\noptions:json<<\n  [["a >> b","c"]]\n>>\nempty:json<< [] >>`);
results.json_details = parseDetails(detailsToText(jsonDetails));
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
            encoding="utf-8",
            timeout=30,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)
        cls.results = json.loads(proc.stdout)

    def test_json_values_roundtrip_in_the_details_editor(self):
        self.assertEqual(
            {"tag": ["a", "b"], "options": [["a >> b", "c"]], "empty": []},
            self.results["json_details"],
        )

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

    def test_habit_guidance_is_scoped_to_the_record_editor(self):
        html = self.results["habit_editor"]
        for key in ("habit_cue", "habit_minimum"):
            with self.subTest(key=key):
                self.assertIn(f'for="edit-{key}"', html)
                self.assertIn(f'aria-describedby="edit-{key}-help"', html)
                self.assertRegex(
                    self.results["habit_read_only"],
                    rf'<input id="edit-{key}"[^>]* disabled>',
                )
                self.assertNotIn(key, self.results["render_task_html"])
                self.assertNotIn(key, self.results["habit_drawer"])
        self.assertIn('value="After breakfast, before work, After lunch"', html)
        self.assertNotIn("<img>", html)
        self.assertIn("&lt;img&gt;", html)

    def test_habit_guidance_preserves_unchanged_values_and_literal_commas(self):
        merged = self.results["habit_merge"]
        self.assertEqual(
            ["After breakfast, before work", "After lunch"], merged["habit_cue"]
        )
        self.assertEqual(["Read, then review one word"], merged["habit_minimum"])
        self.assertEqual(["2026-01-01"], merged["done"])
        self.assertNotIn("habit_cue", self.results["habit_cleared"])

    def test_task_field_help_distinguishes_deadline_schedule_and_tags(self):
        html = self.results["render_task_html"]
        for key, text in (
            ("due", "Example: 2026-12-15."),
            ("do", "This can be earlier than its deadline."),
            ("tag", "Separate tags with commas"),
        ):
            with self.subTest(key=key):
                self.assertIn(f'aria-describedby="edit-{key}-help"', html)
                self.assertRegex(
                    html,
                    rf'<small id="edit-{key}-help" class="field-help-text">[^<]*{re.escape(text)}',
                )

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

    def test_status_options_localize_labels_but_keep_canonical_values(self):
        html = self.results["render_standard_status"]
        labels = {
            "available": "対応可能",
            "busy": "取り込み中",
            "focus": "集中",
            "meeting": "会議中",
            "away": "離席中",
            "commuting": "移動中",
            "working": "作業中",
            "offline": "オフライン",
            "sleeping": "睡眠中",
        }
        for state, label in labels.items():
            self.assertIn(f'value="{state}"', html)
            self.assertIn(f">{label}</option>", html)

    def test_custom_state_matching_a_ui_word_remains_verbatim(self):
        html = self.results["render_ui_word_custom_status"]
        self.assertIn('value="review"', html)
        self.assertNotIn('value="レビュー"', html)

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
