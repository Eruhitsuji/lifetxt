"""Node.js-driven behavioral tests for the Web UI's Native Timeline visual
explorer (#769): the rendering functions in `lifetxt/web_assets_js_11.js`
that turn `GET /api/native-timeline/{id}`'s existing temporal-timeline-v1
result into a grouped, scannable HTML panel.

These functions are pure presentation: they never parse history records,
recalculate ordering, or recompute completeness -- every fact rendered is
read directly from the shared result object, mirroring how #762's own
GET /api/native-timeline/{id} route (tests/test_web_native_timeline.py)
already proves the API/domain contract those facts come from.

Extracts the real assembled Web UI script from `lifetxt.web_assets.HTML_PAGE`
(the same source served to a browser) and drives it under Node with a small
stub -- no headless browser dependency, matching this project's established
pattern (tests/test_beginner_authoring_mode_js.py). Skips gracefully when
`node` is not on PATH.
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
    escape_html = _extract_block(
        full_script, "function escapeHtml", "function escapeHtml"
    )
    timeline_block = _extract_block(
        full_script,
        "let _ntCurrentItemId",
        "function clearNativeTimelineFilters",
    )
    return escape_html + "\n" + timeline_block


_HARNESS = """
%s

const results = {};

// -- nativeTimelineEventLabel -------------------------------------------
results.label_status_changed = nativeTimelineEventLabel({event: "status_changed", record_kind: "item_event"});
results.label_progress = nativeTimelineEventLabel({event: "progress_increment", record_kind: "progress_event"});
results.label_ticket = nativeTimelineEventLabel({event: "field_change", record_kind: "ticket_event"});
results.label_unknown = nativeTimelineEventLabel({event: "", record_kind: "time_entry"});

// -- nativeTimelineTransitionHtml ----------------------------------------
results.transition_status = nativeTimelineTransitionHtml({before_status: "[ ]", after_status: "[x]"});
results.transition_progress = nativeTimelineTransitionHtml({before_progress: "10%%", after_progress: "55%%"});
results.transition_progress_missing = nativeTimelineTransitionHtml({before_missing: true, after_progress: "20%%"});
results.transition_schedule = nativeTimelineTransitionHtml({field: "due", before: "2026-09-01", after: "2026-09-10", before_missing: false, after_missing: false});
results.transition_relation = nativeTimelineTransitionHtml({relation: "related", target: "t2"});
results.transition_none = nativeTimelineTransitionHtml({foo: "bar"});
results.transition_escapes = nativeTimelineTransitionHtml({before_status: "<img onerror=x>", after_status: "[x]"});

// -- nativeTimelineDateKey -------------------------------------------------
results.date_key = nativeTimelineDateKey("2026-09-12T10:20:00Z");
results.date_key_missing = nativeTimelineDateKey("");

// -- nativeTimelineProgressTrendHtml ---------------------------------------
results.trend_insufficient = nativeTimelineProgressTrendHtml([
  {record_kind: "progress_event", payload: {after_progress: "40%%"}},
]);
results.trend_present = nativeTimelineProgressTrendHtml([
  {record_kind: "progress_event", payload: {after_progress: "55%%"}},
  {record_kind: "progress_event", payload: {after_progress: "40%%"}},
]);
results.trend_ignores_fractions = nativeTimelineProgressTrendHtml([
  {record_kind: "progress_event", payload: {after_progress: "3/10"}},
  {record_kind: "progress_event", payload: {after_progress: "5/10"}},
]);

// -- renderNativeTimelinePanel ---------------------------------------------
results.panel_null = renderNativeTimelinePanel(null);

const complete = {
  complete: true,
  bounds: {returned_events: 2, total_valid_events: 2, truncated: false},
  limitations: [],
  invalid_events: [],
  diagnostics: [],
  events: [
    {record_kind: "item_event", record_id: "t1", event: "created", at: "2026-09-11T14:00:00Z", sequence: 1, transaction: "ITX-1", source_revision: "abc", payload: {item_kind: "T", item_title: "Thesis", after_status: "[ ]"}, valid: true},
    {record_kind: "item_event", record_id: "t1", event: "status_changed", at: "2026-09-12T09:30:00Z", sequence: 2, transaction: "ITX-2", source_revision: "def", payload: {before_status: "[ ]", after_status: "[/]"}, valid: true},
  ],
};
results.panel_complete = renderNativeTimelinePanel(complete);

const partial = {
  complete: false,
  bounds: {returned_events: 1, total_valid_events: 3, truncated: true},
  limitations: ["event_limit_truncated", "malformed_events_excluded"],
  invalid_events: [{record_kind: "item_event"}],
  diagnostics: [{severity: "warning", code: "W1", message: "oops"}],
  events: [
    {record_kind: "item_event", record_id: "t1", event: "created", at: "2026-09-11T14:00:00Z", sequence: 1, transaction: "ITX-1", source_revision: "abc", payload: {}, valid: true},
  ],
};
results.panel_partial = renderNativeTimelinePanel(partial);

