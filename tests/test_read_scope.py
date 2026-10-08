import unittest

from lifetxt.parser import parse_text
from lifetxt.read_scope import resolve_read_scope, resolve_temporal_read_scope


class ReadScopeTests(unittest.TestCase):
    def setUp(self):
        self.items, diagnostics = parse_text(
            "#! timezone: UTC\n"
            "[ ] T Work_task project:work area:work\n[ ] T Home_task project:home area:home\n"
        )
        self.assertFalse(
            any(getattr(item, "severity", "") == "error" for item in diagnostics)
        )

    def test_area_returns_metadata_and_scoped_items(self):
        items, metadata = resolve_read_scope(self.items, {}, area="work")
        self.assertEqual({"kind": "area", "name": "work"}, metadata)
        self.assertEqual(["Work_task"], [item.title for item in items])

    def test_scope_selectors_are_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            resolve_read_scope(self.items, {}, area="work", saved_view="focus")

    def test_no_scope_is_identity(self):
        items, metadata = resolve_read_scope(self.items, {})
        self.assertIs(items, self.items)
        self.assertIsNone(metadata)


class TemporalReadScopeTests(unittest.TestCase):
    def parse(self, text):
        return parse_text(text)[0]

    def test_all_native_history_families_follow_selected_parent(self):
        items = self.parse(
            "[ ] T Work id:work area:Work\n[ ] T Home id:home area:Home\n"
            + "".join(
                "[N] N Evidence record:%s parent:%s\n" % (kind, parent)
                for kind in (
                    "item_event",
                    "progress_event",
                    "ticket_event",
                    "time_entry",
                )
                for parent in ("work", "home")
            )
        )
        selected, scope = resolve_temporal_read_scope(items, {}, area="Work")
        self.assertEqual({"kind": "area", "name": "Work"}, scope)
        self.assertEqual("Work", selected[0].title)
        self.assertEqual(5, len(selected))
        self.assertEqual({"work"}, {row.details["parent"][0] for row in selected[1:]})
        # The generic selector remains unchanged and does not add history.
        self.assertEqual([items[0]], resolve_read_scope(items, {}, area="Work")[0])

    def test_no_scope_preserves_snapshot_identity_and_ambiguous_records(self):
        items = self.parse("[ ] T One id:same\n[ ] T Two id:same\n")
        selected, scope = resolve_temporal_read_scope(items, {})
        self.assertIs(items, selected)
        self.assertIsNone(scope)

    def test_selected_history_is_not_a_target_and_unrelated_ambiguity_is_ignored(self):
        items = self.parse(
            "[ ] T Work id:work area:Work\n"
            "[N] N Unrelated record:item_event parent:home parent:other area:Work\n"
            "[N] N Missing_parent record:item_event area:Work\n"
            "[ ] T Home id:home area:Home\n[ ] T Duplicate id:home area:Home\n"
        )
        self.assertEqual(
            [items[0]], resolve_temporal_read_scope(items, {}, area="Work")[0]
        )

    def test_missing_or_multiple_target_ids_do_not_attach_history(self):
        items = self.parse(
            "[ ] T No_id area:Work\n[ ] T Multiple id:one id:two area:Work\n"
            "[N] N Evidence record:item_event parent:one\n"
        )
        self.assertEqual(
            items[:2], resolve_temporal_read_scope(items, {}, area="Work")[0]
        )

    def test_duplicate_identity_in_multiple_id_unselected_target_fails_closed(self):
        items = self.parse(
            "[ ] T Work id:work area:Work\n[ ] T Home id:home id:work area:Home\n"
        )
        with self.assertRaisesRegex(ValueError, "ambiguous native history association"):
            resolve_temporal_read_scope(items, {}, area="Work")

    def test_upcoming_agenda_receives_only_selected_targets(self):
        from lifetxt.agenda import agenda_records
        from lifetxt.timeutil import parse_date_or_datetime

        items = self.parse(
            "[ ] T Work id:work area:Work due:2031-02-04\n"
            "[ ] T Home id:home area:Home due:2031-02-04\n"
        )
        selected, _ = resolve_temporal_read_scope(items, {}, area="Work")
        rows = agenda_records(
            selected,
            parse_date_or_datetime("2031-02-03"),
            parse_date_or_datetime("2031-02-05"),
        )
        self.assertEqual(["Work"], [row["title"] for row in rows])
