import os
import tempfile
import unittest
from unittest.mock import patch
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

    def test_planner_daily_flow_reads_existing_model_without_mutation(self):
        from datetime import datetime, timezone

        original = Path(self.path).read_bytes()
        client = TestClient(
            webapp.create_app(
                paths=[self.path],
                writable_path=self.path,
                read_only=True,
                config={"defaults": {"timezone": "Asia/Tokyo"}},
            )
        )
        page = client.get("/planner")
        self.assertEqual(200, page.status_code)
        self.assertIn('id="flow-form"', page.text)
        self.assertIn('id="flow-disclosure"', page.text)
        with patch(
            "lifetxt.daily_flow_web.now",
            return_value=datetime(2031, 2, 2, tzinfo=timezone.utc),
        ):
            response = client.get(
                "/api/daily-flow",
                params={"date": "2031-02-03", "day_start": "09:00", "day_end": "17:00"},
            )
        self.assertEqual(200, response.status_code)
        result = response.json()
        self.assertEqual("daily-flow-lite-v1", result["schema"])
        self.assertEqual("Asia/Tokyo", result["timezone"])
        self.assertEqual("blocked", result["completeness"]["state"])
        self.assertTrue(result["diagnostics"])
        self.assertIn("missing_estimate", {x["reason"] for x in result["unplaced"]})
        self.assertEqual(original, Path(self.path).read_bytes())

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

    def test_config_datetime_and_today_use_one_workspace_clock_snapshot(self):
        import datetime

        instant = datetime.datetime(
            2031,
            2,
            3,
            23,
            59,
            59,
            tzinfo=datetime.timezone(datetime.timedelta(hours=9)),
        )
        with (
            patch("lifetxt.webapp.resolve_timezone_name", return_value="Asia/Tokyo"),
            patch("lifetxt.timezone_policy.now", return_value=instant) as clock,
        ):
            response = self.client.get("/api/config")
        self.assertEqual(200, response.status_code)
        self.assertEqual("2031-02-03", response.json()["today"])
        self.assertEqual(
            "2031-02-03T23:59:59+09:00", response.json()["current_datetime"]
        )
        self.assertIn(unittest.mock.call("Asia/Tokyo"), clock.call_args_list)
        self.assertEqual("no-store", response.headers["cache-control"])

    def test_today_completion_evidence_is_read_only_and_scoped(self):
        Path(self.path).write_text(
            "[x] T Completed_Work id:done-work area:Work done:2031-02-03\n"
            "[x] T Completed_Home id:done-home area:Home done:2031-02-03\n",
            encoding="utf-8",
        )
        from lifetxt.native_history import build_item_event
        from lifetxt.serializer import item_to_line

        with Path(self.path).open("a", encoding="utf-8") as handle:
            for index, target in enumerate(["done-work", "done-home"]):
                event = build_item_event(
                    target,
                    "completed",
                    "2031-02-03T12:00:00Z",
                    1,
                    "ITX-" + str(index),
                    "a" * 64,
                    before_status="[ ]",
                    after_status="[x]",
                )
                handle.write(item_to_line(event) + "\n")
        before = Path(self.path).read_bytes()
        response = self.client.get("/api/temporal-review?date=2031-02-03")
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"Completed_Work", "Completed_Home"},
            {r["target"]["title"] for r in response.json()["completed"]},
        )
        scoped = self.client.get("/api/temporal-review?date=2031-02-03&area=Work")
        self.assertEqual(200, scoped.status_code)
        # Shared scope currently omits native history; the UI must retain its
        # incomplete flag rather than inventing completions from status/done.
        self.assertFalse(scoped.json()["complete"])
        self.assertEqual([], scoped.json()["completed"])
        self.assertEqual(before, Path(self.path).read_bytes())

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

    def test_public_config_normalizes_planner_preferences(self):
        planner = webapp.public_web_config(
            {
                "web": {
                    "planner": {
                        "sections": ["journal", "journal", "future"],
                        "hidden_sections": ["habits", "future"],
                        "density": "invalid",
                    }
                }
            }
        )["planner"]
        self.assertEqual(
            ["journal", "schedule", "tasks", "habits", "notes", "review"],
            planner["sections"],
        )
        self.assertEqual(["habits"], planner["hidden_sections"])
        self.assertEqual("comfortable", planner["density"])

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
            'id="review-panel"',
            "/api/temporal-review?date=",
            "reviewActivity",
            "dayPosition()",
            "data-position",
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
        self.assertIn("config.today", PLANNER_HTML_PAGE)
        self.assertIn(
            'date<today?"past":date>today?"future":"today"', PLANNER_HTML_PAGE
        )
        self.assertIn('dayPosition()==="today"&&writable', PLANNER_HTML_PAGE)
        self.assertIn('past:"過去"', PLANNER_HTML_PAGE)
        self.assertIn('future:"未来"', PLANNER_HTML_PAGE)

    def test_planner_details_and_revision_safe_capture_are_available(self):
        for expected in (
            'id="detail-dialog"',
            "showDetail(record,match)",
            "row.setAttribute('role','button')",
            "expected_source_revision:typeof sourceRevision==='string'?sourceRevision:''",
            "sourceRevision=tasks.source_revision",
        ):
            self.assertIn(expected, PLANNER_HTML_PAGE)

    def test_planner_form_controls_have_shared_focusable_defaults(self):
        self.assertIn("input,select,textarea,button{font:inherit", PLANNER_HTML_PAGE)
        self.assertIn("min-height:44px", PLANNER_HTML_PAGE)

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
