import os
import subprocess
import tempfile
import unittest

from lifetxt.remote_access import RemoteAccessError, principal_registry
from lifetxt.remote_historical import read_historical_resource


class GitRepoCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = self.temp_dir.name
        self.life = os.path.join(self.repo, "life.txt")
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Test User")
        self._git("config", "user.email", "test@example.invalid")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args):
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            self.fail("git %s failed: %s" % (" ".join(args), result.stderr))
        return result.stdout.strip()

    def _commit(self, content, message="snapshot"):
        with open(self.life, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        self._git("add", "life.txt")
        self._git("commit", "-m", message)
        return self._git("rev-parse", "HEAD")


def _config(historical_enabled=True, extra_principal=None):
    principals = [
        {
            "id": "alice",
            "role": "reader",
            "scopes": ["historical"],
            "projects": ["web"],
            "visibilities": ["public", "shared"],
        }
    ]
    if extra_principal:
        principals.append(extra_principal)
    return {
        "remote": {
            "enabled": True,
            "historical_reads_enabled": bool(historical_enabled),
            "principals": principals,
        }
    }


class RemoteHistoricalReadTests(GitRepoCase):
    def test_authorized_bounded_read_returns_historical_items(self):
        revision = self._commit("[ ] T Old_item id:I-1 project:web visibility:shared\n")
        self._commit(
            "[x] T Old_item id:I-1 project:web visibility:shared\n"
            "[ ] T New_item id:I-2 project:web visibility:shared\n"
        )
        config = _config()
        principal = principal_registry(config)["alice"]
        result = read_historical_resource(
            [self.life], config, principal, {"revision": revision}
        )
        self.assertEqual("git_exact_revision", result["historical"]["mode"])
        ids = [row["details"].get("id") for row in result["items"]]
        self.assertEqual([["I-1"]], ids)
        self.assertEqual(1, result["count"])
        self.assertFalse(result["truncated"])

    def test_disclosure_denied_when_historical_record_is_private(self):
        revision = self._commit(
            "[ ] T Secret id:I-1 project:web visibility:private owner:bob\n"
        )
        config = _config()
        principal = principal_registry(config)["alice"]
        result = read_historical_resource(
            [self.life], config, principal, {"revision": revision}
        )
        self.assertEqual([], result["items"])

    def test_disclosure_denied_when_currently_private_even_if_historically_shared(
        self,
    ):
        revision = self._commit(
            "[ ] T Later_private id:I-1 project:web visibility:shared\n"
        )
        self._commit(
            "[ ] T Later_private id:I-1 project:web visibility:private owner:bob\n"
        )
        config = _config()
        principal = principal_registry(config)["alice"]
        result = read_historical_resource(
            [self.life], config, principal, {"revision": revision}
        )
        self.assertEqual(
            [],
            result["items"],
            "current policy is more restrictive and must still deny (#727 Section 7)",
        )

    def test_disclosure_denied_scope_missing_never_falls_back(self):
        revision = self._commit("[ ] T Item id:I-1 project:web visibility:shared\n")
        config = _config(historical_enabled=True)
        # Remove the historical scope explicitly.
        config["remote"]["principals"][0]["scopes"] = []
        principal = principal_registry(config)["alice"]
        with self.assertRaises(RemoteAccessError) as ctx:
            read_historical_resource(
                [self.life], config, principal, {"revision": revision}
            )
        self.assertIn("scope", str(ctx.exception).lower())

    def test_workspace_configuration_disabled_by_default(self):
        revision = self._commit("[ ] T Item id:I-1 project:web visibility:shared\n")
        config = _config(historical_enabled=False)
        principal = principal_registry(config)["alice"]
        with self.assertRaises(RemoteAccessError) as ctx:
            read_historical_resource(
                [self.life], config, principal, {"revision": revision}
            )
        self.assertEqual("REMOTE_HISTORICAL_DISABLED", ctx.exception.code)

    def test_bounds_enforcement_via_limit_param(self):
        lines = "".join(
            "[ ] T Item_%d id:I-%d project:web visibility:shared\n" % (i, i)
            for i in range(5)
        )
        revision = self._commit(lines)
        config = _config()
        principal = principal_registry(config)["alice"]
        result = read_historical_resource(
            [self.life], config, principal, {"revision": revision, "limit": "2"}
        )
        self.assertEqual(2, result["count"])
        self.assertTrue(result["truncated"])

    def test_invalid_limit_rejected(self):
        revision = self._commit("[ ] T Item id:I-1 project:web visibility:shared\n")
        config = _config()
        principal = principal_registry(config)["alice"]
        with self.assertRaises(RemoteAccessError):
            read_historical_resource(
                [self.life],
                config,
                principal,
                {"revision": revision, "limit": "not-a-number"},
            )

    def test_unknown_revision_fails_closed_without_fallback(self):
        self._commit("[ ] T Item id:I-1 project:web visibility:shared\n")
        config = _config()
        principal = principal_registry(config)["alice"]
        with self.assertRaises(RemoteAccessError) as ctx:
            read_historical_resource(
                [self.life],
                config,
                principal,
                {"revision": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"},
            )
        self.assertEqual("REMOTE_HISTORICAL_UNAVAILABLE", ctx.exception.code)

    def test_result_never_contains_raw_local_paths(self):
        revision = self._commit(
            "[ ] T Item id:I-1 project:web visibility:shared attachment:/tmp/x.txt\n"
        )
        config = _config()
        principal = principal_registry(config)["alice"]
        result = read_historical_resource(
            [self.life], config, principal, {"revision": revision}
        )
        self.assertNotIn(self.temp_dir.name, str(result))

    def test_audit_log_never_contains_raw_content(self):
        revision = self._commit(
            "[ ] T Item id:I-1 project:web visibility:shared secrettoken:hunter2\n"
        )
        audit_path = os.path.join(self.repo, "audit.jsonl")
        config = _config()
        config["remote"]["audit_log"] = audit_path
        principal = principal_registry(config)["alice"]
        read_historical_resource([self.life], config, principal, {"revision": revision})
        with open(audit_path, encoding="utf-8") as handle:
            audit_text = handle.read()
        self.assertNotIn("hunter2", audit_text)
        self.assertNotIn(self.temp_dir.name, audit_text)
        self.assertIn("remote_historical_read", audit_text)
        self.assertIn('"classification":"served"', audit_text)


class GitFreeWorkspaceTests(unittest.TestCase):
    def test_git_free_workspace_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Item id:I-1\n")
            config = _config()
            principal = principal_registry(config)["alice"]
            with self.assertRaises(RemoteAccessError) as ctx:
                read_historical_resource(
                    [path], config, principal, {"revision": "HEAD"}
                )
            self.assertEqual("REMOTE_HISTORICAL_UNAVAILABLE", ctx.exception.code)


if __name__ == "__main__":
    unittest.main()
