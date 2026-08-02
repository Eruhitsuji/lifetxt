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
    def setUp(self):
        try:
            from fastapi.testclient import TestClient  # noqa: F401
        except Exception:
            self.skipTest("web extras unavailable, so routes cannot be exercised")

    def build(self, config=None):
        import tempfile

        from fastapi.testclient import TestClient

        from lifetxt.webapp import create_app

        directory = tempfile.mkdtemp(prefix="lifetxt-git-routes-")
        path = os.path.join(directory, "life.txt")
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Sample\n")
        return TestClient(create_app(paths=[path], writable_path=path, config=config))

    def test_every_git_route_is_registered(self):
        client = self.build()
        registered = sorted(
            route.path
            for route in client.app.routes
            if getattr(route, "path", "").startswith("/api/git")
        )
        self.assertEqual(list(GIT_PATHS), registered)

    def test_guard_refuses_when_the_api_is_not_enabled(self):
        """The 403 body is part of the contract; moving code must not reshape it."""
        client = self.build()
        response = client.get("/api/git/status")
        self.assertEqual(403, response.status_code)
        detail = response.json()
        self.assertEqual("FORBIDDEN", detail["error"])
        self.assertIn("git.enable_api", detail["message"])
        self.assertIsNone(detail["detail"])

    def test_guard_applies_to_write_routes_too(self):
        client = self.build()
        for path in ("/api/git/pull", "/api/git/push"):
            self.assertEqual(403, client.post(path).status_code, path)


if __name__ == "__main__":
    unittest.main()
