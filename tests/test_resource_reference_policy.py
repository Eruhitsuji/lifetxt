import copy
import os
import unittest
from unittest.mock import patch

import lifetxt

lifetxt.bootstrap_legacy_surfaces()
from lifetxt.config import config_template
from lifetxt.config_registry import explain_key
from lifetxt.config_validation import validate_config
from lifetxt.remote_access import authenticate_token, authenticate, RemoteAccessError
from lifetxt.resource_reference_policy import DEFAULTS, policy, validate_principals
from lifetxt.resource_reference_store import BindingUnavailable
from lifetxt.safety_foundation import schema_bundle


class ResourcePolicyTests(unittest.TestCase):
    def test_default_disabled_and_explain_registry(self):
        self.assertFalse(policy({})["enabled"])
        self.assertEqual(DEFAULTS, config_template()["remote"]["resource_references"])
        for key in (
            "enabled",
            "store_path",
            "workspace_id",
            "enrolled_items",
            "limits.file_bytes",
            "metadata.digest",
        ):
            entry = explain_key("remote.resource_references." + key)
            self.assertIsNotNone(entry)
            self.assertFalse(entry["secret"])
            self.assertEqual(key.split(".")[0] != "metadata", entry["restart_required"])

    def test_strict_types_lower_only_and_downgrade(self):
        for fields in (
            {"enabled": 1},
            {"contract_version": "2"},
            {"extra": True},
            {"limits": {"file_bytes": 10485761}},
            {"limits": {"chunk_bytes": True}},
            {"metadata": {"digest": 1}},
            {"enrolled_items": [{}]},
        ):
            with self.subTest(fields=fields):
                with self.assertRaises(BindingUnavailable):
                    policy({"remote": {"resource_references": fields}})
        self.assertEqual(
            4,
            policy({"remote": {"resource_references": {"limits": {"file_bytes": 4}}}})[
                "limits"
            ]["file_bytes"],
        )

    def test_plain_legacy_auth_never_accepts_restricted_login_credential(self):
        config = {
            "remote": {
                "principals": [
                    {
                        "id": "fixture",
                        "disclosure_mode": "restricted-resource",
                        "token_env": "RESOURCE_TEST_TOKEN",
                    }
                ]
            }
        }
        with patch.dict(os.environ, {"RESOURCE_TEST_TOKEN": "synthetic-bearer"}):
            with self.assertRaises(RemoteAccessError):
                authenticate_token("synthetic-bearer", config)
            row, _ = authenticate_token(
                "synthetic-bearer", config, allow_restricted=True
            )
            self.assertEqual("fixture", row["id"])
            config["remote"]["trusted_proxies"] = ["127.0.0.1/32"]
            with self.assertRaises(RemoteAccessError):
                authenticate({"X-Lifetxt-Principal": "fixture"}, "127.0.0.1", config)
            config["remote"]["principals"].append(
                {"id": "alias", "token_env": "RESOURCE_TEST_TOKEN"}
            )
            with self.assertRaises(BindingUnavailable):
                validate_principals(config)

    def test_config_diagnostic_and_generated_schema_boundary(self):
        rows = validate_config(
            {"remote": {"resource_references": {"enabled": "yes"}}},
            use_jsonschema=False,
        )
        self.assertIn("C011", [row["code"] for row in rows])
        remote = schema_bundle()["config-v1.schema.json"]["properties"]["remote"]
        rule = remote["properties"]["resource_references"]
        self.assertFalse(rule["additionalProperties"])
        self.assertEqual(
            65536, rule["properties"]["limits"]["properties"]["chunk_bytes"]["maximum"]
        )
