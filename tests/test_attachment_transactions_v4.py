import os
import tempfile
import unittest

from lifetxt import mutation
from lifetxt.attachment_transactions import (
    AttachmentTransactionError,
    attachment_state,
    delete_attachment,
    put_attachment,
    reference_attachment,
)


class AttachmentTransactionV4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.life = os.path.join(self.temp.name, "life.txt")
        self.target = os.path.join(self.temp.name, "attachments", "note.txt")
        self.config = {
            "attachments": {"root": self.temp.name},
            "transactions": {
                "journal_dir": os.path.join(self.temp.name, "transactions")
            },
        }
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:t1\n")

    def item_revision(self):
        return mutation.read_text_snapshot(self.life).content_hash

    def test_put_and_delete_are_two_target_transactions(self):
        put = put_attachment(
            self.life,
            "t1",
            "attachments/note.txt",
            b"hello attachment",
            item_revision=self.item_revision(),
            attachment_expected_revision=mutation.MISSING_HASH,
            config=self.config,
            require_revisions=True,
        )
        self.assertEqual("put", put["action"])
        self.assertEqual(2, len(put["targets"]))
        self.assertTrue(put["transaction_id"])
        self.assertTrue(os.path.exists(put["journal_path"]))
        with open(self.target, "rb") as handle:
            self.assertEqual(b"hello attachment", handle.read())
        with open(self.life, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("file:./attachments/note.txt#sha256=", text)

        deleted = delete_attachment(
            self.life,
            "t1",
            "attachments/note.txt",
            item_revision=put["item_revision"],
            attachment_expected_revision=put["attachment_revision"],
            config=self.config,
            require_revisions=True,
        )
        self.assertEqual("delete", deleted["action"])
        self.assertFalse(os.path.exists(self.target))
        with open(self.life, encoding="utf-8") as handle:
            self.assertNotIn("attachments/note.txt", handle.read())

    def test_reference_existing_file_checks_both_revisions(self):
        os.makedirs(os.path.dirname(self.target), exist_ok=True)
        with open(self.target, "wb") as handle:
            handle.write(b"existing")
        attachment_rev = mutation.hash_bytes(b"existing")
        result = reference_attachment(
            self.life,
            "t1",
            "attachments/note.txt",
            item_revision=self.item_revision(),
            attachment_expected_revision=attachment_rev,
            config=self.config,
            require_revisions=True,
        )
        self.assertEqual(attachment_rev, result["attachment_revision"])
        state = attachment_state(self.life, "attachments/note.txt", config=self.config)
        self.assertTrue(state["exists"])
        self.assertEqual(attachment_rev, state["revision"])

    def test_missing_required_revisions_are_rejected(self):
        with self.assertRaises(AttachmentTransactionError):
            put_attachment(
                self.life,
                "t1",
                "attachments/note.txt",
                b"payload",
                config=self.config,
                require_revisions=True,
            )

    def test_stale_item_revision_never_writes_attachment(self):
        stale = self.item_revision()
        with open(self.life, "a", encoding="utf-8") as handle:
            handle.write("[ ] N External id:n1\n")
        with self.assertRaises(mutation.MutationConflict):
            put_attachment(
                self.life,
                "t1",
                "attachments/note.txt",
                b"payload",
                item_revision=stale,
                attachment_expected_revision=mutation.MISSING_HASH,
                config=self.config,
                require_revisions=True,
            )
        self.assertFalse(os.path.exists(self.target))

    def test_path_escape_and_script_content_are_rejected(self):
        with self.assertRaises(AttachmentTransactionError):
            put_attachment(
                self.life,
                "t1",
                "../outside.txt",
                b"payload",
                item_revision=self.item_revision(),
                attachment_expected_revision=mutation.MISSING_HASH,
                config=self.config,
                require_revisions=True,
            )
        with self.assertRaises(AttachmentTransactionError):
            put_attachment(
                self.life,
                "t1",
                "attachments/run.sh",
                b"#!/bin/sh\necho unsafe\n",
                item_revision=self.item_revision(),
                attachment_expected_revision=mutation.MISSING_HASH,
                config=self.config,
                require_revisions=True,
            )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support unavailable")
    def test_symlink_target_is_rejected_by_default(self):
        os.makedirs(os.path.dirname(self.target), exist_ok=True)
        real = os.path.join(self.temp.name, "real.txt")
        with open(real, "wb") as handle:
            handle.write(b"real")
        try:
            os.symlink(real, self.target)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(AttachmentTransactionError):
            reference_attachment(
                self.life,
                "t1",
                "attachments/note.txt",
                item_revision=self.item_revision(),
                attachment_expected_revision=mutation.hash_bytes(b"real"),
                config=self.config,
                require_revisions=True,
            )


if __name__ == "__main__":
    unittest.main()
