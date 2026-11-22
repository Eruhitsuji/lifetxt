import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None


@unittest.skipIf(TestClient is None, "Web extras not installed")
class DeskPageTests(unittest.TestCase):
    def setUp(self):
        from lifetxt.webapp import create_app

        self.dir = tempfile.TemporaryDirectory()
        path = os.path.join(self.dir.name, "life.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write('[ ] T "a"\n')
            f.write('[ ] T "Repeat" id:repeat-1 due:2026-01-01 repeat:daily repeat_base:done done:2026-01-01\n')
        self.client = TestClient(create_app([path]))

    def tearDown(self):
        self.client.close()
        self.dir.cleanup()

    def test_page_is_no_store_and_scroll_free(self):
        r = self.client.get("/desk")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["cache-control"], "no-store")
        self.assertIn("overflow:hidden", r.text.replace(" ", ""))
        self.assertIn("detail-dialog", r.text)
        self.assertNotIn("__DESK_", r.text)

    def test_week_toggle_present(self):
        r = self.client.get("/desk")
        self.assertIn('id="mode-week"', r.text)
        self.assertIn('aria-pressed', r.text)

    def test_month_toggle_present(self):
        self.assertIn('id="mode-month"', self.client.get("/desk").text)

    def test_detail_actions_container_present(self):
        self.assertIn('id="detail-actions"', self.client.get("/desk").text)

    def test_event_edit_copy_present(self):
        self.assertIn("badRange", self.client.get("/desk").text)

    def test_event_move_copy_present(self):
        self.assertIn("evDate", self.client.get("/desk").text)

    def test_event_at_edit_present(self):
        self.assertIn("detail-date", self.client.get("/desk").text)

    def complete_repeat(self, **payload):
        revision = self.client.get("/api/revision").headers["ETag"]
        return self.client.post(
            "/api/items/id/repeat-1/complete",
            headers={"If-Match": revision},
            json=payload,
        )

    def test_repeat_completion_preserves_selected_timestamp(self):
        result = self.complete_repeat(done_at="2026-01-06T13:27:42")
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data["item"]["details"]["done"], ["2026-01-06T13:27:42"])
        self.assertEqual(data["next"]["details"]["due"], ["2026-01-07"])
        self.assertNotIn("done", data["next"]["details"])

    def test_repeat_completion_keeps_legacy_date_behavior(self):
        result = self.complete_repeat(date="2026-01-06")
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data["item"]["details"]["done"], ["2026-01-01"])
        self.assertEqual(data["next"]["details"]["due"], ["2026-01-07"])

    def test_invalid_completion_timestamp_does_not_complete(self):
        for value in (None, "2026-01-06", "2026-01-06T13:27Z", "2026-02-30T13:27"):
            with self.subTest(value=value):
                self.assertEqual(self.complete_repeat(done_at=value).status_code, 400)
        self.assertEqual(self.client.get("/api/items/id/repeat-1").json()["item"]["status"], "[ ]")

    def test_manifest(self):
        r = self.client.get("/desk.webmanifest")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["start_url"], "/desk")


if __name__ == "__main__":
    unittest.main()
