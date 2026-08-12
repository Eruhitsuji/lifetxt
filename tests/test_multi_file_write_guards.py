import importlib.util
import os
import tempfile
import unittest

from lifetxt.mcp import McpContext
from lifetxt.paths import resolve_write_target
from lifetxt.webapp import create_app


class MultiFileWriteGuardTests(unittest.TestCase):
    def setUp(self):
        if importlib.util.find_spec("fastapi") is None:
            self.skipTest("FastAPI is required for Web/MCP write guard tests")
        self.root = tempfile.mkdtemp()
        self.first = os.path.join(self.root, "first.life.txt")
        self.second = os.path.join(self.root, "second.life.txt")
        self._write(self.first, "[ ] T First id:first\n")
        self._write(self.second, "[ ] T Second id:second\n")

    def tearDown(self):
        for name in (self.first, self.second):
            try:
                os.remove(name)
            except OSError:
                pass
        try:
            os.rmdir(self.root)
        except OSError:
            pass

    def _write(self, path, text):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_resolve_write_target_requires_explicit_target_for_multiple_paths(self):
        with self.assertRaisesRegex(ValueError, "explicit write target"):
            resolve_write_target([self.first, self.second])
        self.assertEqual(
            self.second,
            resolve_write_target([self.first, self.second], self.second),
        )

    def test_web_and_mcp_require_explicit_target(self):
        with self.assertRaisesRegex(ValueError, "explicit write target"):
            create_app(paths=[self.first, self.second])
        with self.assertRaisesRegex(ValueError, "explicit write target"):
            McpContext(paths=[self.first, self.second])

    def test_authoritative_writes_reject_duplicate_workspace_ids(self):
        self._write(self.second, "[ ] T Duplicate id:first\n")
        with self.assertRaisesRegex(ValueError, "workspace IDs must be unique"):
            create_app(paths=[self.first, self.second], writable_path=self.first)
        with self.assertRaisesRegex(ValueError, "workspace IDs must be unique"):
            McpContext(paths=[self.first, self.second], writable_path=self.first)


if __name__ == "__main__":
    unittest.main()
