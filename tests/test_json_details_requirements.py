import unittest
from datetime import datetime

from lifetxt.agenda import agenda_records
from lifetxt.csvio import items_from_csv_text, items_to_csv
from lifetxt.links import dependency_blockers_by_item
from lifetxt.parser import parse_text
from lifetxt.serializer import (
    encode_detail_value,
    item_to_line,
    items_from_json_text,
    items_from_jsonl_text,
    items_to_json,
    items_to_jsonl,
)


class JsonDetailsTests(unittest.TestCase):
    def test_typed_values_and_repeated_keys_roundtrip(self):
        values = [{"room": "会議室 A", "equipment": ["mic", None]}, [], 2, 2.5, True, None]
        native = '[ ] T Example custom:json:true custom:"json:true" ' + " ".join(
            "custom:" + encode_detail_value(value) for value in values
        ) + ' custom:tail'
        items, diagnostics = parse_text(native)
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        expected = ["json:true", "json:true", *values, "tail"]
        self.assertEqual(items[0].details["custom"], expected)
        for restored in (
            parse_text(item_to_line(items[0]))[0],
            items_from_json_text(items_to_json(items)),
            items_from_jsonl_text(items_to_jsonl(items)),
            items_from_csv_text(items_to_csv(items)),
        ):
            actual = restored[0].details["custom"]
            self.assertEqual(actual, expected)
            self.assertEqual(list(map(type, actual)), list(map(type, expected)))

    def test_explicit_json_string_and_malformed_values(self):
        items, diagnostics = parse_text(r'[ ] T Example note:json:"\"text\""')
        self.assertEqual(items[0].details["note"], ["text"])
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        for payload in ("broken", "[", "NaN", "1e999"):
            with self.subTest(payload=payload):
                _, diagnostics = parse_text(f'[ ] T Example note:json:"{payload}"')
                self.assertIn("E023", [d.code for d in diagnostics])


class RequiresTests(unittest.TestCase):
    def test_cancel_does_not_satisfy_done_and_started_item_stays_actionable(self):
        items, diagnostics = parse_text(
            '[-] T Review id:review\n'
            '[ ] T Submit id:submit requires:review=done do:2030-01-01\n'
            '[/] T Started requires:review=done\n'
            '[ ] T Legacy depends_on:review\n'
        )
        self.assertFalse(diagnostics)
        blockers = dependency_blockers_by_item(items)
        self.assertEqual(list(blockers), [id(items[1])])
        self.assertEqual(blockers[id(items[1])][0]["condition_state"], "waiting")
        records = agenda_records(items, datetime(2030, 1, 1), datetime(2030, 1, 2))
        self.assertEqual(records[0]["blocked_by"][0]["required_statuses"], ["[x]"])

    def test_nested_conditions_and_unresolved_references(self):
        condition = {"all": [
            {"any": [{"id": "missing", "state": "done"}, {"id": "review", "state": "done"}]},
            {"id": "draft", "state": ["in_progress", "done"]},
        ]}
        source = (
            '[x] T Review id:review\n[/] T Draft id:draft\n'
            '[ ] T Submit requires:' + encode_detail_value(condition)
        )
        items, diagnostics = parse_text(source)
        self.assertIn("W215", [d.code for d in diagnostics])
        self.assertFalse(dependency_blockers_by_item(items))
        items, _ = parse_text(source.replace("[x] T Review", "[ ] T Review"))
        blockers = dependency_blockers_by_item(items)[id(items[2])]
        self.assertTrue(all(entry["condition_state"] == "unknown" for entry in blockers))

    def test_malformed_requirement_is_diagnosed(self):
        _, diagnostics = parse_text("[ ] T Example requires:review=unknown")
        self.assertIn("E024", [d.code for d in diagnostics])
