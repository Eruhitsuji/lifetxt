import datetime
import unittest
from types import SimpleNamespace

from lifetxt.parser import parse_text
from lifetxt.temporal_thread import (
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
