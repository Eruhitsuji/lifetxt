import unittest

from lifetxt.model import Item
from lifetxt.nextaction import blocked_map, is_actionable, next_action_items


class IsActionableTests(unittest.TestCase):
    def test_open_status_with_no_details_is_actionable(self):
        self.assertTrue(is_actionable("[ ]", {}))
        self.assertTrue(is_actionable("[/]", {}))

    def test_closed_and_someday_statuses_are_not_actionable(self):
        self.assertFalse(is_actionable("[x]", {}))
        self.assertFalse(is_actionable("[-]", {}))
        self.assertFalse(is_actionable("[?]", {}))

    def test_blocked_flag_excludes_regardless_of_details(self):
        self.assertFalse(is_actionable("[ ]", {}, blocked=True))

    def test_kind_filtering_only_applies_when_kind_given(self):
        self.assertTrue(is_actionable("[ ]", {}, kind="T"))
        self.assertTrue(is_actionable("[ ]", {}, kind="D"))
        self.assertTrue(is_actionable("[ ]", {}, kind="R"))
        self.assertTrue(is_actionable("[ ]", {}, kind="H"))
        self.assertFalse(is_actionable("[ ]", {}, kind="E"))
        self.assertTrue(is_actionable("[ ]", {}, kind=None))

    def test_parked_tags_exclude_even_with_open_status(self):
        for tag in ("someday", "maybe", "waiting", "blocked"):
            self.assertFalse(is_actionable("[ ]", {"tag": [tag]}))
            self.assertFalse(is_actionable("[ ]", {"tag": ["#" + tag]}))
        self.assertTrue(is_actionable("[ ]", {"tag": ["errand"]}))

    def test_resolved_depends_on_does_not_exclude_the_item(self):
        # Regression: is_actionable used to reject any item carrying a
        # depends_on detail even after the caller had already determined the
        # dependency was resolved (blocked=False). blocked is the sole source
        # of truth for dependency state.
        self.assertTrue(is_actionable("[ ]", {"depends_on": ["t1"]}, blocked=False))

    def test_unresolved_depends_on_excludes_via_blocked_flag(self):
        self.assertFalse(is_actionable("[ ]", {"depends_on": ["t1"]}, blocked=True))


class NextActionItemsTests(unittest.TestCase):
    def _item(self, status, kind, title, details=None, line=1):
        return Item(status=status, kind=kind, title=title, details=details, line=line)

    def test_excludes_closed_someday_and_parked_items(self):
        items = [
            self._item("[ ]", "T", "Open", {"id": ["a1"]}, line=1),
            self._item("[x]", "T", "Done", {"id": ["a2"]}, line=2),
            self._item("[?]", "T", "Someday status", {"id": ["a3"]}, line=3),
            self._item(
                "[ ]", "T", "Someday tag", {"id": ["a4"], "tag": ["someday"]}, line=4
            ),
        ]
        actionable = next_action_items(items)
        ids = {item.title for item in actionable}
        self.assertEqual({"Open"}, ids)

    def test_dependency_blocking_is_resolved_across_the_whole_item_set(self):
        blocker = self._item("[ ]", "T", "Blocker", {"id": ["b1"]}, line=1)
        blocked = self._item(
            "[ ]", "T", "Blocked", {"id": ["b2"], "depends_on": ["b1"]}, line=2
        )
        actionable = next_action_items([blocker, blocked])
        titles = {item.title for item in actionable}
        self.assertEqual({"Blocker"}, titles)

    def test_item_becomes_actionable_once_its_dependency_is_closed(self):
        blocker = self._item("[x]", "T", "Blocker done", {"id": ["c1"]}, line=1)
        formerly_blocked = self._item(
            "[ ]", "T", "Now free", {"id": ["c2"], "depends_on": ["c1"]}, line=2
        )
        actionable = next_action_items([blocker, formerly_blocked])
        titles = {item.title for item in actionable}
        self.assertEqual({"Now free"}, titles)

    def test_dangling_dependency_reference_is_not_actionable(self):
        item = self._item(
            "[ ]", "T", "Dangling", {"id": ["d1"], "depends_on": ["missing"]}, line=1
        )
        actionable = next_action_items([item])
        self.assertEqual([], actionable)


class BlockedMapTests(unittest.TestCase):
    def _item(self, status, kind, title, details=None, line=1):
        return Item(status=status, kind=kind, title=title, details=details, line=line)

    def test_item_with_no_dependency_is_not_blocked(self):
        item = self._item("[ ]", "T", "Free", {"id": ["m1"]}, line=1)
        self.assertEqual({}, blocked_map([item]))

    def test_dependency_on_an_open_item_blocks(self):
        blocker = self._item("[ ]", "T", "Open blocker", {"id": ["m1"]}, line=1)
        blocked = self._item(
            "[ ]", "T", "Waiting", {"id": ["m2"], "depends_on": ["m1"]}, line=2
        )
        result = blocked_map([blocker, blocked])
        self.assertTrue(result.get(id(blocked)))
        self.assertNotIn(id(blocker), result)

    def test_dependency_on_a_closed_item_does_not_block(self):
        blocker = self._item("[x]", "T", "Closed blocker", {"id": ["m1"]}, line=1)
        formerly_blocked = self._item(
            "[ ]", "T", "Free now", {"id": ["m2"], "depends_on": ["m1"]}, line=2
        )
        result = blocked_map([blocker, formerly_blocked])
        self.assertNotIn(id(formerly_blocked), result)

    def test_dependency_on_a_missing_id_blocks_conservatively(self):
        item = self._item(
            "[ ]", "T", "Dangling", {"id": ["m1"], "depends_on": ["nope"]}, line=1
        )
        result = blocked_map([item])
        self.assertTrue(result.get(id(item)))


if __name__ == "__main__":
    unittest.main()