const emptyEvents = {
  complete: true,
  bounds: {returned_events: 0, total_valid_events: 0, truncated: false},
  limitations: [],
  invalid_events: [],
  diagnostics: [],
  events: [],
};
results.panel_empty = renderNativeTimelinePanel(emptyEvents);

const escaping = {
  complete: true,
  bounds: {returned_events: 1, total_valid_events: 1, truncated: false},
  limitations: [],
  invalid_events: [],
  diagnostics: [],
  events: [
    {record_kind: "item_event", record_id: "t1", event: "<script>alert(1)</script>", at: "2026-09-12T09:30:00Z", sequence: 1, transaction: "ITX-1", source_revision: "abc", payload: {note: "<b>bold</b>"}, valid: true},
  ],
};
results.panel_escapes = renderNativeTimelinePanel(escaping);

process.stdout.write(JSON.stringify(results));
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class NativeTimelineVisualJsTests(unittest.TestCase):
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

    def test_event_domain_labels(self):
        results = self._run()
        self.assertEqual("Status changed", results["label_status_changed"])
        self.assertEqual("Progress increment", results["label_progress"])
        self.assertIn("Ticket", results["label_ticket"])
        self.assertEqual("time_entry", results["label_unknown"])

    def test_transition_payloads_render_before_after(self):
        results = self._run()
        self.assertIn("[ ]", results["transition_status"])
        self.assertIn("[x]", results["transition_status"])
        self.assertIn("→", results["transition_status"])
        self.assertIn("10%", results["transition_progress"])
        self.assertIn("55%", results["transition_progress"])
        self.assertIn("—", results["transition_progress_missing"])
        self.assertIn("due", results["transition_schedule"])
        self.assertIn("2026-09-01", results["transition_schedule"])
        self.assertIn("2026-09-10", results["transition_schedule"])
        self.assertIn("related", results["transition_relation"])
        self.assertIn("t2", results["transition_relation"])
        self.assertEqual("", results["transition_none"])

    def test_transition_escapes_values(self):
        results = self._run()
        self.assertNotIn("<img", results["transition_escapes"])
        self.assertIn("&lt;img", results["transition_escapes"])

    def test_date_grouping_key(self):
        results = self._run()
        self.assertEqual("2026-09-12", results["date_key"])
        self.assertEqual("Unknown date", results["date_key_missing"])

    def test_progress_trend_bounded_visual_indicator(self):
        results = self._run()
        self.assertEqual("", results["trend_insufficient"])
        self.assertIn("nt-progress-trend", results["trend_present"])
        # Fraction-form progress values (e.g. "3/10") are not rendered as a
        # bar-height trend; exact text remains available in the payload
        # details regardless, so this must not crash or fabricate a bar.
        self.assertEqual("", results["trend_ignores_fractions"])

    def test_panel_handles_missing_result(self):
        results = self._run()
        self.assertIn("unavailable", results["panel_null"])

    def test_panel_shows_completeness_state(self):
        results = self._run()
        self.assertIn("Complete history", results["panel_complete"])
        self.assertIn("Partial", results["panel_partial"])

    def test_panel_groups_events_by_day(self):
        results = self._run()
        html = results["panel_complete"]
        self.assertIn("2026-09-11", html)
        self.assertIn("2026-09-12", html)
        self.assertIn("nt-day-group", html)

    def test_panel_shows_limitations_and_diagnostics_prominently(self):
        results = self._run()
        html = results["panel_partial"]
        self.assertIn("nt-limitations", html)
        self.assertIn("truncated", html)
        self.assertIn("invalid event", html)
        self.assertIn("diagnostic", html)

    def test_panel_empty_state_is_intentional(self):
        results = self._run()
        self.assertIn("empty", results["panel_empty"])
        self.assertIn("yet", results["panel_empty"])

    def test_panel_bounds_summary_always_present(self):
        results = self._run()
        self.assertIn("2/2 event(s) returned", results["panel_complete"])
        self.assertIn("1/3 event(s) returned", results["panel_partial"])

    def test_panel_escapes_event_and_payload_text(self):
        results = self._run()
        html = results["panel_escapes"]
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<b>bold</b>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_filters_are_present_and_prefilled_from_state(self):
        results = self._run()
        # The filter inputs are part of every rendered panel (bounded
        # since/until/event/limit controls), including the "unavailable"
        # and empty states, so a user can always retry with different
        # bounds rather than being stuck.
        for key in ("panel_null", "panel_empty", "panel_complete", "panel_partial"):
            self.assertIn("nt-filter-since", results[key])
            self.assertIn("nt-filter-until", results[key])
            self.assertIn("nt-filter-event", results[key])
            self.assertIn("nt-filter-limit", results[key])


if __name__ == "__main__":
    unittest.main()
