"""Integration tests for `lifetxt check`'s "Did you mean?" suggestions
(#640): end-to-end coverage of invalid status/type tokens, a typo'd detail
key, and an invalid `state:` value, through the real CLI, including
`--format json` invariance and exit-code parity with the pre-#640 output.
"""

import json
import os
import tempfile
import unittest

from tests.test_lifetxt import normalize_newlines, run_cli


def _make_file(text):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.flush()
    handle.close()
    return handle.name


class CheckSuggestionIntegrationTests(unittest.TestCase):
    def test_invalid_status_gets_a_unique_suggestion(self):
        path = _make_file("[X] T Buy_milk\n")
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertEqual(rc, 1)
            self.assertIn("E003", out)
            self.assertIn("Did you mean '[x]'?", out)
        finally:
            os.unlink(path)

    def test_invalid_type_gets_a_unique_suggestion(self):
        path = _make_file("[ ] Z Buy milk\n")
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertIn("E005", out)
            self.assertNotIn("Did you mean", out)
        finally:
            os.unlink(path)

    def test_detail_key_typo_gets_a_unique_suggestion(self):
        path = _make_file('[ ] T "Write report" priorty:high\n')
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertEqual(rc, 0)
            self.assertIn("W106", out)
            self.assertIn("Did you mean 'priority'?", out)
        finally:
            os.unlink(path)

    def test_genuinely_custom_key_shows_no_suggestion(self):
        path = _make_file('[N] J "Entry" mood_score:8\n')
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertEqual(rc, 0)
            self.assertIn("W106", out)
            self.assertNotIn("Did you mean", out)
        finally:
            os.unlink(path)

    def test_state_value_typo_gets_a_unique_suggestion(self):
        path = _make_file("[/] S Status state:buzy from:2026-01-01T09:00\n")
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertIn("W207", out)
            self.assertIn("Did you mean 'busy'?", out)
        finally:
            os.unlink(path)

    def test_format_json_is_completely_unaffected_by_suggestions(self):
        path = _make_file("[X] T Buy_milk\n")
        try:
            out, err, rc = run_cli("check", path, "--format", "json")
            payload = json.loads(out)
            self.assertEqual(1, len(payload))
            self.assertEqual("E003", payload[0]["code"])
            self.assertNotIn("suggestion", json.dumps(payload).lower())
            self.assertNotIn("did you mean", json.dumps(payload).lower())
        finally:
            os.unlink(path)

    def test_exit_code_unaffected_by_presence_of_a_suggestion(self):
        # Same diagnostic set/severity as pre-#640; only presentation changed.
        path = _make_file("[X] T Buy_milk\n")
        try:
            _, _, rc_text = run_cli("check", path)
            _, _, rc_json = run_cli("check", path, "--format", "json")
            self.assertEqual(rc_text, rc_json)
            self.assertEqual(1, rc_text)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
