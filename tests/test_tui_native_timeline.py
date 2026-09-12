"""Tests for the TUI /timeline command (#761).

/timeline exposes the existing shared Native Temporal Timeline read model
(:func:`lifetxt.native_timeline.native_timeline`) through the interactive
TUI, mirroring how /thread already delegates to
:mod:`lifetxt.temporal_thread`. No history/filtering/analytics logic is
duplicated here; these tests confirm the command is a thin adapter over
the unmodified shared reader.
"""

import unittest
from types import SimpleNamespace

from lifetxt import tui_app
from lifetxt.native_history import build_item_event
from lifetxt.native_timeline import DEFAULT_LIMIT, native_timeline
from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line


REVISION = "a" * 64


class _FakeLocalBackend(object):
    """Minimal stand-in for :class:`lifetxt.tui_backend.LocalTuiBackend`'s
    ``native_timeline`` method (#768), so these tests keep exercising the
    exact shared reader without constructing a real backend/args pair.
    """

    is_remote = False

    def __init__(self, items):
        self.items = items

    def native_timeline(
        self, target_id, since=None, until=None, event=None, limit=None
    ):
        return native_timeline(
            self.items,
            target_id,
            limit=limit if limit is not None else DEFAULT_LIMIT,
            since=since,
            until=until,
            event=event,
        )


def _fixture():
    created = build_item_event(
        "task-1",
        "created",
        "2026-09-10T10:00:00Z",
        1,
        "ITX-1",
        REVISION,
        item_kind="T",
        item_title="Task",
        after_status="[ ]",
    )
    completed = build_item_event(
        "task-1",
        "completed",
        "2026-09-10T12:00:00Z",
        2,
        "ITX-2",
        REVISION,
        before_status="[ ]",
        after_status="[x]",
    )
    text = (
        "[x] T Task id:task-1\n"
        + item_to_line(created)
        + "\n"
        + item_to_line(completed)
        + "\n"
    )
    return parse_text(text)[0]


class TuiTimelineCommandTests(unittest.TestCase):
    def setUp(self):
        self.items = _fixture()

    def _state(self, row=None):
        row = {"id": "task-1"} if row is None else row
        return SimpleNamespace(
            args=SimpleNamespace(config_data={}),
            backend=_FakeLocalBackend(self.items),
            _items=self.items,
            rows=[row],
            selected=0,
            show_detail=False,
            selected_row=lambda: row,
        )

    def test_delegates_to_the_shared_timeline_model(self):
        state = self._state()
        level, message = tui_app._cmd_timeline(state, "")
        self.assertEqual("info", level)
        self.assertIn("Native Timeline", message)
        self.assertEqual("temporal-timeline-v1", state._native_timeline["schema"])
        self.assertEqual(2, len(state._native_timeline["events"]))
        self.assertTrue(state.show_detail)
        self.assertEqual("task-1", state._native_timeline_target)

    def test_explicit_id_argument_overrides_the_selected_row(self):
        state = self._state(row={"id": "other"})
        level, message = tui_app._cmd_timeline(state, "task-1")
        self.assertEqual("info", level)
        self.assertEqual("task-1", state._native_timeline_target)

    def test_since_until_event_filters_are_parsed_from_trailing_tokens(self):
        state = self._state()
        tui_app._cmd_timeline(
            state,
            "task-1 since=2026-09-10T11:00:00Z event=completed",
        )
        events = state._native_timeline["events"]
        self.assertEqual(1, len(events))
        self.assertEqual("completed", events[0]["event"])

    def test_missing_id_with_no_selection_fails_loudly(self):
        state = self._state(row={})
        with self.assertRaisesRegex(ValueError, "Usage: /timeline"):
            tui_app._cmd_timeline(state, "")

    def test_unknown_id_fails_loudly(self):
        state = self._state()
        with self.assertRaises(ValueError):
            tui_app._cmd_timeline(state, "no-such-id")

    def test_command_is_registered(self):
        command = tui_app.COMMANDS_BY_NAME["timeline"]
        self.assertIs(tui_app._cmd_timeline, command.handler)
        self.assertEqual("id", command.values)


if __name__ == "__main__":
    unittest.main()
