import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

from lifetxt.completion import bash_completion
from lifetxt.csvio import items_from_csv_text, items_to_csv
from lifetxt.model import Item
from lifetxt.parser import parse_text
from lifetxt.serializer import (
    item_to_line,
    items_from_json_text,
    items_from_jsonl_text,
    items_to_json,
    items_to_jsonl,
)


GOLDEN_PATH = os.path.join(
    os.path.dirname(__file__), "golden", "roundtrip_cases.json"
)


def _canonical_text(items):
    return "".join(item_to_line(item) + "\n" for item in items)


def _semantic_items(items, include_indent=True):
    records = []
    for item in items:
        record = {
            "status": item.status,
            "type": item.kind,
            "title": item.title,
            "details": {key: list(values) for key, values in item.details.items()},
        }
        if include_indent:
            record["indent"] = int(getattr(item, "indent", 0) or 0)
        records.append(record)
    return records


def _error_codes(diagnostics):
    return [diagnostic.code for diagnostic in diagnostics if diagnostic.severity == "error"]


class GoldenRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(GOLDEN_PATH, "r", encoding="utf-8") as handle:
            cls.corpus = json.load(handle)

    def test_manifest_version_is_explicit(self):
        self.assertEqual(1, self.corpus["version"])
        self.assertGreaterEqual(len(self.corpus["cases"]), 9)

    def test_parse_serialize_parse_corpus(self):
        for case in self.corpus["cases"]:
            with self.subTest(case=case["name"]):
                items, diagnostics = parse_text(case["input"])
                self.assertEqual([], _error_codes(diagnostics))

                canonical = _canonical_text(items)
                self.assertEqual(case["canonical"], canonical)

                reparsed, reparse_diagnostics = parse_text(canonical)
                self.assertEqual([], _error_codes(reparse_diagnostics))
                self.assertEqual(_semantic_items(items), _semantic_items(reparsed))
                self.assertEqual(canonical, _canonical_text(reparsed))

    def test_json_jsonl_and_csv_preserve_golden_values(self):
        for case in self.corpus["cases"]:
            with self.subTest(case=case["name"], format="json"):
                items = parse_text(case["input"])[0]
                restored = items_from_json_text(items_to_json(items))
                self.assertEqual(_semantic_items(items), _semantic_items(restored))

            with self.subTest(case=case["name"], format="jsonl"):
                items = parse_text(case["input"])[0]
                restored = items_from_jsonl_text(items_to_jsonl(items))
                self.assertEqual(_semantic_items(items), _semantic_items(restored))

            if case.get("csv_roundtrip", True):
                with self.subTest(case=case["name"], format="csv"):
                    items = parse_text(case["input"])[0]
                    restored = items_from_csv_text(items_to_csv(items))
                    self.assertEqual(
                        _semantic_items(items, include_indent=False),
                        _semantic_items(restored, include_indent=False),
                    )

    def test_offset_strings_survive_every_interchange_format(self):
        case = next(
            entry
            for entry in self.corpus["cases"]
            if entry["name"] == "offset-aware-unicode-event"
        )
        items = parse_text(case["input"])[0]
        expected_from = "2026-07-22T09:30:15.25+09:00"
        expected_to = "2026-07-22T10:45:00+09:00"

        variants = (
            items_from_json_text(items_to_json(items)),
            items_from_jsonl_text(items_to_jsonl(items)),
            items_from_csv_text(items_to_csv(items)),
        )
        for restored in variants:
            self.assertEqual(expected_from, restored[0].details["from"][0])
            self.assertEqual(expected_to, restored[0].details["to"][0])

    def test_inline_body_and_continuation_are_rejected(self):
        text = "[N] N Note body:inline\n| continuation\n"
        items, diagnostics = parse_text(text)
        errors = [diagnostic for diagnostic in diagnostics if diagnostic.code == "E022"]
        self.assertEqual(1, len(items))
        self.assertEqual(1, len(errors))
        self.assertEqual(2, errors[0].line)
        self.assertEqual(1, errors[0].column)

    def test_indented_ambiguous_body_reports_continuation_column(self):
        text = "  [N] N Note body:inline\n  | continuation\n"
        _items, diagnostics = parse_text(text)
        error = next(diagnostic for diagnostic in diagnostics if diagnostic.code == "E022")
        self.assertEqual(2, error.line)
        self.assertEqual(3, error.column)

    def test_repeated_body_with_multiline_value_cannot_serialize(self):
        item = Item(
            "[N]",
            "N",
            "Note",
            {"body": ["first", "second\nthird"]},
            1,
        )
        with self.assertRaisesRegex(ValueError, "cannot be represented losslessly"):
            item_to_line(item)

    def test_single_multiline_body_uses_continuation_lines(self):
        item = Item("[N]", "N", "Note", {"body": ["first\n\nthird"]}, 1)
        self.assertEqual("[N] N Note\n| first\n|\n| third", item_to_line(item))


@unittest.skipUnless(shutil.which("bash"), "bash is required for executable completion tests")
class BashCompletionExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.script_path = os.path.join(self.temp_dir.name, "lifetxt-completion.bash")
        with open(self.script_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(bash_completion())

        self.stub_path = os.path.join(self.temp_dir.name, "lifetxt")
        with open(self.stub_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "#!/usr/bin/env bash\n"
                "if [[ $1 == completion && $2 == values && $3 == --kind ]]; then\n"
                "  case $4 in\n"
                "    project) printf 'research\\nhome\\n' ;;\n"
                "    state) printf 'busy\\naway\\n' ;;\n"
                "  esac\n"
                "fi\n"
            )
        os.chmod(self.stub_path, os.stat(self.stub_path).st_mode | stat.S_IXUSR)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _complete(self, words, cword):
        quoted_words = " ".join("'%s'" % word.replace("'", "'\\''") for word in words)
        command = (
            "source \"$1\"\n"
            "COMP_WORDS=(%s)\n"
            "COMP_CWORD=%d\n"
            "_lifetxt_completion\n"
            "printf '%s\\n' \"${COMPREPLY[@]}\"\n"
        ) % (quoted_words, cword, "%s")
        environment = dict(os.environ)
        environment["PATH"] = self.temp_dir.name + os.pathsep + environment.get("PATH", "")
        result = subprocess.run(
            [shutil.which("bash"), "--noprofile", "--norc", "-c", command, "bash", self.script_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        return [line for line in result.stdout.splitlines() if line]

    def test_command_completion_executes(self):
        self.assertIn("agenda", self._complete(["lifetxt", "ag"], 1))

    def test_command_scoped_option_completion_executes(self):
        self.assertIn("--from", self._complete(["lifetxt", "agenda", "--fr"], 2))

    def test_dynamic_value_completion_executes(self):
        self.assertEqual(
            ["research"],
            self._complete(["lifetxt", "filter", "--project", "re"], 3),
        )

    def test_subcommand_completion_executes(self):
        self.assertIn("bash", self._complete(["lifetxt", "completion", "ba"], 2))


if __name__ == "__main__":
    unittest.main()
