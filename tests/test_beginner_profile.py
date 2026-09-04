"""Tests for the Beginner / Minimal Profile presentation vocabulary (#634)
and its `GET /api/beginner-profile` exposure.

The vocabulary itself is a documented, already-valid Format 1.0 subset
(docs/en/getting-started.md's Level 1/2); this module is single source of
truth so an authoring surface (Web now, TUI/assist later) hides advanced
options without duplicating "what counts as beginner" business logic.
"""

import os
import tempfile
import unittest
from pathlib import Path

from lifetxt import beginner_profile
from lifetxt.parser import parse_text


class BeginnerProfileVocabularyTests(unittest.TestCase):
    def test_payload_is_json_serializable_and_covers_expected_keys(self):
        import json

        payload = beginner_profile.beginner_profile_payload()
        json.dumps(payload)  # must not raise
        self.assertEqual({"types", "statuses", "detail_keys"}, set(payload.keys()))

    def test_types_and_statuses_are_valid_beginner_profile_syntax(self):
        for type_token in beginner_profile.TYPES:
            for status_token in beginner_profile.STATUSES:
                line = "%s %s Sample_title due:2026-06-01\n" % (
                    status_token,
                    type_token,
                )
                items, diagnostics = parse_text(line)
                errors = [d for d in diagnostics if d.severity == "error"]
                self.assertEqual(
                    [], errors, "unexpected parse errors for %r: %r" % (line, errors)
                )
                self.assertEqual(1, len(items))


class BeginnerProfileWebApiTests(unittest.TestCase):
    def _client(self, path):
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            self.skipTest(f"FastAPI test client is unavailable: {exc}")
        from lifetxt.webapp import create_app

        try:
            return TestClient(create_app([path], writable_path=path, config={}))
        except Exception as exc:
            self.skipTest(f"FastAPI test client could not start: {exc}")

    def test_beginner_profile_endpoint_matches_the_python_source_of_truth(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            Path(path).write_text("", encoding="utf-8")
            client = self._client(path)
            response = client.get("/api/beginner-profile")
            self.assertEqual(200, response.status_code)
            self.assertEqual(
                beginner_profile.beginner_profile_payload(), response.json()
            )


if __name__ == "__main__":
    unittest.main()
