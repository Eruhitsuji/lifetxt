import unittest

from lifetxt.parser import parse_text
from lifetxt.temporal_review import build_temporal_review
from lifetxt.timezone_policy import timezone_context


class TemporalReviewTests(unittest.TestCase):
    def test_empty_period_is_bounded_and_deterministic(self):
        items, diagnostics = parse_text('[ ] T "Open task" id:task-1\n')
        self.assertEqual([], diagnostics)
        result = build_temporal_review(
            items, since="2030-01-01", until="2030-01-07", limit=10
        )
        self.assertEqual("temporal-life-review-v1", result["schema"])
        self.assertEqual(0, result["counts"]["events"])
        self.assertEqual(1, result["counts"]["carry_forward"])

    def test_week_and_explicit_bounds_cannot_be_combined(self):
        items, _ = parse_text('[ ] T "Open task"\n')
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            build_temporal_review(items, since="2030-01-01", week=True)

    def test_date_bounds_use_workspace_timezone_when_requested(self):
        items, _ = parse_text('[ ] T "Open task"\n')
        result = build_temporal_review(
            items,
            since="2030-06-01",
            until="2030-06-01",
            timezone_name="Asia/Tokyo",
        )
        self.assertEqual("2030-06-01T00:00:00+09:00", result["period"]["since"])
        self.assertEqual("2030-06-01T23:59:59.999999+09:00", result["period"]["until"])

    def test_upcoming_due_on_and_spans_use_shared_order_and_limit(self):
        items, _ = parse_text(
            "[ ] E Later id:later on:2031-02-06\n"
            "[ ] T Due id:due due:2031-02-04\n"
            "[ ] E Span id:span from:2031-02-05T09:00Z to:2031-02-05T10:00Z\n"
            "[ ] E Past id:past on:2031-02-01\n"
        )
        with timezone_context("UTC"):
            result = build_temporal_review(
                items,
                since="2031-02-03",
                until="2031-02-03",
                limit=2,
                timezone_name="UTC",
            )
        self.assertEqual(["Due", "Span"], [row["title"] for row in result["upcoming"]])
        self.assertEqual([], result["completed"])
        self.assertFalse(result["complete"])

    def test_upcoming_includes_ongoing_span_under_agenda_overlap_semantics(self):
        items, _ = parse_text(
            "[ ] E Ongoing id:span from:2031-02-03T20:00Z to:2031-02-04T01:00Z\n"
            "[ ] E Finished id:past from:2031-02-03T20:00Z to:2031-02-03T21:00Z\n"
        )
        with timezone_context("UTC"):
            result = build_temporal_review(
                items, since="2031-02-03", until="2031-02-03", timezone_name="UTC"
            )
        self.assertEqual(["Ongoing"], [row["title"] for row in result["upcoming"]])

    def test_upcoming_recurring_rows_use_agenda_finite_expansion(self):
        from lifetxt.agenda import agenda_records
        from lifetxt.timeutil import parse_date_or_datetime
        import datetime

        items, _ = parse_text(
            "[ ] E Daily id:daily on:2031-02-04 repeat:daily at:09:00\n"
            "[ ] E Limited id:limited on:2031-02-05 "
            "repeat:RRULE:FREQ=DAILY;COUNT=3 at:10:00\n"
            "[ ] E Beyond id:beyond on:2033-02-04 repeat:daily at:11:00\n"
        )
        with timezone_context("UTC"):
            result = build_temporal_review(
                items, since="2031-02-03", until="2031-02-03", timezone_name="UTC"
            )
            rows = agenda_records(
                items,
                parse_date_or_datetime(result["period"]["until"], is_end=True),
                datetime.datetime.max,
            )
        self.assertEqual(
            ["Daily", "Limited"], [row["title"] for row in result["upcoming"]]
        )
        self.assertEqual(
            [row["when"] for row in rows], [row["when"] for row in result["upcoming"]]
        )
        # An infinite repeat expands only the existing Agenda 366-day horizon.
        self.assertGreater(len(rows[0]["matches"]), 1)
        self.assertLessEqual(len(rows[0]["matches"]), 367)

    def test_upcoming_offset_aware_points_respect_workspace_date_boundary(self):
        items, _ = parse_text(
            "[ ] E Before id:before at:2031-02-03T14:00:00Z\n"
            "[ ] E After id:after at:2031-02-03T15:00:00Z\n"
        )
        with timezone_context("Asia/Tokyo"):
            result = build_temporal_review(
                items,
                since="2031-02-03",
                until="2031-02-03",
                timezone_name="Asia/Tokyo",
            )
        self.assertEqual(["After"], [row["title"] for row in result["upcoming"]])

    def test_project_filter_restricts_upcoming_and_carry_forward(self):
        items, _ = parse_text(
            "[ ] T Work id:work project:Work due:2031-02-04\n"
            "[ ] T Home id:home project:Home due:2031-02-04\n"
        )
        with timezone_context("UTC"):
            result = build_temporal_review(
                items,
                since="2031-02-03",
                until="2031-02-03",
                project="Work",
                timezone_name="UTC",
            )
        for key in ("upcoming", "carry_forward"):
            self.assertEqual(["Work"], [row["title"] for row in result[key]])

    def test_native_history_is_evidence_not_a_current_agenda_or_task_target(self):
        from lifetxt.native_history import build_item_event

        items, _ = parse_text("[ ] T Work id:work due:2031-02-04\n")
        event = build_item_event(
            "work",
            "created",
            "2031-02-05T12:00:00Z",
            1,
            "ITX-work-1",
            "a" * 64,
            item_kind="T",
            item_title="Work",
            after_status="[ ]",
        )
        items.append(event)
        malformed = build_item_event(
            "work",
            "completed",
            "2031-02-05T13:00:00Z",
            2,
            "ITX-work-2",
            "a" * 64,
            before_status="[ ]",
            after_status="[x]",
        )
        malformed.details["custom"] = ["invalid"]
        malformed.title = "History_only"
        items.append(malformed)
        with timezone_context("UTC"):
            result = build_temporal_review(
                items, since="2031-02-03", until="2031-02-03", timezone_name="UTC"
            )
        for key in ("upcoming", "carry_forward"):
            self.assertEqual(["Work"], [row["title"] for row in result[key]])
        self.assertTrue(result["diagnostics"])
