"""Status API atomicity, revision compatibility and persistence (#1378)."""

import codecs
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from lifetxt import mutation, presence, webapp
from lifetxt.parser import parse_text
from lifetxt.surface_runtime import SurfaceTransaction


try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


TASK = '[ ] T "Keep me" id:task-1\n'
STATUS = "[/] S Busy from:2026-01-01T09:00 state:busy person:self id:status-1\n"
OTHER = "[/] S Other from:2026-01-01T09:00 state:away person:other id:status-other\n"


@unittest.skipIf(TestClient is None, "Web extras are unavailable")
class WebStatusAtomicTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "life.txt"
        self.path.write_text(TASK + STATUS + OTHER, encoding="utf-8")
        self.config = {
            "web": {"revision_metrics_path": str(self.path.parent / "metrics.json")},
            "timer": {"state_file": str(self.path.parent / "timer.json")},
        }
        self.client = self.make_client()

    def make_client(self, **kwargs):
        app = webapp.create_app(
            [str(self.path)], writable_path=str(self.path), config=self.config, **kwargs
        )
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    def post(self, payload, client=None, **kwargs):
        return (client or self.client).post("/api/status", json=payload, **kwargs)

    def items(self):
        items, diagnostics = parse_text(mutation.read_text_snapshot(self.path).text)
        self.assertEqual([], [d.format() for d in diagnostics if d.severity == "error"])
        return items

    def assert_saved_revision(self, response):
        revision = mutation.read_text_snapshot(self.path).content_hash
        self.assertEqual(revision, response.headers["X-Lifetxt-Revision"])
        self.assertEqual('"%s"' % revision, response.headers["ETag"])
        self.assertEqual("no-store", response.headers["Cache-Control"])

    def test_transition_runs_under_lock_and_keeps_details_ids_and_other_person(self):
        transition = presence.status_transition

        def locked_transition(text, **kwargs):
            self.assertTrue(Path(str(self.path) + ".lifetxt.lock").is_file())
            self.assertEqual(TASK + STATUS + OTHER, text)
            return transition(text, **kwargs)

        with mock.patch(
            "lifetxt.presence.status_transition", side_effect=locked_transition
        ):
            response = self.post(
                {
                    "state": "custom state",
                    "title": "Deep work",
                    "person": "self",
                    "note": "hello",
                    "project": "work",
                    "service": "desk",
                    "visibility": "team",
                }
            )
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual(
            {"closed", "opened", "unchanged", "path"}, set(response.json())
        )
        self.assertEqual(str(self.path), response.json()["path"])
        self.assert_saved_revision(response)
        text = self.path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(TASK))
        self.assertIn(OTHER, text)
        items = self.items()
        self.assertEqual(["status-1"], items[1].details["id"])
        self.assertEqual("[x]", items[1].status)
        opened = items[-1]
        self.assertEqual("Deep work", opened.title)
        for key, value in {
            "state": "custom state",
            "person": "self",
            "note": "hello",
            "project": "work",
            "service": "desk",
            "visibility": "team",
        }.items():
            self.assertEqual([value], opened.details[key])
        self.assertEqual(items[1].details["to"], opened.details["from"])
        ids = [item.details["id"][0] for item in items]
        self.assertEqual(len(ids), len(set(ids)))

    def test_preserves_bom_crlf_and_unmodified_bytes(self):
        before = (
            codecs.BOM_UTF8 + (TASK + STATUS + OTHER).replace("\n", "\r\n").encode()
        )
        self.path.write_bytes(before)
        response = self.post({"state": "focus"})
        self.assertEqual(201, response.status_code, response.text)
        saved = self.path.read_bytes()
        self.assertTrue(
            saved.startswith(codecs.BOM_UTF8 + TASK.replace("\n", "\r\n").encode())
        )
        self.assertIn(OTHER.replace("\n", "\r\n").encode(), saved)
        self.assertNotIn(b"\n", saved.replace(b"\r\n", b""))
        self.assert_saved_revision(response)

    def test_same_state_is_byte_and_mtime_preserving_noop(self):
        before = self.path.read_bytes()
        before_stat = self.path.stat()
        response = self.post({"state": "busy", "title": "Ignored", "note": "Ignored"})
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual("busy", response.json()["unchanged"])
        self.assertEqual([], response.json()["closed"])
        self.assertEqual("", response.json()["opened"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(before_stat.st_mtime_ns, self.path.stat().st_mtime_ns)
        self.assert_saved_revision(response)

    def test_force_and_end_keep_existing_meaning(self):
        response = self.post({"state": "busy", "force": True})
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual(1, len(response.json()["closed"]))
        self.assertEqual("", response.json()["unchanged"])
        self.assert_saved_revision(response)
        count = len(self.items())
        ended = self.post(
            {"end": True, "state": "away", "title": "Ignored", "force": True}
        )
        self.assertEqual(201, ended.status_code, ended.text)
        self.assertEqual("", ended.json()["opened"])
        self.assertEqual(1, len(ended.json()["closed"]))
        self.assertEqual(count, len(self.items()))
        self.assertEqual([], presence.active_status_items(self.items(), person="self"))
        again = self.post({"end": True})
        self.assertEqual(201, again.status_code, again.text)
        self.assertEqual([], again.json()["closed"])

    def test_multiple_open_records_converge_even_when_state_matches(self):
        self.path.write_text(
            TASK + STATUS + STATUS.replace("status-1", "status-2") + OTHER
        )
        response = self.post({"state": "busy"})
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual(2, len(response.json()["closed"]))
        self.assertEqual(
            1, len(presence.active_status_items(self.items(), person="self"))
        )
        self.assertIn(OTHER, self.path.read_text())

    def test_explicit_person_does_not_close_self(self):
        response = self.post({"person": "other", "state": "working"})
        self.assertEqual(201, response.status_code, response.text)
        self.assertIn(STATUS, self.path.read_text())
        active = presence.active_status_items(self.items(), person="other")
        self.assertEqual(["working"], active[0].details["state"])

    def test_missing_file_creation_remains_supported(self):
        self.path.unlink()
        response = self.post({"state": "focus"})
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual(1, len(self.items()))
        self.assert_saved_revision(response)

    def test_restart_reads_the_persisted_status(self):
        response = self.post({"state": "focus", "title": "Persistent"})
        self.assertEqual(201, response.status_code, response.text)
        restarted = self.make_client()
        records = restarted.get("/api/status?person=self&active=true")
        self.assertEqual(200, records.status_code, records.text)
        matching = [r for r in records.json()["records"] if r["person"] == "self"]
        self.assertEqual(1, len(matching))
        self.assertEqual("focus", matching[0]["state"])
        self.assertEqual("Persistent", matching[0]["title"])

    def test_observe_legacy_and_required_revision_contracts(self):
        legacy = self.post({"state": "focus"})
        self.assertEqual(201, legacy.status_code, legacy.text)
        self.assertEqual("used", legacy.headers["X-Lifetxt-Legacy-Revision-Fallback"])
        self.config["web"]["revision_mode"] = "required"
        required = self.make_client()
        before = self.path.read_bytes()
        missing = self.post({"state": "away"}, client=required)
        self.assertEqual(428, missing.status_code, missing.text)
        self.assertEqual(before, self.path.read_bytes())
        revision = required.get("/api/revision").headers["ETag"]
        saved = self.post(
            {"state": "away"}, client=required, headers={"If-Match": revision}
        )
        self.assertEqual(201, saved.status_code, saved.text)
        self.assert_saved_revision(saved)
        self.assertNotIn("X-Lifetxt-Legacy-Revision-Fallback", saved.headers)

    def test_stale_revision_rejected_even_for_same_state(self):
        revision = mutation.read_text_snapshot(self.path).content_hash
        external = self.path.read_bytes() + b"[ ] T External id:external\n"
        self.path.write_bytes(external)
        for payload in ({"state": "busy"}, {"state": "focus"}, {"end": True}):
            with self.subTest(payload=payload):
                response = self.post(payload, headers={"If-Match": revision})
                self.assertEqual(409, response.status_code, response.text)
                self.assertEqual("CONFLICT", response.json()["error"])
                self.assertEqual(external, self.path.read_bytes())

    def test_concurrent_requests_have_one_winner_and_no_automatic_retry(self):
        revision = mutation.read_text_snapshot(self.path).content_hash
        barrier = threading.Barrier(2, timeout=5)
        initialize = SurfaceTransaction.__init__

        def synchronized(transaction, path, expected_hash, operation, **kwargs):
            initialize(transaction, path, expected_hash, operation, **kwargs)
            if operation == "web.presence":
                barrier.wait()

        second_client = self.make_client()
        with mock.patch.object(SurfaceTransaction, "__init__", synchronized):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(
                        self.post,
                        {"state": state},
                        client=client,
                        headers={"If-Match": revision},
                    )
                    for state, client in (
                        ("focus", self.client),
                        ("away", second_client),
                    )
                ]
                responses = [future.result(timeout=10) for future in futures]
        self.assertEqual(
            [201, 409], sorted(response.status_code for response in responses)
        )
        self.assertEqual(4, len(self.items()))
        self.assertEqual(
            1, len(presence.active_status_items(self.items(), person="self"))
        )
        self.assertIn(TASK, self.path.read_text())
        self.assertIn(OTHER, self.path.read_text())

    def test_external_edit_during_transform_conflicts_without_losing_edit(self):
        before = self.path.read_bytes()
        transition = presence.status_transition
        for external in (
            before + b"[ ] T External id:external\n",
            before.replace(b"Keep me", b"Edited task"),
        ):
            with self.subTest(external=external):
                self.path.write_bytes(before)

                def edit_during_transform(text, **kwargs):
                    result = transition(text, **kwargs)
                    self.path.write_bytes(external)  # Editor ignoring the sidecar lock.
                    return result

                with mock.patch(
                    "lifetxt.presence.status_transition",
                    side_effect=edit_during_transform,
                ) as call:
                    response = self.post({"state": "focus"})
                self.assertEqual(409, response.status_code, response.text)
                self.assertEqual("CONFLICT", response.json()["error"])
                self.assertEqual("no-store", response.headers["Cache-Control"])
                self.assertEqual(external, self.path.read_bytes())
                call.assert_called_once()

    def test_noop_still_detects_external_edit(self):
        transition = presence.status_transition
        external = self.path.read_bytes() + b"[ ] T External id:external\n"

        def edit(text, **kwargs):
            result = transition(text, **kwargs)
            self.path.write_bytes(external)
            return result

        with mock.patch("lifetxt.presence.status_transition", side_effect=edit):
            response = self.post({"state": "busy"})
        self.assertEqual(409, response.status_code, response.text)
        self.assertEqual(external, self.path.read_bytes())

    def test_cooperating_external_writer_waits_and_preserves_status(self):
        entered = threading.Event()
        release = threading.Event()
        writer_started = threading.Event()
        transition = presence.status_transition

        def pause(text, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError("Status transform was not released")
            return transition(text, **kwargs)

        def append():
            writer_started.set()
            return mutation.write_text(
                self.path, transform=lambda text: text + "[ ] T External id:external\n"
            )

        with mock.patch("lifetxt.presence.status_transition", side_effect=pause):
            with ThreadPoolExecutor(max_workers=2) as pool:
                request = pool.submit(self.post, {"state": "focus"})
                try:
                    self.assertTrue(entered.wait(5))
                    writer = pool.submit(append)
                    self.assertTrue(writer_started.wait(5))
                    self.assertFalse(writer.done())
                finally:
                    release.set()
                response = request.result(timeout=10)
                writer.result(timeout=10)
        self.assertEqual(201, response.status_code, response.text)
        self.assertIn("id:external", self.path.read_text())
        self.assertEqual(
            ["focus"],
            presence.active_status_items(self.items(), person="self")[0].details[
                "state"
            ],
        )

    def test_success_waits_for_one_completed_persistent_write(self):
        write = mutation.atomic_write_bytes
        targets = []

        def persist(path, data, **kwargs):
            result = write(path, data, **kwargs)
            if os.path.abspath(path) == str(self.path):
                self.assertEqual(data, self.path.read_bytes())
                targets.append(path)
            return result

        with mock.patch("lifetxt.mutation.atomic_write_bytes", side_effect=persist):
            response = self.post({"state": "focus"})
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual(1, len(targets))
        self.assert_saved_revision(response)

    def test_write_failure_is_reported_and_original_bytes_survive(self):
        before = self.path.read_bytes()
        write = mutation.atomic_write_bytes

        def fail(path, data, **kwargs):
            if os.path.abspath(path) == str(self.path):
                raise PermissionError("sensitive filesystem diagnostic")
            return write(path, data, **kwargs)

        with mock.patch("lifetxt.mutation.atomic_write_bytes", side_effect=fail):
            response = self.post({"state": "focus"})
        self.assertEqual(500, response.status_code, response.text)
        self.assertEqual("IO_ERROR", response.json()["error"])
        self.assertNotIn("sensitive", response.text)
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse(Path(str(self.path) + ".lifetxt.lock").exists())

    def test_lock_timeout_is_reported_without_mutation(self):
        before = self.path.read_bytes()
        acquire = mutation.FileLock.acquire

        def timeout(lock):
            if lock.path == str(self.path):
                raise mutation.LockTimeout(lock.path, lock.lock_path, 0)
            return acquire(lock)

        with mock.patch.object(mutation.FileLock, "acquire", timeout):
            response = self.post({"state": "focus"})
        self.assertEqual(503, response.status_code, response.text)
        self.assertEqual("LOCK_TIMEOUT", response.json()["error"])
        self.assertEqual(before, self.path.read_bytes())

    def test_read_failure_inside_mutation_does_not_replace_file_with_empty_text(self):
        before = self.path.read_bytes()
        read = mutation.read_text_snapshot

        def unreadable(path, **kwargs):
            if (
                os.path.abspath(path) == str(self.path)
                and Path(str(self.path) + ".lifetxt.lock").exists()
            ):
                raise PermissionError("private read failure")
            return read(path, **kwargs)

        with mock.patch("lifetxt.mutation.read_text_snapshot", side_effect=unreadable):
            response = self.post({"state": "focus"})
        self.assertEqual(500, response.status_code, response.text)
        self.assertEqual("IO_ERROR", response.json()["error"])
        self.assertNotIn("private read failure", response.text)
        self.assertEqual(before, self.path.read_bytes())

    def test_edit_after_request_snapshot_is_rechecked_under_lock(self):
        external = self.path.read_bytes() + b"[ ] T External id:external\n"
        acquire = mutation.FileLock.acquire

        def edit_after_lock(lock):
            result = acquire(lock)
            if lock.path == str(self.path):
                self.path.write_bytes(external)
            return result

        with mock.patch.object(mutation.FileLock, "acquire", edit_after_lock):
            with mock.patch(
                "lifetxt.presence.status_transition", wraps=presence.status_transition
            ) as transform:
                response = self.post({"state": "focus"})
        self.assertEqual(409, response.status_code, response.text)
        transform.assert_not_called()
        self.assertEqual(external, self.path.read_bytes())

    def test_post_write_external_edit_never_returns_success_or_retries(self):
        write = mutation.atomic_write_bytes
        external = (TASK + STATUS + OTHER + "[ ] T External id:external\n").encode()
        writes = []

        def overwritten(path, data, **kwargs):
            result = write(path, data, **kwargs)
            if os.path.abspath(path) == str(self.path):
                writes.append(path)
                self.path.write_bytes(external)
            return result

        with mock.patch("lifetxt.mutation.atomic_write_bytes", side_effect=overwritten):
            response = self.post({"state": "focus"})
        self.assertEqual(409, response.status_code, response.text)
        self.assertEqual("CONFLICT", response.json()["error"])
        self.assertEqual(1, len(writes))
        self.assertEqual(external, self.path.read_bytes())

    def test_custom_id_key_and_ignored_falsy_details_remain_compatible(self):
        self.path.write_text((TASK + STATUS + OTHER).replace(" id:", " uid:"))
        self.config["ids"] = {"key": "uid"}
        client = self.make_client()
        response = self.post(
            {
                "state": "focus",
                "note": "",
                "project": False,
                "service": 0,
                "visibility": None,
                "unused": "ignored",
            },
            client=client,
        )
        self.assertEqual(201, response.status_code, response.text)
        items, diagnostics = parse_text(
            mutation.read_text_snapshot(self.path).text, id_key="uid"
        )
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertIn("uid", items[-1].details)
        self.assertEqual({"from", "state", "person", "uid"}, set(items[-1].details))

    def test_invalid_payload_parse_and_future_status_fail_without_changes(self):
        for payload in ({}, [], "busy"):
            with self.subTest(payload=payload):
                before = self.path.read_bytes()
                response = self.post(payload)
                self.assertEqual(400, response.status_code, response.text)
                self.assertEqual(before, self.path.read_bytes())
        for text in ("invalid life.txt\n", STATUS.replace("2026-01-01", "9999-01-01")):
            with self.subTest(text=text):
                self.path.write_text(text)
                before = self.path.read_bytes()
                response = self.post({"state": "focus"})
                self.assertEqual(400, response.status_code, response.text)
                self.assertEqual(before, self.path.read_bytes())

    def test_auth_and_readonly_guards_are_preserved(self):
        self.config["api"] = {"token": "test-status-token"}
        protected = self.make_client()
        readonly = self.make_client(read_only=True)
        before = self.path.read_bytes()
        unauthorized = self.post({"state": "focus"}, client=protected)
        self.assertEqual(401, unauthorized.status_code, unauthorized.text)
        denied = self.post(
            {"state": "focus"},
            client=readonly,
            headers={"Authorization": "Bearer test-status-token"},
        )
        self.assertEqual(403, denied.status_code, denied.text)
        self.assertEqual(before, self.path.read_bytes())
        allowed = self.post(
            {"state": "focus"},
            client=protected,
            headers={"Authorization": "Bearer test-status-token"},
        )
        self.assertEqual(201, allowed.status_code, allowed.text)

    def test_ambiguous_write_target_is_still_rejected_at_startup(self):
        second = self.path.parent / "second.txt"
        second.write_text("[ ] T Second id:second\n")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "explicit write target"):
            webapp.create_app([str(self.path), str(second)], config=self.config)
        self.assertEqual(before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
