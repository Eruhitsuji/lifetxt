import codecs
import hashlib
import os
import tempfile
import unittest

from lifetxt import tickets
from lifetxt.ticket_revision_writes import ticket_file_revision


class TicketRevisionByteTests(unittest.TestCase):
    def test_revision_hashes_exact_bom_crlf_bytes_and_preserves_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            raw = codecs.BOM_UTF8 + (
                "#! timezone: UTC\r\n"
                "[ ] T Login record:ticket id:BUG-1 ticket_status:new priority:high\r\n"
            ).encode("utf-8")
            with open(path, "wb") as handle:
                handle.write(raw)

            revision = ticket_file_revision(path)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), revision)
            updated = tickets.apply_ticket_patch(
                path,
                "BUG-1",
                {"priority": "urgent"},
                expected_revision=revision,
                require_revision=True,
            )

            with open(path, "rb") as handle:
                changed = handle.read()
            self.assertTrue(changed.startswith(codecs.BOM_UTF8))
            self.assertIn(b"\r\n", changed)
            self.assertNotIn(b"\n", changed.replace(b"\r\n", b""))
            self.assertEqual(
                hashlib.sha256(changed).hexdigest(), updated.revision_after
            )
            self.assertEqual(updated.revision_after, ticket_file_revision(path))


if __name__ == "__main__":
    unittest.main()
