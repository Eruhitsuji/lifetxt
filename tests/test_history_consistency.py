import json
import os
import shutil
import subprocess
import tempfile
import unittest

from lifetxt import mutation
from lifetxt.history_consistency import verify_history_consistency
from lifetxt.native_history import build_item_event
from lifetxt.parser import parse_text
from lifetxt.progress_history import build_progress_event
from lifetxt.serializer import item_to_line
from lifetxt.ticket_activity import build_ticket_event
from tests.test_lifetxt import run_cli


def _git(directory, *args):
    result = subprocess.run(
        ["git"] + list(args),
        cwd=directory,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class HistoryConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = self.temp.name
        _git(self.repo, "init", "-b", "main")
        _git(self.repo, "config", "user.name", "Test")
        _git(self.repo, "config", "user.email", "test@example.invalid")
        self.path = os.path.join(self.repo, "life.txt")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def commit(self, message):
        _git(self.repo, "add", "life.txt")
        _git(self.repo, "commit", "-m", message)

    def items(self):
        with open(self.path, encoding="utf-8") as handle:
            return parse_text(handle.read())[0]

    def build_verified_history(self, progress_after="40%", native_progress_after=None):
        empty_revision = mutation.hash_text("")
        created = build_item_event(
            "task-1",
            "created",
            "2026-09-10T09:00:00Z",
            1,
            "ITX-1",
            empty_revision,
            item_kind="T",
            item_title="Task",
            after_status="[ ]",
        )
        base = (
            "[ ] T Task id:task-1 progress:20% due:2026-09-10\n"
            + item_to_line(created)
            + "\n"
        )
        self.write(base)
        self.commit("base")
        source_revision = mutation.hash_text(base)
        status = build_item_event(
            "task-1",
            "status_changed",
            "2026-09-10T10:00:00Z",
            2,
            "ITX-2",
            source_revision,
            before_status="[ ]",
            after_status="[/]",
        )
        relation = build_item_event(
            "task-1",
            "relation_added",
            "2026-09-10T10:00:01Z",
            3,
            "ITX-3",
            source_revision,
            relation="follows",
            target="task-0",
        )
        schedule = build_item_event(
            "task-1",
            "schedule_changed",
            "2026-09-10T10:00:02Z",
            4,
            "ITX-4",
            source_revision,
            field="due",
            before="2026-09-10",
            after="2026-09-12",
        )
        progress = build_progress_event(
            "task-1",
            "20%",
            native_progress_after or progress_after,
            "set",
            "2026-09-10T10:00:03Z",
            1,
            "PTX-1",
            source_revision,
        )
        after = (
            "[/] T Task id:task-1 progress:%s due:2026-09-12 follows:task-0\n"
            % progress_after
            + item_to_line(created)
            + "\n"
            + item_to_line(status)
            + "\n"
            + item_to_line(relation)
            + "\n"
            + item_to_line(schedule)
            + "\n"
            + item_to_line(progress)
            + "\n"
        )
        self.write(after)
        self.commit("compound")

    def test_one_commit_can_verify_multiple_native_events_semantically(self):
        self.build_verified_history()
        report = verify_history_consistency(self.items(), [self.path])
        self.assertEqual(5, report["summary"]["verified"])
        self.assertEqual(0, report["summary"]["conflict"])
        self.assertTrue(report["complete"])
        self.assertTrue(
            any(
                row["native"]["source_revision"] == row["git"]["source_revision"]
                for row in report["comparisons"]
                if row["classification"] == "verified"
            )
        )

    def test_comparable_disagreement_is_conflict_with_both_values(self):
        self.build_verified_history(progress_after="40%", native_progress_after="50%")
        report = verify_history_consistency(self.items(), [self.path])
        conflict = next(
            row
            for row in report["comparisons"]
            if row["classification"] == "conflict"
        )
        self.assertEqual("50%", conflict["after"])
        self.assertEqual("40%", conflict["git"]["after"])
        self.assertFalse(report["complete"])

    def test_git_only_manual_change_is_coverage_gap(self):
        self.write("[ ] T Task id:task-1 due:2026-09-10\n")
        self.commit("base")
        self.write("[ ] T Task id:task-1 due:2026-09-12\n")
        self.commit("manual")
        report = verify_history_consistency(self.items(), [self.path], item_id="task-1")
        self.assertGreaterEqual(report["summary"]["git_only"], 1)
        self.assertTrue(
            all(
                row["reason"] == "native_event_not_found"
                for row in report["comparisons"]
                if row["classification"] == "git_only"
            )
        )

    def test_uncommitted_native_event_is_native_only(self):
        self.write("[ ] T Task id:task-1\n")
        self.commit("base")
        event = build_item_event(
            "task-1",
            "status_changed",
            "2026-09-10T10:00:00Z",
            1,
            "ITX-1",
            mutation.hash_text("[ ] T Task id:task-1\n"),
            before_status="[ ]",
            after_status="[/]",
        )
        self.write("[/] T Task id:task-1\n" + item_to_line(event) + "\n")
        report = verify_history_consistency(self.items(), [self.path], item_id="task-1")
        self.assertEqual(1, report["summary"]["native_only"])

    def test_malformed_and_unsupported_events_are_unverifiable(self):
        self.write("[ ] T Ticket record:ticket id:TK-1 ticket_status:new\n")
        self.commit("base")
        malformed = build_item_event(
            "TK-1",
            "status_changed",
            "2026-09-10T10:00:00Z",
            1,
            "ITX-1",
            mutation.hash_text("x"),
            before_status="[ ]",
            after_status="[/]",
        )
        malformed.details["at"] = ["bad"]
        ticket = build_ticket_event(
            "TK-1", "comment", "me", "2026-09-10T11:00:00Z", 1, "TX-1", "a" * 64
        )
        items = self.items() + [malformed, ticket]
        report = verify_history_consistency(items, [self.path], item_id="TK-1")
        self.assertEqual(2, report["summary"]["unverifiable"])

    def test_git_free_workspace_returns_deterministic_native_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            event = build_item_event(
                "task-1",
                "status_changed",
                "2026-09-10T10:00:00Z",
                1,
                "ITX-1",
                "a" * 64,
                before_status="[ ]",
                after_status="[/]",
            )
            items, _ = parse_text("[/] T Task id:task-1\n" + item_to_line(event) + "\n")
            report = verify_history_consistency(items, [path], item_id="task-1")
            self.assertFalse(report["git_evidence"]["available"])
            self.assertEqual(1, report["summary"]["native_only"])
            self.assertFalse(report["complete"])

    def test_shallow_history_is_never_complete(self):
        self.build_verified_history()
        clone_parent = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, clone_parent)
        clone = os.path.join(clone_parent, "clone")
        _git(clone_parent, "clone", "--depth", "1", "file://" + self.repo, clone)
        path = os.path.join(clone, "life.txt")
        with open(path, encoding="utf-8") as handle:
            items = parse_text(handle.read())[0]
        report = verify_history_consistency(items, [path])
        self.assertFalse(report["git_evidence"]["history_complete"])
        self.assertIn("shallow_or_unverifiable_history", report["limitations"])

    def test_commit_limit_truncation_is_explicit(self):
        self.build_verified_history()
        report = verify_history_consistency(
            self.items(), [self.path], commit_limit=1
        )
        self.assertFalse(report["git_evidence"]["history_complete"])
        self.assertIn("commit_limit_truncated", report["limitations"])
        self.assertFalse(report["complete"])

    def test_path_missing_at_a_revision_is_explicit(self):
        self.write("[ ] T First id:first\n")
        self.commit("first path")
        second_path = os.path.join(self.repo, "second.txt")
        with open(second_path, "w", encoding="utf-8", newline="") as handle:
            handle.write("[ ] T Second id:second\n")
        _git(self.repo, "add", "second.txt")
        _git(self.repo, "commit", "-m", "second path")
        with open(second_path, encoding="utf-8") as handle:
            second_items = parse_text(handle.read())[0]
        report = verify_history_consistency(
            self.items() + second_items,
            [self.path, second_path],
        )
        self.assertIn("missing_at_revision:second.txt", report["limitations"])
        self.assertFalse(report["complete"])

    def test_cli_text_and_json_use_the_same_verifier_result(self):
        self.build_verified_history()
        stdout, stderr, code = run_cli(
            "history-check", self.path, "--id", "task-1", "--json"
        )
        self.assertEqual(0, code, stderr)
        report = json.loads(stdout)
        self.assertEqual("native-git-history-consistency-v1", report["schema"])
        self.assertEqual(5, report["summary"]["verified"])

        stdout, stderr, code = run_cli(
            "history-check", self.path, "--id", "task-1"
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("History consistency for task-1", stdout)
        self.assertIn("verified:", stdout)

    def test_cli_rejects_unbounded_commit_limit(self):
        self.write("[ ] T Task id:task-1\n")
        self.commit("base")
        _stdout, stderr, code = run_cli(
            "history-check", self.path, "--commit-limit", "501"
        )
        self.assertNotEqual(0, code)
        self.assertIn("between 1 and 500", stderr)
