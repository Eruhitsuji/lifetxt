import json
import unittest
from pathlib import Path

from lifetxt.parser import parse_text


ROOT = Path(__file__).resolve().parents[1]


class PromptProfileTests(unittest.TestCase):
    def test_profile_is_provider_independent_and_has_required_modes(self):
        profile = (ROOT / "prompts" / "lifetxt-assistant.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "Convert",
            "Explain",
            "Review",
            "`do:` means",
            "`due:` means",
            "Do not add `id:` by default",
            "Do not invent `project:`",
            "actual conversation date",
        ):
            self.assertIn(phrase, profile)

    def test_conformance_examples_are_valid_and_do_not_require_an_llm(self):
        examples = json.loads(
            (ROOT / "examples" / "lifetxt_ai_prompt_conformance.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(4, len(examples))
        for example in examples:
            items, diagnostics = parse_text(example["valid_lifetxt"] + "\n")
            self.assertEqual([], diagnostics, example["id"])
            self.assertEqual(1, len(items), example["id"])

        standalone = examples[-1]["valid_lifetxt"]
        self.assertNotIn(" id:", standalone)
        self.assertNotIn(" project:", standalone)
        self.assertNotIn(" tag:", standalone)
        self.assertNotIn(" priority:", standalone)
