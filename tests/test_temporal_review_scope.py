"""Scoped reviews retain native evidence without exposing unselected records."""

import json
from pathlib import Path
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

from lifetxt.native_history import build_item_event
from lifetxt.serializer import item_to_line
from lifetxt import webapp


@unittest.skipIf(TestClient is None, "FastAPI web extras unavailable")
class TemporalReviewScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.targets = Path(self.temp.name) / "targets.txt"
        self.history = Path(self.temp.name) / "history.txt"
        self.targets.write_text(
            "[x] T Completed_Work id:work area:Work\n"
            "[x] T Completed_Home id:home area:Home\n",
            encoding="utf-8",
        )
        self.events = []
        for target, title in [("work", "Completed_Work"), ("home", "Completed_Home")]:
            self.events.extend(
                [
                    self.event(
                        target,
                        "created",
                        1,
                        item_kind="T",
                        item_title=title,
                        after_status="[ ]",
                    ),
                    self.event(
                        target, "completed", 2, before_status="[ ]", after_status="[x]"
                    ),
                ]
            )
        self.write_history()
        self.config = {
            "defaults": {"timezone": "UTC"},
            "saved_views": {
                "Work": {"query": "type:T area:Work"},
                "Empty": {"query": "type:T area:Absent"},
                "First": {"query": "type:T", "sort": "title", "limit": 1},
            },
        }

    def event(self, target, event, sequence, **payload):
        return build_item_event(
            target,
            event,
            "2031-02-03T12:00:00Z",
            sequence,
            "ITX-%s-%s" % (target, sequence),
            "a" * 64,
            **payload,
        )

    def write_history(self):
        self.history.write_text(
            "".join(item_to_line(event) + "\n" for event in self.events),
            encoding="utf-8",
        )

    def request(self, **params):
        with (
            TestClient(
                webapp.create_app(
                    paths=[str(self.targets), str(self.history)],
                    read_only=True,
                    config=self.config,
                )
            ) as client,
        ):
            return client.get(
                "/api/temporal-review", params={"date": "2031-02-03", **params}
            )

    def result(self, **params):
        response = self.request(**params)
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def test_area_and_saved_view_retain_complete_history_across_files_read_only(self):
        before = [path.read_bytes() for path in (self.targets, self.history)]
        for selector in ({"area": "Work"}, {"saved_view": "Work"}):
            with self.subTest(selector=selector):
                result = self.result(**selector)
                self.assertEqual(
                    ["work"], [row["target_id"] for row in result["completed"]]
                )
                self.assertTrue(result["complete"])
                self.assertEqual([], result["diagnostics"])
                self.assertNotIn("Home", json.dumps(result))
                self.assertEqual(next(iter(selector)), result["scope"]["kind"])
        self.assertEqual(
            before, [path.read_bytes() for path in (self.targets, self.history)]
        )

    def test_unscoped_review_is_unchanged_and_repeatable(self):
        from lifetxt.webapp import read_life_inputs
        from lifetxt.temporal_review import build_temporal_review

        items, _ = read_life_inputs([str(self.targets), str(self.history)], self.config)
        expected = build_temporal_review(
            items, since="2031-02-03", until="2031-02-03", timezone_name="UTC"
        )
        expected["scope"] = None
        self.assertEqual(expected, self.result())
        self.assertEqual(self.result(), self.result())

    def test_saved_view_limit_selects_targets_before_history_event_limit(self):
        result = self.result(saved_view="First", limit=1)
        self.assertEqual(2, result["bounds"]["total_valid_events"])
        self.assertEqual(1, result["bounds"]["returned_events"])
        self.assertTrue(result["bounds"]["truncated"])
        self.assertIn("event_limit_truncated", result["limitations"])
        self.assertNotIn("Work", json.dumps(result))
        self.assertEqual(self.result(saved_view="First", limit=1), result)

    def test_current_rows_and_unrelated_diagnostics_remain_scoped(self):
        with self.targets.open("a") as handle:
            handle.write(
                "[ ] T Open_Work id:open-work area:Work due:2031-02-04\n"
                "[ ] T Secret_Home id:open-home area:Home due:2031-02-04\n"
            )
        self.events[3].details["secret"] = ["Home_payload"]
        orphan = self.event(
            "orphan", "completed", 1, before_status="[ ]", after_status="[x]"
        )
        orphan.title = "Secret_orphan"
        self.events.append(orphan)
        self.write_history()
        result = self.result(area="Work")
        self.assertEqual(
            ["Open_Work"], [row["title"] for row in result["carry_forward"]]
        )
        self.assertEqual(["Open_Work"], [row["title"] for row in result["upcoming"]])
        self.assertEqual([], result["diagnostics"])
        self.assertNotIn("Home", json.dumps(result))
        self.assertNotIn("orphan", json.dumps(result))

    def test_missing_history_does_not_infer_completion_from_status_or_done(self):
        self.events = [
            event for event in self.events if event.details["parent"] != ["work"]
        ]
        self.write_history()
        with self.targets.open("a") as handle:
            handle.write("[x] T Status_only area:Work done:2031-02-03\n")
        result = self.result(area="Work")
        self.assertEqual([], result["completed"])
        self.assertFalse(result["complete"])
        self.assertIn("no_native_history", result["limitations"])
        self.assertIn("target_without_unique_id", result["limitations"])

    def test_malformed_associated_history_remains_diagnosed_and_excluded(self):
        self.events[1].details["custom"] = ["invalid"]
        self.write_history()
        result = self.result(area="Work")
        self.assertFalse(result["complete"])
        self.assertEqual([], result["completed"])
        self.assertIn("W264", [row["code"] for row in result["diagnostics"]])
        self.assertIn("malformed_events_excluded", result["limitations"])

    def test_duplicate_history_retains_diagnostics(self):
        self.events.append(self.events[1])
        self.write_history()
        result = self.result(area="Work")
        self.assertFalse(result["complete"])
        self.assertTrue(result["diagnostics"])
        self.assertIn("history_diagnostics_present", result["limitations"])

    def test_duplicate_target_identity_outside_scope_fails_without_details(self):
        with self.targets.open("a") as handle:
            handle.write("[x] T Secret_Duplicate id:work area:Home\n")
        response = self.request(area="Work")
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            {
                "error": "ERROR",
                "message": "read scope: ambiguous native history association.",
                "detail": None,
            },
            response.json(),
        )

    def test_ambiguous_parent_touching_selected_target_fails_in_either_order(self):
        for parents in (["work", "home"], ["home", "work"], ["work", "work"]):
            with self.subTest(parents=parents):
                self.events[1].details["parent"] = parents
                self.write_history()
                response = self.request(saved_view="Work")
                self.assertEqual(400, response.status_code)
                self.assertEqual(
                    {
                        "error": "ERROR",
                        "message": "read scope: ambiguous native history association.",
                        "detail": None,
                    },
                    response.json(),
                )

    def test_empty_scope_does_not_retain_history(self):
        result = self.result(saved_view="Empty")
        for key in ("completed", "changed", "carry_forward", "upcoming", "diagnostics"):
            self.assertEqual([], result[key])
        self.assertNotIn("Home", json.dumps(result))
        self.assertNotIn("Work", json.dumps(result))

    def test_invalid_selectors_are_client_errors(self):
        for params in (
            {"area": "Work", "saved_view": "Work"},
            {"saved_view": "Missing"},
        ):
            with self.subTest(params=params):
                self.assertEqual(400, self.request(**params).status_code)

    def test_configured_target_id_key_preserves_history(self):
        self.config["ids"] = {"key": "uid"}
        self.targets.write_text(self.targets.read_text().replace(" id:", " uid:"))
        # Native event envelope IDs remain id; only target IDs are configurable.
        result = self.result(area="Work")
        self.assertEqual(["work"], [row["target_id"] for row in result["completed"]])

    def test_date_and_project_filters_use_existing_builder(self):
        self.targets.write_text(
            self.targets.read_text().replace(
                "area:Work", "area:Work project:work-project"
            )
        )
        result = self.result(area="Work", project="work-project")
        self.assertEqual(["work"], [row["target_id"] for row in result["completed"]])
        self.assertEqual([], self.result(area="Work", date="2031-02-04")["completed"])

    def test_upcoming_api_is_scoped_and_read_only_for_area_and_saved_view(self):
        with self.targets.open("a") as handle:
            handle.write(
                "[ ] T Due_Work id:due-work area:Work project:Work due:2031-02-04\n"
                "[ ] E Meeting_Work id:meeting-work area:Work project:Work on:2031-02-05\n"
                "[ ] E Repeat_Work id:repeat-work area:Work project:Work "
                "on:2031-02-06 at:09:00 repeat:daily\n"
                "[ ] E Secret_Home id:future-home area:Home project:Home on:2031-02-04\n"
                "[ ] E Other_Project id:other-project area:Work project:Other on:2031-02-04\n"
            )
        self.config["saved_views"]["Work"]["query"] = "area:Work"
        before = [path.read_bytes() for path in (self.targets, self.history)]
        for selector in ({"area": "Work"}, {"saved_view": "Work"}):
            with self.subTest(selector=selector):
                result = self.result(**selector, project="Work", limit=2)
                self.assertEqual(
                    ["Due_Work", "Meeting_Work"],
                    [row["title"] for row in result["upcoming"]],
                )
                self.assertNotIn("Home", json.dumps(result))
                self.assertNotIn("Other_Project", json.dumps(result))
        unscoped = self.result()
        self.assertIn("Secret_Home", [row["title"] for row in unscoped["upcoming"]])
        self.assertEqual(
            before, [path.read_bytes() for path in (self.targets, self.history)]
        )
