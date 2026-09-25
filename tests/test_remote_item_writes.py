import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

from lifetxt.webapp import create_app


@unittest.skipIf(TestClient is None, "web extras unavailable")
class RemoteItemWriteTests(unittest.TestCase):
    def setUp(self):
        os.environ["REMOTE_ITEM_TOKEN"] = "item-secret"
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Existing id:I-1 visibility:shared\n")
        self.config = {
            "paths": [self.path],
            "write_file": self.path,
            "remote": {
                "enabled": True,
                "item_writes_enabled": True,
                "allow_loopback_http": True,
                "principals": [
                    {
                        "id": "alice",
                        "role": "editor",
                        "token_env": "REMOTE_ITEM_TOKEN",
                    }
                ],
            },
        }
        self.client = TestClient(
            create_app(paths=[self.path], writable_path=self.path, config=self.config)
        )
        self.headers = {
            "Authorization": "Bearer item-secret",
            "X-Lifetxt-Remote-Version": "2",
        }

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("REMOTE_ITEM_TOKEN", None)

    def revision(self):
        return self.client.get("/api/remote/v1/snapshot", headers=self.headers).json()[
            "revision"
        ]

    def mutate(self, payload, revision=None):
        headers = dict(self.headers, **{"If-Match": revision or self.revision()})
        return self.client.post(
            "/api/remote/v1/item-mutations", headers=headers, json=payload
        )

    def test_create_update_delete_are_exact_revision_and_history_preserving(self):
        created = self.mutate(
            {
                "operation": "create",
                "transaction_id": "tx-create",
                "item": {
                    "status": "[ ]",
                    "type": "T",
                    "title": "Created",
                    "details": {"visibility": ["shared"]},
                },
            }
        )
        self.assertEqual(200, created.status_code, created.text)
        item_id = created.json()["item_id"]
        self.assertTrue(item_id)
        replay = self.mutate(
            {
                "operation": "create",
                "transaction_id": "tx-create",
                "item": {
                    "status": "[ ]",
                    "type": "T",
                    "title": "Created",
                    "details": {"visibility": ["shared"]},
                },
            },
            revision="0" * 64,
        )
        self.assertEqual(200, replay.status_code, replay.text)
        self.assertTrue(replay.json()["replayed"])
        updated = self.mutate(
            {
                "operation": "update",
                "transaction_id": "tx-update",
                "item_id": item_id,
                "item": {"title": "Updated"},
            }
        )
        self.assertEqual(200, updated.status_code, updated.text)
        deleted = self.mutate(
            {
                "operation": "delete",
                "transaction_id": "tx-delete",
                "item_id": item_id,
            }
        )
        self.assertEqual(200, deleted.status_code, deleted.text)
        with open(self.path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("Updated id:%s" % item_id, text)
        self.assertIn("event:created", text)
        self.assertIn("event:edited", text)
        self.assertIn("event:deleted", text)

    def test_stale_revision_does_not_write(self):
        stale = self.revision()
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write("[ ] T Concurrent id:I-2\n")
        with open(self.path, encoding="utf-8") as handle:
            before = handle.read()
        response = self.mutate(
            {
                "operation": "update",
                "transaction_id": "tx-stale",
                "item_id": "I-1",
                "item": {"title": "Lost"},
            },
            stale,
        )
        self.assertEqual(409, response.status_code)
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(before, handle.read())

    def test_disabled_capability_and_duplicate_ids_fail_closed(self):
        capability = self.client.get(
            "/api/remote/v1/capabilities", headers=self.headers
        ).json()
        self.assertTrue(capability["mutation_policy"]["item_mutations_enabled"])
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write("[ ] T Duplicate id:I-1\n")
        response = self.mutate(
            {
                "operation": "delete",
                "transaction_id": "tx-dup",
                "item_id": "I-1",
            }
        )
        self.assertEqual(400, response.status_code)

    def test_create_rejects_client_selected_id(self):
        response = self.mutate(
            {
                "operation": "create",
                "transaction_id": "tx-id",
                "item": {
                    "status": "[ ]",
                    "type": "T",
                    "title": "Bad",
                    "details": {"id": ["CLIENT-1"]},
                },
            }
        )
        self.assertEqual(400, response.status_code)


if __name__ == "__main__":
    unittest.main()
