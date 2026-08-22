"""CLI text-output coverage for `lifetxt today`'s ticket_attention section (#499)."""

import json
import os
import tempfile
import unittest

from tests.test_lifetxt import run_cli


SAMPLE = (
    "#! timezone: UTC\n"
    "[ ] T Reviewed record:ticket ticket_status:review id:tk1 severity:low\n"
    "[ ] T Normal record:ticket severity:low id:tk2\n"
)


class TodayCliTicketAttentionTests(unittest.TestCase):
    def _write_source(self, temp_dir, text=SAMPLE):
        path = os.path.join(temp_dir, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_text_output_lists_tickets_needing_attention(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src)
            self.assertEqual(0, code, stderr)
            self.assertIn("Tickets needing attention (1):", stdout)
            self.assertIn("Reviewed: review", stdout)
            # "Normal" has no due:/project:/assignee: either, so it
            # legitimately appears under Captures -- only the
            # ticket_attention row format ("status title: reasons") is
            # asserted absent here.
            self.assertNotIn("Normal:", stdout)

    def test_text_output_omits_the_section_when_nothing_qualifies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(
                temp_dir, "#! timezone: UTC\n[ ] T Plain record:ticket severity:low\n"
            )
            stdout, stderr, code = run_cli("today", src)
            self.assertEqual(0, code, stderr)
            self.assertNotIn("Tickets needing attention", stdout)

    def test_json_output_includes_ticket_attention(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src, "--json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(
                ["Reviewed"], [r["title"] for r in data["ticket_attention"]]
            )
            self.assertEqual(1, data["counts"]["ticket_attention"])


if __name__ == "__main__":
    unittest.main()
