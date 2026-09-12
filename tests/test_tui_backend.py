from __future__ import unicode_literals

import argparse
import os
import tempfile
import unittest
from unittest.mock import patch

from lifetxt import tui_app
from lifetxt.tui_backend import LocalTuiBackend, TuiBackend


def _write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class TuiBackendContractTests(unittest.TestCase):
    def test_base_backend_methods_are_unimplemented(self):
        backend = TuiBackend()
        self.assertFalse(backend.is_remote)
        self.assertEqual(backend.connection_label(), "local")
        with self.assertRaises(NotImplementedError):
            backend.load_items()
        with self.assertRaises(NotImplementedError):
            backend.apply_semantic_changes({}, {}, id_key="id")
        with self.assertRaises(NotImplementedError):
            backend.edit_item({})
        with self.assertRaises(NotImplementedError):
            backend.native_timeline("t1")


class LocalTuiBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "life.txt")
        _write(self.path, "[ ] T Buy_milk id:t1\n")
        self.args = argparse.Namespace(paths=[self.path], config_data={})

    def test_load_items_matches_tui_load_items(self):
        from lifetxt.tui import load_items as tui_load_items

        backend = LocalTuiBackend(self.args)
        items, diagnostics = backend.load_items()
        self.assertIsNone(diagnostics)
        expected = tui_load_items(self.args.paths)
        self.assertEqual([i.title for i in items], [i.title for i in expected])
        self.assertEqual(items[0].source, self.path)

    def test_apply_semantic_changes_writes_a_single_file(self):
        from lifetxt import mutation

        backend = LocalTuiBackend(self.args)
        before = {self.path: mutation.read_text_snapshot(self.path)}
        grouped = {self.path: [{"id": "t1", "status": "[x]"}]}
        after = backend.apply_semantic_changes(grouped, before, id_key="id")
        self.assertIn(self.path, after)
        with open(self.path, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("[x]", text)

    def test_connection_label_is_local(self):
        backend = LocalTuiBackend(self.args)
        self.assertFalse(backend.is_remote)
        self.assertEqual(backend.connection_label(), "local")

    def test_edit_item_preserves_existing_local_editor_flow(self):
        record = {"source": self.path, "line": 1, "id": "t1"}
        config = {"editor": "vim"}
        with patch("lifetxt.fzf_helper.open_editor", return_value=0) as editor:
            result = LocalTuiBackend(self.args).edit_item(record, config=config)
        self.assertEqual(result, 0)
        editor.assert_called_once_with(record, config=config)

    def test_native_timeline_matches_a_direct_native_timeline_call(self):
        from lifetxt.native_history import build_item_event
        from lifetxt.native_timeline import native_timeline
        from lifetxt.serializer import item_to_line

        created = build_item_event(
            "t1",
            "created",
            "2026-09-10T10:00:00Z",
            1,
            "ITX-1",
            "a" * 64,
            item_kind="T",
            item_title="Buy_milk",
            after_status="[ ]",
        )
        _write(
            self.path,
            "[ ] T Buy_milk id:t1\n" + item_to_line(created) + "\n",
        )
        backend = LocalTuiBackend(self.args)
        result = backend.native_timeline("t1")
        expected = native_timeline(backend.load_items()[0], "t1")
        self.assertEqual(expected, result)

    def test_native_timeline_forwards_since_until_event_and_limit(self):
        from lifetxt.native_history import build_item_event
        from lifetxt.serializer import item_to_line

        created = build_item_event(
            "t1",
            "created",
            "2026-09-10T10:00:00Z",
            1,
            "ITX-1",
            "a" * 64,
            item_kind="T",
            item_title="Buy_milk",
            after_status="[ ]",
        )
        completed = build_item_event(
            "t1",
            "completed",
            "2026-09-10T12:00:00Z",
            2,
            "ITX-2",
            "a" * 64,
            before_status="[ ]",
            after_status="[x]",
        )
        _write(
            self.path,
            "[x] T Buy_milk id:t1\n"
            + item_to_line(created)
            + "\n"
            + item_to_line(completed)
            + "\n",
        )
        backend = LocalTuiBackend(self.args)
        result = backend.native_timeline(
            "t1", since="2026-09-10T11:00:00Z", event="completed", limit=1
        )
        self.assertEqual(1, len(result["events"]))
        self.assertEqual("completed", result["events"][0]["event"])


class WorkspaceStateBackendWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "life.txt")
        _write(self.path, "[ ] T Buy_milk id:t1\n")
        self.args = argparse.Namespace(
            paths=[self.path], config_data={}, config_paths=[]
        )

    def test_default_backend_is_local(self):
        state = tui_app.WorkspaceState(self.args, glyphs=tui_app.ASCII_GLYPHS)
        self.assertIsInstance(state.backend, LocalTuiBackend)
        self.assertFalse(state.backend.is_remote)

    def test_load_uses_the_backend_and_populates_rows(self):
        state = tui_app.WorkspaceState(self.args, glyphs=tui_app.ASCII_GLYPHS)
        state.load()
        state.refresh()
        self.assertEqual(state.error, "")
        self.assertTrue(any("t1" == row.get("id") for row in state.rows))

    def test_injected_backend_is_used_instead_of_local(self):
        class RecordingBackend(LocalTuiBackend):
            def __init__(self, args):
                LocalTuiBackend.__init__(self, args)
                self.load_calls = 0

            def load_items(self):
                self.load_calls += 1
                return LocalTuiBackend.load_items(self)

        backend = RecordingBackend(self.args)
        state = tui_app.WorkspaceState(
            self.args, glyphs=tui_app.ASCII_GLYPHS, backend=backend
        )
        state.load()
        self.assertEqual(backend.load_calls, 1)


if __name__ == "__main__":
    unittest.main()
