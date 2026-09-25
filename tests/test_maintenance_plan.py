"""Regression coverage for ``lifetxt maintenance plan`` (#946).

``maintenance plan`` is a thin, plan-only orchestration layer over
``lifetxt project archive --dry-run --emit-plan``: it reuses the same
``project archive`` candidate-selection policy and the same
``archive-plan-v1`` builder (see ``lifetxt/archive_plan_v1.py`` and
``tests/test_archive_plan_v1.py``) rather than introducing a second
mutation engine or plan schema. These tests focus on the orchestration
layer itself -- reporting, blocking, and multi-source resolution -- and
reuse ``ArchivePlanV1TestCase``'s fixture/assertion helpers so the two
suites stay consistent about what ``archive-plan-v1`` looks like.
"""

import json
import os

from tests.test_archive_plan_v1 import ArchivePlanV1TestCase


class MaintenancePlanTests(ArchivePlanV1TestCase):
    def maintenance_plan(
        self, config, project="alpha", plan_name="plan.json", extra_args=()
    ):
        plan_path = self.path(plan_name)
        code, stdout, stderr = self.run_cli(
            config,
            "maintenance",
            "plan",
            project,
            "--emit-plan",
            plan_path,
            *extra_args,
        )
        return plan_path, code, stdout, stderr

    def test_writes_an_archive_plan_v1_document_and_makes_no_other_change(self):
        config, work, archive = self.workspace()
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        plan_path, code, stdout, stderr = self.maintenance_plan(config)

        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertTrue(os.path.exists(plan_path))
        self.assert_unchanged(before)

        self.assertIn("Maintenance requested:", stdout)
        self.assertIn("no automatic Storage Health recommendation", stdout)
        self.assertIn("Project: alpha", stdout)
        self.assertIn("Selection policy:", stdout)
        self.assertIn("Candidates: 1 item(s)", stdout)
        self.assertIn("Plan written to %s." % plan_path, stdout)
        self.assertIn("No workspace file was changed.", stdout)
        self.assertIn("lifetxt project archive --apply-plan %s" % plan_path, stdout)

        plan = self.load_plan(plan_path)
        self.assertEqual(1, plan["plan_version"])
        self.assertEqual("alpha", plan["project"])
        self.assertEqual(["t1"], plan["selected_item_ids"])

    def test_plan_matches_the_equivalent_project_archive_emit_plan_call(self):
        # Two independent, identically-seeded fixtures: one driven through
        # the existing `project archive --dry-run --emit-plan` path, one
        # through the new orchestration -- the resulting plans must agree
        # on everything except the two ever-differing fields (writer PID,
        # reserved_transaction_id) and therefore also their plan_hash.
        ref_config, _ref_work, _ref_archive = self.workspace()
        ref_plan_path, ref_code, _stdout, ref_stderr = self.emit_plan(ref_config)
        self.assertEqual(0, ref_code, ref_stderr)
        reference = self.load_plan(ref_plan_path)

        config, _work, _archive = self.workspace()
        plan_path, code, _stdout, stderr = self.maintenance_plan(config)
        self.assertEqual(0, code, stderr)
        plan = self.load_plan(plan_path)

        for field in (
            "plan_version",
            "project",
            "workspace",
            "sources",
            "destination",
            "selected_item_ids",
            "external_references",
            "parameters",
        ):
            self.assertEqual(reference[field], plan[field], field)

    def test_no_candidates_writes_no_plan_and_reports_the_block_reason(self):
        config, work, archive = self.workspace("[ ] T Open id:t1 project:alpha\n")
        before = {p: self.read_bytes(p) for p in (config, work, archive)}
        plan_path = self.path("plan.json")

        code, stdout, stderr = self.run_cli(
            config, "maintenance", "plan", "alpha", "--emit-plan", plan_path
        )

        self.assertEqual(1, code)
        self.assertFalse(os.path.exists(plan_path))
        self.assert_unchanged(before)
        self.assertIn("Candidates: 0 item(s)", stdout)
        self.assertIn("No plan written: no items match the archive criteria", stdout)
        self.assertIn("No workspace file was changed.", stdout)

    def test_orphan_blocked_selection_writes_no_plan(self):
        config, work, archive = self.workspace(
            "[x] T Parent id:p1 project:alpha done:2026-01-01\n[ ] T Child parent:p1\n"
        )
        before = {p: self.read_bytes(p) for p in (config, work, archive)}
        plan_path = self.path("plan.json")

        code, stdout, stderr = self.run_cli(
            config, "maintenance", "plan", "alpha", "--emit-plan", plan_path
        )

        self.assertEqual(1, code)
        self.assertFalse(os.path.exists(plan_path))
        self.assert_unchanged(before)
        self.assertIn("open children block the selection", stdout)

    def test_json_format_reports_candidate_count_and_plan_path(self):
        config, _work, _archive = self.workspace()
        plan_path, code, stdout, stderr = self.maintenance_plan(
            config, extra_args=("--format", "json")
        )
        self.assertEqual(0, code, stderr)
        record = json.loads(stdout)
        self.assertEqual("alpha", record["project"])
        self.assertEqual(1, record["candidate_count"])
        self.assertIsNone(record["blocked"])
        self.assertEqual(plan_path, record["plan_path"])
        self.assertFalse(record["mutated"])
        self.assertIn("no automatic Storage Health recommendation", record["reason"])

    def test_json_format_reports_block_reason_with_no_plan_path(self):
        config, _work, _archive = self.workspace("[ ] T Open id:t1 project:alpha\n")
        code, stdout, stderr = self.run_cli(
            config,
            "maintenance",
            "plan",
            "alpha",
            "--emit-plan",
            self.path("plan.json"),
            "--format",
            "json",
        )
        self.assertEqual(1, code)
        record = json.loads(stdout)
        self.assertEqual(0, record["candidate_count"])
        self.assertIsNone(record["plan_path"])
        self.assertIn("no items match", record["blocked"])

    def test_generated_plan_applies_through_the_existing_apply_plan_path(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.maintenance_plan(config)
        self.assertEqual(0, code, stderr)

        code, stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("Archived", stdout)
        self.assertNotIn(
            "[x] T Done id:t1 project:alpha done:2026-01-01\n",
            self.read_bytes(work).decode("utf-8"),
        )
        self.assertIn(
            "[x] T Done id:t1 project:alpha done:2026-01-01",
            self.read_bytes(archive).decode("utf-8"),
        )

    def test_multi_source_workspace_selects_across_every_scanned_source(self):
        work_a = self.write(
            "a.life.txt", "[x] T Done id:t1 project:alpha done:2026-01-01\n"
        )
        work_b = self.write(
            "b.life.txt", "[x] T Also id:t2 project:alpha done:2026-01-02\n"
        )
        archive = self.path("archive.life.txt")
        self.write("archive.life.txt", "")
        config = self.write(
            "config.json",
            json.dumps(
                {
                    "config_version": 1,
                    "default_workspace": "work",
                    "workspaces": {
                        "work": {
                            "sources": [
                                {
                                    "path": "a.life.txt",
                                    "role": "primary",
                                    "required": True,
                                    "writable": True,
                                },
                                {
                                    "path": "b.life.txt",
                                    "role": "reference",
                                    "required": False,
                                    "writable": False,
                                },
                                {
                                    "path": "archive.life.txt",
                                    "role": "archive",
                                    "required": False,
                                    "writable": False,
                                },
                            ],
                            "write_file": "a.life.txt",
                        }
                    },
                },
                indent=2,
            )
            + "\n",
        )
        before = {p: self.read_bytes(p) for p in (config, work_a, work_b, archive)}

        plan_path, code, stdout, stderr = self.maintenance_plan(config)

        self.assertEqual(0, code, stderr)
        self.assert_unchanged(before)
        self.assertIn("Candidates: 2 item(s)", stdout)

        plan = self.load_plan(plan_path)
        self.assertEqual(sorted(["t1", "t2"]), sorted(plan["selected_item_ids"]))
        source_paths = sorted(row["path"] for row in plan["sources"])
        self.assertEqual(sorted([work_a, work_b]), source_paths)

    def test_query_behavior_is_unaffected_by_generating_a_plan(self):
        config, _work, _archive = self.workspace()

        before_code, before_stdout, before_stderr = self.run_cli(
            config, "query", "project:alpha"
        )
        self.assertEqual(0, before_code, before_stderr)

        _plan_path, code, _stdout, stderr = self.maintenance_plan(config)
        self.assertEqual(0, code, stderr)

        after_code, after_stdout, after_stderr = self.run_cli(
            config, "query", "project:alpha"
        )
        self.assertEqual(0, after_code, after_stderr)
        self.assertEqual(before_stdout, after_stdout)
        self.assertEqual(before_stderr, after_stderr)

    def test_explicit_dest_overrides_the_workspace_archive_source(self):
        config, _work, _archive = self.workspace()
        alt_dest = self.write("alt-archive.life.txt", "")

        plan_path, code, stdout, stderr = self.maintenance_plan(
            config, extra_args=("--dest", alt_dest)
        )
        self.assertEqual(0, code, stderr)

        plan = self.load_plan(plan_path)
        self.assertEqual(alt_dest, plan["destination"]["path"])
