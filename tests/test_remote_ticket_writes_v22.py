import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None

from lifetxt.safety_foundation import schema_bundle
from lifetxt.webapp import create_app


@unittest.skipIf(TestClient is None, "web extras unavailable")
class RemoteTicketWritesV22Tests(unittest.TestCase):
    def setUp(self):
        os.environ["REMOTE_EDITOR_V22"] = "editor-v22"
        os.environ["REMOTE_READER_V22"] = "reader-v22"
        os.environ["REMOTE_OTHER_PROJECT_V22"] = "other-project-v22"
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Existing_ticket record:ticket id:T-1 project:web "
                "visibility:shared ticket_status:new priority:normal reporter:alice\n"
            )
        self.config = {
            "remote": {
                "enabled": True,
                "ticket_writes_enabled": True,
                "principals": [
                    {
                        "id": "alice",
                        "role": "editor",
                        "token_env": "REMOTE_EDITOR_V22",
                        "projects": ["web"],
                        "visibilities": ["public", "shared"],
                    },
                    {
                        "id": "bob",
                        "role": "reader",
                        "token_env": "REMOTE_READER_V22",
                        "projects": ["web"],
                        "visibilities": ["public", "shared"],
                    },
                    {
                        "id": "carol",
                        "role": "editor",
                        "token_env": "REMOTE_OTHER_PROJECT_V22",
                        "projects": ["other"],
                        "visibilities": ["public", "shared"],
                    },
                ],
                "allow_loopback_http": True,
            },
        }
        self.client = TestClient(
            create_app(
                paths=[self.path],
                writable_path=self.path,
                config=self.config,
                read_only=False,
            )
        )
        self.editor = {
            "Authorization": "Bearer editor-v22",
            "X-Lifetxt-Remote-Version": "2",
        }
        self.reader = {
            "Authorization": "Bearer reader-v22",
            "X-Lifetxt-Remote-Version": "2",
        }
        self.other_project_editor = {
            "Authorization": "Bearer other-project-v22",
            "X-Lifetxt-Remote-Version": "2",
        }

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("REMOTE_EDITOR_V22", None)
        os.environ.pop("REMOTE_READER_V22", None)
        os.environ.pop("REMOTE_OTHER_PROJECT_V22", None)

    def revision(self):
        response = self.client.get("/api/remote/v1/snapshot", headers=self.editor)
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["revision"]

    def mutate(self, payload, revision=None, headers=None):
        values = dict(headers or self.editor)
        values["If-Match"] = revision or self.revision()
        return self.client.post(
            "/api/remote/v1/ticket-mutations",
            headers=values,
            json=payload,
        )

    def test_create_is_history_backed_and_idempotent(self):
        revision = self.revision()
        payload = {
            "operation": "create",
            "transaction_id": "TX-REMOTE-CREATE-1",
            "ticket_id": "T-2",
            "subject": "Remote created ticket",
            "project": "web",
            "priority": "high",
        }
        created = self.mutate(payload, revision=revision)
        self.assertEqual(200, created.status_code, created.text)
        self.assertFalse(created.json()["replayed"])
        self.assertEqual("T-2", created.json()["result"]["ticket_id"])

        replayed = self.mutate(payload, revision=revision)
        self.assertEqual(200, replayed.status_code, replayed.text)
        self.assertTrue(replayed.json()["replayed"])

        with open(self.path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(1, text.count("id:T-2"))
        self.assertEqual(1, text.count("transaction:TX-REMOTE-CREATE-1"))
        self.assertIn("event:created", text)
        self.assertIn("remote_request_hash:", text)

    def test_edit_transition_comment_and_time_append_events(self):
        edit = self.mutate(
            {
                "operation": "edit",
                "transaction_id": "TX-REMOTE-EDIT-1",
                "ticket_id": "T-1",
                "set": {"priority": "urgent", "assignee": "alice"},
                "comment": "Escalated remotely",
            }
        )
        self.assertEqual(200, edit.status_code, edit.text)

        transition = self.mutate(
            {
                "operation": "transition",
                "transaction_id": "TX-REMOTE-TRANSITION-1",
                "ticket_id": "T-1",
                "target_status": "triaged",
                "comment": "Triaged remotely",
            }
        )
        self.assertEqual(200, transition.status_code, transition.text)

        comment = self.mutate(
            {
                "operation": "comment",
                "transaction_id": "TX-REMOTE-COMMENT-1",
                "ticket_id": "T-1",
                "body": "Remote investigation note",
            }
        )
        self.assertEqual(200, comment.status_code, comment.text)

        time_entry = self.mutate(
            {
                "operation": "log_time",
                "transaction_id": "TX-REMOTE-TIME-1",
                "ticket_id": "T-1",
                "duration": "30m",
                "activity": "development",
                "date": "2026-07-26",
                "comment": "Remote implementation",
            }
        )
        self.assertEqual(200, time_entry.status_code, time_entry.text)

        with open(self.path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("priority:urgent", text)
        self.assertIn("assignee:alice", text)
        self.assertIn("ticket_status:triaged", text)
        self.assertIn("event:field_change", text)
        self.assertIn("event:transition", text)
        self.assertIn("event:comment", text)
        self.assertIn("record:time_entry", text)
        self.assertIn("elapsed:30m", text)

    def test_stale_revision_and_transaction_reuse_fail_closed(self):
        old_revision = self.revision()
        first = self.mutate(
            {
                "operation": "comment",
                "transaction_id": "TX-REMOTE-REUSE-1",
                "ticket_id": "T-1",
                "body": "First request",
            },
            revision=old_revision,
        )
        self.assertEqual(200, first.status_code, first.text)

        stale = self.mutate(
            {
                "operation": "comment",
                "transaction_id": "TX-REMOTE-STALE-2",
                "ticket_id": "T-1",
                "body": "Second request",
            },
            revision=old_revision,
        )
        self.assertEqual(409, stale.status_code, stale.text)
        self.assertEqual("REVISION_CONFLICT", stale.json()["error"])
        detail = stale.json()["detail"]
        schema = schema_bundle()["conflict-v1.schema.json"]
        self.assertEqual(set(schema["properties"]), set(detail))
        self.assertTrue(set(schema["required"]).issubset(detail))
        self.assertEqual(schema["properties"]["error"]["const"], detail["error"])
        self.assertEqual(old_revision, detail["expected_revision"])
        self.assertIsInstance(detail["current_revision"], str)
        self.assertEqual("comment", detail["attempted_change"]["operation"])
        self.assertEqual("Second request", detail["attempted_change"]["body"])
        self.assertEqual(["T-1"], detail["current_item"]["details"]["id"])

        reused = self.mutate(
            {
                "operation": "comment",
                "transaction_id": "TX-REMOTE-REUSE-1",
                "ticket_id": "T-1",
                "body": "Different request",
            }
        )
        self.assertEqual(409, reused.status_code, reused.text)
        self.assertEqual("REMOTE_TRANSACTION_REUSED", reused.json()["error"])

    def test_create_conflict_has_no_current_item_for_ticket_that_does_not_exist(self):
        old_revision = self.revision()
        first = self.mutate(
            {
                "operation": "comment",
                "transaction_id": "TX-REMOTE-BUMP-1",
                "ticket_id": "T-1",
                "body": "Bump the aggregate revision",
            },
            revision=old_revision,
        )
        self.assertEqual(200, first.status_code, first.text)

        stale_create = self.mutate(
            {
                "operation": "create",
                "transaction_id": "TX-REMOTE-CREATE-CONFLICT-1",
                "ticket_id": "T-NEW",
                "subject": "Never created",
                "project": "web",
            },
            revision=old_revision,
        )
        self.assertEqual(409, stale_create.status_code, stale_create.text)
        detail = stale_create.json()["detail"]
        self.assertEqual("create", detail["attempted_change"]["operation"])
        self.assertIsNone(detail["current_item"])

    def test_conflict_current_item_is_hidden_from_a_principal_without_access(self):
        old_revision = self.revision()
        first = self.mutate(
            {
                "operation": "comment",
                "transaction_id": "TX-REMOTE-BUMP-2",
                "ticket_id": "T-1",
                "body": "Bump the aggregate revision",
            },
            revision=old_revision,
        )
        self.assertEqual(200, first.status_code, first.text)

        stale = self.mutate(
            {
                "operation": "comment",
                "transaction_id": "TX-REMOTE-OTHER-PROJECT-1",
                "ticket_id": "T-1",
                "body": "From a principal without web project access",
            },
            revision=old_revision,
            headers=self.other_project_editor,
        )
        self.assertEqual(409, stale.status_code, stale.text)
        self.assertIsNone(stale.json()["detail"]["current_item"])

    def test_permissions_configuration_and_source_scope_are_enforced(self):
        reader_revision = self.revision()
        denied = self.mutate(
            {
                "operation": "comment",
                "transaction_id": "TX-READER-1",
                "ticket_id": "T-1",
                "body": "Not allowed",
            },
            revision=reader_revision,
            headers=self.reader,
        )
        self.assertEqual(403, denied.status_code, denied.text)
        self.assertEqual("FORBIDDEN", denied.json()["error"])

        disabled_config = dict(self.config)
        disabled_config["remote"] = dict(self.config["remote"])
        disabled_config["remote"]["ticket_writes_enabled"] = False
        disabled = TestClient(
            create_app(
                paths=[self.path],
                writable_path=self.path,
                config=disabled_config,
                read_only=False,
            )
        )
        snapshot = disabled.get(
            "/api/remote/v1/snapshot",
            headers=self.editor,
        ).json()
        response = disabled.post(
            "/api/remote/v1/ticket-mutations",
            headers=dict(self.editor, **{"If-Match": snapshot["revision"]}),
            json={
                "operation": "comment",
                "transaction_id": "TX-DISABLED-1",
                "ticket_id": "T-1",
                "body": "Disabled",
            },
        )
        self.assertEqual(403, response.status_code, response.text)
        self.assertEqual("REMOTE_TICKET_WRITES_DISABLED", response.json()["error"])

    def test_remote_clock_precondition_applies_to_ticket_mutations(self):
        clock_config = dict(self.config)
        clock_config["remote"] = dict(self.config["remote"])
        clock_config["clock"] = {
            "require_remote_write_time": True,
            "skew_reject_seconds": 315360000,
        }
        client = TestClient(
            create_app(
                paths=[self.path],
                writable_path=self.path,
                config=clock_config,
                read_only=False,
            )
        )
        revision = client.get(
            "/api/remote/v1/snapshot",
            headers=self.editor,
        ).json()["revision"]
        payload = {
            "operation": "comment",
            "transaction_id": "TX-CLOCK-1",
            "ticket_id": "T-1",
            "body": "Clock protected",
        }
        missing = client.post(
            "/api/remote/v1/ticket-mutations",
            headers=dict(self.editor, **{"If-Match": revision}),
            json=payload,
        )
        self.assertEqual(428, missing.status_code, missing.text)
        self.assertEqual("CLIENT_TIME_REQUIRED", missing.json()["error"])
        accepted = client.post(
            "/api/remote/v1/ticket-mutations",
            headers=dict(
                self.editor,
                **{
                    "If-Match": revision,
                    "X-Lifetxt-Client-Time": "2026-07-26T12:00:00+09:00",
                },
            ),
            json=payload,
        )
        self.assertEqual(200, accepted.status_code, accepted.text)
        self.assertIn("X-Lifetxt-Clock-State", accepted.headers)

    def test_capability_advertises_only_scoped_ticket_mutations(self):
        response = self.client.get(
            "/api/remote/v1/capabilities",
            headers=self.editor,
        )
        self.assertEqual(200, response.status_code, response.text)
        policy = response.json()["mutation_policy"]
        self.assertTrue(policy["ticket_mutations_enabled"])
        self.assertTrue(policy["authoritative_remote_writes_enabled"])
        self.assertFalse(policy["multi_file_mutations_enabled"])
        self.assertEqual(
            ["create", "edit", "transition", "comment", "log_time"],
            policy["operations"],
        )


if __name__ == "__main__":
    unittest.main()
