"""Cross-buffer semantics and limits are delegated to Core, without disk I/O."""

import unittest
from unittest.mock import patch

from lifetxt.lsp import Server
from lifetxt.lsp_document import Document, utf16_length
from lifetxt.lsp_features import completion, hover


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.server = Server(self.messages.append)
        self.send("initialize", {}, True)

    def send(self, method, params, request=False):
        self.server.handle(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                **({"id": 1} if request else {}),
            }
        )

    def open(self, uri, text):
        self.send(
            "textDocument/didOpen",
            {"textDocument": {"uri": uri, "version": 1, "text": text}},
        )

    def change(self, uri, text, version=2):
        self.send(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": version},
                "contentChanges": [{"text": text}],
            },
        )

    def codes(self, uri):
        row = next(
            m
            for m in reversed(self.messages)
            if m.get("method") == "textDocument/publishDiagnostics"
            and m["params"]["uri"] == uri
        )
        return [d["code"] for d in row["params"]["diagnostics"]]

    def labels(self, uri):
        doc = self.server.documents[uri]
        self.send(
            "textDocument/completion",
            {
                "textDocument": {"uri": uri},
                "position": {"line": 0, "character": utf16_length(doc.text)},
            },
            True,
        )
        return [r["label"] for r in self.messages[-1]["result"]]

    def test_reference_diagnostic_tracks_other_unsaved_buffer_and_close(self):
        self.open("untitled:a", "[ ] T a ref:b")
        self.assertIn("W215", self.codes("untitled:a"))
        self.open("vscode-remote://host/b", "[ ] T b id:b")
        self.assertNotIn("W215", self.codes("untitled:a"))
        self.change("vscode-remote://host/b", "[ ] T b id:renamed")
        self.assertIn("W215", self.codes("untitled:a"))
        self.change("vscode-remote://host/b", "[ ] T b id:b", 3)
        self.send(
            "textDocument/didClose", {"textDocument": {"uri": "vscode-remote://host/b"}}
        )
        self.assertIn("W215", self.codes("untitled:a"))
        self.assertEqual([], self.messages[-1]["params"]["diagnostics"])

    def test_duplicate_ids_and_ambiguous_reference_are_routed_to_source(self):
        self.open("a", "[ ] T a id:same")
        self.open("b", "[ ] T b id:same")
        self.open("c", "[ ] T c ref:same")
        self.assertIn("W213", self.codes("b"))
        self.assertNotIn("W213", self.codes("a"))
        self.assertIn("W218", self.codes("c"))

    def test_workspace_values_and_custom_id_key_follow_open_buffers(self):
        self.server.id_key = "uid"
        self.open(
            "a", '[ ] T a uid:custom project:"team alpha" assignee:alice tag:demo'
        )
        self.open("b", "[ ] T b ref:")
        self.assertEqual(["custom"], self.labels("b"))
        self.change("b", "[ ] T b project:")
        self.assertEqual(["team alpha"], self.labels("b"))
        self.change("b", "[ ] T b assignee:", 3)
        self.assertEqual(["alice"], self.labels("b"))
        self.send("textDocument/didClose", {"textDocument": {"uri": "a"}})
        self.assertEqual([], self.labels("b"))

    def test_workspace_no_io_and_unopened_file_uri_is_not_read(self):
        with (
            patch("builtins.open", side_effect=AssertionError("disk")),
            patch("socket.socket", side_effect=AssertionError("network")),
        ):
            self.open("file:///unopened/private.life.txt", "[ ] T a ref:unopened")
            self.assertIn("W215", self.codes("file:///unopened/private.life.txt"))

    def test_limit_open_documents_and_candidate_results(self):
        for i in range(32):
            self.open(f"buffer:{i}", f"[ ] T title id:t{i}")
        self.open("too-many", "[ ] T extra")
        self.assertNotIn("too-many", self.server.documents)
        self.assertEqual("window/logMessage", self.messages[-1]["method"])
        self.assertEqual(32, len(self.server.documents))

    def test_deep_core_reference_graph_reports_analysis_limit_without_crashing(self):
        text = "\n".join(f"[ ] T t id:t{i} depends_on:t{i + 1}" for i in range(1100))
        self.open("deep", text)
        self.assertIn("LSP001", self.codes("deep"))
        self.change("deep", "[ ] T recovered")
        self.assertNotIn("LSP001", self.codes("deep"))

    def test_unsupported_format_does_not_supply_ids_to_current_documents(self):
        self.open("future", "#! format_version: 999\n[ ] T future id:untrusted")
        self.open("current", "[ ] T current ref:")
        self.assertEqual([], self.labels("current"))
        self.assertIn("F110", self.codes("future"))


class PositionAndCompletionRegressions(unittest.TestCase):
    def test_continued_quote_span_maps_to_second_physical_line(self):
        text = '\ufeff[ ] T "日本語😀" \\\r\n  note:"unclosed'
        doc = Document("a", 1, text)
        diag = next(d for d in doc.diagnostics() if d["code"] == "E018")
        self.assertEqual({"line": 1, "character": 7}, diag["range"]["start"])
        self.assertEqual(
            {"line": 1, "character": len('  note:"unclosed')}, diag["range"]["end"]
        )

    def test_hover_does_not_misread_unfinished_quoted_values(self):
        text = '[ ] T title note:"incomplete due:example'
        doc = Document("a", 1, text)
        self.assertIsNone(hover(doc, {"line": 0, "character": text.index("due:")}))

    def test_prefix_filter_happens_before_result_cap(self):
        text = (
            "\n".join(f"[ ] T t project:p{i}" for i in range(210))
            + "\n[ ] T t project:zzmatch\n[ ] T t project:zz"
        )
        doc = Document("a", 1, text)
        result = completion(doc, {"line": 211, "character": len("[ ] T t project:zz")})
        self.assertIn("zzmatch", [r["label"] for r in result])

    def test_non_ascii_prefix_preserves_utf16_edit_range(self):
        text = '[ ] T "😀" project:日本'
        doc = Document("a", 1, text)
        result = completion(doc, {"line": 0, "character": utf16_length(text)})
        self.assertEqual("日本", result[0]["textEdit"]["newText"])
        self.assertEqual(
            utf16_length(text[: text.index("日本")]),
            result[0]["textEdit"]["range"]["start"]["character"],
        )

    def test_result_cap_is_enforced_for_diagnostics_and_completion(self):
        text = "\n".join(f"[ ] T title id:t{i}" for i in range(205)) + "\n[ ] T t ref:"
        doc = Document("a", 1, text)
        self.assertEqual(
            200, len(completion(doc, {"line": 205, "character": len("[ ] T t ref:")}))
        )
        doc = Document("a", 1, "\n".join("[ ] X invalid" for _ in range(205)))
        self.assertEqual(200, len(doc.diagnostics()))

    def test_unicode_separator_core_lines_map_back_to_one_lsp_line(self):
        text = "\ufeff[ ] T a\u2028[ ] X b"
        doc = Document("a", 1, text)
        diagnostic = next(d for d in doc.diagnostics() if d["code"] == "E005")
        expected = utf16_length(text[: text.index("X")])
        self.assertEqual(
            {"line": 0, "character": expected}, diagnostic["range"]["start"]
        )

    def test_extreme_content_length_is_rejected_as_protocol_error(self):
        import io
        from lifetxt.lsp import read_message, ProtocolError

        with self.assertRaises(ProtocolError):
            read_message(io.BytesIO(b"Content-Length: " + b"9" * 5000 + b"\r\n\r\n"))
