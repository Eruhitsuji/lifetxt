from __future__ import unicode_literals

import argparse
import os
import tempfile
import unittest

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
