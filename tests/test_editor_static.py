"""Editor fixtures remain aligned with the authoritative Format model."""

import json
from pathlib import Path
import re
import unittest

from lifetxt.model import VALID_TYPES, VALID_STATUSES
from lifetxt.parser import parse_text

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "editors/vscode/lifetxt"


class StaticEditorTests(unittest.TestCase):
    def test_every_record_snippet_is_accepted_after_explicit_date_entry(self):
        snippets = json.loads((EDITOR / "snippets/lifetxt.code-snippets").read_text())
        found = set()
        for snippet in snippets.values():
            body = snippet["body"]
            text = "\n".join(body) if isinstance(body, list) else body
            self.assertNotRegex(text, r"20\d\d-\d\d-\d\d")
            text = re.sub(r"\$\{\d+\|([^|]+)\|\}", lambda m: m[1].split(",")[0], text)
            text = re.sub(r"\$\{\d+:([^}]+)\}", r"\1", text).replace(
                "YYYY-MM-DD", "2026-10-17"
            )
            if text.lstrip().startswith("["):
                items, diagnostics = parse_text(text)
                self.assertFalse(
                    [d.to_dict() for d in diagnostics if d.severity == "error"], text
                )
                found.update(i.kind for i in items)
        self.assertEqual(set(VALID_TYPES), found)

    def test_associations_do_not_capture_generic_txt(self):
        manifest = json.loads((EDITOR / "package.json").read_text())
        language = manifest["contributes"]["languages"][0]
        self.assertNotIn(".txt", language["extensions"])
        self.assertNotIn("*.txt", language["filenamePatterns"])

    def test_grammar_corpus_covers_core_types_and_statuses(self):
        fixtures = json.loads((ROOT / "tests/fixtures/editor/grammar.json").read_text())
        for value in (*VALID_TYPES, *VALID_STATUSES):
            self.assertTrue(
                any(value == needle for f in fixtures for needle, _ in f["expect"])
            )
