import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import jinja2
except ImportError:  # pragma: no cover - exercised only where Jinja2 is absent
    jinja2 = None

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only where PyYAML is absent
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate_conda_recipe.py"
FAKE_SHA256 = "d" * 64


def run_cli(sha256=FAKE_SHA256, output_dir=None):
    args = [
        sys.executable,
        str(SCRIPT),
        "--version",
        "1.0.0",
        "--sha256",
        sha256,
    ]
    if output_dir is not None:
        args += ["--output-dir", str(output_dir)]
    return subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


class GenerateCondaRecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_writes_meta_yaml(self):
        result = run_cli(output_dir=self.tmp.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        meta = Path(self.tmp.name) / "meta.yaml"
        self.assertTrue(meta.exists())

    def test_references_the_pypi_sdist_and_checksum(self):
        result = run_cli(output_dir=self.tmp.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (Path(self.tmp.name) / "meta.yaml").read_text(encoding="utf-8")
        self.assertIn("pypi.io/packages/source", text)
        self.assertIn(FAKE_SHA256, text)
        self.assertIn("lifetxt.entrypoint:main", text)

    def test_windows_only_tzdata_selector_is_present(self):
        result = run_cli(output_dir=self.tmp.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (Path(self.tmp.name) / "meta.yaml").read_text(encoding="utf-8")
        self.assertIn("tzdata  # [win]", text)

    def test_rejects_a_malformed_sha256(self):
        result = run_cli(sha256="not-a-hash", output_dir=self.tmp.name)
        self.assertEqual(result.returncode, 1)
        self.assertIn("sha256", result.stderr.lower())
        self.assertFalse((Path(self.tmp.name) / "meta.yaml").exists())

    @unittest.skipUnless(
        jinja2 is not None and yaml is not None, "Jinja2/PyYAML unavailable"
    )
    def test_recipe_renders_to_valid_yaml_with_expected_sections(self):
        result = run_cli(output_dir=self.tmp.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (Path(self.tmp.name) / "meta.yaml").read_text(encoding="utf-8")
        rendered = jinja2.Template(text).render()
        data = yaml.safe_load(rendered)
        self.assertEqual(data["package"]["name"], "lifetxt")
        self.assertEqual(data["package"]["version"], "1.0.0")
        self.assertEqual(data["build"]["noarch"], "python")
        self.assertIn("lifetxt", data["test"]["imports"])


if __name__ == "__main__":
    unittest.main()
