from __future__ import unicode_literals

import datetime
import os
import tempfile
import unittest

from lifetxt.clock_skew import (
    ClockSkewError,
    clock_skew_report,
    require_acceptable_clock,
)
from lifetxt.mcp import McpContext, call_tool


class ClockSkewTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.datetime(2026, 7, 24, 12, 0, tzinfo=datetime.timezone.utc)

    def test_ok_warning_and_reject(self):
        config = {"clock": {"skew_warning_seconds": 10, "skew_reject_seconds": 60}}
        self.assertEqual(
            "ok", clock_skew_report("2026-07-24T12:00:05Z", config, self.now)["state"]
        )
        self.assertEqual(
            "warning",
            clock_skew_report("2026-07-24T12:00:30Z", config, self.now)["state"],
        )
        rejected = clock_skew_report("2026-07-24T12:02:00Z", config, self.now)
        self.assertEqual("reject", rejected["state"])
        self.assertFalse(rejected["write_allowed"])
        with self.assertRaises(ClockSkewError):
            require_acceptable_clock("2026-07-24T12:02:00Z", config, self.now)

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ClockSkewError):
            clock_skew_report("2026-07-24T12:00:00", now=self.now)

    def test_mcp_exposes_clock_status(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "life.txt")
            open(path, "w", encoding="utf-8").close()
            context = McpContext(paths=[path], writable_path=path, read_only=True)
            result = call_tool("get_clock_status", {}, context)
            self.assertTrue(result["server_authoritative"])
            self.assertEqual("not_measured", result["state"])


if __name__ == "__main__":
    unittest.main()
