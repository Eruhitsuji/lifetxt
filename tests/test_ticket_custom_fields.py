import contextlib
import io
import json
import os
import tempfile
import unittest
from collections import OrderedDict

from lifetxt import entrypoint
from lifetxt.model import Item
from lifetxt.mutation import MutationConflict
from lifetxt.safety_foundation import capability_document, schema_bundle
from lifetxt.ticket_custom_fields import (
    apply_custom_defaults,
    custom_field_definitions,
    custom_field_registry_report,
    custom_field_values,
    parse_custom_field_assignments,
    ticket_custom_field_contract,
    validate_ticket_custom_fields,
)
from lifetxt.ticket_revision_writes import ticket_file_revision
from lifetxt.tickets import apply_ticket_patch, build_ticket_line, validate_ticket


class TicketCustomFieldTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.life = os.path.join(self.temp_dir.name, "life.txt")
        self.config_path = os.path.join(self.temp_dir.name, "config.json")
        self.config = {
            "paths": [self.life],
            "write_file": self.life,
            "ticketing": {
                "id_prefix": "BUG",
                "custom_fields": OrderedDict(
                    (
                        (
                            "risk_score",
                            {
                                "type": "integer",
                                "required": True,
                                "minimum": 0,
                                "maximum": 10,
                                "default": 3,
                                "filterable": True,
                                "searchable": True,
                                "trackers": ["bug"],
                                "privacy": "internal",
                            },
                        ),
                        (
                            "customer_tier",
                            {
                                "type": "enum",
                                "enum": ["free", "standard", "enterprise"],
                                "default": "standard",
                                "filterable": True,
                                "privacy": "private",
                                "visible_roles": ["manager"],
                                "editable_roles": ["manager"],
                            },
                        ),
                        (
                            "security_label",
                            {
                                "type": "string",
                                "repeatable": True,
                                "pattern": "^[a-z0-9_-]+$",
                                "privacy": "secret",
                            },
                        ),
                        (
                            "internal_note",
                            {"type": "string", "filterable": False},
                        ),
                    )
                ),
            },
        }
        self.write_config()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_config(self):
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(self.config, handle)

    def write_life(self, text):
        with open(self.life, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def run_cli(self, args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(["--config", self.config_path] + list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def ticket(self, details=None, tracker="bug", project="web"):
        values = OrderedDict(
            (
                ("record", ["ticket"]),
                ("id", ["BUG-1"]),
                ("tracker", [tracker]),
                ("ticket_status", ["new"]),
                ("priority", ["normal"]),
                ("project", [project]),
            )
        )
        for key, field_values in (details or {}).items():
            values[key] = list(field_values)
        return Item("[ ]", "T", "Bug", values, line=1)

    def test_registry_normalizes_types_defaults_scope_and_privacy(self):
        report = custom_field_registry_report(self.config)
        self.assertTrue(report["valid"], report)
        risk = report["definitions"]["risk_score"]
        self.assertEqual("integer", risk["type"])
        self.assertEqual(["3"], risk["default_values"])
        self.assertEqual(["bug"], risk["trackers"])
        self.assertTrue(risk["filterable"])
        contract = ticket_custom_field_contract(self.config, role="viewer")
        self.assertTrue(contract["unknown_unconfigured_keys_allowed"])
        self.assertFalse(contract["remote_write_enforcement"])
        self.assertFalse(contract["definitions"]["customer_tier"]["visible_for_role"])

    def test_invalid_registry_metadata_is_reported_as_tk006(self):
        config = {
            "ticketing": {
                "custom_fields": {
                    "priority": {"type": "integer"},
                    "bad field": {"type": "mystery"},
                    "enum_without_values": {"type": "enum"},
                    "bad_pattern": {"type": "string", "pattern": "["},
                }
            }
        }
        report = custom_field_registry_report(config)
        self.assertFalse(report["valid"])
        self.assertTrue(report["diagnostics"])
        self.assertEqual({"TK006"}, {row["code"] for row in report["diagnostics"]})
        with self.assertRaises(ValueError):
            custom_field_definitions(config, strict=True)

    def test_validation_enforces_required_type_bounds_cardinality_and_applicability(self):
        missing = self.ticket()
        codes = {row["code"] for row in validate_ticket_custom_fields(missing, self.config)}
        self.assertIn("TK007", codes)

        invalid = self.ticket(
            {
                "risk_score": ["11"],
                "customer_tier": ["vip"],
                "security_label": ["ok", "BAD SPACE"],
            }
        )
        rows = validate_ticket_custom_fields(invalid, self.config)
        self.assertGreaterEqual(sum(row["code"] == "TK009" for row in rows), 3)

        repeated = self.ticket({"risk_score": ["1", "2"]})
        self.assertIn("TK008", {row["code"] for row in validate_ticket_custom_fields(repeated, self.config)})

        wrong_tracker = self.ticket({"risk_score": ["3"]}, tracker="feature")
        self.assertIn("TK010", {row["code"] for row in validate_ticket_custom_fields(wrong_tracker, self.config)})

    def test_unknown_unconfigured_keys_remain_valid(self):
        item = self.ticket({"risk_score": ["3"], "vendor_extension": ["anything"]})
        rows = validate_ticket(item, self.config)
        self.assertFalse(any(row.get("field") == "vendor_extension" for row in rows))
        self.assertFalse(any(row["severity"] == "error" for row in rows), rows)

    def test_defaults_and_explicit_repeatable_values_are_serialized(self):
        line = build_ticket_line(
            self.config,
            "Security bug",
            tracker="bug",
            project="web",
            ticket_id="BUG-1",
            extra={"security_label": ["cve", "auth"]},
        )
        self.assertIn("risk_score:3", line)
        self.assertIn("customer_tier:standard", line)
        self.assertEqual(2, line.count("security_label:"))

    def test_cli_new_fields_show_and_filter(self):
        code, stdout, stderr = self.run_cli(
            [
                "ticket", "new", "Login failure", "--tracker", "bug", "--project", "web",
                "--field", "risk_score=7", "--field", "customer_tier=enterprise",
                "--field", "security_label=auth", "--field", "security_label=cve",
            ]
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("risk_score:7", open(self.life, encoding="utf-8").read())

        code, stdout, stderr = self.run_cli(
            ["ticket", "list", "--field", "risk_score=7", "--field", "customer_tier=enterprise", "--json"]
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(1, len(json.loads(stdout)))

        code, stdout, stderr = self.run_cli(["ticket", "show", "BUG-1", "--json"])
        self.assertEqual(0, code, stderr)
        shown = json.loads(stdout)
        self.assertEqual("7", shown["custom_fields"]["risk_score"])
        self.assertEqual(["auth", "cve"], shown["custom_fields"]["security_label"])

        code, stdout, stderr = self.run_cli(["ticket", "fields", "--format", "json", "--pretty"])
        self.assertEqual(0, code, stderr)
        self.assertIn("risk_score", json.loads(stdout)["definitions"])

    def test_cli_rejects_nonfilterable_field(self):
        self.write_life(
            "[ ] T Bug record:ticket id:BUG-1 tracker:bug ticket_status:new priority:normal "
            "risk_score:3 internal_note:secret\n"
        )
        code, stdout, stderr = self.run_cli(
            ["ticket", "list", "--field", "internal_note=secret"]
        )
        self.assertEqual(1, code)
        self.assertIn("not filterable", stderr)

    def test_invalid_edit_is_rejected_before_replacement(self):
        self.write_life(
            "[ ] T Bug record:ticket id:BUG-1 tracker:bug ticket_status:new priority:normal "
            "risk_score:3 customer_tier:standard\n"
        )
        before = open(self.life, "rb").read()
        revision = ticket_file_revision(self.life)
        code, stdout, stderr = self.run_cli(
            ["ticket", "edit", "BUG-1", "--set", "risk_score=99", "--revision", revision]
        )
        self.assertEqual(1, code)
        self.assertIn("TK009", stderr)
        self.assertEqual(before, open(self.life, "rb").read())

        code, stdout, stderr = self.run_cli(
            ["ticket", "edit", "BUG-1", "--set", "risk_score=8", "--revision", revision]
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("risk_score:8", open(self.life, encoding="utf-8").read())

    def test_direct_revision_write_accepts_config_and_preserves_conflicts(self):
        self.write_life(
            "[ ] T Bug record:ticket id:BUG-1 tracker:bug ticket_status:new priority:normal risk_score:3\n"
        )
        revision = ticket_file_revision(self.life)
        with self.assertRaises(ValueError):
            apply_ticket_patch(
                self.life,
                "BUG-1",
                {"risk_score": "20"},
                expected_revision=revision,
                config=self.config,
            )
        self.assertEqual(revision, ticket_file_revision(self.life))
        apply_ticket_patch(
            self.life,
            "BUG-1",
            {"risk_score": "4"},
            expected_revision=revision,
            config=self.config,
        )
        with self.assertRaises(MutationConflict):
            apply_ticket_patch(
                self.life,
                "BUG-1",
                {"risk_score": "5"},
                expected_revision=revision,
                config=self.config,
            )

    def test_role_visibility_and_assignment_normalization(self):
        item = self.ticket(
            {"risk_score": ["3"], "customer_tier": ["enterprise"], "security_label": ["cve"]}
        )
        viewer = custom_field_values(item, self.config, role="viewer")
        self.assertNotIn("customer_tier", viewer)
        manager = custom_field_values(item, self.config, role="manager")
        self.assertEqual("enterprise", manager["customer_tier"])
        parsed = parse_custom_field_assignments(
            ["risk_score=+04", "security_label=auth", "security_label=cve"], self.config
        )
        self.assertEqual(["4"], parsed["risk_score"])
        self.assertEqual(["auth", "cve"], parsed["security_label"])

    def test_capability_and_schema_bundle_publish_contract(self):
        capability = capability_document(config=self.config)
        self.assertIn("ticket_custom_fields", capability)
        self.assertEqual("1", capability["ticket_custom_fields"]["contract_version"])
        bundle = schema_bundle()
        self.assertIn("ticket-custom-field-registry-v1.schema.json", bundle)
        self.assertIn("custom_fields", bundle["ticket-v1.schema.json"]["properties"])


if __name__ == "__main__":
    unittest.main()
