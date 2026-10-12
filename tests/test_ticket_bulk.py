import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from lifetxt import mutation
from lifetxt.parser import parse_text
from lifetxt.ticket_bulk import preview_assignment, apply_assignment_plan, _digest
from lifetxt.ticket_activity import iter_ticket_events, validate_ticket_history
from tests.test_lifetxt import run_cli


class TicketBulkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "life.txt"
        self.config = {"paths": [str(self.path)], "write_file": str(self.path)}
        self.path.write_bytes(
            b"# keep comment\r\n[ ] T One record:ticket id:A tracker:bug ticket_status:new project:web custom:kept\r\n[ ] T Two record:ticket id:B tracker:bug ticket_status:new project:web\r\n"
        )

    def preview(self, ids=None, **kwargs):
        defaults = dict(
            path=str(self.path),
            ids=ids or ["A", "B"],
            assignee="alice",
            actor="reviewer",
            expected_revision=mutation.read_text_snapshot(str(self.path)).content_hash,
            transaction_id="batch.1",
            config=self.config,
            at="2026-10-12T10:00:00+09:00",
        )
        defaults.update(kwargs)
        return preview_assignment(**defaults)

    def apply(self, plan):
        return apply_assignment_plan(plan, plan["plan_sha256"], self.config)

    def items(self):
        return parse_text(
            self.path.read_text(), check_ids=False, check_references=False
        )[0]

    def test_preview_and_atomic_apply_preserve_scope_and_append_history(self):
        before = self.path.read_bytes()
        plan = self.preview()
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual("2026-10-12T01:00:00Z", plan["at"])
        self.assertEqual(2, len(plan["changes"]))
        with patch(
            "lifetxt.mutation.atomic_write_bytes", wraps=mutation.atomic_write_bytes
        ) as writer:
            result = self.apply(plan)
        self.assertEqual(1, writer.call_count)
        self.assertTrue(result["changed"])
        self.assertEqual(
            plan["revision_after"],
            mutation.read_text_snapshot(str(self.path)).content_hash,
        )
        self.assertTrue(self.path.read_bytes().startswith(b"# keep comment\r\n"))
        self.assertNotIn(b"\n", self.path.read_bytes().replace(b"\r\n", b""))
        items = self.items()
        self.assertEqual(["alice"], items[0].details["assignee"])
        self.assertEqual(["kept"], items[0].details["custom"])
        self.assertEqual(2, len(iter_ticket_events(items)))
        self.assertFalse(
            [d for d in validate_ticket_history(items) if d["severity"] == "error"]
        )

    def test_missing_duplicate_or_too_many_ids_are_zero_write(self):
        before = self.path.read_bytes()
        for ids in (["A", "missing"], ["A", "A"], [str(i) for i in range(101)]):
            with self.subTest(ids=ids[:2]), self.assertRaises(ValueError):
                self.preview(ids)
            self.assertEqual(before, self.path.read_bytes())
        self.path.write_text(
            self.path.read_text()
            + "[ ] T Dup record:ticket id:A tracker:bug ticket_status:new\n"
        )
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.preview()
        self.assertEqual(before, self.path.read_bytes())

    def test_invalid_later_ticket_rolls_back_all(self):
        self.path.write_text(
            self.path.read_text().replace(
                "id:B tracker:bug ticket_status:new",
                "id:B tracker:bug ticket_status:resolved",
            )
        )
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.preview()
        self.assertEqual(before, self.path.read_bytes())

    def test_stale_tampered_config_and_wrong_review_digest_are_zero_write(self):
        plan = self.preview()
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            apply_assignment_plan(plan, "0" * 64, self.config)
        altered = copy.deepcopy(plan)
        altered["changes"][0]["changed"] = False
        with self.assertRaises(ValueError):
            self.apply(altered)
        altered["plan_sha256"] = _digest(
            {k: v for k, v in altered.items() if k != "plan_sha256"}
        )
        with self.assertRaises(ValueError):
            self.apply(altered)
        with self.assertRaises(ValueError):
            apply_assignment_plan(
                plan, plan["plan_sha256"], dict(self.config, user={"name": "other"})
            )
        with self.assertRaises(ValueError):
            apply_assignment_plan(plan, plan["plan_sha256"], self.config, key="uid")
        self.assertEqual(before, self.path.read_bytes())
        self.path.write_bytes(before + b"# concurrent\r\n")
        changed = self.path.read_bytes()
        with self.assertRaises(mutation.MutationConflict):
            self.apply(plan)
        self.assertEqual(changed, self.path.read_bytes())

    def test_replay_and_transaction_reuse_are_rejected(self):
        plan = self.preview()
        self.apply(plan)
        before = self.path.read_bytes()
        with self.assertRaises(mutation.MutationConflict):
            self.apply(plan)
        with self.assertRaises(ValueError):
            self.preview(assignee="bob")
        self.assertEqual(before, self.path.read_bytes())

    def test_noop_emits_no_event_and_no_write(self):
        self.path.write_text(
            self.path.read_text().replace("project:web", "project:web assignee:alice")
        )
        plan = self.preview()
        before = self.path.read_bytes()
        with patch("lifetxt.mutation.atomic_write_bytes") as writer:
            self.assertFalse(self.apply(plan)["changed"])
        writer.assert_not_called()
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([], iter_ticket_events(self.items()))

    def test_bom_and_custom_id_key(self):
        self.path.write_bytes(
            b"\xef\xbb\xbf" + self.path.read_bytes().replace(b"id:", b"uid:")
        )
        plan = self.preview(key="uid")
        apply_assignment_plan(plan, plan["plan_sha256"], self.config, key="uid")
        self.assertTrue(self.path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_write_failure_and_locked_revision_race_preserve_bytes(self):
        plan = self.preview()
        before = self.path.read_bytes()
        with (
            patch(
                "lifetxt.mutation.atomic_write_bytes",
                side_effect=OSError("disk failure"),
            ),
            self.assertRaises(OSError),
        ):
            self.apply(plan)
        self.assertEqual(before, self.path.read_bytes())
        real = mutation.mutate_text

        def race(path, transform, **kwargs):
            self.path.write_bytes(before + b"# raced\r\n")
            return real(path, transform, **kwargs)

        with (
            patch("lifetxt.mutation.mutate_text", side_effect=race),
            self.assertRaises(mutation.MutationConflict),
        ):
            self.apply(plan)
        self.assertEqual(before + b"# raced\r\n", self.path.read_bytes())

    def test_scope_rejects_cross_file_generated_readonly_and_symlink(self):
        before = self.path.read_bytes()
        other = Path(self.temp.name) / "other.txt"
        other.write_text("")
        for config in (
            dict(self.config, paths=[str(self.path), str(other)]),
            dict(self.config, generated_paths=[str(self.path)]),
            {
                "workspaces": {
                    "one": {
                        "sources": [
                            {
                                "path": str(self.path),
                                "role": "archive",
                                "writable": True,
                            }
                        ]
                    }
                },
                "default_workspace": "one",
            },
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                self.preview(config=config)
        self.path.chmod(0o444)
        with self.assertRaises(ValueError):
            self.preview()
        self.path.chmod(0o644)
        alias = Path(self.temp.name) / "alias.txt"
        alias.symlink_to(self.path)
        with self.assertRaises(ValueError):
            self.preview(path=str(alias))
        self.assertEqual(before, self.path.read_bytes())

    def test_bound_of_100_and_scalar_validation(self):
        self.path.write_text(
            "".join(
                "[ ] T Ticket record:ticket id:K%d tracker:bug ticket_status:new\n" % n
                for n in range(100)
            )
        )
        plan = self.preview(["K%d" % n for n in range(100)])
        self.assertEqual(100, len(plan["changes"]))
        self.apply(plan)
        self.assertEqual(100, len(iter_ticket_events(self.items())))
        for kwargs in (
            {"assignee": "bad\nname"},
            {"actor": ""},
            {"transaction_id": "bad-id"},
            {"at": "2026-10-12T10:00:00"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.preview(["K0"], **kwargs)

    def test_mixed_noop_and_ambiguous_scalar_targets(self):
        original = self.path.read_bytes()
        self.path.write_bytes(
            original.replace(b"id:A tracker", b"id:A assignee:alice tracker")
        )
        plan = self.preview()
        self.assertEqual([False, True], [row["changed"] for row in plan["changes"]])
        self.apply(plan)
        self.assertEqual(1, len(iter_ticket_events(self.items())))
        for old, new in (
            (b"id:A", b"id:A id:OTHER"),
            (b"record:ticket id:A", b"record:ticket record:risk id:A"),
        ):
            self.path.write_bytes(original.replace(old, new))
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                self.preview()
            self.assertEqual(before, self.path.read_bytes())

    def test_invalid_existing_history_refuses_all_targets(self):
        self.apply(self.preview())
        data = self.path.read_bytes()
        event = [
            line
            for line in data.splitlines(keepends=True)
            if b"record:ticket_event" in line
        ][0]
        self.path.write_bytes(data + event)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.preview(transaction_id="new.batch", assignee="bob")
        self.assertEqual(before, self.path.read_bytes())

    def test_cli_preview_saved_plan_and_apply(self):
        conf = Path(self.temp.name) / "config.json"
        conf.write_text(json.dumps(self.config))
        revision = mutation.read_text_snapshot(str(self.path)).content_hash
        out, err, code = run_cli(
            "--config",
            str(conf),
            "ticket",
            "bulk",
            "assign",
            str(self.path),
            "--id",
            "A",
            "--id",
            "B",
            "--assignee",
            "alice",
            "--revision",
            revision,
            "--transaction-id",
            "cli.1",
            "--dry-run",
        )
        self.assertEqual(0, code, err)
        plan = json.loads(out)
        saved = Path(self.temp.name) / "plan.json"
        saved.write_text(out)
        out, err, code = run_cli(
            "--config",
            str(conf),
            "ticket",
            "bulk",
            "apply",
            str(saved),
            "--plan-sha256",
            plan["plan_sha256"],
        )
        self.assertEqual(0, code, err)
        self.assertTrue(json.loads(out)["changed"])
        saved.write_text("{}")
        self.assertEqual(
            1,
            run_cli(
                "--config",
                str(conf),
                "ticket",
                "bulk",
                "apply",
                str(saved),
                "--plan-sha256",
                "0" * 64,
            )[2],
        )
