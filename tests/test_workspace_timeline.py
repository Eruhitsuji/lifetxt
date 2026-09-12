import json
import os
import tempfile
import unittest

from lifetxt.native_history import build_item_event
from lifetxt.native_timeline import native_timeline
from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line
from lifetxt.workspace_timeline import workspace_timeline
from tests.test_lifetxt import run_cli


REVISION = "a" * 64


def _items():
    first = build_item_event(
        "one",
        "completed",
        "2026-09-10T10:00:00Z",
        1,
        "TX-1",
        REVISION,
        before_status="[ ]",
        after_status="[x]",
    )
    second = build_item_event(
        "two",
        "completed",
        "2026-09-10T09:00:00Z",
        1,
        "TX-2",
        REVISION,
        before_status="[ ]",
        after_status="[x]",
    )
    items, _ = parse_text(
        "[x] T One id:one project:p\n"
        "[x] T Two id:two project:p\n"
        + item_to_line(first)
        + "\n"
        + item_to_line(second)
        + "\n"
    )
    items[0].source = "one.txt"
    items[1].source = "two.txt"
    return items


class WorkspaceTimelineTests(unittest.TestCase):
    def test_merges_targets_in_native_order_with_provenance(self):
        result = workspace_timeline(_items(), project="p")
        self.assertEqual("workspace-life-timeline-v1", result["schema"])
        self.assertEqual(["two", "one"], [row["target_id"] for row in result["events"]])
        self.assertEqual("one.txt", result["events"][1]["source"])
        self.assertFalse(result["git_composed"])

    def test_limit_and_filters_are_bounded(self):
        result = workspace_timeline(_items(), limit=1)
        self.assertEqual(1, len(result["events"]))
        self.assertTrue(result["bounds"]["truncated"])
        self.assertIn("event_limit_truncated", result["limitations"])
        with self.assertRaisesRegex(ValueError, "since must not be after until"):
            workspace_timeline(
                _items(), since="2026-09-11T00:00:00Z", until="2026-09-10T00:00:00Z"
            )

    def test_cli_workspace_json_uses_shared_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                for item in _items():
                    handle.write(item_to_line(item) + "\n")
            stdout, stderr, code = run_cli(
                "timeline", "--workspace-timeline", path, "--json"
            )
            self.assertEqual(0, code, stderr)
            self.assertEqual("workspace-life-timeline-v1", json.loads(stdout)["schema"])
