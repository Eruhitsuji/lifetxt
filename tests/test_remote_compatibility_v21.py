import unittest
from unittest import mock

from lifetxt import remote_client, remote_compatibility_v21
from lifetxt.remote_access import capability
from lifetxt.remote_compatibility_v21 import evaluate_compatibility
from lifetxt.safety_foundation import schema_bundle

_SAMPLE_CAPABILITIES = {
    "contract_version": "2",
    "protocol": {"minimum": 1, "current": 2},
    "server": {"package": "lifetxt", "version": "test"},
    "schema_bundle": {"document_count": 0, "revision": "0" * 64},
    "optional_dependencies": {},
    "compatibility": {},
    "contracts": {
        "ticket_workflow": {
            "available": True,
            "minimum": 1,
            "current": 2,
            "schemas": ["ticket-workflow-v2.schema.json"],
        },
        "attachment": {
            "available": False,
            "minimum": None,
            "current": None,
            "schemas": [],
        },
    },
    "capability_revision": "expected-revision",
}


class RemoteCompatibilityV21Tests(unittest.TestCase):
    def test_v2_capability_publishes_expanded_manifest(self):
        first = capability({"remote": {"enabled": True}}, 2)
        second = capability({"remote": {"enabled": True}}, 2)
        self.assertEqual("lifetxt", first["server"]["package"])
        self.assertEqual(len(schema_bundle()), first["schema_bundle"]["document_count"])
        self.assertEqual(64, len(first["schema_bundle"]["revision"]))
        self.assertEqual(first["capability_revision"], second["capability_revision"])
        self.assertIn("workspace_manifest", first["contracts"])
        self.assertIn("transaction_journal_policy", first["contracts"])
        self.assertIn("ticket_workflow", first["contracts"])
        self.assertIn("remote_resource", first["contracts"])
        self.assertEqual([1, 2], first["compatibility"]["supported_protocols"])
        self.assertEqual("ignore", first["compatibility"]["unknown_fields"])
        self.assertEqual(
            {"fastapi", "uvicorn"},
            set(first["optional_dependencies"]["web"]["modules"]),
        )

    def test_client_compatibility_reports_overlap_and_legacy_metadata(self):
        value = evaluate_compatibility(
            {
                "contract_version": "2",
                "protocol": {"minimum": 2, "current": 3},
            },
            2,
        )
        self.assertTrue(value["ok"])
        self.assertEqual([2], value["overlap"])
        self.assertFalse(value["manifest_present"])
        self.assertTrue(value["warnings"])

        incompatible = evaluate_compatibility(
            {
                "protocol": {"minimum": 3, "current": 4},
            },
            2,
        )
        self.assertFalse(incompatible["ok"])
        self.assertEqual([], incompatible["overlap"])
        self.assertIsNone(incompatible["selected_protocol"])

    def test_schema_inventory_is_cached_process_locally(self):
        original = remote_compatibility_v21._SCHEMA_INVENTORY
        remote_compatibility_v21._SCHEMA_INVENTORY = None
        try:
            with mock.patch(
                "lifetxt.safety_foundation.schema_bundle",
                wraps=schema_bundle,
            ) as bundled:
                remote_compatibility_v21.compatibility_manifest()
                remote_compatibility_v21.compatibility_manifest()
            self.assertEqual(1, bundled.call_count)
        finally:
            remote_compatibility_v21._SCHEMA_INVENTORY = original

    def test_remote_capability_schema_requires_manifest(self):
        schema = schema_bundle()["remote-capability-v2.schema.json"]
        for name in (
            "server",
            "schema_bundle",
            "contracts",
            "optional_dependencies",
            "compatibility",
        ):
            self.assertIn(name, schema["required"])
            self.assertIn(name, schema["properties"])

    def test_two_argument_call_is_unchanged_by_new_optional_parameters(self):
        for capabilities in (
            {"contract_version": "2", "protocol": {"minimum": 2, "current": 3}},
            {"protocol": {"minimum": 3, "current": 4}},
            _SAMPLE_CAPABILITIES,
        ):
            baseline = evaluate_compatibility(capabilities, 2)
            self.assertNotIn("header_status", baseline)
            self.assertEqual(baseline, evaluate_compatibility(dict(capabilities), 2))

    def test_required_contracts_warns_on_missing_domain(self):
        value = evaluate_compatibility(
            _SAMPLE_CAPABILITIES, 2, required_contracts=["attachment"]
        )
        self.assertTrue(any("attachment" in warning for warning in value["warnings"]))

    def test_required_contracts_silent_when_domain_satisfied(self):
        value = evaluate_compatibility(
            _SAMPLE_CAPABILITIES, 2, required_contracts=["ticket_workflow"]
        )
        self.assertEqual([], value["warnings"])

    def test_required_contracts_rejects_unknown_domain(self):
        with self.assertRaises(ValueError):
            evaluate_compatibility(
                _SAMPLE_CAPABILITIES, 2, required_contracts=["not_a_real_domain"]
            )

    def test_required_contracts_version_mapping_warns_on_shortfall(self):
        value = evaluate_compatibility(
            _SAMPLE_CAPABILITIES, 2, required_contracts={"ticket_workflow": 9}
        )
        self.assertTrue(
            any(
                "ticket_workflow" in warning and "9" in warning
                for warning in value["warnings"]
            )
        )

    def test_required_contracts_version_mapping_silent_when_met(self):
        value = evaluate_compatibility(
            _SAMPLE_CAPABILITIES, 2, required_contracts={"ticket_workflow": 2}
        )
        self.assertEqual([], value["warnings"])

    def test_header_status_omitted_when_parameter_not_supplied(self):
        value = evaluate_compatibility(_SAMPLE_CAPABILITIES, 2)
        self.assertNotIn("header_status", value)

    def test_header_status_missing_when_header_is_none(self):
        value = evaluate_compatibility(
            _SAMPLE_CAPABILITIES, 2, capability_revision_header=None
        )
        self.assertEqual("missing", value["header_status"])
        self.assertTrue(value["warnings"])

    def test_header_status_mismatch_when_header_disagrees_with_body(self):
        value = evaluate_compatibility(
            _SAMPLE_CAPABILITIES,
            2,
            capability_revision_header="a-different-revision",
        )
        self.assertEqual("mismatch", value["header_status"])
        self.assertTrue(value["warnings"])

    def test_header_status_consistent_when_header_matches_body(self):
        value = evaluate_compatibility(
            _SAMPLE_CAPABILITIES,
            2,
            capability_revision_header="expected-revision",
        )
        self.assertEqual("present-and-consistent", value["header_status"])
        self.assertEqual([], value["warnings"])


