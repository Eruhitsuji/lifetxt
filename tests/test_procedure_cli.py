import codecs
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lifetxt.procedure_cli import read_definition
from lifetxt.procedure_definition import ProcedureError
from tests.test_lifetxt import run_cli
from tests.test_procedure_definition import SAMPLE


class ProcedureCliTests(unittest.TestCase):
    def test_show_and_all_graph_formats_are_read_only_and_warnings_use_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "procedure with spaces.txt"
            path.write_text(SAMPLE)
            before = path.read_bytes()
            for verb, flags in (
                ("show", ()),
                ("graph", ("--format", "mermaid")),
                ("graph", ("--format", "dot")),
                ("graph", ("--format", "text")),
            ):
                with self.subTest(verb=verb, flags=flags):
                    out, err, code = run_cli(
                        "procedure", verb, str(path), "--id", "r", *flags
                    )
                    self.assertEqual(0, code, err)
                    self.assertTrue(out)
                    self.assertIn("PG201", err)
                    self.assertNotIn("WARNING", out)
                    self.assertNotIn("W106", err)
                    self.assertEqual(before, path.read_bytes())
                    self.assertEqual([path], list(Path(directory).iterdir()))

    def test_errors_have_nonzero_exit_and_empty_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "procedure.txt"
            cases = [
                (SAMPLE.replace("proc_next:q", "proc_next:missing", 1), "r", "PG110"),
                (SAMPLE, "missing", "PG005"),
                (SAMPLE + "invalid syntax\n", "r", "PG404"),
            ]
            for text, ident, expected in cases:
                path.write_text(text)
                out, err, code = run_cli(
                    "procedure",
                    "graph",
                    str(path),
                    "--id",
                    ident,
                    "--format",
                    "mermaid",
                )
                self.assertNotEqual(0, code)
                self.assertEqual("", out)
                self.assertIn(expected, err)
            path.write_bytes(b"\xff\xff")
            out, err, code = run_cli("procedure", "show", str(path), "--id", "r")
            self.assertEqual(("", 1), (out, code))
            self.assertIn("PG403", err)

    def test_missing_file_no_private_path_leak(self):
        out, err, code = run_cli(
            "procedure", "show", "missing/private/path", "--id", "r"
        )
        self.assertEqual(("", 1), (out, code))
        self.assertIn("PG405", err)
        self.assertNotIn("missing/private/path", err)

    def test_exact_source_byte_revision_bom_and_crlf(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            for raw in (
                SAMPLE.encode(),
                codecs.BOM_UTF8 + SAMPLE.replace("\n", "\r\n").encode(),
            ):
                path.write_bytes(raw)
                graph = read_definition(str(path), "r")
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(), graph.projection.template_revision
                )
            path.write_text(SAMPLE + "# comment changes revision\n")
            self.assertNotEqual(
                hashlib.sha256(SAMPLE.encode()).hexdigest(),
                read_definition(str(path), "r").projection.template_revision,
            )

    def test_bounded_read_and_record_count_before_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            path.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
            with patch("lifetxt.procedure_cli.parse_text") as parser:
                with self.assertRaises(ProcedureError) as caught:
                    read_definition(str(path), "r")
                parser.assert_not_called()
            self.assertEqual("PG402", caught.exception.diagnostics[0].code)
            path.write_text("[N] N note\n" * 10_001)
            with patch("lifetxt.procedure_cli.parse_text") as parser:
                with self.assertRaises(ProcedureError) as caught:
                    read_definition(str(path), "r")
                parser.assert_not_called()
            self.assertEqual("PG002", caught.exception.diagnostics[0].code)

    def test_body_and_backslash_continuations_are_not_extra_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            path.write_text(
                SAMPLE.replace(
                    "proc_role:root proc_version:1",
                    "proc_role:root \\\n proc_version:1",
                )
            )
            self.assertEqual(4, len(read_definition(str(path), "r").projection.steps))

    def test_extra_file_glob_stdin_and_alternate_id_key_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            path.write_text(SAMPLE)
            for args in (
                (str(path), str(path), "--id", "r"),
                ("-", "--id", "r"),
                (str(Path(directory) / "*.txt"), "--id", "r"),
            ):
                out, err, code = run_cli("procedure", "show", *args)
                self.assertNotEqual(0, code)
                self.assertEqual("", out)
            with self.assertRaises(ProcedureError) as caught:
                read_definition(str(path), "r", id_key="uid")
            self.assertEqual("PG001", caught.exception.diagnostics[0].code)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO is POSIX only")
    def test_fifo_refused_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fifo"
            os.mkfifo(path)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lifetxt",
                    "procedure",
                    "show",
                    str(path),
                    "--id",
                    "r",
                ],
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("", result.stdout)
            self.assertIn("PG401", result.stderr)

    def test_subprocess_nontty_and_cli_help_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            path.write_text(SAMPLE)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lifetxt",
                    "procedure",
                    "graph",
                    str(path),
                    "--id",
                    "r",
                    "--format",
                    "dot",
                ],
                input="yes\n",
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(result.stdout.startswith("digraph procedure"))
        out, err, code = run_cli("procedure", "show", "--help")
        self.assertEqual(0, code, err)
        self.assertIn("--id", out)
        from lifetxt.completion import _subparser_map

        self.assertIn("procedure", _subparser_map())

    def test_unrelated_deep_relation_graph_is_not_traversed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            text = (
                SAMPLE
                + "\n".join(
                    "[ ] T Work id:t%d depends_on:t%d" % (i, i + 1) for i in range(1500)
                )
                + "\n"
            )
            path.write_text(text)
            self.assertEqual(4, len(read_definition(str(path), "r").projection.steps))

    def test_bilingual_examples_and_independent_occurrences(self):
        from lifetxt.parser import parse_text
        from lifetxt.serializer import item_to_line

        for lang in ("en", "ja"):
            template = Path("examples/procedure-template-" + lang + ".txt").read_text()
            work = Path("examples/procedure-work-" + lang + ".txt").read_text()
            items, diagnostics = parse_text(template + work)
            self.assertFalse([row for row in diagnostics if row.severity == "error"])
            self.assertEqual(
                {"[N]"}, {item.status for item in items if item.kind == "N"}
            )
            first = [
                item
                for item in items
                if item.details.get("id", [""])[0].startswith("work1_")
            ]
            second = [
                item
                for item in items
                if item.details.get("id", [""])[0].startswith("work2_")
            ]
            self.assertEqual(4, len(first))
            self.assertEqual({"[x]"}, {item.status for item in first})
            self.assertEqual(4, len(second))
            self.assertIn("[?]", {item.status for item in second})
            graph = read_definition("examples/procedure-flow-" + lang + ".txt", "r")
            self.assertEqual(4, len(graph.projection.steps))
            decoded, _ = parse_text(
                "\n".join(item_to_line(item) for item in items) + "\n"
            )
            self.assertEqual(
                [item.to_dict() for item in items], [item.to_dict() for item in decoded]
            )
