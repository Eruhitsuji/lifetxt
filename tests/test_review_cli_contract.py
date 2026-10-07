"""Public review CLI contracts for temporal and error boundaries (#1137)."""

import json
import os
import tempfile
from unittest import mock

from lifetxt import entrypoint
from lifetxt.native_history import build_item_event
from lifetxt.serializer import item_to_line
from lifetxt.temporal_review import build_temporal_review
from tests.test_core_cli_entrypoint import CliContractTestCase


REVISION = "a" * 64


class ReviewCliContractTests(CliContractTestCase):
    def _make_file(self, text):
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        handle.write(text)
        handle.flush()
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        return handle.name

    def _run(self, *argv):
        self.stdout.seek(0)
        self.stdout.truncate()
        self.stderr.seek(0)
        self.stderr.truncate()
        code = entrypoint.main(list(argv))
        return code, self.stdout.getvalue(), self.stderr.getvalue()

    def _temporal_fixture(self):
        created = build_item_event(
            "task-1",
            "created",
            "2026-06-01T09:00:00Z",
            1,
            "ITX-task-1-000001",
            REVISION,
            item_kind="T",
            item_title="Temporal task",
            after_status="[ ]",
        )
        completed = build_item_event(
            "task-1",
            "completed",
            "2026-06-02T10:00:00Z",
            2,
            "ITX-task-1-000002",
            REVISION,
            before_status="[ ]",
            after_status="[x]",
            completed_at="2026-06-02T10:00:00Z",
        )
        return self._make_file(
            '[x] T "Temporal task" id:task-1 project:alpha\n'
            + item_to_line(created)
            + "\n"
            + item_to_line(completed)
            + "\n"
        )

    def test_temporal_text_json_jsonl_and_pretty_json_are_deterministic(self):
        path = self._temporal_fixture()
        base = (
            "review",
            path,
            "--temporal",
            "--since",
            "2026-06-01",
            "--until",
            "2026-06-03",
        )

        code, out, err = self._run(*base)
        self.assertEqual(0, code, err)
        self.assertIn(
            "Temporal Life Review: 2026-06-01T00:00:00+00:00 .. "
            "2026-06-03T23:59:59.999999+00:00",
            out,
        )
        self.assertIn("events: 2", out)
        self.assertIn("completed: 1", out)

        for fmt in ("json", "jsonl"):
            with self.subTest(fmt=fmt):
                code, out, err = self._run(*base, "--format", fmt)
                self.assertEqual(0, code, err)
                self.assertEqual(1, out.count("\n"))
                payload = json.loads(out)
                self.assertEqual("temporal-life-review-v1", payload["schema"])
                self.assertEqual(2, payload["counts"]["events"])
                self.assertEqual(1, payload["counts"]["completed"])

        code, out, err = self._run(*base, "--format", "json", "--pretty")
        self.assertEqual(0, code, err)
        self.assertGreater(out.count("\n"), 1)
        self.assertIn('\n  "period": {', out)
        self.assertEqual(2, json.loads(out)["counts"]["events"])

    def test_temporal_adapter_forwards_public_cli_options(self):
        path = self._temporal_fixture()
        with mock.patch(
            "lifetxt.temporal_review.build_temporal_review",
            wraps=build_temporal_review,
        ) as delegate:
            code, out, err = self._run(
                "review",
                path,
                "--temporal",
                "--since",
                "2026-06-01",
                "--until",
                "2026-06-03",
                "--limit",
                "7",
                "--project",
                "alpha",
                "--format",
                "json",
            )

        self.assertEqual(0, code, err)
        self.assertEqual("temporal-life-review-v1", json.loads(out)["schema"])
        delegate.assert_called_once()
        _items = delegate.call_args.args[0]
        self.assertGreaterEqual(len(_items), 1)
        self.assertEqual(
            {
                "since": "2026-06-01",
                "until": "2026-06-03",
                "week": False,
                "limit": 7,
                "project": "alpha",
                "id_key": "id",
            },
            delegate.call_args.kwargs,
        )

    def test_temporal_week_conflict_is_a_clean_cli_error(self):
        path = self._make_file('[ ] T "Open task" id:task-1\n')
        code, out, err = self._run(
            "review",
            path,
            "--temporal",
            "--week",
            "--since",
            "2026-06-01",
        )
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertIn("ERROR: --week cannot be combined with --since/--until.", err)
        self.assertNotIn("Traceback", err)

    def test_legacy_invalid_ranges_are_clean_public_cli_errors(self):
        path = self._make_file("[x] T Done done:2026-06-10\n")
        cases = (
            (("--month", "2026-13"), "Invalid month"),
            (("--from", "bad"), "Invalid from date"),
            (("--to", "bad"), "Invalid to date"),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                code, out, err = self._run("review", path, *args)
                self.assertEqual(1, code)
                self.assertEqual("", out)
                self.assertIn("ERROR:", err)
                self.assertIn(expected, err)
                self.assertNotIn("Traceback", err)
