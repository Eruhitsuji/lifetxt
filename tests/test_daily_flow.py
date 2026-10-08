"""Behavioral contract and invariants for the shared Daily Flow engine (#1144)."""

import copy
import datetime as dt
import json
import os
import random
import tempfile
import unittest
from unittest.mock import patch

from lifetxt.daily_flow import build_daily_flow
from lifetxt.model import Item
from lifetxt.mutation import hash_bytes
from lifetxt.parser import parse_text
from lifetxt.timezone_policy import current_timezone_name, timezone_context


def items(text, source="work.txt"):
    result, diagnostics = parse_text(text)
    for item in result:
        item.source = source
    return result


def plan(text="", **kw):
    data = items(text) if isinstance(text, str) else text
    options = dict(
        date="2026-10-09",
        day_start="09:00",
        day_end="12:00",
        timezone="Asia/Tokyo",
        evaluated_at="2026-10-08T18:00+09:00",
        occupancy_complete=True,
    )
    options.update(kw)
    return build_daily_flow(data, **options)


def candidates(result):
    return [row for row in result["timeline"] if row["kind"] == "candidate"]


def reasons(result):
    return {row["item"]["id"]: row["reason"] for row in result["unplaced"]}


def codes(result):
    return {row["code"] for row in result["diagnostics"]}


TASK = "[ ] T Task id:t est:30m\n"
MEETING = "[ ] E Meeting id:e from:2026-10-09T10:00 to:2026-10-09T11:00\n"


