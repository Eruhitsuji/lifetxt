"""Regression coverage for archive-plan-v1 (#254 emit, #255 apply).

Mirrors ``tests/test_project_archive_safety_v3.py``'s fixture and
byte-for-byte immutability assertion style: every rejection path must leave
every source/destination file, and the config file, exactly as it was.
"""

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import archive_plan_v1, entrypoint


def _has_draft_2020_validator():
    try:
        from jsonschema import Draft202012Validator  # noqa: F401
        from referencing import Registry, Resource  # noqa: F401
    except ImportError:
        return False
    return True


class ArchivePlanV1TestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.addCleanup(self.temp.cleanup)

    def path(self, name):
        return os.path.join(self.root, name)

    def write(self, name, text):
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def read_bytes(self, path):
        with open(path, "rb") as handle:
            return handle.read()

    def revision(self, path):
        return hashlib.sha256(self.read_bytes(path)).hexdigest()

    def workspace(self, text=None, create_archive=True, extra=None):
        work = self.write(
            "work.life.txt",
            text
            if text is not None
            else "[x] T Done id:t1 project:alpha done:2026-01-01\n",
        )
        archive = self.path("archive.life.txt")
        if create_archive:
            self.write("archive.life.txt", "")
        data = {
            "config_version": 1,
            "default_workspace": "work",
            "workspaces": {
                "work": {
                    "sources": [
                        {
                            "path": "work.life.txt",
                            "role": "primary",
                            "required": True,
                            "writable": True,
                        },
                        {
                            "path": "archive.life.txt",
                            "role": "archive",
                            "required": False,
                            "writable": False,
                        },
                    ],
                    "write_file": "work.life.txt",
                }
            },
        }
        if extra:
            data.update(extra)
        config = self.write("config.json", json.dumps(data, indent=2) + "\n")
        return config, work, archive

    def run_cli(self, config, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = entrypoint.main(["--config", config] + list(args))
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_unchanged(self, snapshots):
        for path, expected in snapshots.items():
            self.assertTrue(os.path.exists(path), path)
            self.assertEqual(expected, self.read_bytes(path), path)

    def emit_plan(self, config, project="alpha", plan_name="plan.json", extra_args=()):
        plan_path = self.path(plan_name)
        code, stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            project,
            "--dry-run",
            "--emit-plan",
            plan_path,
            *extra_args,
        )
        return plan_path, code, stdout, stderr

    def load_plan(self, plan_path):
        with open(plan_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def save_plan(self, plan_path, plan):
        with open(plan_path, "w", encoding="utf-8") as handle:
            json.dump(plan, handle)

    def retamper_hash(self, plan):
        """Recompute plan_hash so a deliberate field edit is self-consistent.

        Used only to isolate one verification step from the tamper-hash
        check itself (e.g. testing plan_version or selection drift alone).
        """
        fields = dict(plan)
        fields.pop("plan_hash", None)
        plan["plan_hash"] = archive_plan_v1.compute_plan_hash(fields)
        return plan


class EmitPlanTests(ArchivePlanV1TestCase):
    def test_emit_plan_writes_schema_valid_document_and_makes_no_other_change(self):
        config, work, archive = self.workspace()
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        plan_path, code, stdout, stderr = self.emit_plan(config)

        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertTrue(os.path.exists(plan_path))
        self.assert_unchanged(before)

        plan = self.load_plan(plan_path)
        for required in (
            "plan_version",
            "created_at",
            "project",
            "workspace",
            "sources",
            "destination",
            "selected_item_ids",
            "external_references",
            "parameters",
            "writer",
            "reserved_transaction_id",
            "plan_hash",
        ):
            self.assertIn(required, plan)
        self.assertEqual(1, plan["plan_version"])
        self.assertEqual("alpha", plan["project"])

    def test_plan_revisions_match_live_sha256(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)

        plan = self.load_plan(plan_path)
        source_paths = {row["path"]: row["revision"] for row in plan["sources"]}
        self.assertEqual(self.revision(work), source_paths[work])
        self.assertEqual(self.revision(archive), plan["destination"]["revision"])
        self.assertEqual(work, plan["sources"][0]["path"])
        self.assertEqual(archive, plan["destination"]["path"])

    def test_plan_selected_item_ids_match_dry_run_candidates(self):
        config, work, archive = self.workspace(
            "[x] T Done id:t1 project:alpha done:2026-01-01\n"
            "[ ] T Open id:t2 project:alpha\n"
            "[x] T Other id:t3 project:beta done:2026-01-01\n"
        )
        plan_path, code, stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        self.assertIn("Items to archive (1,", stdout)
        self.assertIn("Done", stdout)

        plan = self.load_plan(plan_path)
        self.assertEqual(["t1"], plan["selected_item_ids"])

    def test_omitting_emit_plan_is_byte_for_byte_unaffected(self):
        config, work, archive = self.workspace()

        code_without, stdout_without, stderr_without = self.run_cli(
            config, "project", "archive", "alpha", "--dry-run"
        )
        code_with, stdout_with, stderr_with = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            "--dry-run",
            "--emit-plan",
            self.path("plan.json"),
        )
        self.assertEqual(code_without, code_with)
        self.assertEqual(stderr_without, stderr_with)
        # --emit-plan adds exactly one extra confirmation line; strip it and
        # the remaining text must be identical to the flag being omitted.
        self.assertEqual(
            stdout_without,
            stdout_with.replace(
                "Archive plan written to %s.\n" % self.path("plan.json"), ""
            ),
        )

    def test_emit_plan_requires_dry_run(self):
        config, work, archive = self.workspace()
        before = {p: self.read_bytes(p) for p in (config, work, archive)}
        plan_path = self.path("plan.json")

        code, _stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            "--emit-plan",
            plan_path,
            "--yes",
        )

        self.assertEqual(1, code)
        self.assertIn("--emit-plan requires --dry-run", stderr)
        self.assertFalse(os.path.exists(plan_path))
        self.assert_unchanged(before)

    def test_emit_plan_and_apply_plan_are_mutually_exclusive(self):
        config, work, archive = self.workspace()
        before = {p: self.read_bytes(p) for p in (config, work, archive)}
        plan_path = self.path("plan.json")

        code, _stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            "--dry-run",
            "--emit-plan",
            plan_path,
            "--apply-plan",
            plan_path,
        )

        self.assertEqual(1, code)
        self.assertIn("mutually exclusive", stderr)
        self.assertFalse(os.path.exists(plan_path))
        self.assert_unchanged(before)

    def test_no_plan_written_when_no_candidates_match(self):
        config, work, archive = self.workspace("[ ] T Open id:t2 project:alpha\n")
        before = {p: self.read_bytes(p) for p in (config, work, archive)}
        plan_path = self.path("plan.json")

        code, stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--dry-run", "--emit-plan", plan_path
        )

        self.assertEqual(0, code, stderr)
        self.assertIn("No items match the archive criteria.", stdout)
        self.assertIn("No archive plan written", stderr)
        self.assertFalse(os.path.exists(plan_path))
        self.assert_unchanged(before)

    def test_no_plan_written_when_orphan_children_block_selection(self):
        config, work, archive = self.workspace(
            "[x] T Parent id:p1 project:alpha done:2026-01-01\n"
            "[ ] T Child id:c1 project:alpha parent:p1\n"
        )
        before = {p: self.read_bytes(p) for p in (config, work, archive)}
        plan_path = self.path("plan.json")

        code, stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--dry-run", "--emit-plan", plan_path
        )

        self.assertEqual(1, code)
        self.assertIn("Cannot archive", stdout)
        self.assertIn("No archive plan written", stderr)
        self.assertFalse(os.path.exists(plan_path))
        self.assert_unchanged(before)

    @unittest.skipUnless(
        _has_draft_2020_validator(), "Draft 2020-12 jsonschema validation not available"
    )
    def test_emitted_plan_validates_against_the_published_schema(self):
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource

        from lifetxt.safety_foundation import schema_bundle

        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        plan = self.load_plan(plan_path)

        bundle = schema_bundle()
        schema = bundle["archive-plan-v1.schema.json"]
        registry = Registry()
        for name, value in bundle.items():
            resource = Resource.from_contents(value)
            registry = registry.with_resource(name, resource)
            registry = registry.with_resource(value["$id"], resource)
        validator = Draft202012Validator(schema, registry=registry)
        errors = list(validator.iter_errors(plan))
        self.assertEqual([], errors)


