"""Headless Chromium checks for the Planner phone viewport matrix."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lifetxt.web_assets import PLANNER_HTML_PAGE

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "browser_planner_probe.mjs"


def browser_path():
    for candidate in (
        os.environ.get("LIFETXT_BROWSER_BIN"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


class BrowserPathTests(unittest.TestCase):
    def test_configured_browser_path_is_selected(self):
        configured = "/tmp/planner-test-browser"
        with (
            patch.dict(os.environ, {"LIFETXT_BROWSER_BIN": configured}),
            patch("tests.test_web_planner_browser.os.path.isfile", return_value=True),
        ):
            self.assertEqual(configured, browser_path())


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
@unittest.skipUnless(browser_path(), "Chrome/Chromium unavailable")
class PlannerBrowserTests(unittest.TestCase):
    def test_phone_landscape_and_language_matrix(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", encoding="utf-8", delete=False
        ) as handle:
            handle.write(PLANNER_HTML_PAGE)
            filename = handle.name
        try:
            run = subprocess.run(
                ["node", str(PROBE), browser_path(), filename],
                capture_output=True,
                text=True,
                timeout=90,
            )
        finally:
            os.unlink(filename)
        self.assertEqual(0, run.returncode, run.stderr or run.stdout)
        result = json.loads(run.stdout)
        for item in result["focusMatrix"]:
            with self.subTest(focus_viewport=(item["width"], item["height"])):
                self.assertEqual("morning", item["initial"])
                self.assertLessEqual(item["scrollWidth"], item["width"])
                self.assertGreaterEqual(item["minHeight"], 44)
                self.assertTrue(item["accessible"])
                self.assertTrue(item["readonly"])
                self.assertEqual("A", item["focused"])
                self.assertEqual(0, item["flowCalls"])
                self.assertEqual({"GET"}, set(item["methods"]))
                self.assertIn("#schedule", item["modes"]["morning"]["links"])
                self.assertIn("#tasks", item["modes"]["daytime"]["links"])
                self.assertIn("#flow-heading", item["modes"]["daytime"]["links"])
                self.assertIn("#review-panel", item["modes"]["evening"]["links"])
                self.assertIn("Authored completion", item["modes"]["evening"]["text"])
                self.assertEqual(0, item["modes"]["standard"]["emphasis"])
        focus = result["focusStates"]
        self.assertEqual(
            [
                "evening",
                "morning",
                "morning",
                "daytime",
                "daytime",
                "evening",
                "evening",
            ],
            focus["boundaries"],
        )
        for key in ["missing", "mismatched", "error", "pending", "stale"]:
            self.assertEqual("standard", focus[key])
        self.assertEqual("evening", focus["manualUnknown"])
        self.assertEqual("daytime", focus["browserSkew"])
        self.assertEqual(1, focus["candidate"]["highlight"])
        self.assertEqual("Current / upcoming suggestion", focus["candidate"]["label"])
        self.assertTrue(focus["candidate"]["unplaced"])
        self.assertEqual(
            ["fixed", "candidate", "policy_break", "buffer"],
            [
                name.split()[1].removeprefix("flow-")
                for name in focus["candidate"]["cards"]
            ],
        )
        self.assertEqual(0, focus["standardCandidate"])
        self.assertEqual("auto", focus["persisted"]["mode"])
        self.assertEqual("morning", focus["persisted"]["band"])
        self.assertEqual("07:00", focus["persisted"]["pref"]["morning"])
        self.assertEqual("morning", focus["custom"]["mode"])
        self.assertEqual("12:00", focus["custom"]["pref"]["time_bands"]["daytime"])
        self.assertTrue(focus["invalid"]["open"])
        self.assertTrue(focus["invalid"]["error"])
        self.assertEqual("12:00", focus["invalid"]["stored"])
        self.assertTrue(focus["hidden"]["reviewHidden"])
        self.assertNotIn("#review-panel", focus["hidden"]["links"])
        self.assertIn("saved_view=Focus", focus["hidden"]["url"])
        self.assertIn("tz=UTC", focus["hidden"]["url"])
        self.assertNotIn("#schedule", focus["hiddenSchedule"]["links"])
        self.assertNotIn("Next appointment", focus["hiddenSchedule"]["text"])
        self.assertIsNone(focus["reset"])
        self.assertTrue(focus["future"]["hidden"])
        self.assertEqual(0, focus["future"]["emphasis"])
        self.assertEqual("morning", focus["newDay"]["mode"])
        self.assertIn("Today", focus["newDay"]["temporal"])
        self.assertEqual(
            ["05:00", "11:00", "18:00"],
            [focus["malformed"][k] for k in ["morning", "daytime", "evening"]],
        )
        self.assertTrue(focus["malformed"]["compact"])
        self.assertTrue(focus["malformed"]["scheduleHidden"])
        for item in result["flowMatrix"]:
            with self.subTest(flow_viewport=(item["width"], item["height"])):
                self.assertEqual(0, item["optIn"])
                self.assertLessEqual(item["scrollWidth"], item["width"])
                self.assertTrue(item["accessible"])
                self.assertTrue(item["readonly"])
                self.assertTrue(item["unplaced"])
                self.assertEqual(0, item["emptyImages"])
                self.assertGreaterEqual(item["buttonHeight"], 44)
                self.assertGreaterEqual(item["inputHeight"], 44)
                self.assertEqual(
                    [
                        "flow-card flow-" + kind
                        for kind in ["fixed", "candidate", "policy_break", "buffer"]
                    ],
                    item["cards"],
                )
                self.assertIn("area=Work", item["request"])
                self.assertIn("date=2031-02-04", item["request"])
                self.assertNotIn("tz=", item["request"])
                self.assertIn("tz=UTC", item["url"])
                self.assertEqual({"GET"}, set(item["methods"]))
        states = result["flowStates"]
        self.assertIn("Blocked", states["blocked"]["status"])
        self.assertIn("Recurring occupancy is unsupported", states["blocked"]["text"])
        self.assertIn("Partial", states["partial"]["status"])
        self.assertIn("limit_exceeded", states["partial"]["text"])
        self.assertIn("No timeline entries", states["empty"]["text"])
        self.assertIn("Access denied", states["auth"]["status"])
        self.assertIn("Could not load", states["error"]["status"])
        self.assertIn("Could not load", states["bad-schema"]["status"])
        self.assertIn("HH:MM", states["invalid"]["status"])
        self.assertIn("HH:MM", states["windowInvalid"]["status"])
        self.assertEqual(0, states["windowInvalid"]["cards"])
        self.assertEqual(0, states["dateRace"]["cards"])
        self.assertEqual(0, states["scopeRace"])
        self.assertEqual(0, states["weekRace"])
        self.assertEqual(4, states["requestRace"]["cards"])
        self.assertTrue(states["keyboardClosed"])
        self.assertGreater(states["keyboardRequested"], 1)
        self.assertTrue(states["details"]["open"])
        self.assertIn("est: 30m", states["details"]["text"])
        self.assertIn("saved_view=Focus", states["savedView"]["request"])
        self.assertIn("tz=UTC", states["savedView"]["url"])
        self.assertTrue(states["past"]["disabled"])
        self.assertIn("過去", states["past"]["status"])
        self.assertEqual(0, states["past"]["calls"])
        matrix = result["matrix"]
        self.assertEqual([320, 360, 390, 430, 667, 390], [x["width"] for x in matrix])
        for item in matrix:
            with self.subTest(viewport=(item["width"], item["height"])):
                self.assertLessEqual(item["scrollWidth"], item["width"])
                self.assertGreaterEqual(item["dateHeight"], 44)
                self.assertGreaterEqual(item["captureHeight"], 44)
                self.assert_date_navigation_geometry(
                    item["label"], item["prev"], item["date"], item["next"]
                )
        self.assertEqual("予定", matrix[1]["schedule"])
        self.assertEqual("Schedule", matrix[0]["schedule"])
        self.assertEqual(
            [320, 360, 390, 430], [x["width"] for x in result["notesMatrix"]]
        )
        for item in result["notesMatrix"]:
            with self.subTest(notes_viewport=item["width"]):
                self.assertEqual(5, item["initial"]["count"])
                self.assertIn("5 / 12", item["initial"]["total"])
                self.assertEqual(
                    "さらに表示" if item["lang"] == "ja" else "Load more",
                    item["initial"]["label"],
                )
                self.assertGreaterEqual(item["initial"]["moreHeight"], 44)
                self.assertEqual(0, item["initial"]["editButtons"])
                self.assertTrue(item["initial"]["newDisabled"])
                self.assertEqual(10, len(item["middle"]["rows"]))
                self.assertEqual(2, item["middle"]["calls"])
                self.assertEqual(12, len(set(item["final"])))
                self.assertEqual(item["middle"]["rows"], item["final"][:10])
                self.assertTrue(item["moreHidden"])
                self.assertEqual(3, len(item["calls"]))
                self.assertIn("offset=5", item["calls"][1])
                self.assertIn("offset=10", item["calls"][2])
                self.assertLessEqual(item["scrollWidth"], item["width"])
        self.assertEqual(5, result["notesError"]["rows"])
        self.assertTrue(result["notesError"]["enabled"])
        self.assertIn("temporary error", result["notesError"]["feedback"])
        self.assertEqual(5, result["notesRevision"]["rows"])
        self.assertEqual(3, result["notesRevision"]["calls"])
        self.assertEqual(5, len(result["notesRace"]["rows"]))
        self.assertTrue(
            all(
                result["notesRace"]["date"] in row
                for row in result["notesRace"]["rows"]
            )
        )
        self.assertIn("0 / 0", result["notesEmpty"]["total"])
        self.assertTrue(result["notesEmpty"]["moreHidden"])
        self.assertTrue(result["notesEmpty"]["empty"])
        week_matrix = result["weekMatrix"]
        self.assertEqual([320, 360, 390, 430], [x["width"] for x in week_matrix])
        for item in week_matrix:
            with self.subTest(week_viewport=item["width"]):
                self.assertEqual(7, item["days"])
                self.assertLessEqual(item["scrollWidth"], item["width"])
                self.assertTrue(all(height >= 44 for height in item["controls"]))
                self.assertIn("Daily Standup", item["eventText"])
                if item["lang"] == "ja":
                    labels = ["予定", "リマインダー", "期限", "タスク"]
                else:
                    labels = ["Event", "Reminder", "Deadline", "Task"]
                for label in labels:
                    self.assertIn(label, item["eventText"])
                self.assertIsNotNone(item["today"])
                self.assertIsNotNone(item["selected"])
                self.assertEqual(1, item["agendaRequests"])
                self.assertEqual(4, item["timeCount"])
                self.assertTrue(item["contentFits"])
                self.assertTrue(item["longTitle"])
                geometry = item["dateNav"]
                self.assert_date_navigation_geometry(
                    geometry["label"],
                    geometry["prev"],
                    geometry["date"],
                    geometry["next"],
                )
        month_matrix = result["monthMatrix"]
        self.assertEqual([320, 360, 390, 430], [x["width"] for x in month_matrix])
        for item in month_matrix:
            with self.subTest(month_viewport=item["width"]):
                self.assertEqual(35, item["days"])
                self.assertEqual(7, item["outside"])
                self.assertEqual(1, item["today"])
                self.assertEqual(1, item["selected"])
                self.assertLessEqual(item["scrollWidth"], item["width"])
                self.assertGreaterEqual(item["minHeight"], 44)
                self.assertEqual(1, item["agendaRequests"])
                self.assertTrue(
                    any("items" in label or "件" in label for label in item["labels"])
                )
        self.assertIn("view=month", result["monthNext"]["url"])
        self.assertIn("date=2031-03-01", result["monthNext"]["url"])
        self.assertIn("from=2031-02-24&to=2031-04-06", result["monthNext"]["request"])
        self.assertNotIn("view=month", result["monthDayTransition"]["url"])
        self.assertTrue(result["monthDayTransition"]["monthHidden"])
        self.assertTrue(result["monthDayTransition"]["dayVisible"])
        self.assertIn("date=2031-02-10", result["nav"]["url"])
        self.assertIn("view=week", result["nav"]["url"])
        self.assertIn("from=2031-02-10&to=2031-02-16", result["nav"]["request"])
        self.assertIn("date=2031-02-03", result["navBack"]["url"])
        self.assertIn("from=2031-02-03&to=2031-02-09", result["navBack"]["request"])
        self.assertIn("date=2031-02-03", result["returnToToday"]["url"])
        self.assertIn("lang=ja", result["dayTransition"]["url"])
        self.assertIn("date=2031-02-10", result["dayTransition"]["url"])
        self.assertNotIn("view=week", result["dayTransition"]["url"])
        self.assertTrue(result["dayTransition"]["weekHidden"])
        self.assertTrue(result["dayTransition"]["dayVisible"])
        self.assertIn(
            "from=2031-12-29&to=2032-01-04", result["yearBoundary"]["request"]
        )
        self.assertEqual(7, result["yearBoundary"]["days"])
        self.assertEqual(7, result["yearBoundary"]["emptyDays"])
        self.assertIn(
            "from=2031-02-24&to=2031-03-02", result["monthBoundary"]["request"]
        )
        self.assertEqual(7, result["monthBoundary"]["days"])
        self.assertEqual(7, result["monthBoundary"]["emptyDays"])
        self.assertEqual(7, result["readOnly"]["days"])
        self.assertTrue(result["readOnly"]["dockHidden"])
        self.assertTrue(result["readOnly"]["captureDisabled"])

    def assert_date_navigation_geometry(self, label, prev, date, next_button):
        self.assertLessEqual(abs(prev["top"] - date["top"]), 2)
        self.assertLessEqual(abs(next_button["top"] - date["top"]), 2)
        self.assertLessEqual(abs(prev["width"] - 44), 1)
        self.assertLessEqual(abs(next_button["width"] - 44), 1)
        self.assertGreater(date["width"], prev["width"])
        control_row_top = min(prev["top"], date["top"], next_button["top"])
        self.assertLessEqual(label["bottom"], control_row_top)
        self.assertGreaterEqual(prev["height"], 44)
        self.assertGreaterEqual(next_button["height"], 44)
        self.assertGreaterEqual(date["height"], 44)


if __name__ == "__main__":
    unittest.main()
