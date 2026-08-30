import datetime
import unittest

from lifetxt.parser import parse_text
from lifetxt.report_v2 import (
    ReportContext,
    ReportError,
    apply_scope,
    build_report_model,
    next_period,
    previous_period,
    redact_for_external_audience,
    render_html,
    render_json,
    render_markdown,
    resolve_period,
    validate_scope,
    validate_sections,
)

FIXTURE = """\
[x] T Buy milk done:2026-08-25 project:home
[ ] T Overdue task due:2026-08-20 project:work
[/] T In progress task project:work
[x] H Meditate done:2026-08-24
[ ] H Meditate
[x] J Reflection done:2026-08-24 body:"a good day" mood:good
"""


def _context(period="weekly", reference_date=None):
    items, _diag = parse_text(FIXTURE)
    reference_date = reference_date or datetime.date(2026, 8, 26)
    start, end = resolve_period(period, reference_date)
    return ReportContext(
        items,
        {},
        reference_date,
        period,
        start,
        end,
        "UTC",
    )


class PeriodMathTests(unittest.TestCase):
    def test_resolve_period_weekly_is_monday_to_sunday(self):
        start, end = resolve_period("weekly", datetime.date(2026, 8, 26))
        self.assertEqual(start, datetime.date(2026, 8, 24))
        self.assertEqual(end, datetime.date(2026, 8, 30))

    def test_previous_and_next_period_are_inverses(self):
        start, end = resolve_period("weekly", datetime.date(2026, 8, 26))
        prev_start, prev_end = previous_period("weekly", start, end)
        self.assertEqual(next_period("weekly", prev_start, prev_end), (start, end))

    def test_monthly_previous_period_crosses_year_boundary(self):
        start, end = resolve_period("monthly", datetime.date(2026, 1, 15))
        prev_start, prev_end = previous_period("monthly", start, end)
        self.assertEqual(prev_start, datetime.date(2025, 12, 1))
        self.assertEqual(prev_end, datetime.date(2025, 12, 31))

    def test_unsupported_period_raises(self):
        with self.assertRaises(ReportError):
            resolve_period("yearly", datetime.date(2026, 1, 1))


class SectionValidationTests(unittest.TestCase):
    def test_unknown_section_type_rejected(self):
        with self.assertRaises(ReportError):
            validate_sections([{"type": "not-a-real-section"}])

    def test_external_audience_rejects_unsafe_section_type(self):
        with self.assertRaises(ReportError):
            validate_sections([{"type": "review"}], audience="external")

    def test_external_audience_accepts_safe_section_type(self):
        validate_sections([{"type": "stats"}], audience="external")

    def test_empty_sections_rejected(self):
        with self.assertRaises(ReportError):
            validate_sections([])


class ScopeTests(unittest.TestCase):
    def test_none_scope_validates_to_empty_dict(self):
        self.assertEqual(validate_scope(None), {})

    def test_unknown_scope_key_rejected(self):
        with self.assertRaises(ReportError):
            validate_scope({"nope": "x"})

    def test_open_must_be_boolean(self):
        with self.assertRaises(ReportError):
            validate_scope({"open": "yes"})

    def test_list_or_string_fields_reject_other_types(self):
        with self.assertRaises(ReportError):
            validate_scope({"project": 123})

    def test_valid_scope_passes_through(self):
        scope = {"project": ["home"], "tag": "urgent", "open": True}
        self.assertEqual(validate_scope(scope), scope)

    def test_apply_scope_with_no_scope_returns_items_unchanged(self):
        items, _diag = parse_text(FIXTURE)
        self.assertEqual(apply_scope(items, {}), items)
        self.assertEqual(apply_scope(items, None), items)

    def test_apply_scope_filters_by_project(self):
        items, _diag = parse_text(FIXTURE)
        scoped = apply_scope(items, {"project": ["home"]})
        self.assertTrue(scoped)
        self.assertTrue(
            all("home" in item.details.get("project", []) for item in scoped)
        )

    def test_apply_scope_open_only(self):
        items, _diag = parse_text(FIXTURE)
        scoped = apply_scope(items, {"open": True})
        statuses = {item.status for item in scoped}
        self.assertNotIn("[x]", statuses)

    def test_apply_scope_combines_filters_with_and_semantics(self):
        items, _diag = parse_text(FIXTURE)
        scoped = apply_scope(items, {"project": ["work"], "open": True})
        for item in scoped:
            self.assertIn("work", item.details.get("project", []))
            self.assertNotEqual(item.status, "[x]")


