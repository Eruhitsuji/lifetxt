import unittest

from lifetxt.parser import parse_text
from lifetxt.read_scope import resolve_read_scope


class ReadScopeTests(unittest.TestCase):
    def setUp(self):
        self.items, diagnostics = parse_text(
            "#! timezone: UTC\n"
            "[ ] T Work_task project:work area:work\n[ ] T Home_task project:home area:home\n"
        )
        self.assertFalse(any(getattr(item, "severity", "") == "error" for item in diagnostics))

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
