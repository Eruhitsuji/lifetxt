import json
import subprocess
import sys
import unittest


class CoreImportBoundaryTests(unittest.TestCase):
    def test_package_root_is_core_only(self):
        script = """
import json, sys
import lifetxt
print(json.dumps({
  'version': lifetxt.__version__,
  'modules': sorted(name for name in sys.modules if name.startswith('lifetxt.')),
}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["version"], "1.0.3")
        self.assertNotIn("lifetxt.surface_runtime", payload["modules"])
        self.assertNotIn("lifetxt.remote_client", payload["modules"])
        self.assertNotIn("lifetxt.release_translation", payload["modules"])

    def test_core_surface_exposes_authoritative_operations(self):
        from lifetxt.core import convert_text, parse_text, resolve_quick_input

        items, diagnostics = parse_text('[ ] T "Read paper"')
        self.assertEqual(len(items), 1)
        self.assertEqual(diagnostics, [])
        self.assertEqual(resolve_quick_input("Review").__class__.__name__, "QuickInput")
        self.assertIn("Read paper", convert_text("life", "json", '[ ] T "Read paper"').content)

    def test_cli_bootstraps_legacy_surface(self):
        result = subprocess.run(
            [sys.executable, "-m", "lifetxt", "check", "examples/minimal_life.txt"],
            capture_output=True, text=True, check=True
        )
        self.assertIn("OK:", result.stdout)
