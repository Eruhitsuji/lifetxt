"""Offline acceptance of the isolated #1356 probe, not the public website."""

import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from contrib.browser_check_poc.adapter import MAX_BYTES, check_text
from contrib.browser_check_poc import build as builder

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contrib/browser_check_poc"


class BrowserCheckPocTests(unittest.TestCase):
    def test_corpus_preserves_authoritative_parser_diagnostics(self):
        from lifetxt.parser import parse_text
        from lifetxt.diagnostic_contract import diagnostics_to_output

        for fixture in json.loads((SOURCE / "fixtures.json").read_text()):
            with self.subTest(name=fixture["name"]):
                result = check_text(fixture["text"])
                parsed = parse_text(fixture["text"])
                self.assertEqual(
                    result["diagnostics"], diagnostics_to_output(parsed[1])
                )
                self.assertEqual(result["items"], len(parsed[0]))
        future = check_text('#! format_version: 999\n[ ] T "Read"')
        self.assertFalse(future["supported_format"])
        self.assertFalse(future["valid"])

    def test_limits_count_utf8_and_bound_diagnostics(self):
        check_text("#" + "x" * (MAX_BYTES - 1))
        with self.assertRaises(ValueError):
            check_text("あ" * 22000)
        with self.assertRaises(ValueError):
            check_text(None)
        result = check_text("bad\n" * 300)
        self.assertEqual(len(result["diagnostics"]), 100)
        self.assertEqual(result["diagnostic_count"], 300)
        self.assertTrue(result["truncated"])
        self.assertFalse(result["valid"])

    def test_build_is_reproducible_and_never_bundles_ambient_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            shutil.copytree(
                SOURCE,
                source,
                ignore=shutil.ignore_patterns("node_modules", "__pycache__"),
            )
            runtime = source / "node_modules/pyodide"
            runtime.mkdir(parents=True)
            (runtime / "package.json").write_text(
                json.dumps({"version": builder.VERSION})
            )
            for name in builder.RUNTIME_FILES:
                (runtime / name).write_text("runtime fixture")
            a, b = Path(directory) / "a", Path(directory) / "b"
            with patch.object(builder, "SOURCE", source):
                builder.build(a)
                # An unrelated module already loaded by a larger suite must not leak.
                with patch.dict(
                    sys.modules,
                    {
                        "lifetxt.unrelated_probe": SimpleNamespace(
                            __file__=str(ROOT / "lifetxt/remote_client.py")
                        )
                    },
                ):
                    builder.build(b)
                with self.assertRaises(FileExistsError):
                    builder.build(a)
                with self.assertRaises(ValueError):
                    builder.build(source / "output")
            self.assertEqual(
                (a / "core.zip").read_bytes(), (b / "core.zip").read_bytes()
            )
            with zipfile.ZipFile(a / "core.zip") as z:
                self.assertNotIn("lifetxt/cli.py", z.namelist())
                self.assertIn("lifetxt/parser.py", z.namelist())
                self.assertIn("LICENSE", z.namelist())
                self.assertEqual(
                    {entry.date_time for entry in z.infolist()}, {(2026, 1, 1, 0, 0, 0)}
                )
            manifest = json.loads((a / "manifest.json").read_text())
            self.assertEqual(manifest["pyodide"], builder.VERSION)
            for notice in (SOURCE / "notices").iterdir():
                copied = a / "notices" / notice.name
                self.assertEqual(copied.read_bytes(), notice.read_bytes())
                self.assertEqual(
                    manifest["files"]["notices/" + notice.name]["sha256"],
                    hashlib.sha256(copied.read_bytes()).hexdigest(),
                )
            self.assertEqual(
                manifest["files"]["core.zip"]["bytes"], (a / "core.zip").stat().st_size
            )

    def test_notice_provenance_and_distribution_gap_are_preserved(self):
        provenance = json.loads((SOURCE / "notices/provenance.json").read_text())
        self.assertFalse(provenance["complete_distribution_audit"])
        for notice in provenance["files"]:
            stored = (SOURCE / "notices" / notice["file"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(stored).hexdigest(), notice["stored_sha256"]
            )
            self.assertTrue(
                notice["source_url"].startswith("https://raw.githubusercontent.com/")
            )

    @unittest.skipUnless(shutil.which("node"), "Node.js not available")
    def test_ui_lifecycle(self):
        result = subprocess.run(
            ["node", str(SOURCE / "test_ui.mjs")],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_website_stays_without_checker_scripts(self):
        # The PoC is isolated from production's publication artifact.
        from scripts.build_website import build
        from scripts.check_website import check

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            build(output)
            self.assertEqual(check(output), [])
            self.assertFalse(any(output.rglob("*.mjs")))
            self.assertFalse((output / "runtime").exists())
