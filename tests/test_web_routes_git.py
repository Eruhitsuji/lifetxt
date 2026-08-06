"""The Git route group is registered from its own module, and stays importable.

`grep -rln "api/git" tests/` returned nothing before #84: the five `/api/git/*`
routes had no coverage at all, so moving them out of `create_app` was protected
by nothing. These tests are that protection.

The constraint worth pinning is the import: `webapp.create_app` imports fastapi
inside the function behind an `ImportError` guard, which is what lets
`import lifetxt.webapp` succeed without the Web extras and keeps the no-Web CI
job green. A route module that imports fastapi at module level would undo that,
and the only thing that would notice is a CI job on a different machine.
"""

from __future__ import unicode_literals

import io
import os
import shutil
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP_SOURCE = os.path.join(ROOT, "lifetxt", "webapp.py")
ROUTES_SOURCE = os.path.join(ROOT, "lifetxt", "web_routes_git.py")
GIT_PATHS = (
    "/api/git/commit",
    "/api/git/log",
    "/api/git/pull",
    "/api/git/push",
    "/api/git/status",
)


class _BlockFastapi(object):
    """Meta-path hook that makes `import fastapi` fail, as a no-extras host does."""

    def find_module(self, name, path=None):
        if name == "fastapi" or name.startswith("fastapi."):
            return self
        return None

    def load_module(self, name):
        raise ImportError("fastapi is unavailable in this check")


