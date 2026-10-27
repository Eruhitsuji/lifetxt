from __future__ import unicode_literals

import argparse
import os
import tempfile
import unittest

from lifetxt import tui_app
from lifetxt.parser import parse_text


class TuiTodoPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("")
        args = argparse.Namespace(paths=[self.path], config_data={}, config_paths=[])
        self.state = tui_app.WorkspaceState(args, glyphs=tui_app.ASCII_GLYPHS)
        self.state.load()
        self.state.refresh()

    def read(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            return handle.read()

    def preview(self):
        return tui_app.run_command(
            self.state,
            "/todo x 2026-10-27 2026-10-01 (A) 日本語を確認 "
            "+仕事 @家 due:2026-10-30 owner:alice",
        )

    def test_explicit_todo_mode_previews_every_mapped_field_without_writing(self):
        level, message = self.preview()

        self.assertEqual("info", level)
        self.assertIn("Enter", message)
        self.assertEqual("", self.read())
        frame = tui_app.frame_to_text(tui_app.build_frame(self.state, 100, 35))
        for expected in (
            "todo.txt preview",
            "日本語を確認",
            "[x]",
            "priority    A",
            "project     仕事",
            "context     家",
            "due         2026-10-30",
            "owner       alice",
            "done        2026-10-27",
            "created     2026-10-01",
            "source      todo.txt",
            "id          todo_",
            "Diagnostics none",
            "Enter confirm",
            "Esc cancel",
        ):
            self.assertIn(expected, frame)

    def test_enter_confirms_through_atomic_writer_and_escape_cancels(self):
        self.preview()
        self.assertTrue(tui_app.handle_key(self.state, "resize"))
        self.assertIsNotNone(self.state.todo_preview)
        narrow = tui_app.frame_to_text(tui_app.build_frame(self.state, 44, 14))
        self.assertIn("up/down", narrow)
        self.assertTrue(tui_app.handle_key(self.state, "down"))
        self.assertEqual(1, self.state.todo_preview_scroll)
        for _index in range(20):
            tui_app.handle_key(self.state, "down")
            narrow = tui_app.frame_to_text(tui_app.build_frame(self.state, 44, 14))
        self.assertIn("Diagnostics", narrow)
        self.assertTrue(tui_app.handle_key(self.state, "x"))
        self.assertEqual("", self.read())

        self.assertTrue(tui_app.handle_key(self.state, "enter"))
        self.assertIsNone(self.state.todo_preview)
        items, diagnostics = parse_text(self.read())
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(1, len(items))
        self.assertEqual("日本語を確認", items[0].title)
        self.assertEqual("[x]", items[0].status)
        self.assertEqual(["A"], items[0].details["priority"])

        before = self.read()
        self.preview()
        self.assertTrue(tui_app.handle_key(self.state, "enter"))
        self.assertIn("Duplicate id", self.state.toast.text)
        self.assertEqual(before, self.read())
        self.assertIsNotNone(self.state.todo_preview)
        tui_app.handle_key(self.state, "escape")

        tui_app.run_command(self.state, "/todo Cancel_me +work")
        self.assertTrue(tui_app.handle_key(self.state, "escape"))
        self.assertIsNone(self.state.todo_preview)
        self.assertEqual(before, self.read())

    def test_invalid_multiline_and_stale_preview_never_write(self):
        with self.assertRaises(ValueError):
            tui_app._cmd_todo(self.state, "One\nTwo")
        self.assertIsNone(self.state.todo_preview)
        self.assertEqual("", self.read())

        tui_app.run_command(self.state, "/todo Safe +work")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Concurrent id:other\n")
        self.assertTrue(tui_app.handle_key(self.state, "enter"))
        self.assertIn("Workspace changed", self.state.toast.text)
        self.assertEqual("[ ] T Concurrent id:other\n", self.read())
        self.assertIsNotNone(self.state.todo_preview)

    def test_add_remains_the_immediate_default_creation_command(self):
        level, _message = tui_app.run_command(self.state, "/add Ordinary @home")

        self.assertEqual("success", level)
        self.assertIsNone(self.state.todo_preview)
        self.assertIn("[ ] T Ordinary", self.read())


if __name__ == "__main__":
    unittest.main()
