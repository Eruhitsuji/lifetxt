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
            [
                "items",
                "tickets",
                "ticket-detail",
                "projects",
                "ticket-report",
                "links",
                "status",
                "agenda",
                "search",
            ],
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
        self.assertEqual(
            ["web"], [row["project"] for row in projects["data"]["projects"]]
        )
        report = read_resource(
            "ticket-report", [self.path], self.config, self.principal
        )
        self.assertEqual(1, report["data"]["summary"]["total"])

    def test_status_search_and_snapshot(self):
        status = read_resource("status", [self.path], self.config, self.principal)
        self.assertEqual("alice", status["data"]["status"][0]["person"])
        search = read_resource(
            "search", [self.path], self.config, self.principal, {"q": "Shared"}
        )
        self.assertGreaterEqual(search["data"]["total"], 1)
        value = snapshot([self.path], self.config, self.principal)
        self.assertEqual("remote-snapshot-v1.schema.json", value["schema"])
        self.assertEqual(1, len(value["tickets"]))

    def test_invalid_parameters_fail_loudly(self):
        with self.assertRaises(RemoteAccessError) as caught:
            read_resource(
                "items", [self.path], self.config, self.principal, {"limit": "many"}
            )
        self.assertEqual("REMOTE_PARAMETER_INVALID", caught.exception.code)
        with self.assertRaises(RemoteAccessError):
            read_resource(
                "search",
                [self.path],
                self.config,
                self.principal,
                {"q": "x", "types": "proposal"},
            )

    def test_unknown_resource_fails_closed(self):
        with self.assertRaises(RemoteAccessError) as caught:
            read_resource("secrets", [self.path], self.config, self.principal)
        self.assertEqual("REMOTE_RESOURCE_UNKNOWN", caught.exception.code)


class RemoteTicketDetailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Visible_ticket record:ticket id:TK-1 project:web "
                "visibility:shared ticket_status:new priority:high "
                "depends_on:TK-2 est:2h\n"
                "[ ] T Hidden_ticket record:ticket id:TK-2 project:web "
                "visibility:private owner:bob ticket_status:new\n"
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

    def test_visible_ticket_returns_full_detail(self):
        result = read_resource(
            "ticket-detail", [self.path], self.config, self.principal, {"id": "TK-1"}
        )
        detail = result["data"]
        self.assertEqual("TK-1", detail["summary"]["id"])
        self.assertEqual("high", detail["fields"]["priority"])
        self.assertEqual("2h", detail["est"])

    def test_relation_to_invisible_ticket_does_not_expose_it(self):
        result = read_resource(
            "ticket-detail", [self.path], self.config, self.principal, {"id": "TK-1"}
        )
        detail = result["data"]
        # depends_on still names the ID (the relation field itself), but
        # nothing about TK-2's own fields/title/priority ever appears.
        self.assertIn("TK-2", detail["relations"].get("depends_on", []))
        self.assertNotIn("Hidden_ticket", str(detail))

    def test_nonexistent_and_invisible_ticket_ids_are_indistinguishable(self):
        with self.assertRaises(RemoteAccessError) as missing:
            read_resource(
                "ticket-detail",
                [self.path],
                self.config,
                self.principal,
                {"id": "TK-DOES-NOT-EXIST"},
            )
        with self.assertRaises(RemoteAccessError) as hidden:
            read_resource(
                "ticket-detail",
                [self.path],
                self.config,
                self.principal,
                {"id": "TK-2"},
            )
        self.assertEqual("REMOTE_TICKET_NOT_FOUND", missing.exception.code)
        self.assertEqual("REMOTE_TICKET_NOT_FOUND", hidden.exception.code)
        self.assertEqual(missing.exception.status, hidden.exception.status)

    def test_missing_id_parameter_is_not_found(self):
        with self.assertRaises(RemoteAccessError) as caught:
            read_resource("ticket-detail", [self.path], self.config, self.principal, {})
        self.assertEqual("REMOTE_TICKET_NOT_FOUND", caught.exception.code)


