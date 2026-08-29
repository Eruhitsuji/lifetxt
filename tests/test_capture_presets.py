"""Unit coverage for `lifetxt.capture_presets` (#594): named quick-capture
defaults resolved and validated independently of the CLI/mutation path."""

import unittest

from lifetxt.capture_presets import (
    capture_presets,
    normalize_capture_preset,
    resolve_capture_preset,
)


class NormalizeCapturePresetTests(unittest.TestCase):
    def test_normalizes_every_supported_field(self):
        normalized = normalize_capture_preset(
            "work-task",
            {
                "type": "T",
                "status": "[ ]",
                "project": "work",
                "tags": ["work", "focus"],
                "priority": "normal",
            },
        )
        self.assertEqual(
            {
                "type": "T",
                "status": "[ ]",
                "project": "work",
                "tags": ["work", "focus"],
                "priority": "normal",
            },
            dict(normalized),
        )

    def test_missing_fields_are_simply_absent(self):
        normalized = normalize_capture_preset("idea", {"type": "N", "tags": ["idea"]})
        self.assertEqual({"type": "N", "tags": ["idea"]}, dict(normalized))

    def test_scalar_values_are_stripped(self):
        normalized = normalize_capture_preset("x", {"project": "  work  "})
        self.assertEqual("work", normalized["project"])

    def test_duplicate_tags_are_deduplicated_preserving_order(self):
        normalized = normalize_capture_preset("x", {"tags": ["work", "focus", "work"]})
        self.assertEqual(["work", "focus"], normalized["tags"])

    def test_rejects_a_non_object_definition(self):
        with self.assertRaises(ValueError) as ctx:
            normalize_capture_preset("x", "not-an-object")
        self.assertIn("x", str(ctx.exception))

    def test_rejects_an_unsupported_field(self):
        with self.assertRaises(ValueError) as ctx:
            normalize_capture_preset("x", {"type": "T", "shell": "rm -rf /"})
        self.assertIn("shell", str(ctx.exception))
        self.assertIn("x", str(ctx.exception))

    def test_rejects_an_empty_scalar_value(self):
        with self.assertRaises(ValueError):
            normalize_capture_preset("x", {"project": "   "})

    def test_rejects_a_non_string_scalar_value(self):
        with self.assertRaises(ValueError):
            normalize_capture_preset("x", {"priority": 5})

    def test_rejects_tags_that_are_not_a_list(self):
        with self.assertRaises(ValueError):
            normalize_capture_preset("x", {"tags": "work"})

    def test_rejects_an_empty_tags_list(self):
        with self.assertRaises(ValueError):
            normalize_capture_preset("x", {"tags": []})

    def test_rejects_a_non_string_tag(self):
        with self.assertRaises(ValueError):
            normalize_capture_preset("x", {"tags": ["work", 5]})


class CapturePresetsTests(unittest.TestCase):
    def test_returns_empty_when_no_capture_section_is_configured(self):
        self.assertEqual({}, dict(capture_presets({})))
        self.assertEqual({}, dict(capture_presets({"capture": {}})))

    def test_normalizes_every_configured_preset(self):
        config = {
            "capture": {
                "presets": {
                    "work-task": {"type": "T", "project": "work"},
                    "idea": {"type": "N", "tags": ["idea"]},
                }
            }
        }
        presets = capture_presets(config)
        self.assertEqual({"work-task", "idea"}, set(presets))
        self.assertEqual("work", presets["work-task"]["project"])

    def test_raises_loudly_on_the_first_malformed_preset(self):
        config = {"capture": {"presets": {"broken": {"bogus": "x"}}}}
        with self.assertRaises(ValueError):
            capture_presets(config)

    def test_rejects_a_non_object_presets_value(self):
        with self.assertRaises(ValueError):
            capture_presets({"capture": {"presets": "nope"}})


class ResolveCapturePresetTests(unittest.TestCase):
    def test_resolves_a_configured_preset(self):
        config = {"capture": {"presets": {"work-task": {"type": "T"}}}}
        self.assertEqual("T", resolve_capture_preset(config, "work-task")["type"])

    def test_unknown_preset_lists_available_names(self):
        config = {
            "capture": {"presets": {"work-task": {"type": "T"}, "idea": {"type": "N"}}}
        }
        with self.assertRaises(ValueError) as ctx:
            resolve_capture_preset(config, "nope")
        message = str(ctx.exception)
        self.assertIn("nope", message)
        self.assertIn("work-task", message)
        self.assertIn("idea", message)

    def test_unknown_preset_with_no_presets_configured_says_so(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_capture_preset({}, "nope")
        self.assertIn("none configured", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
