"""Tests for `lifetxt init --preset` starter presets (#637)."""

import json
import os
import tempfile
import unittest

from lifetxt.init_presets import (
    PRESET_SECTIONS,
    preset_names,
    render_life_text,
    validate_preset,
)
from lifetxt.parser import parse_text
from tests.test_lifetxt import run_cli


class InitPresetsModuleTests(unittest.TestCase):
    def test_minimal_preset_matches_the_original_unconditional_init_output(self):
        text = render_life_text("self", "UTC", "", "2026-06-01", "minimal")
        self.assertEqual(
            "#! self: self\n#! timezone: UTC\n\n[ ] T First_Task due:2026-06-01\n",
            text,
        )

    def test_every_preset_produces_a_parser_valid_file(self):
        for preset in preset_names():
            text = render_life_text("self", "UTC", "work", "2026-06-01", preset)
            items, diagnostics = parse_text(text)
            errors = [d for d in diagnostics if d.severity == "error"]
            self.assertEqual(
                [], errors, "preset %r produced parse errors: %r" % (preset, errors)
            )
            self.assertEqual(1, len(items))

    def test_non_minimal_presets_include_their_section_headings(self):
        text = render_life_text("self", "UTC", "", "2026-06-01", "student")
        for heading in PRESET_SECTIONS["student"]:
            self.assertIn(heading, text)

    def test_unknown_preset_raises_naming_available_presets(self):
        with self.assertRaises(ValueError) as ctx:
            validate_preset("nonexistent")
        message = str(ctx.exception)
        self.assertIn("nonexistent", message)
        for preset in preset_names():
            self.assertIn(preset, message)


class InitPresetCliTests(unittest.TestCase):
    def test_preset_flag_selects_a_starter_skeleton(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            config_file = os.path.join(tmpdir, ".lifetxt.json")
            out, err, rc = run_cli(
                "init",
                "--file",
                life_file,
                "--config-output",
                config_file,
                "--preset",
                "research",
                "--yes",
            )
            self.assertEqual(rc, 0)
            content = open(life_file, encoding="utf-8").read()
            self.assertIn("# Experiments", content)
            self.assertIn("# Research Notes", content)

    def test_unknown_preset_flag_is_rejected_by_argparse(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            out, err, rc = run_cli(
                "init", "--file", life_file, "--preset", "nonexistent", "--yes"
            )
            self.assertNotEqual(rc, 0)

    def test_default_omits_preset_and_matches_prior_behavior(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            config_file = os.path.join(tmpdir, ".lifetxt.json")
            out, err, rc = run_cli(
                "init",
                "--file",
                life_file,
                "--config-output",
                config_file,
                "--yes",
            )
            self.assertEqual(rc, 0)
            content = open(life_file, encoding="utf-8").read()
            self.assertNotIn("# Tasks", content)
            self.assertIn("First_Task", content)

    def test_yes_automation_contract_is_unaffected_by_the_new_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            config_file = os.path.join(tmpdir, ".lifetxt.json")
            out, err, rc = run_cli(
                "init",
                "--file",
                life_file,
                "--config-output",
                config_file,
                "--yes",
            )
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(life_file))
            self.assertTrue(os.path.exists(config_file))

    def test_generated_file_passes_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            config_file = os.path.join(tmpdir, ".lifetxt.json")
            run_cli(
                "init",
                "--file",
                life_file,
                "--config-output",
                config_file,
                "--preset",
                "work",
                "--yes",
            )
            out, err, rc = run_cli("check", life_file)
            self.assertEqual(rc, 0)
            self.assertIn("OK", out)


if __name__ == "__main__":
    unittest.main()
