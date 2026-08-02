import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from lifetxt import atomic
from lifetxt import mutation
from lifetxt import timer
from lifetxt import tui_app
from lifetxt import webapp
from lifetxt.fzf_helper import _write_text as fzf_write_text
from lifetxt.mcp import McpContext, _tool_create_item
from lifetxt.mutation import MutationResult, read_text_snapshot
from lifetxt.parser import parse_text


class _TuiState(object):
    def __init__(self, path, rows=None):
        self.args = SimpleNamespace(paths=[path], config_data={})
        self.options = {"id_key": "id"}
        self._rows = list(rows or [])
        self.marked = set()
        self.undo_stack = []
        self.reload_count = 0

    def target_rows(self):
        return list(self._rows)

    def reload(self):
        self.reload_count += 1


class SharedSurfaceMutationRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def path(self, name="life.txt"):
        return os.path.join(self.temp_dir.name, name)

    def write(self, path, text):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def items(self, path):
        parsed, diagnostics = parse_text(read_text_snapshot(path).text)
        errors = [item for item in diagnostics if item.severity == "error"]
        self.assertEqual([], errors)
        return parsed

    def test_atomic_text_compatibility_api_calls_shared_writer(self):
        path = self.path()
        with mock.patch(
            "lifetxt.mutation.write_text", wraps=mutation.write_text
        ) as routed:
            result = atomic.atomic_write_text(path, "one\n")
        self.assertIsInstance(result, MutationResult)
        self.assertEqual("one\n", read_text_snapshot(path).text)
        routed.assert_called_once()
        self.assertEqual("atomic_write_text", routed.call_args[1]["operation"])
        self.assertTrue(routed.call_args[1]["create"])

    def test_atomic_json_compatibility_api_calls_shared_writer(self):
        path = self.path("state.json")
        with mock.patch(
            "lifetxt.mutation.write_text", wraps=mutation.write_text
        ) as routed:
            result = atomic.atomic_write_json(path, {"count": 1})
        self.assertIsInstance(result, MutationResult)
        self.assertEqual({"count": 1}, json.loads(read_text_snapshot(path).text))
        routed.assert_called_once()

    def test_atomic_text_keeps_legacy_newline_translation(self):
        path = self.path()
        atomic.atomic_write_text(path, "one\ntwo\n", newline="\r\n")
        with open(path, "rb") as handle:
            self.assertEqual(b"one\r\ntwo\r\n", handle.read())

    def test_fzf_direct_writer_is_replaced_by_shared_route(self):
        path = self.path()
        self.write(path, "[ ] T Task id:T-1\n")
        with mock.patch(
            "lifetxt.mutation.write_text", wraps=mutation.write_text
        ) as routed:
            fzf_write_text(path, "[x] T Task id:T-1\n")
        self.assertEqual("[x]", self.items(path)[0].status)
        routed.assert_called_once()
        self.assertEqual("fzf_helper.write_text", routed.call_args[1]["operation"])

    def test_tui_mutate_rows_routes_status_write_through_shared_layer(self):
        path = self.path()
        self.write(path, "[ ] T Task id:T-1\n")
        state = _TuiState(
            path,
            rows=[
                {
                    "source": path,
                    "id": "T-1",
                    "type": "T",
                    "title": "Task",
                }
            ],
        )
        with mock.patch(
            "lifetxt.mutation.write_text", wraps=mutation.write_text
        ) as routed:
            level, _message = tui_app._cmd_status(state, "done")
        self.assertEqual("success", level)
        self.assertEqual("[x]", self.items(path)[0].status)
        self.assertGreaterEqual(routed.call_count, 1)
        self.assertEqual(1, state.reload_count)

    def test_tui_presence_transition_routes_through_shared_layer(self):
        path = self.path()
        self.write(path, "")
        state = _TuiState(path)
        with mock.patch(
            "lifetxt.mutation.write_text", wraps=mutation.write_text
        ) as routed:
            level, _message = tui_app._cmd_state(state, "busy Focus")
        self.assertEqual("success", level)
        item = self.items(path)[0]
        self.assertEqual("S", item.kind)
        self.assertEqual(["busy"], item.details["state"])
        self.assertGreaterEqual(routed.call_count, 1)

    def test_timer_item_update_routes_through_shared_layer(self):
        path = self.path()
        self.write(path, "[ ] T Task id:T-1\n")
        with mock.patch(
            "lifetxt.mutation.write_text", wraps=mutation.write_text
        ) as routed:
            timer.update_item_in_file(
                path,
                "T-1",
                "id",
                status="[/]",
                set_details={"elapsed": ["25m"]},
            )
        item = self.items(path)[0]
        self.assertEqual("[/]", item.status)
        self.assertEqual(["25m"], item.details["elapsed"])
        self.assertGreaterEqual(routed.call_count, 1)

    def test_web_notification_ack_routes_through_shared_layer(self):
        path = self.path()
        self.write(path, "[ ] M Ping id:M-1 sender:self recipient:self\n")
        with mock.patch(
            "lifetxt.mutation.write_text", wraps=mutation.write_text
        ) as routed:
            item = webapp.ack_message_in_file(
                path,
                "M-1",
                {"ack": "2026-07-22T12:00"},
                key="id",
            )
        self.assertEqual(["2026-07-22T12:00"], item.details["ack"])
        self.assertGreaterEqual(routed.call_count, 1)

    def test_mcp_create_routes_through_shared_layer(self):
        path = self.path()
        self.write(path, "")
        context = McpContext(paths=[path], writable_path=path, config={})
        with mock.patch(
            "lifetxt.mutation.write_text", wraps=mutation.write_text
        ) as routed:
            result = _tool_create_item(
                {"type": "T", "title": "Created by MCP", "details": {}},
                context,
            )
        self.assertEqual("Created by MCP", result["item"]["title"])
        self.assertGreaterEqual(routed.call_count, 1)
        self.assertFalse(os.path.exists(path + ".lifetxt.lock"))


if __name__ == "__main__":
    unittest.main()
