import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*args):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = os.pathsep.join(
        [ROOT_DIR] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    with tempfile.TemporaryDirectory(prefix="lifetxt-integrity-cwd-") as cwd:
        process = subprocess.Popen(
            [sys.executable, "-m", "lifetxt"] + list(args),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
    return stdout.decode("utf-8"), stderr.decode("utf-8"), process.returncode


class LifeTxtIntegrityCliTests(unittest.TestCase):
    def _fixture(self, temp_dir, name="life.txt", text="[ ] T Task id:t1\n"):
        path = os.path.join(temp_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_clean_file_reports_ok_without_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(temp_dir)
            before_files = sorted(os.listdir(temp_dir))
            before_text = self._read(path)

            stdout, stderr, code = run_cli("integrity", path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("integrity: OK", stdout)
            self.assertIn("syntax", stdout)
            self.assertEqual(before_files, sorted(os.listdir(temp_dir)))
            self.assertEqual(before_text, self._read(path))

    def test_json_report_normalizes_parser_and_reference_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text=("[ ] T First id:dup depends_on:missing\n[ ] T Second id:dup\n"),
            )

            stdout, stderr, code = run_cli("integrity", path, "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual("integrity-v1", payload["schema"])
            self.assertEqual(False, payload["ok"])
            diagnostics = payload["diagnostics"]
            self.assertTrue(any(row["code"] == "W213" for row in diagnostics))
            self.assertTrue(any(row["category"] == "reference" for row in diagnostics))
            for row in diagnostics:
                self.assertIn("severity", row)
                self.assertIn("effective_severity", row)
                self.assertIn("category", row)
                self.assertIn("message", row)
                self.assertIn("check_state", row)

    def test_missing_file_is_reported_as_blocked_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = os.path.join(temp_dir, "missing.life.txt")

            stdout, stderr, code = run_cli("integrity", missing, "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual(False, payload["ok"])
            self.assertTrue(
                any(
                    row["check_state"] == "blocked"
                    and row["category"] == "source"
                    and row["source_file"] == missing
                    for row in payload["diagnostics"]
                )
            )

    def test_verify_files_surfaces_attachment_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text='[ ] T Review id:t1 file:"./missing.md#sha256=0123456789abcdef"\n',
            )

            stdout, stderr, code = run_cli(
                "integrity", path, "--json", "--verify-files"
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertTrue(
                any(row["category"] == "files" for row in payload["diagnostics"])
            )

    def test_default_profile_preserves_warning_effective_severity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text="[ ] T First id:dup\n[ ] T Second id:dup\n",
            )

            stdout, stderr, code = run_cli("integrity", path, "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual("default", payload["profile"])
            duplicate = next(
                row for row in payload["diagnostics"] if row["code"] == "W213"
            )
            self.assertEqual("warning", duplicate["severity"])
            self.assertEqual("warning", duplicate["effective_severity"])

    def test_strict_profile_escalates_warning_effective_severity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text="[ ] T First id:dup\n[ ] T Second id:dup\n",
            )

            stdout, stderr, code = run_cli(
                "integrity", path, "--json", "--profile", "strict"
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual("strict", payload["profile"])
            duplicate = next(
                row for row in payload["diagnostics"] if row["code"] == "W213"
            )
            self.assertEqual("warning", duplicate["severity"])
            self.assertEqual("error", duplicate["effective_severity"])
            self.assertEqual(1, payload["summary"]["severities"]["error"])

    def test_strict_profile_does_not_change_check_command_warning_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text="[ ] T First id:dup\n[ ] T Second id:dup\n",
            )

            stdout, stderr, code = run_cli("check", path)

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("WARNING W213", stdout)
            self.assertNotIn("ERROR W213", stdout)

    def test_cross_file_registry_reports_duplicate_and_missing_reference(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = self._fixture(temp_dir, "first.life.txt", "[ ] T First id:dup\n")
            second = self._fixture(
                temp_dir,
                "second.life.txt",
                "[ ] T Second id:dup depends_on:missing\n",
            )

            stdout, stderr, code = run_cli("integrity", first, second, "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            codes = {row["code"] for row in payload["diagnostics"]}
            self.assertIn("I220", codes)
            self.assertIn("I221", codes)
            cross = next(row for row in payload["diagnostics"] if row["code"] == "I220")
            self.assertEqual(sorted([first, second]), cross["details"]["sources"])

    def test_source_uid_reconciliation_reports_duplicate_and_manual_conflict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text=(
                    "[ ] E Generated id:g source:ics uid:event-1 generated:true\n"
                    "[ ] E Manual id:m source:ics uid:event-1\n"
                ),
            )

            stdout, stderr, code = run_cli("integrity", path, "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            codes = {row["code"] for row in payload["diagnostics"]}
            self.assertIn("I300", codes)
            self.assertIn("I301", codes)

    def test_recovery_diagnostics_report_corrupt_local_journal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(temp_dir)
            journal_dir = os.path.join(temp_dir, "journals")
            corrupt_dir = os.path.join(journal_dir, "tx-corrupt")
            os.makedirs(corrupt_dir)
            with open(
                os.path.join(corrupt_dir, "journal.json"),
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write("{not-json")
            config_path = os.path.join(temp_dir, "config.json")
            with open(config_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump({"transactions": {"journal_dir": journal_dir}}, handle)

            stdout, stderr, code = run_cli(
                "--config", config_path, "integrity", path, "--json"
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertTrue(
                any(row["code"] == "I404" for row in payload["diagnostics"])
            )

    def test_integrity_plan_is_deterministic_and_non_mutating(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(temp_dir, text="[ ] T Missing id candidate\n")
            before = self._read(path)

            first, stderr, code = run_cli("integrity", "plan", path)
            second, second_stderr, second_code = run_cli("integrity", "plan", path)

            self.assertEqual("", stderr)
            self.assertEqual("", second_stderr)
            self.assertEqual(0, code)
            self.assertEqual(0, second_code)
            self.assertEqual(first, second)
            payload = json.loads(first)
            self.assertEqual("integrity-plan-v1", payload["schema"])
            action = next(row for row in payload["actions"] if row["code"] == "I210")
            self.assertEqual("automatic", action["classification"])
            self.assertEqual("assign_id", action["operation"])
            self.assertRegex(action["expected_revision"], r"^[0-9a-f]{64}$")
            self.assertEqual(before, self._read(path))

    def test_integrity_apply_requires_confirmation_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(temp_dir, text="[ ] T Missing\n")
            revision = self._revision(path)
            before = self._read(path)

            stdout, stderr, code = run_cli(
                "integrity",
                "apply",
                path,
                "--expected-revision",
                revision,
                "--json",
            )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertIn("--confirm", stderr)
            self.assertEqual(before, self._read(path))

    def test_integrity_apply_requires_expected_revision_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(temp_dir, text="[ ] T Missing\n")
            before = self._read(path)

            stdout, stderr, code = run_cli(
                "integrity",
                "apply",
                path,
                "--confirm",
                "--json",
            )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertIn("--expected-revision", stderr)
            self.assertEqual(before, self._read(path))

    def test_integrity_apply_revision_mismatch_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(temp_dir, text="[ ] T Missing\n")
            before = self._read(path)

            stdout, stderr, code = run_cli(
                "integrity",
                "apply",
                path,
                "--expected-revision",
                "0" * 64,
                "--confirm",
                "--json",
            )

            self.assertEqual(1, code)
            self.assertEqual("", stdout)
            self.assertIn("conflict", stderr.lower())
            self.assertEqual(before, self._read(path))

    def test_integrity_apply_assigns_missing_ids_with_revision_guard(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(temp_dir, text="[ ] T Missing\n[ ] T Has id:keep\n")
            revision = self._revision(path)

            stdout, stderr, code = run_cli(
                "integrity",
                "apply",
                path,
                "--expected-revision",
                revision,
                "--confirm",
                "--json",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual("integrity-apply-v1", payload["schema"])
            self.assertEqual("assign_id", payload["operation"])
            self.assertEqual(1, payload["assignment_count"])
            self.assertEqual(revision, payload["before_revision"])
            self.assertRegex(payload["after_revision"], r"^[0-9a-f]{64}$")
            self.assertNotEqual(revision, payload["after_revision"])
            updated = self._read(path)
            self.assertRegex(updated, r"^\[ \] T Missing id:task_\d{14}\n")
            self.assertIn("[ ] T Has id:keep\n", updated)

    def test_ai_context_checks_are_opt_in(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text='[ ] N "Prefers dark mode" person:self tag:preference id:m1\n',
            )
            before = self._read(path)

            stdout, stderr, code = run_cli("integrity", path, "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertFalse(
                any(row["category"] == "ai_context" for row in payload["diagnostics"])
            )
            self.assertEqual(before, self._read(path))

    def test_ai_context_reports_safe_workspace_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            primary, inbox, config_path = self._ai_workspace(temp_dir)
            before_primary = self._read(primary)
            before_inbox = self._read(inbox)

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "--workspace",
                "ai",
                "integrity",
                "--ai-context",
                "--json",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            row = next(row for row in payload["diagnostics"] if row["code"] == "AI102")
            self.assertEqual("ai_context", row["category"])
            self.assertEqual("passed", row["check_state"])
            self.assertTrue(row["details"]["has_dedicated_write_target"])
            self.assertEqual(inbox, row["details"]["write_file"])
            self.assertEqual(before_primary, self._read(primary))
            self.assertEqual(before_inbox, self._read(inbox))

    def test_ai_context_reports_non_dedicated_workspace_write_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            primary = self._fixture(temp_dir, text="[ ] T Real id:t1\n")
            reference = self._fixture(
                temp_dir, "reference.life.txt", "[ ] N Ref id:r1\n"
            )
            config_path = self._workspace_config(
                temp_dir,
                {
                    "workspaces": {
                        "ai": {
                            "sources": [
                                {"path": "life.txt", "role": "primary"},
                                {
                                    "path": "reference.life.txt",
                                    "role": "readonly",
                                    "writable": False,
                                },
                            ],
                            "write_file": "life.txt",
                        }
                    },
                    "default_workspace": "ai",
                },
            )
            before_primary = self._read(primary)
            before_reference = self._read(reference)

            stdout, stderr, code = run_cli(
                "--config",
                config_path,
                "integrity",
                "--ai-context",
                "--json",
            )

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            row = next(row for row in payload["diagnostics"] if row["code"] == "AI101")
            self.assertEqual("warning", row["severity"])
            self.assertFalse(row["details"]["has_dedicated_write_target"])
            self.assertEqual(primary, row["details"]["write_file"])
            self.assertEqual(before_primary, self._read(primary))
            self.assertEqual(before_reference, self._read(reference))

    def test_ai_context_reports_personal_memory_status_and_duplicate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text=(
                    '[ ] N "Prefers dark mode" person:self tag:preference id:m1\n'
                    '[N] N "prefers   dark mode" person:self tag:preference id:m2\n'
                ),
            )
            before = self._read(path)

            stdout, stderr, code = run_cli("integrity", path, "--ai-context", "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            codes = {row["code"] for row in payload["diagnostics"]}
            self.assertIn("AI201", codes)
            self.assertIn("AI202", codes)
            status = next(
                row for row in payload["diagnostics"] if row["code"] == "AI201"
            )
            self.assertEqual("m1", status["item_id"])
            duplicate = next(
                row for row in payload["diagnostics"] if row["code"] == "AI202"
            )
            self.assertEqual("prefers dark mode", duplicate["details"]["title_key"])
            self.assertEqual(before, self._read(path))

    def test_graph_flag_is_omitted_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir, text="[ ] T A id:a depends_on:b\n[ ] T B id:b\n"
            )

            stdout, stderr, code = run_cli("integrity", path, "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertFalse(
                any(row["category"] == "graph" for row in payload["diagnostics"])
            )

    def test_graph_reports_orphans_hubs_components_and_longest_chain(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text=(
                    "[ ] T A id:a depends_on:b\n"
                    "[ ] T B id:b depends_on:c\n"
                    "[ ] T C id:c\n"
                    "[ ] T Orphan1 id:o1\n"
                    "[ ] T Orphan2 id:o2\n"
                ),
            )
            before = self._read(path)

            stdout, stderr, code = run_cli("integrity", path, "--graph", "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            rows = {
                row["code"]: row
                for row in payload["diagnostics"]
                if row["category"] == "graph"
            }
            self.assertEqual({"G002", "G003", "G004", "G005"}, set(rows))

            orphan_row = rows["G002"]
            self.assertEqual(2, orphan_row["details"]["count"])
            self.assertEqual({"o1", "o2"}, set(orphan_row["details"]["ids"]))
            self.assertFalse(orphan_row["details"]["truncated"])

            hub_row = rows["G003"]
            hub_ids = [entry["id"] for entry in hub_row["details"]["hubs"]]
            self.assertIn("b", hub_ids)
            self.assertIn("c", hub_ids)

            component_row = rows["G004"]
            self.assertEqual(3, component_row["details"]["component_count"])
            self.assertEqual(3, component_row["details"]["largest_component_size"])

            chain_row = rows["G005"]
            self.assertEqual(3, chain_row["details"]["length"])
            self.assertEqual(["c", "b", "a"], chain_row["details"]["path"])
            self.assertEqual(before, self._read(path))

    def test_graph_reports_no_orphans_when_every_item_participates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir, text="[ ] T A id:a depends_on:b\n[ ] T B id:b\n"
            )

            stdout, stderr, code = run_cli("integrity", path, "--graph", "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            row = next(row for row in payload["diagnostics"] if row["code"] == "G002")
            self.assertEqual("passed", row["check_state"])
            self.assertEqual(0, row["details"]["count"])

    def test_graph_reports_no_ids_state_when_workspace_has_no_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(temp_dir, text="[ ] T No_id\n")

            stdout, stderr, code = run_cli("integrity", path, "--graph", "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            row = next(row for row in payload["diagnostics"] if row["code"] == "G001")
            self.assertEqual("skipped", row["check_state"])

    def test_graph_longest_chain_check_is_blocked_by_a_cycle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir,
                text="[ ] T X id:x depends_on:y\n[ ] T Y id:y depends_on:x\n",
            )

            stdout, stderr, code = run_cli("integrity", path, "--graph", "--json")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            row = next(row for row in payload["diagnostics"] if row["code"] == "G005")
            self.assertEqual("blocked", row["check_state"])
            self.assertEqual("warning", row["severity"])
            self.assertFalse(payload["ok"])

    def test_graph_flag_works_with_the_plan_subcommand(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._fixture(
                temp_dir, text="[ ] T A id:a depends_on:b\n[ ] T B id:b\n"
            )

            stdout, stderr, code = run_cli("integrity", "plan", path, "--graph")

            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertTrue(payload["ok"])

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def _revision(self, path):
        from lifetxt.write_operations import current_revision

        return current_revision(path, allow_missing=False)

    def _workspace_config(self, temp_dir, payload):
        config_path = os.path.join(temp_dir, ".lifetxt.json")
        with open(config_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle)
        return config_path

    def _ai_workspace(self, temp_dir):
        primary = self._fixture(temp_dir, text="[ ] T Real_Task id:t1 project:work\n")
        inbox = self._fixture(temp_dir, "ai-inbox.life.txt", "")
        config_path = self._workspace_config(
            temp_dir,
            {
                "workspaces": {
                    "ai": {
                        "sources": [
                            {
                                "path": "life.txt",
                                "role": "readonly",
                                "writable": False,
                            },
                            {
                                "path": "ai-inbox.life.txt",
                                "role": "primary",
                                "writable": True,
                            },
                        ],
                        "write_file": "ai-inbox.life.txt",
                    }
                },
                "default_workspace": "ai",
            },
        )
        return primary, inbox, config_path


if __name__ == "__main__":
    unittest.main()