class ApplyPlanTests(ArchivePlanV1TestCase):
    def test_apply_unmodified_plan_matches_equivalent_revision_invocation(self):
        # Reference outcome using the existing --revision-flag path.
        ref_config, ref_work, ref_archive = self.workspace()
        code, _stdout, stderr = self.run_cli(
            ref_config,
            "project",
            "archive",
            "alpha",
            "--yes",
            "--revision",
            ref_work + "=" + self.revision(ref_work),
            "--revision",
            ref_archive + "=" + self.revision(ref_archive),
        )
        self.assertEqual(0, code, stderr)
        reference_work = self.read_bytes(ref_work)
        reference_archive = self.read_bytes(ref_archive)

        # Plan-based path against an identical, independent fixture.
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)

        code, stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertIn("Archived", stdout)
        self.assertEqual(reference_work, self.read_bytes(work))
        self.assertEqual(reference_archive, self.read_bytes(archive))

    def test_apply_plan_without_yes_only_verifies_and_writes_nothing(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path
        )

        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertIn("Archive plan verified against current state", stdout)
        self.assertIn("Re-run the same command with --yes", stdout)
        self.assert_unchanged(before)

    def test_tampered_plan_is_rejected_before_any_write(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        plan = self.load_plan(plan_path)
        plan["project"] = "tampered"
        self.save_plan(plan_path, plan)
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )

        self.assertEqual(1, code)
        self.assertIn("tamper check failed", stderr)
        self.assert_unchanged(before)

    def test_stale_source_revision_is_rejected_before_any_write(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        with open(work, "a", encoding="utf-8") as handle:
            handle.write("[ ] T New id:t2 project:alpha\n")
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )

        self.assertEqual(1, code)
        self.assertIn("Archive plan is stale", stderr)
        self.assertIn(work, stderr)
        self.assert_unchanged(before)

    def test_stale_destination_revision_is_rejected_before_any_write(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        with open(archive, "a", encoding="utf-8") as handle:
            handle.write("[x] T PreExisting id:z9 done:2020-01-01\n")
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )

        self.assertEqual(1, code)
        self.assertIn("Archive plan is stale", stderr)
        self.assertIn(archive, stderr)
        self.assert_unchanged(before)

    def test_workspace_config_drift_is_rejected_before_any_write(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        data = json.loads(self.read_bytes(config).decode("utf-8"))
        data["unrelated_marker"] = True
        self.write("config.json", json.dumps(data, indent=2) + "\n")
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )

        self.assertEqual(1, code)
        self.assertIn("workspace configuration changed", stderr)
        self.assert_unchanged(before)

    def test_selection_drift_is_rejected_independent_of_revision(self):
        config, work, archive = self.workspace(
            "[x] T Done id:t1 project:alpha done:2026-01-01\n"
            "[x] T Done2 id:t3 project:alpha done:2026-01-01\n"
        )
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        plan = self.load_plan(plan_path)
        self.assertEqual(["t1", "t3"], plan["selected_item_ids"])
        plan["selected_item_ids"] = ["t1"]
        self.retamper_hash(plan)
        self.save_plan(plan_path, plan)
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )

        self.assertEqual(1, code)
        self.assertIn("no longer matches the plan's frozen item list", stderr)
        self.assert_unchanged(before)

    def test_unsupported_plan_version_is_rejected_before_any_write(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        plan = self.load_plan(plan_path)
        plan["plan_version"] = 2
        self.retamper_hash(plan)
        self.save_plan(plan_path, plan)
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )

        self.assertEqual(1, code)
        self.assertIn("unsupported plan_version", stderr)
        self.assert_unchanged(before)

    def test_missing_recovery_evidence_directory_is_rejected_before_any_write(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        blocker = self.write("blocker", "x")
        os.environ["LIFETXT_TRANSACTION_JOURNAL_DIR"] = os.path.join(blocker, "journal")
        try:
            code, _stdout, stderr = self.run_cli(
                config,
                "project",
                "archive",
                "alpha",
                "--apply-plan",
                plan_path,
                "--yes",
            )
        finally:
            del os.environ["LIFETXT_TRANSACTION_JOURNAL_DIR"]

        self.assertEqual(1, code)
        self.assertIn("not reachable", stderr)
        self.assert_unchanged(before)

    def test_apply_plan_and_revision_are_mutually_exclusive(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            "--apply-plan",
            plan_path,
            "--revision",
            work + "=" + self.revision(work),
            "--yes",
        )

        self.assertEqual(1, code)
        self.assertIn("mutually exclusive", stderr)
        self.assert_unchanged(before)

    def test_apply_plan_and_dest_are_mutually_exclusive(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            "--apply-plan",
            plan_path,
            "--dest",
            archive,
            "--yes",
        )

        self.assertEqual(1, code)
        self.assertIn("mutually exclusive", stderr)
        self.assert_unchanged(before)

    def test_apply_plan_and_explicit_paths_are_mutually_exclusive(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config,
            "project",
            "archive",
            "alpha",
            work,
            "--apply-plan",
            plan_path,
            "--yes",
        )

        self.assertEqual(1, code)
        self.assertIn("mutually exclusive", stderr)
        self.assert_unchanged(before)

    def test_apply_plan_reports_reserved_transaction_id(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        plan = self.load_plan(plan_path)

        code, stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path
        )

        self.assertEqual(0, code, stderr)
        self.assertIn(plan["reserved_transaction_id"], stdout)

    def test_malformed_plan_json_is_rejected_before_any_write(self):
        config, work, archive = self.workspace()
        plan_path = self.write("plan.json", "{ not valid json")
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )

        self.assertEqual(1, code)
        self.assertIn("not valid JSON", stderr)
        self.assert_unchanged(before)

    def test_plan_missing_required_field_is_rejected_before_any_write(self):
        config, work, archive = self.workspace()
        plan_path, code, _stdout, stderr = self.emit_plan(config)
        self.assertEqual(0, code, stderr)
        plan = self.load_plan(plan_path)
        del plan["plan_hash"]
        self.save_plan(plan_path, plan)
        before = {p: self.read_bytes(p) for p in (config, work, archive)}

        code, _stdout, stderr = self.run_cli(
            config, "project", "archive", "alpha", "--apply-plan", plan_path, "--yes"
        )

        self.assertEqual(1, code)
        self.assertIn("missing required field", stderr)
        self.assert_unchanged(before)


class ArchivePlanV1UnitTests(unittest.TestCase):
    def test_compute_plan_hash_is_order_independent(self):
        a = {"b": 1, "a": 2}
        b = {"a": 2, "b": 1}
        self.assertEqual(
            archive_plan_v1.compute_plan_hash(a), archive_plan_v1.compute_plan_hash(b)
        )

    def test_verify_plan_version_rejects_missing_version(self):
        with self.assertRaises(ValueError):
            archive_plan_v1.verify_plan_version({})

    def test_journal_directory_reachable_true_for_existing_writable_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(archive_plan_v1.journal_directory_reachable(d))

    def test_journal_directory_reachable_true_for_creatable_missing_dir(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "not-yet-created", "journal")
            self.assertTrue(archive_plan_v1.journal_directory_reachable(target))

    def test_journal_directory_reachable_false_when_ancestor_is_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            blocker = os.path.join(d, "blocker")
            with open(blocker, "w") as handle:
                handle.write("x")
            target = os.path.join(blocker, "journal")
            self.assertFalse(archive_plan_v1.journal_directory_reachable(target))


if __name__ == "__main__":
    unittest.main()
