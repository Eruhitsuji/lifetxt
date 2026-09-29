import copy
import datetime
import unittest
from types import SimpleNamespace

from lifetxt.parser import parse_text
from lifetxt.temporal_thread import (
    priority_thread_overlay,
    replacement_chain_analysis,
    temporal_consistency,
    temporal_consistency_summary,
    temporal_thread,
)
from lifetxt import tui_app


TODAY = datetime.date(2026, 9, 8)


def _item(items, item_id):
    return next(item for item in items if item_id in item.details.get("id", []))


class TemporalThreadTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(
            "[ ] E Previous id:previous on:2026-06-01 replaced_by:actual\n"
            "[ ] E Plan id:plan on:2026-09-08\n"
            "[x] E Actual id:actual on:2026-09-08 follows:previous realizes:plan\n"
            "[ ] E Next id:next on:2026-12-08 follows:actual\n"
        )

    def test_groups_authoritative_directions_and_embeds_derived_context(self):
        result = temporal_thread(self.items, _item(self.items, "actual"), TODAY)
        self.assertEqual("temporal-thread-v1", result["schema"])
        self.assertEqual(
            ["previous"], [r["id"] for r in result["relations"]["predecessors"]]
        )
        self.assertEqual(["next"], [r["id"] for r in result["relations"]["successors"]])
        self.assertEqual(
            ["plan"], [r["id"] for r in result["relations"]["realized_plans"]]
        )
        self.assertEqual(
            ["previous"],
            [r["id"] for r in result["relations"]["replacement_predecessors"]],
        )
        self.assertEqual("temporal-context-v1", result["derived"]["schema"])
        self.assertEqual(
            "explicit", result["explicit"]["edges"][0]["provenance"]["kind"]
        )

    def test_inverse_realized_by_is_derived_from_the_stored_edge(self):
        result = temporal_thread(self.items, _item(self.items, "plan"), TODAY)
        self.assertEqual(
            ["actual"], [r["id"] for r in result["relations"]["realized_by"]]
        )
        self.assertNotIn("realized_by", _item(self.items, "plan").details)

    def test_depth_and_node_bounds_report_truncation(self):
        result = temporal_thread(
            self.items, _item(self.items, "actual"), TODAY, max_depth=0, max_nodes=1
        )
        self.assertEqual(["actual"], [n["id"] for n in result["explicit"]["nodes"]])
        self.assertTrue(result["explicit"]["truncated"])

    def test_reachable_cycle_is_reported_with_its_path(self):
        items, _ = parse_text("[ ] N A id:a follows:b\n[ ] N B id:b follows:a\n")
        result = temporal_thread(items, _item(items, "a"), TODAY)
        self.assertEqual("follows", result["explicit"]["cycles"][0]["relation"])
        self.assertEqual(
            result["explicit"]["cycles"][0]["path"][0],
            result["explicit"]["cycles"][0]["path"][-1],
        )

    def test_follows_conflict_reports_explainable_shared_evidence(self):
        items, _ = parse_text(
            "[ ] E Previous id:previous on:2026-09-10\n"
            "[ ] E Current id:current on:2026-09-01 follows:previous\n"
        )
        result = temporal_thread(items, _item(items, "current"), TODAY)
        warning = result["consistency"]["warnings"][0]
        self.assertEqual("follows", warning["relation"])
        self.assertEqual("before", warning["observed_order"])
        self.assertEqual("after", warning["expected_order"])
        self.assertEqual("current", warning["evidence"]["successor_id"])
        self.assertEqual("previous", warning["evidence"]["predecessor_id"])
        self.assertEqual("on", warning["evidence"]["source_field"])
        self.assertEqual("2026-09-01", warning["evidence"]["source_value"])
        self.assertEqual(
            "temporal-context-v1", warning["provenance"]["temporal"]["authority"]
        )

    def test_replaced_by_conflict_uses_target_as_the_successor(self):
        items, _ = parse_text(
            "[ ] E Old id:old on:2026-09-10 replaced_by:new\n"
            "[ ] E New id:new on:2026-09-01\n"
        )
        warning = temporal_consistency(items)["warnings"][0]
        self.assertEqual("replaced_by", warning["relation"])
        self.assertEqual("old", warning["source_id"])
        self.assertEqual("new", warning["target_id"])
        self.assertEqual("new", warning["evidence"]["successor_id"])
        self.assertEqual("old", warning["evidence"]["predecessor_id"])

    def test_valid_same_day_missing_and_realizes_cases_do_not_warn(self):
        cases = (
            (
                "valid follows",
                "[ ] E Old id:old on:2026-09-01\n"
                "[ ] E New id:new on:2026-09-10 follows:old\n",
            ),
            (
                "same day",
                "[ ] E Old id:old on:2026-09-01\n"
                "[ ] E New id:new on:2026-09-01 follows:old\n",
            ),
            (
                "missing evidence",
                "[ ] E Old id:old\n[ ] E New id:new on:2026-09-01 follows:old\n",
            ),
            (
                "incomparable evidence",
                "[ ] E Old id:old on:not-a-date\n"
                "[ ] E New id:new on:2026-09-01 follows:old\n",
            ),
            (
                "realizes has no chronological rule",
                "[ ] E Plan id:plan on:2026-09-10\n"
                "[ ] E Actual id:actual on:2026-09-01 realizes:plan\n",
            ),
        )
        for label, text in cases:
            with self.subTest(label=label):
                items, _ = parse_text(text)
                self.assertEqual([], temporal_consistency(items)["warnings"])

    def test_ambiguous_target_does_not_produce_a_consistency_guess(self):
        items, _ = parse_text(
            "[ ] E OldA id:old on:2026-09-10\n"
            "[ ] E OldB id:old on:2026-09-11\n"
            "[ ] E New id:new on:2026-09-01 follows:old\n"
        )
        self.assertEqual([], temporal_consistency(items)["warnings"])

    def test_consistency_output_is_bounded_with_the_explicit_thread(self):
        items, _ = parse_text(
            "[ ] E Root id:root on:2026-09-01 follows:a follows:b\n"
            "[ ] E A id:a on:2026-09-10\n"
            "[ ] E B id:b on:2026-09-11\n"
        )
        result = temporal_thread(
            items, _item(items, "root"), TODAY, max_depth=1, max_nodes=2
        )
        self.assertLessEqual(len(result["consistency"]["warnings"]), 2)
        self.assertTrue(result["consistency"]["truncated"])

    def test_target_id_must_be_unique(self):
        items, _ = parse_text("[ ] N A id:dup\n[ ] N B id:dup\n")
        with self.assertRaisesRegex(ValueError, "unique id"):
            temporal_thread(items, items[0], TODAY)

    def test_an_unrelated_duplicate_id_also_fails_deterministically(self):
        items, _ = parse_text(
            "[ ] N Target id:target\n[ ] N A id:dup\n[ ] N B id:dup\n"
        )
        with self.assertRaisesRegex(ValueError, "duplicate: dup"):
            temporal_thread(items, items[0], TODAY)

    def test_priority_overlay_reuses_matrix_and_horizon_for_thread_nodes(self):
        import datetime as dt
        from unittest import mock

        items, _ = parse_text(
            "[ ] T Urgent id:urgent importance:high due:2026-08-31\n"
            "[ ] T Soon id:soon importance:high due:2026-09-10 follows:urgent\n"
            "[ ] T Low_urgent id:low-urgent importance:low priority:A "
            "due:2026-08-31 follows:soon\n"
            "[ ] T Unimportant id:unimportant importance:normal follows:low-urgent\n"
            "[ ] T Missing id:missing due:2026-08-31 follows:unimportant\n"
            "[ ] T Invalid id:invalid importance:urgent follows:missing\n"
            "[x] T Done id:done importance:high due:2026-08-31 follows:invalid\n"
            "[-] T Cancelled id:cancelled importance:high due:2026-08-31 follows:done\n"
            "[ ] E Meeting id:meeting on:2026-08-31 follows:cancelled\n"
            "[ ] T No_due id:no-due importance:high follows:meeting\n"
        )
        target = _item(items, "urgent")
        thread = temporal_thread(items, target, TODAY, max_depth=12)
        reference = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
        before = [copy.deepcopy(item.details) for item in items]
        from lifetxt import priority_matrix

        classify = priority_matrix.classify_item
        transition = priority_matrix.next_transition
        classifier_references = []
        classifier_items = {}
        horizon_references = []

        def record_classify(item, ref=None):
            classifier_references.append(ref)
            classifier_items.setdefault(item.details["id"][0], []).append(ref)
            return classify(item, ref)

        def record_transition(item, ref=None):
            horizon_references.append(ref)
            return transition(item, ref)

        with mock.patch(
            "lifetxt.priority_matrix.classify_item", side_effect=record_classify
        ), mock.patch(
            "lifetxt.priority_matrix.next_transition", side_effect=record_transition
        ):
            enriched = priority_thread_overlay(thread, items, reference)

        contexts = {
            node["id"]: node.get("priority_context")
            for node in enriched["explicit"]["nodes"]
        }
        self.assertEqual("Q1", contexts["urgent"]["quadrant"])
        self.assertEqual("Q2", contexts["soon"]["quadrant"])
        self.assertEqual("Q1", contexts["soon"]["next_quadrant"])
        self.assertTrue(contexts["soon"]["next_at"].startswith("2026-09-03T"))
        self.assertEqual("Q3", contexts["low-urgent"]["quadrant"])
        self.assertEqual("Q4", contexts["unimportant"]["quadrant"])
        self.assertEqual("unclassified", contexts["missing"]["quadrant"])
        self.assertIsNone(contexts["missing"]["importance"])
        self.assertEqual("unclassified", contexts["invalid"]["quadrant"])
        self.assertIsNone(contexts["done"])
        self.assertIsNone(contexts["cancelled"])
        self.assertIsNone(contexts["meeting"])
        self.assertEqual("Q2", contexts["no-due"]["quadrant"])
        self.assertIsNone(contexts["no-due"]["next_at"])
        self.assertNotIn("priority_context", thread["explicit"]["nodes"][0])
        self.assertEqual(before, [item.details for item in items])
        self.assertTrue(classifier_references)
        self.assertTrue(horizon_references)
        annotated_ids = [item_id for item_id, value in contexts.items() if value]
        self.assertTrue(
            all(reference in classifier_items[item_id] for item_id in annotated_ids)
        )
        self.assertTrue(all(value is reference for value in horizon_references))

    def test_priority_overlay_observes_exact_urgency_boundary(self):
        import datetime as dt

        items, _ = parse_text(
            "#! timezone: UTC\n"
            "[ ] T Boundary id:boundary importance:high due:2026-09-10T23:59:59+00:00\n"
        )
        thread = temporal_thread(items, items[0], TODAY)
        boundary = dt.datetime(2026, 9, 3, 23, 59, 59, tzinfo=dt.timezone.utc)
        just_before = boundary - dt.timedelta(microseconds=1)
        self.assertEqual(
            "Q2",
            priority_thread_overlay(thread, items, just_before)["explicit"]["nodes"][0][
                "priority_context"
            ]["quadrant"],
        )
        self.assertEqual(
            "Q1",
            priority_thread_overlay(thread, items, boundary)["explicit"]["nodes"][0][
                "priority_context"
            ]["quadrant"],
        )

    def test_priority_overlay_does_not_change_default_thread_result(self):
        thread = temporal_thread(self.items, _item(self.items, "actual"), TODAY)
        enriched = priority_thread_overlay(
            thread,
            self.items,
            datetime.datetime(2026, 9, 8, tzinfo=datetime.timezone.utc),
        )
        self.assertNotIn("priority_context", thread["explicit"]["nodes"][0])
        self.assertEqual("temporal-thread-v1", enriched["schema"])
        self.assertEqual(thread["explicit"]["edges"], enriched["explicit"]["edges"])

    def test_negative_bounds_fail_loudly(self):
        with self.assertRaisesRegex(ValueError, "zero or greater"):
            temporal_thread(
                self.items, _item(self.items, "actual"), TODAY, max_depth=-1
            )

    def test_tui_thread_command_delegates_to_the_shared_model(self):
        row = {"id": "actual", "title": "Actual", "details": {"id": ["actual"]}}
        state = SimpleNamespace(
            args=SimpleNamespace(config_data={}),
            _items=self.items,
            rows=[row],
            selected=0,
            show_detail=False,
            selected_row=lambda: row,
        )
        level, message = tui_app._cmd_thread(state, "")
        self.assertEqual("info", level)
        self.assertIn("Temporal thread", message)
        self.assertEqual("temporal-thread-v1", state._temporal_thread["schema"])
        self.assertTrue(state.show_detail)

    def test_replacement_endpoints_follow_edge_direction(self):
        thread = {
            "target_id": "middle",
            "relations": {
                "replacement_predecessors": [{"id": "z-middle"}],
                "replacement_successors": [{"id": "a-next"}],
            },
            "explicit": {
                "truncated": False,
                "cycles": [],
                "edges": [
                    {"relation": "replaced_by", "source_id": "older", "target_id": "z-middle"},
                    {"relation": "replaced_by", "source_id": "z-middle", "target_id": "middle"},
                    {"relation": "replaced_by", "source_id": "middle", "target_id": "a-next"},
                    {"relation": "replaced_by", "source_id": "a-next", "target_id": "newer"},
                ],
            },
        }
        result = replacement_chain_analysis(thread)
        self.assertEqual("older", result["oldest_endpoint_id"])
        self.assertEqual("newer", result["newest_endpoint_id"])

    def test_consistency_summary_orders_date_and_datetime_by_calendar_date(self):
        thread = {
            "consistency": {
                "warnings": [
                    {"relation": "follows", "evidence": {"source_value": "2030-01-01T00:00:00Z"}},
                    {"relation": "follows", "evidence": {"source_value": "2020-01-01"}},
                ]
            }
        }
        result = temporal_consistency_summary(thread)
        self.assertEqual("2020-01-01", result["earliest_evidence"])
        self.assertEqual("2030-01-01T00:00:00Z", result["latest_evidence"])


if __name__ == "__main__":
    unittest.main()
