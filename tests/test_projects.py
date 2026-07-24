import datetime
import unittest

from lifetxt.parser import parse_text
from lifetxt import projects


TODAY = datetime.date(2026, 7, 24)

SAMPLE = """#! timezone: UTC
[N] N Website record:project project:web owner:alice state:active area:work due:2026-09-01
[ ] T Design_home project:web assignee:alice due:2026-07-01
[x] T Setup_repo project:web assignee:bob
[ ] T Deploy project:web assignee:alice depends_on:T-1 id:T-9
[ ] T Blocker project:web id:T-1
[-] T Dropped project:web
[ ] D Launch_MVP record:milestone project:web due:2026-08-15
[N] N DB_scaling record:risk project:web severity:high state:open owner:bob
[N] N Old_risk record:risk project:web severity:low state:closed
[N] N Use_postgres record:decision project:web on:2026-06-20
[ ] E Kickoff record:meeting project:web on:2026-06-01
[ ] T Orphan project:mobile
"""


class ProjectAggregationTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def project(self, name, config=None):
        return projects.collect_projects(self.items, config or {}, TODAY)[name]

    def test_list_counts_and_health(self):
        rows = {r["name"]: r for r in projects.project_list(self.items, {}, TODAY)}
        web = rows["web"]
        self.assertEqual(4, web["task_total"])  # cancelled task excluded
        self.assertEqual(1, web["task_done"])
        self.assertEqual(25.0, web["progress_percent"])
        self.assertEqual(1, web["overdue_count"])
        self.assertEqual(1, web["blocked_count"])
        self.assertEqual(1, web["open_risk_count"])
        self.assertEqual("red", web["health"])

    def test_progress_excludes_cancelled_and_exposes_formula(self):
        progress = projects.compute_progress(self.project("web"))
        self.assertEqual(4, progress["total"])
        self.assertIn("non_cancelled_tasks", progress["formula"])

    def test_progress_undefined_when_no_tasks(self):
        items, _ = parse_text("#! timezone: UTC\n[N] N Empty record:project project:x\n")
        progress = projects.compute_progress(
            projects.collect_projects(items, {}, TODAY)["x"]
        )
        self.assertIsNone(progress["percent"])
        self.assertTrue(progress["undefined_reason"])

    def test_blocked_detection_uses_depends_on(self):
        hub = projects.project_hub(self.items, {}, "web", TODAY)
        self.assertEqual(["Deploy"], [t["title"] for t in hub["blocked_tasks"]])

    def test_overdue_uses_reference_date(self):
        hub = projects.project_hub(self.items, {}, "web", TODAY)
        self.assertEqual(["Design_home"], [t["title"] for t in hub["overdue_tasks"]])
        # Without a date, overdue is not evaluated and health notes the limitation.
        health = projects.compute_health(self.project("web"), today=None)
        self.assertTrue(any("overdue not evaluated" in n for n in health["limitations"]))

    def test_risks_sorted_open_then_severity(self):
        risks = projects.project_risks(self.items, {}, "web", TODAY)
        self.assertEqual("DB_scaling", risks[0]["title"])  # open/high first
        self.assertFalse(risks[-1]["open"])  # closed last

    def test_workload_by_assignee(self):
        rows = {r["assignee"]: r for r in projects.project_workload(self.items, {}, "web", TODAY)}
        self.assertEqual(2, rows["alice"]["open"])
        self.assertEqual(1, rows["alice"]["overdue"])
        self.assertEqual(1, rows["bob"]["done"])

    def test_alias_resolution_via_registry(self):
        config = {"projects": {"web": {"aliases": ["website"]}}}
        hub = projects.project_hub(self.items, config, "website", TODAY)
        self.assertEqual("web", hub["name"])

    def test_registry_metadata_merges(self):
        config = {"projects": {"web": {"display_name": "Website Revamp", "default_area": "work"}}}
        rows = {r["name"]: r for r in projects.project_list(self.items, config, TODAY)}
        self.assertEqual("Website Revamp", rows["web"]["display_name"])

    def test_registry_only_project_appears_without_records(self):
        config = {"projects": {"ghost": {"display_name": "Ghost"}}}
        names = [r["name"] for r in projects.project_list(self.items, config, TODAY)]
        self.assertIn("ghost", names)

    def test_portfolio_orders_red_first_and_exposes_legend(self):
        report = projects.portfolio(self.items, {}, TODAY)
        self.assertEqual("web", report["projects"][0]["name"])
        self.assertIn("progress", report["legend"])
        mobile = [p for p in report["projects"] if p["name"] == "mobile"][0]
        self.assertTrue(mobile["limitations"])

    def test_timeline_is_sorted_by_date(self):
        rows = projects.project_timeline(self.items, {}, "web", TODAY)
        whens = [r["when"] for r in rows]
        self.assertEqual(sorted(whens), whens)

    def test_unknown_project_raises(self):
        with self.assertRaises(ValueError):
            projects.project_hub(self.items, {}, "nope", TODAY)


class RecordBuilderTests(unittest.TestCase):
    def _roundtrip(self, line):
        items, diags = parse_text("#! timezone: UTC\n%s\n" % line)
        self.assertTrue(items, line)
        self.assertFalse([d for d in diags if d.severity == "error"], line)
        return items[0]

    def test_project_record_line_roundtrips(self):
        line = projects.build_project_record_line("web", owner="alice", area="work", due="2026-09-01")
        item = self._roundtrip(line)
        self.assertEqual(["project"], item.details.get("record"))
        self.assertEqual(["web"], item.details.get("project"))
        self.assertEqual(["alice"], item.details.get("owner"))

    def test_milestone_and_risk_lines(self):
        item = self._roundtrip(projects.build_milestone_line("web", "Launch", due="2026-08-15"))
        self.assertEqual(["milestone"], item.details.get("record"))
        item = self._roundtrip(projects.build_risk_line("web", "Latency", severity="critical"))
        self.assertEqual(["critical"], item.details.get("severity"))

    def test_decision_and_meeting_lines(self):
        item = self._roundtrip(projects.build_decision_line("web", "Use PG", on="2026-06-20"))
        self.assertEqual(["decision"], item.details.get("record"))
        item = self._roundtrip(projects.build_meeting_line("web", "Kickoff", on="2026-06-01"))
        self.assertEqual(["meeting"], item.details.get("record"))


if __name__ == "__main__":
    unittest.main()
