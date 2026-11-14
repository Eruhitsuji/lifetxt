import tempfile
import unittest
from pathlib import Path
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
        items, diagnostics = parse_text('[ ] T Example note:json<< "text" >>')
        self.assertEqual(items[0].details["note"], ["text"])
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        for payload in ("broken", "[", "[1,]", "NaN", "1e999", "true false"):
            with self.subTest(payload=payload):
                _, diagnostics = parse_text(f'[ ] T Example note:json<< {payload} >>')
                self.assertIn("E023", [d.code for d in diagnostics])

    def test_array_expansion_is_independent_of_key(self):
        items, diagnostics = parse_text(
            '[ ] T Example tag:a tag:json<< ["b","c"] >> tag:d '
            'options:json<< ["b","c"] >> nested:json<< [["b","c"]] >> empty:json<< [] >>'
        )
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        self.assertEqual(items[0].details, {
            "tag": ["a", "b", "c", "d"], "options": ["b", "c"],
            "nested": [["b", "c"]], "empty": [],
        })

    def test_empty_value_list_roundtrips_without_other_typed_values(self):
        items, _ = parse_text('[ ] T Example options:json<< [] >>')
        self.assertEqual(parse_text(item_to_line(items[0]))[0][0].details, {"options": []})
        self.assertEqual(items_from_csv_text(items_to_csv(items))[0].details, {"options": []})

    def test_multiline_json_preserves_record_span_and_following_detail(self):
        source = (
            '[ ] T Example options:json<<\n'
            '\t{"note":"a >> b","nested":[1,2]}\n'
            '>> tag:after\n'
            '[ ] T Next\n'
        )
        items, diagnostics = parse_text(source)
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        self.assertEqual([item.line for item in items], [1, 4])
        self.assertEqual(items[0].end_line, 3)
        self.assertEqual(items[0].source_text, source.rsplit("\n[", 1)[0])
        self.assertEqual(items[0].details["options"], [{"note": "a >> b", "nested": [1, 2]}])
        self.assertEqual(items[0].details["tag"], ["after"])

    def test_missing_close_does_not_consume_next_item(self):
        items, diagnostics = parse_text(
            '[ ] T Example options:json<<\n'
            '  {"note":"a >> b"}\n'
            '[ ] T Next\n'
        )
        self.assertEqual([item.line for item in items], [1, 3])
        error = next(d for d in diagnostics if d.code == "E023")
        self.assertEqual((error.line, error.column), (1, 23))

    def test_bare_marker_and_prefix_literals_remain_strings(self):
        items, diagnostics = parse_text(
            '[ ] T Example options:json<< tag:after bare:json<<compact\n'
            '[ ] T Next options:json<<\n'
        )
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        self.assertEqual(items[0].details["options"], ["json<<"])
        self.assertEqual(items[0].details["bare"], ["json<<compact"])
        self.assertEqual(items[1].details["options"], ["json<<"])


    def test_json_strings_keep_literal_types_through_interchange(self):
        items, diagnostics = parse_text(
            r'[ ] T Example empty:json<< "" >> text:json<< "[1,2]" >> '
            r'lines:json<< "first\nsecond" >> literal:json:true'
        )
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        expected = {
            "empty": [""],
            "text": ["[1,2]"],
            "lines": ["first\nsecond"],
            "literal": ["json:true"],
        }
        self.assertEqual(items[0].details, expected)
        for restored in (
            parse_text(item_to_line(items[0]))[0],
            items_from_json_text(items_to_json(items)),
            items_from_jsonl_text(items_to_jsonl(items)),
            items_from_csv_text(items_to_csv(items)),
        ):
            self.assertEqual(restored[0].details, expected)

    def test_malformed_closed_block_recovers_at_following_detail(self):
        items, diagnostics = parse_text(
            '[ ] T Example custom:json<<\n'
            '  ["inside >> string",]\n'
            '>> tag:after\n'
            '[ ] T Next tag:next\n'
        )
        self.assertEqual([d.code for d in diagnostics if d.severity == "error"], ["E023"])
        self.assertEqual(items[0].details["tag"], ["after"])
        self.assertEqual(items[1].details["tag"], ["next"])

    def test_json_arrays_still_use_standard_key_type_constraints(self):
        items, diagnostics = parse_text(
            '[ ] T Example tag:json<< ["valid",2] >> custom:json<< ["valid",2] >>'
        )
        self.assertEqual(items[0].details["tag"], ["valid", 2])
        self.assertEqual(items[0].details["custom"], ["valid", 2])
        errors = [d for d in diagnostics if d.severity == "error"]
        self.assertEqual([d.code for d in errors], ["E025"])
        self.assertIn("tag:", errors[0].message)

    def test_web_update_by_id_preserves_typed_and_empty_values(self):
        from lifetxt.webapp import update_item_in_file

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "life.txt"
            path.write_text(
                '[ ] T Example id:sample options:json<<\n  [[1,2],true,null]\n>>\n'
                '[ ] T Next\n',
                encoding="utf-8",
            )
            details = {"id": ["sample"], "options": [[1, 2], True, None], "empty": []}
            update_item_in_file(path, 1, {"title": "Edited", "details": details})
            items, diagnostics = parse_text(path.read_text(encoding="utf-8"))
            self.assertFalse([d for d in diagnostics if d.severity == "error"])
            self.assertEqual(items[0].title, "Edited")
            self.assertEqual(items[0].details, details)
            self.assertEqual(items[1].title, "Next")


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
