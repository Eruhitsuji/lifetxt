import os
import unittest

from lifetxt.remote_access import (
    RemoteAccessError,
    authenticate_token,
    capability,
    negotiate_protocol,
    redact_remote_value,
    validate_remote_storage,
    require_https,
)


class RemoteAccessV20Tests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("REMOTE_DUP_A", None)
        os.environ.pop("REMOTE_DUP_B", None)

    def test_protocol_negotiation_is_bounded(self):
        self.assertEqual(1, negotiate_protocol({}))
        self.assertEqual(2, negotiate_protocol({"X-Lifetxt-Remote-Version": "2"}))
        with self.assertRaises(RemoteAccessError) as caught:
            negotiate_protocol({"X-Lifetxt-Remote-Version": "3"})
        self.assertEqual("REMOTE_VERSION_UNSUPPORTED", caught.exception.code)
        self.assertEqual(426, caught.exception.status)

    def test_untrusted_forwarded_proto_cannot_bypass_https(self):
        config = {
            "remote": {
                "enabled": True,
                "trusted_proxies": ["10.0.0.0/8"],
                "allow_loopback_http": False,
            }
        }
        with self.assertRaises(RemoteAccessError):
            require_https(
                {"X-Forwarded-Proto": "https"},
                "198.51.100.10",
                config,
                request_scheme="http",
            )
        require_https(
            {"X-Forwarded-Proto": "https"}, "10.1.2.3", config, request_scheme="http"
        )
        require_https({}, "198.51.100.10", config, request_scheme="https")

    def test_duplicate_bearer_secret_fails_closed(self):
        os.environ["REMOTE_DUP_A"] = "same-secret"
        os.environ["REMOTE_DUP_B"] = "same-secret"
        config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {"id": "a", "role": "reader", "token_env": "REMOTE_DUP_A"},
                    {"id": "b", "role": "reader", "token_env": "REMOTE_DUP_B"},
                ],
            }
        }
        with self.assertRaises(RemoteAccessError) as caught:
            authenticate_token("same-secret", config)
        self.assertEqual("AMBIGUOUS_CREDENTIAL", caught.exception.code)

    def test_v2_capability_and_recursive_redaction(self):
        value = capability({"remote": {"enabled": True, "browser_ui": True}}, 2)
        self.assertEqual("remote-capability-v2.schema.json", value["schema"])
        self.assertEqual(64, len(value["capability_revision"]))
        redacted = redact_remote_value(
            {"nested": {"body": "see attachment:/tmp/private.txt"}, "token": "secret"}
        )
        self.assertEqual("<redacted>", redacted["nested"]["body"])
        self.assertEqual("<redacted>", redacted["token"])

    def test_audit_log_cannot_alias_authoritative_source(self):
        config = {"remote": {"enabled": True, "audit_log": "/tmp/life.txt"}}
        with self.assertRaises(RemoteAccessError) as caught:
            validate_remote_storage(config, ["/tmp/life.txt"], "/tmp/life.txt")
        self.assertEqual("REMOTE_AUDIT_PATH_CONFLICT", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