class RemoteClientCompatibilityWrapperTests(unittest.TestCase):
    def setUp(self):
        self._original_test_connection = remote_client.test_connection
        self._had_marker = getattr(
            remote_client, "_lifetxt_remote_compatibility_v21", False
        )

    def tearDown(self):
        remote_client.test_connection = self._original_test_connection
        if self._had_marker:
            remote_client._lifetxt_remote_compatibility_v21 = True
        else:
            if hasattr(remote_client, "_lifetxt_remote_compatibility_v21"):
                delattr(remote_client, "_lifetxt_remote_compatibility_v21")

    def _install_stub(self, capability_revision):
        remote_client._lifetxt_remote_compatibility_v21 = False

        def stub_test_connection(profile):
            return {
                "ok": True,
                "requested_protocol": 2,
                "negotiated_protocol": 2,
                "capability_revision": capability_revision,
                "capabilities": _SAMPLE_CAPABILITIES,
                "session": {},
            }

        remote_client.test_connection = stub_test_connection
        remote_compatibility_v21.install_remote_client_compatibility_v21()

    def test_wrapper_threads_mismatched_header_through_to_report(self):
        self._install_stub("a-different-revision")
        result = remote_client.test_connection({"url": "https://example.invalid"})
        self.assertEqual("mismatch", result["compatibility"]["header_status"])

    def test_wrapper_threads_consistent_header_through_to_report(self):
        self._install_stub("expected-revision")
        result = remote_client.test_connection({"url": "https://example.invalid"})
        self.assertEqual(
            "present-and-consistent", result["compatibility"]["header_status"]
        )


class RemoteClientTestConnectionHeaderCasingTests(unittest.TestCase):
    """remote_client.test_connection() must read the capability-revision header
    under the casing request() actually returns from a real server (lowercase,
    per http.client/urllib), not only the mixed-case header-name constant.
    Regression test for the bug found by running against a live server: every
    prior test stubbed capability_revision directly and never exercised this
    lookup against realistic header casing, so the exact-case-only lookup
    silently always missed and header_status could never report anything but
    "missing".
    """

    @mock.patch("lifetxt.remote_client.request")
    def test_lowercase_wire_header_is_still_read(self, req):
        req.side_effect = [
            (
                dict(_SAMPLE_CAPABILITIES),
                {"x-lifetxt-remote-capability-revision": "expected-revision"},
            ),
            ({"principal": {"id": "alice"}}, {}),
        ]
        result = remote_client.test_connection({"url": "https://example.invalid"})
        self.assertEqual("expected-revision", result["capability_revision"])

    @mock.patch("lifetxt.remote_client.request")
    def test_exact_case_wire_header_is_still_read(self, req):
        req.side_effect = [
            (
                dict(_SAMPLE_CAPABILITIES),
                {"X-Lifetxt-Remote-Capability-Revision": "expected-revision"},
            ),
            ({"principal": {"id": "alice"}}, {}),
        ]
        result = remote_client.test_connection({"url": "https://example.invalid"})
        self.assertEqual("expected-revision", result["capability_revision"])

    @mock.patch("lifetxt.remote_client.request")
    def test_missing_header_is_none_not_an_error(self, req):
        req.side_effect = [
            (dict(_SAMPLE_CAPABILITIES), {}),
            ({"principal": {"id": "alice"}}, {}),
        ]
        result = remote_client.test_connection({"url": "https://example.invalid"})
        self.assertIsNone(result["capability_revision"])


if __name__ == "__main__":
    unittest.main()