class DailyFlowContractTests(unittest.TestCase):
    def test_documented_fixture_and_rest_after_final_task(self):
        result = plan(
            MEETING
            + "[ ] T A id:a priority:A due:2026-10-09 est:45m\n[ ] T B id:b priority:B due:2026-10-09 est:30m\n[ ] T C id:c priority:C due:2026-10-09 est:30m\n[ ] T Unknown id:u\n",
            policy={"break_minutes": 10, "buffer_minutes": 5},
        )
        self.assertEqual(["a", "b"], [r["item"]["id"] for r in candidates(result)])
        self.assertEqual(
            ["09:00", "11:00"], [r["start"][11:16] for r in candidates(result)]
        )
        self.assertEqual(
            {"c": "insufficient_capacity", "u": "missing_estimate"}, reasons(result)
        )
        self.assertEqual("11:45", result["timeline"][-1]["end"][11:16])
        self.assertEqual("partial", result["completeness"]["state"])
        self.assertEqual("certified", result["completeness"]["occupancy"])
        self.assertEqual("11:45", result["free"][0]["start"][11:16])

    def test_no_items_and_capacity_failure_are_complete(self):
        self.assertEqual("complete", plan()["completeness"]["state"])
        result = plan("[ ] T Large id:l est:8h\n")
        self.assertEqual("insufficient_capacity", reasons(result)["l"])
        self.assertEqual("complete", result["completeness"]["state"])

    def test_f1_recurring_suppresses_all_placements_preserves_known_fixed(self):
        result = plan(
            TASK
            + MEETING
            + "[ ] E Repeated id:r from:2025-01-01T09:00 to:2025-01-01T10:00 repeat:daily\n"
        )
        self.assertEqual([], candidates(result))
        self.assertIn("skipped_recurring", codes(result))
        self.assertIn("occupancy_unknown", codes(result))
        self.assertEqual("unknown", result["completeness"]["occupancy"])
        self.assertEqual("fixed", result["timeline"][0]["kind"])
        self.assertEqual([], result["free"])

    def test_f2_f19_all_day_and_on_at_preserve_legacy_occupancy(self):
        for suffix in ("", " at:10:00"):
            with self.subTest(suffix=suffix):
                result = plan(TASK + "[ ] E All id:e on:2026-10-09" + suffix + "\n")
                self.assertEqual([], candidates(result))
                self.assertEqual("insufficient_capacity", reasons(result)["t"])
                self.assertEqual("complete", result["completeness"]["state"])

    def test_f3_reminder_is_instant_event_has_unknown_duration(self):
        result = plan(TASK + "[ ] R Ping id:r at:2026-10-09T10:00\n")
        self.assertEqual(1, len(candidates(result)))
        self.assertEqual(1, len(result["instants"]))
        result = plan(TASK + "[ ] E Ping id:e at:2026-10-09T10:00\n")
        self.assertEqual([], candidates(result))
        self.assertIn("unknown_duration", codes(result))

    def test_f4_dst_day_even_valid_noon_window_is_blocked(self):
        for date, clock in (("2026-03-08", "02:30"), ("2026-11-01", "01:30")):
            for start in (clock, "09:00"):
                with self.subTest(date=date, start=start):
                    result = plan(
                        TASK,
                        date=date,
                        day_start=start,
                        timezone="America/New_York",
                        evaluated_at="2026-01-01T12:00Z",
                    )
                    self.assertEqual([], candidates(result))
                    self.assertIn("unsupported_timezone_window", codes(result))

    def test_f5_invalid_estimates_and_no_guessed_precision(self):
        for est, reason in (
            ("", "missing_estimate"),
            ("est:0m", "invalid_estimate"),
            ("est:-1m", "invalid_estimate"),
            ("est:90x", "invalid_estimate"),
            ("est:20m est:30m", "ambiguous_estimate"),
            ("est:999999999999999999h", "insufficient_capacity"),
        ):
            with self.subTest(est=est):
                result = plan("[ ] T Task id:t " + est + "\n")
                self.assertEqual(reason, reasons(result)["t"])
                self.assertEqual([], candidates(result))

    def test_f6_cross_file_context_does_not_schedule_archived_tasks_or_events(self):
        active = items(TASK.replace("est:30m", "est:30m depends_on:prereq"))
        context = items(
            "[x] T Previous id:prereq\n[ ] T Old id:old est:1h\n[ ] E Archived id:archived on:2026-10-09\n",
            source="old-week.txt",
        )
        result = plan(active, context_items=context)
        self.assertEqual(["t"], [r["item"]["id"] for r in candidates(result)])
        self.assertEqual("unresolved_dependency", reasons(plan(active))["t"])
        self.assertEqual([], result["instants"])

    def test_open_cycles_self_dependencies_and_inverse_blocks(self):
        for extra in ("depends_on:t", "blocks:t"):
            self.assertEqual(
                "unresolved_dependency",
                reasons(plan(TASK.replace("est:30m", "est:30m " + extra)))["t"],
            )
        result = plan(
            "[ ] T A id:a est:10m depends_on:b\n[ ] T B id:b est:10m depends_on:a\n"
        )
        self.assertEqual([], candidates(result))
        result = plan(TASK + "[ ] T Other id:o est:10m blocks:t\n")
        self.assertEqual("unresolved_dependency", reasons(result)["t"])

    def test_proposals_never_unlock_dependents(self):
        result = plan(TASK + "[ ] T Dependent id:d est:10m depends_on:t\n")
        self.assertEqual(["t"], [r["item"]["id"] for r in candidates(result)])
        self.assertEqual("unresolved_dependency", reasons(result)["d"])

    def test_f7_overlap_union_f19_touching_no_conflict(self):
        second = "[ ] E Second id:e2 from:2026-10-09T10:30 to:2026-10-09T11:30\n"
        result = plan(MEETING + second + "[ ] T Big id:t est:90m\n")
        self.assertEqual([], candidates(result))
        self.assertIn("conflict", codes(result))
        result = plan(MEETING + second.replace("10:30", "11:00") + TASK)
        self.assertNotIn("conflict", codes(result))

    def test_f8_f13_incomplete_invalid_nonpositive_missing_busy_details(self):
        fields = (
            "from:2026-10-09T09:00",
            "to:2026-10-09T10:00",
            "from:2026-10-09T10:00 to:2026-10-09T09:00",
            "from:2026-10-09T10:00 to:2026-10-09T10:00",
            "from:nonsense to:nonsense",
            "",
            "on:wrong",
            "at:wrong",
            "from:2026-10-09T09:00 from:2026-10-09T10:00 to:2026-10-09T11:00",
        )
        for value in fields:
            with self.subTest(value=value):
                result = plan(TASK + "[ ] E Unsafe id:e " + value + "\n")
                self.assertEqual([], candidates(result))
                self.assertEqual("blocked", result["completeness"]["state"])

    def test_complete_event_outside_window_is_irrelevant(self):
        result = plan(TASK + MEETING.replace("2026-10-09", "2026-09-09"))
        self.assertEqual(1, len(candidates(result)))
        self.assertEqual("complete", result["completeness"]["state"])

    def test_f9_duplicate_ids_missing_id_and_source_aliases(self):
        result = plan(items(TASK, "one.txt") + items(TASK, "two.txt"))
        self.assertIn("ambiguous_identity", codes(result))
        self.assertEqual([], candidates(result))
        result = plan("[ ] T Missing est:10m\n")
        self.assertEqual("missing_identity", result["unplaced"][0]["reason"])
        original = items(TASK, "folder/../work.txt")
        repeated = items(TASK, "work.txt")
        self.assertEqual(1, len(candidates(plan(original + repeated))))
        repeated[0].title = "Changed"
        self.assertIn("ambiguous_source", codes(plan(original + repeated)))

    def test_multiple_identity_values_block(self):
        self.assertIn(
            "ambiguous_identity", codes(plan(TASK.replace("id:t", "id:t id:t2")))
        )

    def test_missing_source_and_line_are_stable_and_preserve_event_references(self):
        data = [
            Item("[ ]", "T", "Task", {"id": "t", "est": "30m"}),
            Item(
                "[ ]",
                "E",
                "One",
                {"id": "e1", "from": "2026-10-09T10:00", "to": "2026-10-09T11:00"},
            ),
            Item(
                "[ ]",
                "E",
                "Two",
                {"id": "e2", "from": "2026-10-09T11:00", "to": "2026-10-09T12:00"},
            ),
        ]
        result = plan(data)
        self.assertEqual(
            ["e1", "e2"],
            [r["item"]["id"] for r in result["timeline"] if r["kind"] == "fixed"],
        )
        self.assertEqual(result, plan(list(reversed(data))))

    def test_f10_elapsed_is_history_even_above_est_and_progress_complete(self):
        result = plan(TASK.replace("est:30m", "est:30m elapsed:40m progress:100%"))
        row = candidates(result)[0]
        self.assertEqual(30, row["duration_minutes"])
        self.assertIn(
            {"code": "historical_elapsed", "params": {"minutes": 40}}, row["why"]
        )
        for value in ("bad", "1m elapsed:2m"):
            result = plan(TASK.replace("est:30m", "est:30m elapsed:" + value))
            self.assertEqual(30, candidates(result)[0]["duration_minutes"])
            self.assertIn("invalid_elapsed", codes(result))

    def test_f11_do_is_release_not_busy_and_future_intent(self):
        result = plan(TASK.replace("est:30m", "est:30m do:2026-10-09T11:00"))
        self.assertEqual("11:00", candidates(result)[0]["start"][11:16])
        for value in ("2026-10-09", "2026-10-08"):
            self.assertEqual(
                1, len(candidates(plan(TASK.replace("est:30m", "est:30m do:" + value))))
            )
        self.assertEqual(
            "future_intent",
            reasons(plan(TASK.replace("est:30m", "est:30m do:2026-10-10")))["t"],
        )

    def test_f12_today_exact_second_past_and_window_elapsed(self):
        result = plan(TASK, evaluated_at="2026-10-09T09:34:56+09:00")
        self.assertEqual("09:34:56", candidates(result)[0]["start"][11:19])
        self.assertIn(
            "past_date_unsupported",
            codes(plan(TASK, evaluated_at="2026-10-10T09:00+09:00")),
        )
        self.assertIn(
            "window_elapsed", codes(plan(TASK, evaluated_at="2026-10-09T12:00+09:00"))
        )

    def test_invalid_due_do_and_multiple_values_reject_only_task(self):
        for field in (
            "due:bad",
            "do:bad",
            "due:2026-10-09 due:2026-10-10",
            "do:2026-10-09 do:2026-10-10",
        ):
            result = plan(
                TASK.replace("est:30m", "est:30m " + field)
                + "[ ] T Good id:g est:10m\n"
            )
            self.assertEqual(["g"], [r["item"]["id"] for r in candidates(result)])
            self.assertEqual("partial", result["completeness"]["state"])

    def test_f14_project_filter_does_not_remove_occupancy_or_dependency(self):
        result = plan(
            MEETING.replace("id:e", "id:e project:other")
            + "[x] T Done id:p project:other\n"
            + TASK.replace("est:30m", "est:30m project:work depends_on:p"),
            project="work",
        )
        self.assertEqual(1, len(candidates(result)))
        self.assertEqual(
            1, len([r for r in result["timeline"] if r["kind"] == "fixed"])
        )
        with self.assertRaises(ValueError):
            plan(TASK, area="a", saved_view="b")

    def test_non_tasks_closed_and_parked_are_excluded(self):
        for status in ("[x]", "[-]", "[?]", "[>]"):
            self.assertEqual(
                "not_actionable", reasons(plan(TASK.replace("[ ]", status)))["t"]
            )
        for tag in ("someday", "maybe", "waiting", "blocked"):
            self.assertEqual(
                "not_actionable",
                reasons(plan(TASK.replace("est:30m", "est:30m tag:" + tag)))["t"],
            )
        self.assertEqual(1, len(candidates(plan(TASK.replace("[ ]", "[/]")))))
        result = plan(
            "[ ] H Habit id:h est:10m\n[ ] D Deadline id:d due:2026-10-09 est:10m\n"
        )
        self.assertEqual([], candidates(result))
        self.assertEqual({"D": 1, "H": 1}, result["excluded"])

    def test_cancelled_events_keep_existing_conservative_occupancy(self):
        result = plan("[-] E Busy id:e on:2026-10-09\n" + TASK)
        self.assertEqual("insufficient_capacity", reasons(result)["t"])

    def test_f15_rest_footprint_not_clipped(self):
        result = plan(TASK, day_end="09:30", policy={"break_minutes": 1})
        self.assertEqual([], candidates(result))
        self.assertEqual("insufficient_capacity", reasons(result)["t"])

    def test_f16_snapshot_currentness_and_hidden_occupancy_fail_closed(self):
        for kw, code in (
            ({"snapshot_consistent": False}, "source_changed"),
            ({"occupancy_complete": False}, "occupancy_unavailable"),
        ):
            result = plan(TASK + MEETING, **kw)
            self.assertEqual([], result["timeline"])
            self.assertEqual([], result["unplaced"])
            self.assertIsNone(result["source_revision"])
            self.assertEqual({code}, codes(result))
        data, diagnostics = parse_text("invalid item\n" + TASK)
        result = plan(data, input_diagnostics=[{"severity": "error"}])
        self.assertEqual([], candidates(result))
        self.assertIn("input_parse_error", codes(result))

    def test_f17_deterministic_rank_and_importance_is_context(self):
        data = items(
            "[ ] T First id:a priority:A est:30m importance:low\n", "z.txt"
        ) + items("[ ] T Second id:b priority:A est:30m importance:high\n", "a.txt")
        result = plan(data)
        self.assertEqual(["b", "a"], [r["item"]["id"] for r in candidates(result)])
        self.assertEqual(json.dumps(result), json.dumps(plan(list(reversed(data)))))
        overdue = plan(
            "[ ] T High id:h priority:A est:10m due:2026-10-10\n[ ] T Overdue id:o priority:C est:10m due:2026-10-08\n"
        )
        self.assertEqual(["o", "h"], [r["item"]["id"] for r in candidates(overdue)])
        self.assertEqual("missed", candidates(overdue)[0]["deadline_status"])

    def test_soft_deadline_date_only_and_deadline_first_fit(self):
        result = plan(MEETING + TASK.replace("est:30m", "est:90m due:2026-10-09T11:30"))
        self.assertEqual("insufficient_capacity", reasons(result)["t"])
        result = plan(TASK.replace("est:30m", "est:30m due:2026-10-09T09:20"))
        self.assertEqual("missed", candidates(result)[0]["deadline_status"])
        self.assertEqual(
            "met",
            candidates(plan(TASK.replace("est:30m", "est:30m due:2026-10-09")))[0][
                "deadline_status"
            ],
        )

    def test_f18_caps_before_conflict_computation_and_candidate_inventory(self):
        with patch(
            "lifetxt.daily_flow_time.compute_freebusy",
            side_effect=AssertionError("must not run"),
        ):
            result = plan(
                MEETING + MEETING.replace("id:e", "id:e2"),
                policy={"limits": {"conflicts": 1, "slots": 1}},
            )
            self.assertIn("limit_exceeded", codes(result))
        result = plan(
            TASK + TASK.replace("id:t", "id:t2"), policy={"limits": {"candidates": 1}}
        )
        self.assertEqual(1, len(candidates(result)))
        self.assertEqual("limit_exceeded", reasons(result)["t2"])
        self.assertEqual("bounded", result["completeness"]["inventory"])
        result = plan(TASK + MEETING, policy={"limits": {"context": 1}})
        self.assertEqual([], result["timeline"])
        self.assertIn("limit_exceeded", codes(result))
        result = plan(
            TASK + TASK.replace("id:t", "id:t2"), policy={"limits": {"slots": 1}}
        )
        self.assertEqual([], candidates(result))

    def test_bounded_infinite_iterator(self):
        def infinite():
            while True:
                yield Item("[ ]", "T", "Task", {"id": "t", "est": "1m"})

        result = plan(infinite(), policy={"limits": {"context": 10}})
        self.assertIn("limit_exceeded", codes(result))

    def test_edge_and_text_admission_bounds(self):
        for policy in (
            {"limits": {"edges": 1}},
            {"limits": {"text_chars": 1}},
            {"limits": {"detail_values": 1}},
            {"limits": {"events": 1}},
        ):
            result = plan(
                TASK.replace("est:30m", "est:30m depends_on:x depends_on:y")
                + MEETING
                + MEETING.replace("id:e", "id:e2"),
                policy=policy,
            )
            self.assertIn("limit_exceeded", codes(result))
            self.assertEqual([], candidates(result))

    def test_f20_host_independent_offsets_and_mixed_at_on(self):
        result = plan(
            TASK + MEETING.replace("T10:00", "T01:00Z").replace("T11:00", "T02:00Z")
        )
        fixed = [r for r in result["timeline"] if r["kind"] == "fixed"][0]
        self.assertEqual("10:00", fixed["start"][11:16])
        with timezone_context("America/New_York"):
            self.assertEqual(
                result,
                plan(
                    TASK
                    + MEETING.replace("T10:00", "T01:00Z").replace("T11:00", "T02:00Z")
                ),
            )
            self.assertEqual("America/New_York", current_timezone_name())
        result = plan(TASK + "[ ] R Ping id:r on:2026-10-09 at:01:00Z\n")
        self.assertEqual("10:00", result["instants"][0]["at"][11:16])

    def test_source_byte_hash_and_deep_inputs_unchanged_no_path_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "work.txt")
            with open(path, "wb") as f:
                f.write((MEETING + TASK).encode())
            with open(path, "rb") as f:
                before = f.read()
            data = items(before.decode(), path)
            original = copy.deepcopy([it.to_dict() for it in data])
            result = plan(data, source_revisions={path: hash_bytes(before)})
            self.assertEqual(original, [it.to_dict() for it in data])
            self.assertNotIn(directory, json.dumps(result))
            self.assertEqual(
                "source_snapshot", result["source_revision"]["sources"][0]["basis"]
            )
            with open(path, "rb") as f:
                self.assertEqual(before, f.read())

    def test_invalid_window_policy_and_revision(self):
        for kw in (
            {"day_start": None},
            {"day_end": "08:00"},
            {"date": "wrong"},
            {"timezone": "local"},
            {"policy": {"break_minutes": -1}},
            {"policy": {"break_minutes": True}},
            {"policy": {"break_minutes": 181}},
            {"policy": {"wrong": 1}},
            {"policy": {"limits": {"events": 1001}}},
            {"policy": {"limits": {"wrong": 2}}},
            {"policy": {"limits": {"events": 0}}},
            {"source_revisions": {"work.txt": "secret-path"}},
            {"occupancy_complete": 1},
        ):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                plan(TASK, **kw)

    def test_marker_cross_product_is_bounded_before_normalizing(self):
        text = (
            TASK
            + "[ ] R Many id:r "
            + " ".join(["on:2026-10-09"] * 50 + ["at:10:00"] * 50)
            + "\n"
        )
        with patch(
            "lifetxt.daily_flow_time.normalized_event",
            side_effect=AssertionError("must not expand"),
        ):
            result = plan(text)
        self.assertIn("limit_exceeded", codes(result))
        self.assertEqual([], candidates(result))

    def test_input_text_bounds_and_parse_error_never_certify_gaps(self):
        for text in (
            "[ ] T " + "X" * 1025 + " id:t est:1m\n",
            TASK + "[ ] N Note note:" + "X" * 4097 + "\n",
        ):
            self.assertIn("limit_exceeded", codes(plan(text)))
        result = plan(TASK, input_diagnostics=[{"severity": "error"}])
        self.assertEqual("unknown", result["completeness"]["occupancy"])
        self.assertEqual([], result["free"])

    def test_ambiguous_memory_inputs_have_deterministic_blocked_revision(self):
        data = [
            Item("[ ]", "T", "Same", {"id": "t", "est": "10m"}),
            Item("[ ]", "T", "Same", {"id": "t", "est": "20m"}),
        ]
        self.assertEqual(plan(data), plan(list(reversed(data))))

    def test_transition_in_event_span_and_offset_window_validation(self):
        result = plan(
            TASK
            + "[ ] E Span id:e from:2026-03-07T10:00-05:00 to:2026-03-10T10:00-04:00\n",
            date="2026-03-09",
            timezone="America/New_York",
            evaluated_at="2026-03-01T00:00Z",
        )
        self.assertIn("unsupported_timezone_window", codes(result))
        for kw in ({"day_start": "09:00+23:00"}, {"day_end": "00:00-23:00"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                plan(TASK, **kw)

    def test_blank_identity_and_max_date_fail_safely(self):
        for identity in ("", " "):
            result = plan([Item("[ ]", "T", "Task", {"id": identity, "est": "10m"})])
            self.assertEqual("missing_identity", result["unplaced"][0]["reason"])
        with self.assertRaises(ValueError):
            plan(TASK, date="9999-12-31")
        with self.assertRaises(ValueError):
            plan(TASK, source_revisions={1: "0" * 64})

    def test_area_reuse_without_narrowing_busy_context(self):
        data = items(
            TASK.replace("est:30m", "est:30m area:work project:work")
            + "[ ] T Home id:h est:10m area:home project:home\n"
            + MEETING
        )
        result = plan(data, area="work")
        self.assertEqual(["t"], [r["item"]["id"] for r in candidates(result)])
        self.assertEqual(
            1, len([r for r in result["timeline"] if r["kind"] == "fixed"])
        )

    def test_saved_view_filter_is_candidate_only_and_preserves_configuration(self):
        data = items(
            TASK.replace("est:30m", "est:30m project:work")
            + "[ ] T Home id:h est:10m project:home\n"
            + MEETING
        )
        config = {"saved_views": {"focus": {"query": "project:work"}}}
        original = copy.deepcopy(config)
        result = plan(data, saved_view="focus", config=config)
        self.assertEqual(["t"], [r["item"]["id"] for r in candidates(result)])
        self.assertEqual(
            1, len([r for r in result["timeline"] if r["kind"] == "fixed"])
        )
        self.assertEqual(original, config)

    def test_midnight_exclusive_end(self):
        result = plan(TASK, day_start="23:00", day_end="00:00")
        self.assertEqual("2026-10-10", result["window"]["end"][:10])
        self.assertEqual("23:00", candidates(result)[0]["start"][11:16])

    def test_randomized_nonoverlap_capacity_identity_and_determinism(self):
        for seed in range(30):
            rng = random.Random(seed)
            rows = [
                f"[ ] T Task-{i} id:t{i} est:{rng.randint(1, 60)}m priority:{rng.choice('ABC')}\n"
                for i in range(20)
            ]
            for i in range(4):
                minute = rng.randrange(120)
                start = dt.datetime(2026, 10, 9, 9) + dt.timedelta(minutes=minute)
                end = start + dt.timedelta(minutes=rng.randrange(1, 45))
                rows.append(
                    f"[ ] E Event-{i} id:e{i} from:{start.isoformat()} to:{end.isoformat()}\n"
                )
            data = items("".join(rows))
            policy = {
                "break_minutes": rng.randrange(4),
                "buffer_minutes": rng.randrange(4),
            }
            result = plan(data, policy=policy)
            self.assertEqual(result, plan(list(reversed(data)), policy=policy))
            suggestions = [row for row in result["timeline"] if row["kind"] != "fixed"]
            fixed = [row for row in result["timeline"] if row["kind"] == "fixed"]
            occupied = []
            for row in suggestions:
                left, right = (
                    dt.datetime.fromisoformat(row["start"]),
                    dt.datetime.fromisoformat(row["end"]),
                )
                self.assertLess(left, right)
                self.assertGreaterEqual(
                    left, dt.datetime.fromisoformat(result["window"]["start"])
                )
                self.assertLessEqual(
                    right, dt.datetime.fromisoformat(result["window"]["end"])
                )
                for other in fixed:
                    self.assertFalse(
                        left < dt.datetime.fromisoformat(other["end"])
                        and right > dt.datetime.fromisoformat(other["start"])
                    )
                for a, b in occupied:
                    self.assertFalse(left < b and right > a)
                occupied.append((left, right))
            placed = [r["item"]["id"] for r in candidates(result)]
            self.assertEqual(len(placed), len(set(placed)))
            self.assertEqual(20, len(placed) + len(result["unplaced"]))


if __name__ == "__main__":
    unittest.main()
