import datetime
import unittest
from types import SimpleNamespace

from lifetxt.parser import parse_text
from lifetxt.temporal_thread import temporal_thread
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


if __name__ == "__main__":
    unittest.main()