class GitRouteModuleTests(unittest.TestCase):
    def test_module_imports_without_fastapi(self):
        blocker = _BlockFastapi()
        saved = {k: v for k, v in sys.modules.items() if k.startswith("fastapi")}
        for name in saved:
            del sys.modules[name]
        sys.meta_path.insert(0, blocker)
        try:
            import lifetxt.web_routes_git as module

            self.assertTrue(callable(module.register_git_routes))
        finally:
            sys.meta_path.remove(blocker)
            sys.modules.update(saved)

    def test_fastapi_is_not_imported_at_module_level(self):
        """A source check, because an already-imported fastapi hides the mistake."""
        with io.open(ROUTES_SOURCE, encoding="utf-8") as handle:
            source = handle.read()
        module_level = [
            line
            for line in source.splitlines()
            if line.startswith("import fastapi") or line.startswith("from fastapi")
        ]
        self.assertEqual([], module_level)
        self.assertIn("    from fastapi import", source)

    def test_webapp_delegates_instead_of_inlining(self):
        with io.open(WEBAPP_SOURCE, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("register_git_routes(app)", source)
        self.assertNotIn("def _git_guard(request):", source)
        self.assertNotIn('@app.get("/api/git/status")', source)


class GitRouteRegistrationTests(unittest.TestCase):
    """The guard has two refusal reasons and one success path.

    All three matter. Asserting only on the 403 status conflates the two
    refusals, which is exactly the mistake made while reviewing this change: a
    probe that enabled the API still saw 403 and it looked like broken config
    plumbing, when it was the loopback check doing its job.
    """

    def setUp(self):
        self._directories = []
        try:
            from fastapi.testclient import TestClient  # noqa: F401
        except Exception:
            self.skipTest("web extras unavailable, so routes cannot be exercised")

    def tearDown(self):
        for directory in getattr(self, "_directories", []):
            shutil.rmtree(directory, ignore_errors=True)

    def build(self, config=None, loopback=False):
        import tempfile

        from fastapi.testclient import TestClient

        from lifetxt.webapp import create_app

        directory = tempfile.mkdtemp(prefix="lifetxt-git-routes-")
        self._directories.append(directory)
        path = os.path.join(directory, "life.txt")
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Sample\n")
        app = create_app(paths=[path], writable_path=path, config=config)
        client = (
            TestClient(app, client=("127.0.0.1", 50000))
            if loopback
            else TestClient(app)
        )
        return client, directory

    def _git(self, cwd, *args, skip_on_error=True):
        import subprocess

        if shutil.which("git") is None:
            self.skipTest("git executable unavailable")
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if skip_on_error and result.returncode != 0:
            self.skipTest(
                "git fixture setup failed for %r: %s"
                % (" ".join(["git"] + list(args)), result.stderr.strip())
            )
        return result

    def enabled_repo(self, remote=False):
        """A loopback client over a disposable repository with one commit."""
        import tempfile

        client, directory = self.build({"git": {"enable_api": True}}, loopback=True)
        self._git(directory, "init", "-q")
        self._git(directory, "checkout", "-B", "lifetxt-test")
        self._git(directory, "config", "user.email", "t@example.invalid")
        self._git(directory, "config", "user.name", "T")
        self._git(directory, "add", "life.txt")
        self._git(directory, "commit", "-q", "-m", "seed")
        remote_directory = None
        if remote:
            remote_directory = tempfile.mkdtemp(prefix="lifetxt-git-remote-")
            self._directories.append(remote_directory)
            self._git(remote_directory, "init", "--bare", "-q")
            self._git(
                remote_directory,
                "symbolic-ref",
                "HEAD",
                "refs/heads/lifetxt-test",
            )
            self._git(directory, "remote", "add", "origin", remote_directory)
            url = self._git(
                directory, "remote", "get-url", "origin", skip_on_error=False
            )
            self.assertEqual(0, url.returncode)
            self.assertEqual(
                os.path.abspath(remote_directory), os.path.abspath(url.stdout.strip())
            )
            self._git(directory, "push", "-u", "origin", "HEAD")
        return client, directory, remote_directory

    def enabled_repo_client(self):
        client, _directory, _remote = self.enabled_repo()
        return client

    def test_every_git_route_is_registered(self):
        client, _ = self.build()
        registered = sorted(
            route.path
            for route in client.app.routes
            if getattr(route, "path", "").startswith("/api/git")
        )
        self.assertEqual(list(GIT_PATHS), registered)

    def test_guard_refuses_when_the_api_is_not_enabled(self):
        """The 403 body is part of the contract; moving code must not reshape it."""
        client, _ = self.build()
        response = client.get("/api/git/status")
        self.assertEqual(403, response.status_code)
        detail = response.json()
        self.assertEqual("FORBIDDEN", detail["error"])
        self.assertIn("git.enable_api", detail["message"])
        self.assertIsNone(detail["detail"])

    def test_guard_refuses_non_loopback_even_when_enabled(self):
        """The second refusal reason, distinct from the first."""
        client, _ = self.build({"git": {"enable_api": True}})
        response = client.get("/api/git/status")
        self.assertEqual(403, response.status_code)
        detail = response.json()
        self.assertIn("loopback", detail["message"])
        self.assertNotIn("git.enable_api", detail["message"])

    def test_guard_applies_to_write_routes_too(self):
        client, _ = self.build()
        for path in ("/api/git/pull", "/api/git/push"):
            self.assertEqual(403, client.post(path).status_code, path)

    def test_status_succeeds_for_an_enabled_loopback_caller(self):
        client = self.enabled_repo_client()
        response = client.get("/api/git/status")
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            ["exit_code", "ok", "stderr", "stdout"], sorted(response.json().keys())
        )
        self.assertTrue(response.json()["ok"])

    def test_log_parses_commits_and_counts_them(self):
        client = self.enabled_repo_client()
        response = client.get("/api/git/log?n=3&count=true")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(1, payload["total"])
        self.assertEqual(1, len(payload["commits"]))
        commit = payload["commits"][0]
        self.assertEqual(["date", "hash", "message"], sorted(commit.keys()))
        self.assertEqual("seed", commit["message"])
        self.assertEqual(8, len(commit["hash"]))

    def test_log_count_is_omitted_unless_requested(self):
        client = self.enabled_repo_client()
        payload = client.get("/api/git/log").json()
        self.assertIsNone(payload["total"])

    def test_commit_requires_a_message(self):
        """The 400 body is a contract too, and it is reachable without writing."""
        client = self.enabled_repo_client()
        response = client.post("/api/git/commit", json={})
        self.assertEqual(400, response.status_code)
        self.assertIn("message is required", response.json()["message"])

    def test_commit_succeeds_for_a_dirty_writable_file(self):
        client, directory, _remote = self.enabled_repo()
        with io.open(
            os.path.join(directory, "life.txt"), "a", encoding="utf-8"
        ) as handle:
            handle.write("[ ] T Committed_by_API\n")

        response = client.post("/api/git/commit", json={"message": "api commit"})

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"], payload)
        log = self._git(directory, "log", "--pretty=%s", "-1")
        self.assertEqual("api commit", log.stdout.strip())

    def test_commit_reports_git_failure_when_nothing_changed(self):
        client = self.enabled_repo_client()

        response = client.post("/api/git/commit", json={"message": "empty commit"})

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertNotEqual(0, payload["exit_code"])
        self.assertIn("nothing", (payload["stdout"] + payload["stderr"]).lower())

    def test_pull_succeeds_against_a_local_bare_remote(self):
        client, _directory, remote = self.enabled_repo(remote=True)
        self.assertIsNotNone(remote)

        response = client.post("/api/git/pull")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"], payload)

    def test_pull_reports_git_failure_without_a_remote(self):
        client = self.enabled_repo_client()

        response = client.post("/api/git/pull")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertNotEqual(0, payload["exit_code"])

    def test_push_succeeds_against_a_local_bare_remote(self):
        client, directory, remote = self.enabled_repo(remote=True)
        with io.open(
            os.path.join(directory, "life.txt"), "a", encoding="utf-8"
        ) as handle:
            handle.write("[ ] T Pushed_by_API\n")
        commit = client.post("/api/git/commit", json={"message": "api push source"})
        self.assertTrue(commit.json()["ok"], commit.json())

        response = client.post("/api/git/push")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"], payload)
        remote_count = self._git(remote, "rev-list", "--count", "HEAD")
        self.assertEqual("2", remote_count.stdout.strip())

    def test_push_reports_git_failure_without_a_remote(self):
        client = self.enabled_repo_client()

        response = client.post("/api/git/push")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertNotEqual(0, payload["exit_code"])


if __name__ == "__main__":
    unittest.main()
