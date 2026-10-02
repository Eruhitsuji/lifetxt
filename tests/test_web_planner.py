import os
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

from lifetxt import webapp
from lifetxt.web_assets import PLANNER_HTML_PAGE


@unittest.skipIf(TestClient is None, "FastAPI web extras unavailable")
class PlannerTests(unittest.TestCase):  # pragma: no cover -- covered in web-extras CI
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        Path(self.path).write_text(
            "[ ] E Lab_Meeting id:event-1 at:09:00 on:2031-02-03\n"
            "[ ] R Water_Plants id:reminder-1 on:2031-02-03\n"
            "[ ] T Due_Report id:task-1 due:2031-02-03\n"
            "[ ] D Submit_Grant id:deadline-1 on:2031-02-05\n"
            "[ ] E Daily_Standup id:repeat-1 "
            "repeat:RRULE:FREQ=DAILY;COUNT=3 "
            "from:2031-02-04T11:00 to:2031-02-04T11:30\n"
            "[ ] T Untimed_Next_Action id:undated-task\n"
            "[ ] H Exercise id:habit-1 done:2031-02-02\n"
            "[N] J Journal_Entry id:journal-1 on:2031-02-03 body:Existing\n",
            encoding="utf-8",
        )
        self.client = TestClient(
            webapp.create_app(paths=[self.path], writable_path=self.path)
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_route_and_separate_install_manifest_preserve_capture(self):
        page = self.client.get("/planner")
        self.assertEqual(200, page.status_code)
        self.assertEqual("no-store", page.headers["cache-control"])
        self.assertIn('href="/planner.webmanifest"', page.text)
        self.assertEqual(200, self.client.get("/").status_code)
        self.assertEqual(200, self.client.get("/capture").status_code)
        manifest = self.client.get("/planner.webmanifest").json()
        self.assertEqual("/planner", manifest["start_url"])
        self.assertEqual("/planner", manifest["id"])
        for icon in manifest["icons"]:
            self.assertEqual(200, self.client.get(icon["src"]).status_code)
        self.assertEqual(
            "/capture", self.client.get("/manifest.webmanifest").json()["start_url"]
        )

    def test_command_center_uses_selected_date_and_rejects_invalid_date(self):
        response = self.client.get("/api/command-center?date=2031-02-03")
        self.assertEqual(200, response.status_code)
        self.assertEqual("2031-02-03", response.json()["reference_date"])
        self.assertEqual(2, len(response.json()["today_events"]))
        self.assertEqual(
            ["Due_Report"], [x["title"] for x in response.json()["due_today"]]
        )
        self.assertEqual(
            400, self.client.get("/api/command-center?date=2031-02-30").status_code
        )

    def test_week_range_uses_shared_agenda_occurrences_and_excludes_undated_tasks(self):
        response = self.client.get("/api/agenda?from=2031-02-03&to=2031-02-09")
        self.assertEqual(200, response.status_code)
        records = response.json()["records"]
        self.assertTrue(
            {"E", "R", "D", "T"}.issubset({record["type"] for record in records})
        )
        repeating = next(
            record for record in records if record["title"] == "Daily_Standup"
        )
        self.assertEqual(
            ["2031-02-04T11:00", "2031-02-05T11:00", "2031-02-06T11:00"],
            [match["start"] for match in repeating["matches"]],
        )
        self.assertNotIn("Untimed_Next_Action", [record["title"] for record in records])

    def test_normal_journal_record_create_update(self):
        payload = {
            "status": "[N]",
            "type": "J",
            "title": "Journal",
            "details": {"id": ["journal-new"], "on": ["2031-02-05"], "body": ["First"]},
        }
        created = self.client.post("/api/items", json=payload)
        self.assertEqual(201, created.status_code)
        item = created.json()["item"]
        payload["details"]["body"] = ["Revised"]
        updated = self.client.put("/api/items/id/journal-new", json=payload)
        self.assertEqual(200, updated.status_code)
        self.assertEqual(["Revised"], updated.json()["item"]["details"]["body"])

    def test_read_only_does_not_enable_writes(self):
        client = TestClient(
            webapp.create_app(
                paths=[self.path], writable_path=self.path, read_only=True
            )
        )
        self.assertEqual(200, client.get("/planner").status_code)
        self.assertEqual(
            403, client.post("/api/items/capture", json={"text": "No"}).status_code
        )

    def test_assets_include_accessibility_mobile_and_bilingual_contract(self):
        for expected in (
            "viewport-fit=cover",
            'aria-live="polite"',
            "safe-area-inset-bottom",
            "min-height:44px",
            'habits:"習慣"',
            'id="view-week"',
            'id="view-month"',
            'id="week-days"',
            'id="month-grid"',
            'id="temporal-context"',
            'dayPosition()',
            'data-position',
            "weekStart(value)",
            "loadMonth()",
            "densityText(count)",
            "previousWeek",
            "navigator.serviceWorker",
        ):
            if expected == "navigator.serviceWorker":
                self.assertNotIn(expected, PLANNER_HTML_PAGE)
            else:
                self.assertIn(expected, PLANNER_HTML_PAGE)

    def test_temporal_day_semantics_use_workspace_today_and_gate_completion(self):
        self.assertIn('config.today', PLANNER_HTML_PAGE)
        self.assertIn('date<today?"past":date>today?"future":"today"', PLANNER_HTML_PAGE)
        self.assertIn('dayPosition()==="today"&&writable', PLANNER_HTML_PAGE)
        self.assertIn('past:"過去"', PLANNER_HTML_PAGE)
        self.assertIn('future:"未来"', PLANNER_HTML_PAGE)

    def test_month_range_reuses_agenda_for_leap_year_and_recurrence(self):
        response = self.client.get("/api/agenda?from=2031-01-27&to=2031-03-02")
        self.assertEqual(200, response.status_code)
        repeating = next(
            record
            for record in response.json()["records"]
            if record["title"] == "Daily_Standup"
        )
        self.assertEqual(3, len(repeating["matches"]))


if __name__ == "__main__":
    unittest.main()
