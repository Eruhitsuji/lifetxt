"""Observable LSP contracts: in-memory Core parity and protocol lifecycle."""

import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from lifetxt.lsp import Server, ProtocolError, read_message, write_message, serve
from lifetxt.lsp_document import Document, MAX_DOCUMENT_BYTES, utf16_length
from lifetxt.lsp_features import completion, hover
from lifetxt.model import VALID_STATUSES, VALID_TYPES, Diagnostic
from lifetxt.parser import parse_text

URI = "untitled:life.txt"


def position(text):
    lines = text.split("\n")
    return {"line": len(lines) - 1, "character": utf16_length(lines[-1])}


def labels(text):
    return [x["label"] for x in completion(Document(URI, 1, text), position(text))]


class DocumentTests(unittest.TestCase):
    def test_core_diagnostic_code_severity_parity(self):
        texts = [
            "[ ] X invalid",
            "[ ] T title custom:ok",
            "[ ] T title due:nope",
            "[ ] T title id:a\n[ ] T another id:a",
            "| orphan",
            "[ ] T title \\\n  due:invalid",
            '[ ] T "日本語😀é" note:"bad\\q"',
        ]
        for text in texts:
            with self.subTest(text=text):
                core = parse_text(text)[1]
                got = Document(URI, 1, text).diagnostics()
                self.assertEqual(
                    [(d.code, 1 if d.severity == "error" else 2) for d in core],
                    [(d["code"], d["severity"]) for d in got],
                )

    def test_utf16_bom_crlf_and_combining_character_ranges(self):
        text = '\ufeff[ ] T "日本語😀é" note:"bad\\q"\r\n[ ] X invalid\r'
        doc = Document(URI, 1, text)
        self.assertEqual(3, len(doc.lines))
        expected = parse_text(text.removeprefix("\ufeff"))[1]
        for diagnostic, got in zip(expected, doc.diagnostics()):
            row = (diagnostic.line or 1) - 1
            col = (diagnostic.column or 1) - 1 + (row == 0)
            self.assertEqual(
                {"line": row, "character": utf16_length(doc.lines[row][:col])},
                got["range"]["start"],
            )
        emoji = doc.lines[0].index("😀")
        with self.assertRaises(ValueError):
            doc.offset({"line": 0, "character": utf16_length(doc.lines[0][:emoji]) + 1})

    def test_unknown_end_span_is_zero_width(self):
        doc = Document(URI, 1, "[ ] T title")
        doc.result[1].append(Diagnostic("error", "TEST", "test", line=1, column=4))
        self.assertEqual(
            doc.diagnostics()[-1]["range"]["start"],
            doc.diagnostics()[-1]["range"]["end"],
        )

    def test_full_span_comes_from_core(self):
        doc = Document(URI, 1, '[ ] T "unclosed')
        core = doc.result[1][0]
        self.assertIsNotNone(core.end_column)
        got = doc.diagnostics()[0]["range"]
        self.assertEqual(doc.position(core.end_line, core.end_column), got["end"])

    def test_size_and_version_boundaries(self):
        Document(URI, 0, "a" * MAX_DOCUMENT_BYTES)
        with self.assertRaises(ValueError):
            Document(URI, 1, "😀" * (MAX_DOCUMENT_BYTES // 4 + 1))
        with self.assertRaises(ValueError):
            Document(URI, True, "")


class FeatureTests(unittest.TestCase):
    def test_all_types_and_statuses_with_explicit_replacement(self):
        self.assertEqual(list(VALID_STATUSES), labels(""))
        self.assertEqual(list(VALID_TYPES), labels("[ ] "))
        text = "["
        first = completion(Document(URI, 1, text), position(text))[0]
        self.assertEqual("[ ]", first["textEdit"]["newText"])
        self.assertEqual(0, first["textEdit"]["range"]["start"]["character"])

    def test_recommended_keys_custom_keys_and_reference_union(self):
        self.assertEqual("from:", labels("[ ] E title ")[0])
        self.assertEqual("due:", labels("[ ] D title ")[0])
        for key in ["duplicate_of:", "realizes:", "custom:"]:
            self.assertIn(key, labels("[ ] T one custom:yes\n[ ] T title "))
        self.assertIn("done:", labels("[x] T title "))

    def test_no_completion_in_titles_quotes_comments_body_or_joined_lines(self):
        for text in [
            "# comment ",
            "| body ",
            "[ ] T tit",
            '[ ] T "unfinished ',
            '[ ] T title note:"foo ',
            "[ ] T title \\\n  due:",
        ]:
            with self.subTest(text=text):
                self.assertEqual([], labels(text))

    def test_middle_token_and_key_colon_are_replaced(self):
        text = "[ ] T title due:2026-10-17"
        doc = Document(URI, 1, text)
        entries = completion(doc, {"line": 0, "character": text.index("due") + 2})
        entry = next(e for e in entries if e["label"] == "due:")
        self.assertEqual(
            text.index("due") + 4, entry["textEdit"]["range"]["end"]["character"]
        )

    def test_value_completion_quotes_space_and_escaping(self):
        text = '[ ] T one project:"a b"\n[ ] T two project:'
        result = completion(Document(URI, 1, text), position(text))
        self.assertEqual('"a b"', result[0]["textEdit"]["newText"])

    def test_hover_uses_shared_help_and_never_describes_body_values(self):
        text = '[ ] T "日本語😀 title" due:2026-10-17 note:"due: fake"'
        doc = Document(URI, 1, text)
        point = utf16_length(text[: text.index("due:")])
        self.assertIn(
            "Deadline", hover(doc, {"line": 0, "character": point})["contents"]["value"]
        )
        point = utf16_length(text[: text.index("due: fake")])
        self.assertIsNone(hover(doc, {"line": 0, "character": point}))

    def test_unsupported_version_does_not_offer_current_format_completion(self):
        text = "#! format_version: 999\n[ ] T title "
        self.assertEqual([], labels(text))


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.server = Server(self.messages.append)

    def send(self, method, params=None, request=False):
        self.server.handle(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                **({"id": 1} if request else {}),
            }
        )

    def open(self, text="[ ] X bad", version=1):
        self.send(
            "textDocument/didOpen",
            {"textDocument": {"uri": URI, "version": version, "text": text}},
        )

    def test_lifecycle_and_unadvertised_methods(self):
        self.send("textDocument/hover", {}, True)
        self.assertEqual(-32002, self.messages[-1]["error"]["code"])
        self.send("initialize", {}, True)
        self.assertEqual(
            "utf-16", self.messages[-1]["result"]["capabilities"]["positionEncoding"]
        )
        self.open()
        self.assertEqual("textDocument/publishDiagnostics", self.messages[-1]["method"])
        self.send("workspace/executeCommand", {}, True)
        self.assertEqual(-32601, self.messages[-1]["error"]["code"])
        self.send("shutdown", {}, True)
        self.send("exit")
        self.assertTrue(self.server.exited)

    def test_change_uses_unsaved_text_rejects_stale_and_close_clears(self):
        self.send("initialize", {}, True)
        self.open()
        self.send(
            "textDocument/didChange",
            {
                "textDocument": {"uri": URI, "version": 3},
                "contentChanges": [{"text": "[ ] T good"}],
            },
        )
        self.assertEqual([], self.messages[-1]["params"]["diagnostics"])
        count = len(self.messages)
        self.send(
            "textDocument/didChange",
            {
                "textDocument": {"uri": URI, "version": 2},
                "contentChanges": [{"text": "[ ] X stale"}],
            },
        )
        self.assertEqual(count, len(self.messages))
        self.assertEqual(3, self.server.documents[URI].version)
        self.send("textDocument/didClose", {"textDocument": {"uri": URI}})
        self.assertEqual([], self.messages[-1]["params"]["diagnostics"])
        self.open("[ ] T reopened", version=1)
        self.assertEqual(1, self.server.documents[URI].version)

    def test_notification_limits_and_incremental_rejection_do_not_crash(self):
        self.send("initialize", {}, True)
        self.open()
        self.send(
            "textDocument/completion",
            {"textDocument": {"uri": URI}, "position": {"line": -1, "character": 0}},
            True,
        )
        self.assertEqual(-32602, self.messages[-1]["error"]["code"])
        self.send(
            "textDocument/didChange",
            {
                "textDocument": {"uri": URI, "version": 2},
                "contentChanges": [{"range": {}, "text": ""}],
            },
        )
        self.assertEqual(1, self.server.documents[URI].version)
        self.assertEqual("window/logMessage", self.messages[-1]["method"])
        self.send(
            "textDocument/didChange",
            {
                "textDocument": {"uri": URI, "version": 3},
                "contentChanges": [{"text": "a" * (MAX_DOCUMENT_BYTES + 1)}],
            },
        )
        self.assertEqual(1, self.server.documents[URI].version)

    def test_framing_unicode_content_length_and_invalid_input(self):
        stream = io.BytesIO()
        msg = {"jsonrpc": "2.0", "method": "x", "params": {"text": "日本語😀"}}
        write_message(stream, msg)
        stream.seek(0)
        self.assertEqual(msg, read_message(stream))
        for data in [
            b"Content-Length: -1\r\n\r\n",
            b"Content-Length: 3\r\n\r\n{",
            b"Content-Length: 3000000\r\n\r\n",
            b"bad\r\n\r\n",
        ]:
            with self.subTest(data=data), self.assertRaises(ProtocolError):
                read_message(io.BytesIO(data))

    def test_stdio_subprocess_has_no_stdout_noise_and_exits_cleanly(self):
        stream = io.BytesIO()
        for msg in [
            {"id": 1, "method": "initialize", "params": {}},
            {
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {"uri": URI, "version": 1, "text": "[ ] X bad"}
                },
            },
            {"id": 2, "method": "shutdown"},
            {"method": "exit"},
        ]:
            write_message(stream, {"jsonrpc": "2.0", **msg})
        run = subprocess.run(
            [sys.executable, "-m", "lifetxt.lsp", "--stdio"],
            input=stream.getvalue(),
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(0, run.returncode, run.stderr.decode())
        output = io.BytesIO(run.stdout)
        self.assertEqual(1, read_message(output)["id"])
        self.assertEqual(
            "textDocument/publishDiagnostics", read_message(output)["method"]
        )
        self.assertEqual(2, read_message(output)["id"])
        self.assertIsNone(read_message(output))

    def test_no_file_io_or_network_or_commands_from_uri_or_document(self):
        with (
            patch("builtins.open", side_effect=AssertionError("disk access")),
            patch("subprocess.Popen", side_effect=AssertionError("command")),
            patch("socket.socket", side_effect=AssertionError("network")),
        ):
            self.send("initialize", {}, True)
            self.open(
                '[ ] T "command:ignored" file:/private/secret url:https://example.invalid'
            )
        self.assertEqual(URI, self.messages[-1]["params"]["uri"])
