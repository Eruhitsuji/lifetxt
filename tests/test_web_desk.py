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

    def test_manifest(self):
        r = self.client.get("/desk.webmanifest")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["start_url"], "/desk")


if __name__ == "__main__":
    unittest.main()
