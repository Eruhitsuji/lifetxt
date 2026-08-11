from __future__ import unicode_literals

import json
import os
import sys
import tempfile
import unittest

from lifetxt import mutation
from lifetxt.delegated_mutation import (
    DelegatedMutationError,
    apply_delegated_proposal_file,
    delegated_contract_hash,
    normalize_command,
    prepare_delegated_mutation,
    read_delegated_proposal,
    reject_delegated_proposal_file,
)


class DelegatedMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.path = os.path.join(self.root, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Before id:t1\n")
        self.script = os.path.join(self.root, "edit.py")
        with open(self.script, "w", encoding="utf-8") as handle:
            handle.write(
                "import pathlib,sys\n"
                "p=pathlib.Path(sys.argv[1])\n"
                "p.write_text('[ ] T After id:t1\\n', encoding='utf-8')\n"
            )

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_persists_restart_safe_proposal_and_apply(self):
        proposal_path = os.path.join(self.root, "proposal.json")
        report = prepare_delegated_mutation(
            self.path,
            [sys.executable, self.script, "{file}"],
            proposal_path=proposal_path,
        )
        self.assertTrue(report["changed"])
        self.assertIn("Before", report["diff"])
        self.assertIn("After", report["diff"])
        self.assertFalse(os.path.exists(report.get("temporary_path") or ""))
        proposal, snapshot = read_delegated_proposal(proposal_path)
        self.assertEqual("prepared", proposal["state"])
        self.assertEqual("cli.delegated", proposal["adapter"]["id"])
        self.assertEqual("local_process", proposal["adapter"]["kind"])
        self.assertEqual("1", proposal["adapter"]["version"])
        self.assertEqual("lifetxt", proposal["provenance"]["prepared_by"])
        self.assertEqual(
            proposal["before_revision"], proposal["provenance"]["source_revision"]
        )
        self.assertTrue(proposal["provenance"]["temporary_copy"])
        self.assertFalse(proposal["authorization"]["direct_write_allowed"])
        self.assertTrue(proposal["authorization"]["apply_requires_revision"])
        self.assertEqual(proposal["contract_sha256"], delegated_contract_hash(proposal))
        applied = apply_delegated_proposal_file(
            proposal_path,
            expected_proposal_revision=snapshot.content_hash,
        )
        self.assertTrue(applied["applied"])
        with open(self.path, encoding="utf-8") as handle:
            self.assertIn("After", handle.read())
        stored, _snapshot = read_delegated_proposal(proposal_path)
        self.assertEqual("applied", stored["state"])

    @unittest.skipUnless(os.name == "nt", "Windows quoting behavior")
    def test_windows_command_string_strips_outer_quotes(self):
        argv = normalize_command(
            "'%s' '%s' '{file}'" % (sys.executable, self.script),
            os.path.join(self.root, "copy.txt"),
        )
        self.assertEqual(sys.executable, argv[0])
        self.assertFalse(argv[0].startswith("'"))
        self.assertEqual(os.path.join(self.root, "copy.txt"), argv[2])

    def test_command_list_preserves_literal_quotes(self):
        argv = normalize_command(
            ["'literal'", "{file}"],
            os.path.join(self.root, "copy.txt"),
        )
        self.assertEqual("'literal'", argv[0])
        self.assertEqual(os.path.join(self.root, "copy.txt"), argv[1])

    def test_one_winner_one_conflict(self):
        proposal_path = os.path.join(self.root, "proposal.json")
        prepare_delegated_mutation(
            self.path,
            [sys.executable, self.script, "{file}"],
            proposal_path=proposal_path,
        )
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T External id:t1\n")
        with self.assertRaises(mutation.MutationConflict):
            apply_delegated_proposal_file(proposal_path)
        with open(self.path, encoding="utf-8") as handle:
            self.assertIn("External", handle.read())

    def test_tampered_proposal_is_rejected(self):
        proposal_path = os.path.join(self.root, "proposal.json")
        prepare_delegated_mutation(
            self.path,
            [sys.executable, self.script, "{file}"],
            proposal_path=proposal_path,
        )
        with open(proposal_path, encoding="utf-8") as handle:
            payload = json.load(handle)
        payload["edited_text"] = "[ ] T Tampered id:t1\n"
        with open(proposal_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        with self.assertRaises(DelegatedMutationError):
            read_delegated_proposal(proposal_path)

    def test_tampered_metadata_is_rejected(self):
        proposal_path = os.path.join(self.root, "proposal.json")
        prepare_delegated_mutation(
            self.path,
            [sys.executable, self.script, "{file}"],
            proposal_path=proposal_path,
        )
        cases = (
            ("adapter", "id", "other.adapter"),
            ("provenance", "prepared_by", "other"),
            ("provenance", "command_sha256", "0" * 64),
            ("authorization", "direct_write_allowed", True),
            ("authorization", "apply_requires_revision", False),
        )
        for section, key, value in cases:
            with self.subTest(section=section, key=key):
                with open(proposal_path, encoding="utf-8") as handle:
                    payload = json.load(handle)
                payload[section][key] = value
                with open(proposal_path, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
                with self.assertRaises(DelegatedMutationError):
                    read_delegated_proposal(proposal_path)

    def test_custom_adapter_identity_is_recorded_and_validated(self):
        proposal_path = os.path.join(self.root, "proposal.json")
        proposal = prepare_delegated_mutation(
            self.path,
            [sys.executable, self.script, "{file}"],
            proposal_path=proposal_path,
            adapter_id="stable.editor",
            adapter_kind="editor_session",
            adapter_version="2",
        )
        self.assertEqual("stable.editor", proposal["adapter"]["id"])
        self.assertEqual("editor_session", proposal["adapter"]["kind"])
        stored, _snapshot = read_delegated_proposal(proposal_path)
        self.assertEqual(proposal["contract_sha256"], stored["contract_sha256"])

    def test_one_winner_one_conflict_with_metadata(self):
        first_path = os.path.join(self.root, "first.json")
        second_path = os.path.join(self.root, "second.json")
        prepare_delegated_mutation(
            self.path,
            [sys.executable, self.script, "{file}"],
            proposal_path=first_path,
        )
        prepare_delegated_mutation(
            self.path,
            [sys.executable, self.script, "{file}"],
            proposal_path=second_path,
        )
        self.assertTrue(apply_delegated_proposal_file(first_path)["applied"])
        with self.assertRaises(mutation.MutationConflict):
            apply_delegated_proposal_file(second_path)

    def test_reject_is_revision_checked(self):
        proposal_path = os.path.join(self.root, "proposal.json")
        prepare_delegated_mutation(
            self.path,
            [sys.executable, self.script, "{file}"],
            proposal_path=proposal_path,
        )
        _proposal, snapshot = read_delegated_proposal(proposal_path)
        report = reject_delegated_proposal_file(
            proposal_path,
            expected_proposal_revision=snapshot.content_hash,
            reason="not approved",
        )
        self.assertTrue(report["rejected"])
        stored, _ = read_delegated_proposal(proposal_path)
        self.assertEqual("rejected", stored["state"])
        with open(self.path, encoding="utf-8") as handle:
            self.assertIn("Before", handle.read())


if __name__ == "__main__":
    unittest.main()
