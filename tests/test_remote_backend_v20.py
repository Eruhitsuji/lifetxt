import os
import tempfile
import unittest

from lifetxt.remote_access import RemoteAccessError, principal_registry
from lifetxt.remote_backend import read_resource, resource_catalog, snapshot


class RemoteReadBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Shared_item id:I-1 project:web visibility:shared attachment:/tmp/private.txt\n"
                "[ ] T Private_item id:I-2 project:web visibility:private owner:bob\n"
                "[ ] T Other_project id:I-3 project:other visibility:shared\n"
                "[ ] T Shared_ticket record:ticket id:TK-1 project:web visibility:shared ticket_status:new assignee:alice\n"
                "[ ] T Hidden_ticket record:ticket id:TK-2 project:web visibility:private owner:bob ticket_status:new\n"
                "[ ] T Blocker id:B-1 project:web visibility:shared\n"
                "[ ] T Blocked id:B-2 project:web visibility:shared depends_on:B-1\n"
                "[ ] S Working person:alice from:2026-07-26T09:00:00+09:00 project:web visibility:shared\n"
            )
        self.config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {
                        "id": "alice",
                        "role": "reader",
                        "projects": ["web"],
                        "visibilities": ["public", "shared"],
                    }
                ],
            }
        }
        self.principal = principal_registry(self.config)["alice"]

    def tearDown(self):
        self.temp.cleanup()

    def test_catalog_is_stable(self):
        self.assertEqual(
            ["items", "tickets", "projects", "ticket-report", "links", "status", "agenda", "search"],
            [row["name"] for row in resource_catalog()],
        )

    def test_items_share_visibility_filter_and_recursive_path_redaction(self):
        result = read_resource("items", [self.path], self.config, self.principal)
        ids = [row.get("id") for row in result["data"]["items"]]
        self.assertIn("I-1", ids)
        self.assertNotIn("I-2", ids)
        self.assertNotIn("I-3", ids)
        shared = next(row for row in result["data"]["items"] if row.get("id") == "I-1")
        self.assertEqual("<redacted>", shared["details"]["attachment"][0])
        self.assertNotIn(self.temp.name, str(result))

    def test_ticket_and_project_resources_use_same_filtered_items(self):
        tickets = read_resource("tickets", [self.path], self.config, self.principal)
        self.assertEqual(["TK-1"], [row["id"] for row in tickets["data"]["tickets"]])
        projects = read_resource("projects", [self.path], self.config, self.principal)
        self.assertEqual(["web"], [row["project"] for row in projects["data"]["projects"]])
        report = read_resource("ticket-report", [self.path], self.config, self.principal)
        self.assertEqual(1, report["data"]["summary"]["total"])

    def test_status_search_and_snapshot(self):
        status = read_resource("status", [self.path], self.config, self.principal)
        self.assertEqual("alice", status["data"]["status"][0]["person"])
        search = read_resource("search", [self.path], self.config, self.principal, {"q": "Shared"})
        self.assertGreaterEqual(search["data"]["total"], 1)
        value = snapshot([self.path], self.config, self.principal)
        self.assertEqual("remote-snapshot-v1.schema.json", value["schema"])
        self.assertEqual(1, len(value["tickets"]))

    def test_invalid_parameters_fail_loudly(self):
        with self.assertRaises(RemoteAccessError) as caught:
            read_resource("items", [self.path], self.config, self.principal, {"limit": "many"})
        self.assertEqual("REMOTE_PARAMETER_INVALID", caught.exception.code)
        with self.assertRaises(RemoteAccessError):
            read_resource("search", [self.path], self.config, self.principal, {"q": "x", "types": "proposal"})

    def test_unknown_resource_fails_closed(self):
        with self.assertRaises(RemoteAccessError) as caught:
            read_resource("secrets", [self.path], self.config, self.principal)
        self.assertEqual("REMOTE_RESOURCE_UNKNOWN", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
