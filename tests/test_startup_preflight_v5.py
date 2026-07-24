from __future__ import unicode_literals

import os
import tempfile
import unittest

from lifetxt.mcp import McpContext


class StartupPreflightTests(unittest.TestCase):
    def test_mcp_opt_in_creates_private_journal_root(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "life.txt")
            open(path, "w", encoding="utf-8").close()
            journal = os.path.join(root, "journals")
            context = McpContext(
                paths=[path], writable_path=path,
                config={"transactions": {"journal_dir": journal, "preflight_on_startup": True}},
            )
            self.assertTrue(context.transaction_preflight["ok"])
            self.assertTrue(os.path.isdir(journal))


if __name__ == "__main__":
    unittest.main()