class RemoteTicketsPaginationTests(unittest.TestCase):
    TICKET_COUNT = 210

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        lines = [
            "[ ] T Ticket_%03d record:ticket id:TK-%03d project:web "
            "visibility:shared ticket_status:new\n" % (index, index)
            for index in range(self.TICKET_COUNT)
        ]
        lines.append(
            "[ ] T Other_project_ticket record:ticket id:TK-OTHER project:other "
            "visibility:shared ticket_status:new\n"
        )
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
        self.config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {
                        "id": "alice",
                        "role": "reader",
                        "projects": ["web"],
                        "visibilities": ["public", "shared"],
                    },
                    {
                        "id": "other-project-reader",
                        "role": "reader",
                        "projects": ["other"],
                        "visibilities": ["public", "shared"],
                    },
                ],
            }
        }
        self.principal = principal_registry(self.config)["alice"]
        self.other_project_principal = principal_registry(self.config)[
            "other-project-reader"
        ]

    def tearDown(self):
        self.temp.cleanup()

    def test_omitting_limit_returns_bounded_default_page(self):
        result = read_resource("tickets", [self.path], self.config, self.principal)
        self.assertEqual(200, result["data"]["count"])
        self.assertTrue(result["data"]["has_more"])
        self.assertIsNotNone(result["data"]["next_cursor"])

    def test_explicit_limit_within_range_is_unchanged(self):
        result = read_resource(
            "tickets", [self.path], self.config, self.principal, {"limit": 5}
        )
        self.assertEqual(5, result["data"]["count"])
        self.assertEqual(5, len(result["data"]["tickets"]))

    def test_limit_zero_reports_has_more_without_crashing(self):
        result = read_resource(
            "tickets", [self.path], self.config, self.principal, {"limit": 0}
        )
        self.assertEqual(0, result["data"]["count"])
        self.assertEqual([], result["data"]["tickets"])
        self.assertTrue(result["data"]["has_more"])
        self.assertIsNone(result["data"]["next_cursor"])

    def test_limit_zero_with_cursor_returns_the_same_cursor_unchanged(self):
        first = read_resource(
            "tickets", [self.path], self.config, self.principal, {"limit": 1}
        )
        cursor = first["data"]["next_cursor"]
        stalled = read_resource(
            "tickets",
            [self.path],
            self.config,
            self.principal,
            {"limit": 0, "cursor": cursor},
        )
        self.assertEqual([], stalled["data"]["tickets"])
        self.assertTrue(stalled["data"]["has_more"])
        self.assertEqual(cursor, stalled["data"]["next_cursor"])

    def test_cursor_not_matching_any_ticket_id_is_not_an_error(self):
        # "AAA" sorts before every "TK-###" id, so this behaves like no cursor.
        before_everything = read_resource(
            "tickets",
            [self.path],
            self.config,
            self.principal,
            {"cursor": "AAA", "limit": 5},
        )
        self.assertEqual(5, before_everything["data"]["count"])

        # A cursor that sorts after every id (never matched by "> cursor")
        # returns no rows without raising.
        after_everything = read_resource(
            "tickets",
            [self.path],
            self.config,
            self.principal,
            {"cursor": "zzz-not-a-real-ticket-id", "limit": 5},
        )
        self.assertEqual(0, after_everything["data"]["count"])
        self.assertFalse(after_everything["data"]["has_more"])

    def test_cursor_combines_with_project_status_assignee_filters(self):
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Assigned_ticket record:ticket id:TK-ASSIGNED project:web "
                "visibility:shared ticket_status:new assignee:alice\n"
            )
        first = read_resource(
            "tickets",
            [self.path],
            self.config,
            self.principal,
            {"assignee": "alice", "limit": 5},
        )
        self.assertEqual(
            ["TK-ASSIGNED"], [row["id"] for row in first["data"]["tickets"]]
        )
        self.assertFalse(first["data"]["has_more"])

        second = read_resource(
            "tickets",
            [self.path],
            self.config,
            self.principal,
            {"assignee": "alice", "cursor": "TK-000", "limit": 5},
        )
        self.assertEqual(
            ["TK-ASSIGNED"], [row["id"] for row in second["data"]["tickets"]]
        )

    def test_cursor_pagination_visits_every_ticket_exactly_once(self):
        seen = []
        cursor = None
        for _ in range(self.TICKET_COUNT + 5):
            params = {"limit": 30}
            if cursor:
                params["cursor"] = cursor
            page = read_resource(
                "tickets", [self.path], self.config, self.principal, params
            )["data"]
            seen.extend(row["id"] for row in page["tickets"])
            if not page["has_more"]:
                self.assertIsNone(page["next_cursor"])
                break
            cursor = page["next_cursor"]
        else:
            self.fail("pagination did not terminate")
        self.assertEqual(self.TICKET_COUNT, len(seen))
        self.assertEqual(len(set(seen)), len(seen))
        self.assertEqual(sorted(seen), seen)

    def test_page_boundary_and_one_past_boundary(self):
        exact = read_resource(
            "tickets", [self.path], self.config, self.principal, {"limit": 10}
        )["data"]
        self.assertTrue(exact["has_more"])

        one_short = read_resource(
            "tickets",
            [self.path],
            self.config,
            self.principal,
            {"limit": self.TICKET_COUNT - 1},
        )["data"]
        self.assertTrue(one_short["has_more"])
        self.assertIsNotNone(one_short["next_cursor"])

        exact_total = read_resource(
            "tickets",
            [self.path],
            self.config,
            self.principal,
            {"limit": self.TICKET_COUNT},
        )["data"]
        self.assertFalse(exact_total["has_more"])
        self.assertIsNone(exact_total["next_cursor"])

    def test_pagination_only_sees_visible_tickets(self):
        result = read_resource(
            "tickets",
            [self.path],
            self.config,
            self.other_project_principal,
            {"limit": 5},
        )
        self.assertEqual(1, result["data"]["count"])
        self.assertEqual("TK-OTHER", result["data"]["tickets"][0]["id"])
        self.assertFalse(result["data"]["has_more"])

    def test_since_revision_matching_current_behaves_like_omitted(self):
        first = read_resource("tickets", [self.path], self.config, self.principal)
        second = read_resource(
            "tickets",
            [self.path],
            self.config,
            self.principal,
            {"since_revision": first["revision"]},
        )
        self.assertEqual(first["data"], second["data"])

    def test_since_revision_stale_fails_with_distinct_error(self):
        first = read_resource("tickets", [self.path], self.config, self.principal)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Another_ticket record:ticket id:TK-NEW project:web "
                "visibility:shared ticket_status:new\n"
            )
        with self.assertRaises(RemoteAccessError) as caught:
            read_resource(
                "tickets",
                [self.path],
                self.config,
                self.principal,
                {"since_revision": first["revision"]},
            )
        self.assertEqual("REMOTE_RESOURCE_REVISION_CHANGED", caught.exception.code)

    def test_since_revision_only_applies_to_tickets_resource(self):
        first = read_resource("items", [self.path], self.config, self.principal)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write("[ ] T Another_item id:I-NEW project:web visibility:shared\n")
        second = read_resource(
            "items",
            [self.path],
            self.config,
            self.principal,
            {"since_revision": first["revision"]},
        )
        self.assertNotEqual(first["revision"], second["revision"])


if __name__ == "__main__":
    unittest.main()
