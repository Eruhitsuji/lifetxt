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


GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden", "roundtrip_cases.json")


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


#: Resolved once so the usability probe below and the fixture that follows
#: exercise the same binary instead of each re-reading PATH.
BASH_EXECUTABLE = shutil.which("bash")

#: Shell fragment mirroring what BashCompletionExecutionTests needs: sourcing a
#: script by the host path Python wrote it to, and running a stub found through
#: an os.pathsep-joined PATH.
_BASH_PROBE = 'source "$1"\n_lifetxt_probe_function\nlifetxt-probe\n'


def _write_bash_stub(path, body):
    """Write an executable `#!/usr/bin/env bash` stub the way the fixture needs.

    Shared with the usability probe so the probe keeps exercising the mechanism
    the fixture actually relies on rather than drifting from a private copy.
    """
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("#!/usr/bin/env bash\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)


def _run_bash_probe(probe_dir):
    script_path = os.path.join(probe_dir, "probe.bash")
    with open(script_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("_lifetxt_probe_function() { printf ok; }\n")
    _write_bash_stub(os.path.join(probe_dir, "lifetxt-probe"), "printf stub\n")

    environment = dict(os.environ)
    environment["PATH"] = probe_dir + os.pathsep + environment.get("PATH", "")
    return subprocess.run(
        [
            BASH_EXECUTABLE,
            "--noprofile",
            "--norc",
            "-c",
            _BASH_PROBE,
            "bash",
            script_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15.0,
        env=environment,
    )


def _usable_bash():
    """A bash that can run the completion fixture, not merely one that starts.

    On Windows `shutil.which("bash")` commonly finds `C:\\Windows\\System32\\
    bash.exe`, the WSL launcher. It starts and prints just fine, so a
    "does bash run?" check passes, but the Linux bash it starts cannot see the
    Windows temp path this fixture sources or the PATH stub it calls: every
    completion then returns an empty COMPREPLY and the assertions fail for a
    reason that has nothing to do with the completion script. Probe the two
    mechanisms the tests actually depend on instead.
    """
    if not BASH_EXECUTABLE:
        return False
    try:
        # mkdtemp rather than TemporaryDirectory: the latter's cleanup can raise
        # PermissionError on Windows, which the except below would turn into a
        # false "unusable bash" verdict and silently drop real coverage.
        probe_dir = tempfile.mkdtemp()
        try:
            result = _run_bash_probe(probe_dir)
        finally:
            shutil.rmtree(probe_dir, ignore_errors=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout == b"okstub"


def _bash_skip_reason():
    """Why the completion fixture cannot run here, or None when it can.

    Stated concretely because the WSL case is invisible otherwise: the tests
    just disappear, and the next person has to rediscover that `bash` resolved
    to a launcher that cannot reach the paths the fixture uses.
    """
    if not BASH_EXECUTABLE:
        return "bash was not found on PATH"
    if not _usable_bash():
        return (
            "%s starts but cannot source a script at its host path or run a stub "
            "found through PATH, so every completion would return no candidates. "
            "The WSL launcher at C:\\Windows\\System32\\bash.exe behaves this way; "
            "put Git Bash ahead of it on PATH, or run these tests on Linux/macOS."
            % BASH_EXECUTABLE
        )
    return None


_BASH_SKIP_REASON = _bash_skip_reason()


def _error_codes(diagnostics):
    return [
        diagnostic.code for diagnostic in diagnostics if diagnostic.severity == "error"
    ]


class GoldenRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(GOLDEN_PATH, "r", encoding="utf-8") as handle:
            cls.corpus = json.load(handle)

    def test_manifest_version_is_explicit(self):
        self.assertEqual(1, self.corpus["version"])
        self.assertGreaterEqual(len(self.corpus["cases"]), 9)

    def test_canonical_output_is_idempotent(self):
        for case in self.corpus["cases"]:
            with self.subTest(case=case["name"]):
                items, diagnostics = parse_text(case["canonical"])
                self.assertEqual([], _error_codes(diagnostics))
                canonical = _canonical_text(items)
                self.assertEqual(case["canonical"], canonical)
                self.assertEqual(canonical, canonical.replace("\r\n", "\n"))

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

    def test_repeated_body_and_continuation_are_rejected(self):
        text = "[N] N Note body:first body:second\n| continuation\n"
        items, diagnostics = parse_text(text)
        errors = [diagnostic for diagnostic in diagnostics if diagnostic.code == "E022"]
        self.assertEqual(1, len(items))
        self.assertEqual(1, len(errors))
        self.assertEqual(2, errors[0].line)
        self.assertEqual(1, errors[0].column)
        self.assertEqual(["first", "second"], items[0].details["body"])

    def test_indented_repeated_body_reports_continuation_column(self):
        text = "  [N] N Note body:first body:second\n  | continuation\n"
        _items, diagnostics = parse_text(text)
        error = next(
            diagnostic for diagnostic in diagnostics if diagnostic.code == "E022"
        )
        self.assertEqual(2, error.line)
        self.assertEqual(3, error.column)

    def test_single_inline_body_continuation_remains_compatible_and_canonicalizes(self):
        text = "[N] N Note body:First_line\n| Second line\n"
        items, diagnostics = parse_text(text)
        self.assertNotIn("E022", _error_codes(diagnostics))
        self.assertEqual("First_line\nSecond line", items[0].details["body"][0])
        self.assertEqual(
            "[N] N Note\n| First_line\n| Second line", item_to_line(items[0])
        )

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


@unittest.skipIf(_BASH_SKIP_REASON is not None, _BASH_SKIP_REASON or "")
class BashCompletionExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.script_path = os.path.join(self.temp_dir.name, "lifetxt-completion.bash")
        with open(self.script_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(bash_completion())

        self.stub_path = os.path.join(self.temp_dir.name, "lifetxt")
        _write_bash_stub(
            self.stub_path,
            "if [[ $1 == completion && $2 == values && $3 == --kind ]]; then\n"
            "  case $4 in\n"
            "    project) printf 'research\\nhome\\n' ;;\n"
            "    state) printf 'busy\\naway\\n' ;;\n"
            "  esac\n"
            "fi\n",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _complete(self, words, cword):
        quoted_words = " ".join("'%s'" % word.replace("'", "'\\''") for word in words)
        command = (
            'source "$1"\n'
            "COMP_WORDS=(%s)\n"
            "COMP_CWORD=%d\n"
            "_lifetxt_completion\n"
            "printf '%s\\n' \"${COMPREPLY[@]}\"\n"
        ) % (quoted_words, cword, "%s")
        environment = dict(os.environ)
        environment["PATH"] = (
            self.temp_dir.name + os.pathsep + environment.get("PATH", "")
        )
        result = subprocess.run(
            [
                BASH_EXECUTABLE,
                "--noprofile",
                "--norc",
                "-c",
                command,
                "bash",
                self.script_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
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
