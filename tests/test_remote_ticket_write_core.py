import os
import tempfile
import unittest

from lifetxt import mutation
from lifetxt.remote_access import RemoteAccessError
from lifetxt.remote_ticket_write_core import as_remote_error, conflict_current_item

_KEY = "id"


class ConflictCurrentItemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Existing_ticket record:ticket id:T-1 project:web "
                "visibility:shared ticket_status:new priority:normal reporter:alice\n"
            )
        self.owner_principal = {"role": "owner"}
        self.blind_principal = {
            "role": "reader",
            "projects": ["other"],
            "visibilities": [],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_returns_ticket_when_principal_can_see_it(self):
        item = conflict_current_item([self.path], _KEY, "T-1", self.owner_principal)
        self.assertIsNotNone(item)
        self.assertEqual(["T-1"], item["details"]["id"])

    def test_returns_none_when_principal_cannot_see_it(self):
        item = conflict_current_item([self.path], _KEY, "T-1", self.blind_principal)
        self.assertIsNone(item)

    def test_returns_none_when_ticket_id_not_found(self):
        item = conflict_current_item(
            [self.path], _KEY, "NO-SUCH-ID", self.owner_principal
        )
        self.assertIsNone(item)

    def test_returns_none_when_ticket_id_missing(self):
        item = conflict_current_item([self.path], _KEY, "", self.owner_principal)
        self.assertIsNone(item)


class AsRemoteErrorConflictTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Existing_ticket record:ticket id:T-1 project:web "
                "visibility:shared ticket_status:new priority:normal reporter:alice\n"
            )
        self.principal = {"role": "owner"}
        self.payload = {
            "operation": "edit",
            "ticket_id": "T-1",
            "set": {"priority": "high"},
            "unset": ["milestone"],
            "transaction_id": "tx-1",
            "dry_run": True,
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_mutation_conflict_produces_schema_shaped_detail(self):
        exc = mutation.MutationConflict(
            self.path, "expected-hash", "actual-hash", operation="edit"
        )
        result = as_remote_error(
            exc,
            payload=self.payload,
            principal=self.principal,
            paths=[self.path],
            key=_KEY,
            ticket_id_value="T-1",
        )
        self.assertIsInstance(result, RemoteAccessError)
        self.assertEqual("REVISION_CONFLICT", result.code)
        self.assertEqual(
            {
                "error",
                "expected_revision",
                "current_revision",
                "attempted_change",
                "current_item",
            },
            set(result.detail),
        )
        self.assertEqual("CONFLICT", result.detail["error"])
        self.assertEqual("expected-hash", result.detail["expected_revision"])
        self.assertEqual("actual-hash", result.detail["current_revision"])
        self.assertNotIn("transaction_id", result.detail["attempted_change"])
        self.assertNotIn("dry_run", result.detail["attempted_change"])
        self.assertEqual({"priority": "high"}, result.detail["attempted_change"]["set"])
        self.assertEqual(["milestone"], result.detail["attempted_change"]["unset"])
        self.assertEqual(["T-1"], result.detail["current_item"]["details"]["id"])

    def test_precondition_conflict_is_upgraded_to_schema_shaped_detail(self):
        exc = RemoteAccessError(
            "REVISION_CONFLICT",
            "The authoritative revision changed.",
            409,
            {"expected_revision": "old-aggregate", "current_revision": "new-aggregate"},
        )
        result = as_remote_error(
            exc,
            payload=self.payload,
            principal=self.principal,
            paths=[self.path],
            key=_KEY,
            ticket_id_value="T-1",
        )
        self.assertEqual("CONFLICT", result.detail["error"])
        self.assertEqual("old-aggregate", result.detail["expected_revision"])
        self.assertEqual("new-aggregate", result.detail["current_revision"])
        self.assertEqual(["T-1"], result.detail["current_item"]["details"]["id"])

    def test_non_conflict_remote_access_error_passes_through_unchanged(self):
        exc = RemoteAccessError("REMOTE_TICKET_NOT_FOUND", "not found", 404)
        result = as_remote_error(exc)
        self.assertIs(result, exc)

    def test_conflict_with_no_context_degrades_gracefully(self):
        exc = mutation.MutationConflict(
            self.path, "expected-hash", "actual-hash", operation="edit"
        )
        result = as_remote_error(exc)
        self.assertEqual({"operation": ""}, result.detail["attempted_change"])
        self.assertIsNone(result.detail["current_item"])

    def test_create_operation_conflict_with_unknown_ticket_id_yields_none_current_item(
        self,
    ):
        exc = mutation.MutationConflict(
            self.path, "expected-hash", "actual-hash", operation="create"
        )
        result = as_remote_error(
            exc,
            payload={"operation": "create", "ticket_id": "T-NEW"},
            principal=self.principal,
            paths=[self.path],
            key=_KEY,
            ticket_id_value="T-NEW",
        )
        self.assertIsNone(result.detail["current_item"])

    def test_value_error_and_generic_exception_branches_are_unchanged(self):
        value_result = as_remote_error(ValueError("bad payload"))
        self.assertEqual("REMOTE_TICKET_INVALID", value_result.code)

        generic_result = as_remote_error(RuntimeError("boom"))
        self.assertEqual("REMOTE_TICKET_WRITE_FAILED", generic_result.code)


if __name__ == "__main__":
    unittest.main()
