import os, tempfile, unittest
from lifetxt.remote_access import *


class RemoteAccessTests(unittest.TestCase):
    def setUp(self):
        os.environ["REMOTE_ALICE"] = "secret"
        self.config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {
                        "id": "alice",
                        "role": "editor",
                        "token_env": "REMOTE_ALICE",
                        "projects": ["web"],
                        "visibilities": ["public", "shared"],
                    },
                    {"id": "audit", "role": "auditor", "token_env": "REMOTE_AUDIT"},
                ],
                "trusted_proxies": ["10.0.0.0/8"],
            }
        }

    def tearDown(self):
        os.environ.pop("REMOTE_ALICE", None)

    def test_disabled(self):
        with self.assertRaises(RemoteAccessError) as cm:
            authenticate({}, "127.0.0.1", {})
        self.assertEqual(cm.exception.code, "REMOTE_DISABLED")

    def test_bearer(self):
        p, m = authenticate(
            {"Authorization": "Bearer secret"}, "127.0.0.1", self.config
        )
        self.assertEqual((p["id"], m), ("alice", "bearer"))

    def test_proxy(self):
        p, m = authenticate({"X-Lifetxt-Principal": "alice"}, "10.1.2.3", self.config)
        self.assertEqual(m, "trusted-proxy")

    def test_untrusted_proxy_cannot_assert(self):
        with self.assertRaises(RemoteAccessError):
            authenticate({"X-Lifetxt-Principal": "alice"}, "192.168.1.2", self.config)

    def test_scope_and_visibility(self):
        p = principal_registry(self.config)["alice"]
        require_scope(p, "write")
        self.assertTrue(can_access(p, "web", "shared"))
        self.assertFalse(can_access(p, "other", "shared"))
        self.assertFalse(can_access(p, "web", "private", owner="bob"))

    def test_revision(self):
        self.assertEqual(require_exact_revision({"If-Match": '"abc"'}, "abc"), "abc")
        with self.assertRaises(RemoteAccessError):
            require_exact_revision({}, "abc")

    def test_https(self):
        require_https({}, "127.0.0.1", self.config)
        with self.assertRaises(RemoteAccessError):
            require_https({}, "198.51.100.1", self.config)

    def test_filter_redacts(self):
        p = principal_registry(self.config)["alice"]
        rows = filter_records(
            [{"project": "web", "visibility": "shared", "local_path": "/tmp/x"}], p
        )
        self.assertEqual(rows[0]["local_path"], "<redacted>")

    def test_audit(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "remote": {
                    "audit_log": os.path.join(d, "audit.jsonl"),
                    "audit_max_bytes": 10000,
                }
            }
            append_audit(
                cfg, audit_event({"id": "alice", "role": "editor"}, "GET /x", 200, "r1")
            )
            self.assertIn("alice", open(cfg["remote"]["audit_log"]).read())