class ProviderCompositionTests(unittest.TestCase):
    def test_review_provider_reuses_build_review(self):
        context = _context()
        model = build_report_model(
            "weekly-review",
            {"period": "weekly", "sections": [{"type": "review"}]},
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        section = model["sections"][0]
        self.assertEqual(section["type"], "review")
        self.assertEqual(section["data"]["completed_tasks"], 1)

    def test_stats_provider_reuses_build_stats(self):
        context = _context()
        model = build_report_model(
            "weekly-stats",
            {"period": "weekly", "sections": [{"type": "stats", "group": "daily"}]},
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        data = model["sections"][0]["data"]
        self.assertIn("tasks", data)
        self.assertEqual(data["tasks"]["done"], 1)

    def test_agenda_provider_next_period_range(self):
        context = _context()
        model = build_report_model(
            "weekly-agenda",
            {
                "period": "weekly",
                "sections": [{"type": "agenda", "range": "next-period"}],
            },
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        data = model["sections"][0]["data"]
        self.assertEqual(data["from"], "2026-08-31")

    def test_command_center_provider_matches_direct_call(self):
        from lifetxt.command_center import command_center

        context = _context()
        model = build_report_model(
            "daily-cc",
            {
                "period": "weekly",
                "sections": [{"type": "command-center", "horizon": 3}],
            },
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        direct = command_center(
            context.items, config={}, today=context.reference_date, horizon_days=3
        )
        self.assertEqual(model["sections"][0]["data"], direct)

    def test_next_actions_and_inbox_and_ticket_attention_providers_run(self):
        context = _context()
        model = build_report_model(
            "ops",
            {
                "period": "weekly",
                "sections": [
                    {"type": "next-actions"},
                    {"type": "inbox"},
                    {"type": "ticket-attention"},
                    {"type": "project-health"},
                    {"type": "health"},
                ],
            },
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        types = [s["type"] for s in model["sections"]]
        self.assertEqual(
            types,
            ["next-actions", "inbox", "ticket-attention", "project-health", "health"],
        )

    def test_unknown_section_type_raises_before_any_section_renders(self):
        context = _context()
        with self.assertRaises(ReportError):
            build_report_model(
                "bad",
                {"period": "weekly", "sections": [{"type": "nope"}]},
                context,
                datetime.datetime(2026, 8, 26, 9, 0),
            )


class ProjectHealthProviderTests(unittest.TestCase):
    """Regression coverage for #619: project-health nested portfolio() under a
    second "projects" key, so the Markdown/HTML renderer's `row.get(...)`
    calls iterated string keys ("count", "projects", "legend") instead of
    project row dicts, raising AttributeError.
    """

    def _single_project_context(self, count):
        lines = "".join("[ ] T Task %d project:solo\n" % i for i in range(count))
        items, _diag = parse_text(lines)
        reference_date = datetime.date(2026, 8, 26)
        start, end = resolve_period("weekly", reference_date)
        return ReportContext(items, {}, reference_date, "weekly", start, end, "UTC")

    def test_provider_returns_the_flat_row_list_from_portfolio(self):
        from lifetxt.projects import portfolio

        context = _context()
        model = build_report_model(
            "weekly-projects",
            {"period": "weekly", "sections": [{"type": "project-health"}]},
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        data = model["sections"][0]["data"]
        direct = portfolio(context.items, config={}, today=context.reference_date)
        self.assertEqual(data["projects"], direct["projects"])
        self.assertEqual(data["count"], direct["count"])
        self.assertEqual(data["legend"], direct["legend"])
        for row in data["projects"]:
            self.assertIsInstance(row, dict)

    def test_markdown_renders_multiple_projects_without_crashing(self):
        context = _context()
        model = build_report_model(
            "weekly-projects",
            {"period": "weekly", "sections": [{"type": "project-health"}]},
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        text = render_markdown(model)
        self.assertIn("home", text)
        self.assertIn("work", text)

    def test_html_renders_without_crashing(self):
        context = _context()
        model = build_report_model(
            "weekly-projects",
            {"period": "weekly", "sections": [{"type": "project-health"}]},
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        text = render_html(model)
        self.assertIn("home", text)

    def test_empty_portfolio_renders_placeholder(self):
        items, _diag = parse_text("[ ] T No project task\n")
        reference_date = datetime.date(2026, 8, 26)
        start, end = resolve_period("weekly", reference_date)
        context = ReportContext(items, {}, reference_date, "weekly", start, end, "UTC")
        model = build_report_model(
            "weekly-projects",
            {"period": "weekly", "sections": [{"type": "project-health"}]},
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        data = model["sections"][0]["data"]
        self.assertEqual(data["projects"], [])
        self.assertEqual(data["count"], 0)
        self.assertIn("No projects.", render_markdown(model))

    def test_one_project_renders_a_single_row(self):
        context = self._single_project_context(1)
        model = build_report_model(
            "weekly-projects",
            {"period": "weekly", "sections": [{"type": "project-health"}]},
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        data = model["sections"][0]["data"]
        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["projects"]), 1)
        self.assertIn("solo", render_markdown(model))

    def test_compare_previous_diffs_the_flat_count_field(self):
        context = _context()
        prev_start, prev_end = previous_period(
            context.period, context.period_start, context.period_end
        )
        previous_context = context.with_period(prev_start, prev_end)
        model = build_report_model(
            "weekly-projects",
            {
                "period": "weekly",
                "sections": [{"type": "project-health"}],
                "compare": "previous",
            },
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
            previous_context=previous_context,
        )
        # Must render successfully with a comparison attached, and must
        # never crash the way an unrendered comparison-only test would miss.
        render_markdown(model)
        compare = model["sections"][0]["compare"]
        self.assertEqual(
            compare,
            {"count": {"current": 2, "previous": 2, "delta": 0}},
        )


class ComparisonTests(unittest.TestCase):
    def test_previous_context_attaches_numeric_diff(self):
        context = _context()
        prev_start, prev_end = previous_period(
            context.period, context.period_start, context.period_end
        )
        previous_context = context.with_period(prev_start, prev_end)
        model = build_report_model(
            "weekly-review",
            {
                "period": "weekly",
                "sections": [{"type": "review"}],
                "compare": "previous",
            },
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
            previous_context=previous_context,
        )
        compare = model["sections"][0]["compare"]
        self.assertIn("completed_tasks", compare)
        self.assertEqual(compare["completed_tasks"]["current"], 1)

    def test_no_previous_context_means_no_compare_key_populated(self):
        context = _context()
        model = build_report_model(
            "weekly-review",
            {"period": "weekly", "sections": [{"type": "review"}]},
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        self.assertNotIn("compare", model["sections"][0])


class ExternalAudienceRedactionTests(unittest.TestCase):
    def test_redaction_drops_titles_and_replaces_lists_with_counts(self):
        redacted = redact_for_external_audience(
            {
                "completed_tasks": 3,
                "completed": [{"title": "secret"}, {"title": "other"}],
            }
        )
        self.assertEqual(redacted["completed_tasks"], 3)
        self.assertNotIn("completed", redacted)
        self.assertEqual(redacted["completed_count"], 2)

    def test_external_audience_end_to_end_never_leaks_task_titles(self):
        context = _context()
        model = build_report_model(
            "weekly-public",
            {
                "period": "weekly",
                "audience": "external",
                "sections": [{"type": "stats"}],
            },
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )
        rendered = render_json(model)
        self.assertNotIn("Buy milk", rendered)
        self.assertNotIn("Overdue task", rendered)


class RendererTests(unittest.TestCase):
    def _model(self):
        context = _context()
        return build_report_model(
            "weekly-review",
            {"period": "weekly", "sections": [{"type": "review"}, {"type": "stats"}]},
            context,
            datetime.datetime(2026, 8, 26, 9, 0),
        )

    def test_markdown_renderer_includes_section_titles_and_frontmatter(self):
        text = render_markdown(self._model())
        self.assertIn("report_schema: lifetxt-report-v2", text)
        self.assertIn("## Review", text)
        self.assertIn("## Statistics", text)
        self.assertIn("Completed tasks: 1", text)

    def test_json_renderer_round_trips_the_model(self):
        import json

        text = render_json(self._model())
        parsed = json.loads(text)
        self.assertEqual(parsed["report_schema"], "lifetxt-report-v2")
        self.assertEqual(len(parsed["sections"]), 2)

    def test_html_renderer_escapes_and_includes_sections(self):
        text = render_html(self._model())
        self.assertIn("<h1>", text)
        self.assertIn("Review", text)
        self.assertIn("Statistics", text)

    def test_renderers_never_call_a_provider_or_reparse(self):
        # A model built with a mutated items list must not change what the
        # renderer reads: renderers must not re-derive from context/items.
        model = self._model()
        text_before = render_markdown(model)
        model["sections"][0]["data"]["completed_tasks"] = 999
        text_after = render_markdown(model)
        self.assertNotEqual(text_before, text_after)
        self.assertIn("999", text_after)


if __name__ == "__main__":
    unittest.main()
