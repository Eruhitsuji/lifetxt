"""Tests for GET /api/native-timeline/{id} (#762).

Mirrors GET /api/temporal-thread/{id} (#704): the route delegates entirely
to the existing shared ``lifetxt.native_timeline.native_timeline`` reader
with no new Web-specific temporal logic. These tests confirm API/domain
parity, filter wiring, invalid input, escaping, and that adding this route
does not disturb any existing route.
"""

import os
import tempfile
import unittest
from pathlib import Path

from lifetxt.native_history import build_item_event
from lifetxt.serializer import item_to_line


try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None


REVISION = "a" * 64


@unittest.skipIf(TestClient is None, "web extras unavailable")
class NativeTimelineRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")
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
        Path(self.path).write_text(
            "[x] T Task id:task-1\n"
            + item_to_line(created)
            + "\n"
            + item_to_line(completed)
            + "\n",
            encoding="utf-8",
        )
        from lifetxt.webapp import create_app

        self.client = TestClient(create_app([self.path], writable_path=self.path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _direct(self, **kwargs):
        from lifetxt.native_timeline import native_timeline
        from lifetxt.parser import parse_text

        items, _diagnostics = parse_text(Path(self.path).read_text(encoding="utf-8"))
        return native_timeline(items, "task-1", id_key="id", **kwargs)

    def test_matches_the_shared_domain_reader_directly(self):
        response = self.client.get("/api/native-timeline/task-1")
        self.assertEqual(200, response.status_code)
        data = response.json()
        expected = self._direct()
        self.assertEqual("temporal-timeline-v1", data["schema"])
        self.assertEqual(expected["events"], data["events"])
        self.assertEqual(expected["bounds"], data["bounds"])
        self.assertEqual(expected["completeness"], data["completeness"])
        self.assertEqual(expected["limitations"], data["limitations"])

    def test_since_until_event_filters_are_forwarded(self):
        response = self.client.get(
            "/api/native-timeline/task-1?since=2026-09-10T11:00:00Z&event=completed"
        )
        self.assertEqual(200, response.status_code)
        events = response.json()["events"]
        self.assertEqual(1, len(events))
        self.assertEqual("completed", events[0]["event"])

    def test_limit_is_forwarded_and_bounded(self):
        response = self.client.get("/api/native-timeline/task-1?limit=1")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data["events"]))
        self.assertTrue(data["bounds"]["truncated"])

    def test_unknown_item_returns_404(self):
        response = self.client.get("/api/native-timeline/no-such-id")
        self.assertEqual(404, response.status_code)

    def test_invalid_limit_returns_422_not_a_crash(self):
        response = self.client.get("/api/native-timeline/task-1?limit=-1")
        self.assertEqual(422, response.status_code)

    def test_invalid_event_type_returns_422(self):
        response = self.client.get(
            "/api/native-timeline/task-1?event=not-a-real-event-type"
        )
        self.assertEqual(422, response.status_code)

    def test_html_like_item_id_is_escaped_rather_than_executed(self):
        # A 404 for an unknown, HTML-special-character-laden id must not
        # reflect the raw value unescaped; FastAPI's default JSON error
        # response already encodes it safely, confirmed here so a future
        # change cannot silently regress it into raw HTML.
        response = self.client.get(
            "/api/native-timeline/%3Cscript%3Ealert(1)%3C%2Fscript%3E"
        )
        self.assertEqual(404, response.status_code)
        self.assertNotIn("<script>", response.text)

    def test_existing_routes_are_unaffected(self):
        routes = {route.path for route in self.client.app.routes}
        self.assertIn("/api/native-timeline/{item_id}", routes)
        self.assertIn("/api/temporal-thread/{item_id}", routes)
        response = self.client.get("/api/temporal-thread/task-1")
        self.assertEqual(200, response.status_code)


if __name__ == "__main__":
    unittest.main()
