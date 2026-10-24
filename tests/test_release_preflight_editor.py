"""Offline tests for immutable Windows editor release artifact validation."""

import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_editor as editor  # noqa: E402
import release_preflight_proof as proof  # noqa: E402


class EditorArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = proof.candidate(
            "Eruhitsuji/lifetxt", "1.0.4.2", "a" * 40, "b" * 40, 123, 1
        )
        self.payload = self.root / "payload"
        self.payload.mkdir()
        self.version = "0.2.0"
        names = editor.names(self.candidate)
        self.vsix = self.payload / next(n for n, r in names.items() if r == "vsix")
        self.nvim = self.payload / next(n for n, r in names.items() if r == "neovim-config")
        self.vsix_files = {
            "[Content_Types].xml": b"<Types/>",
            "extension.vsixmanifest": b'<PackageManifest><Metadata><Identity Id="lifetxt" Version="0.2.0" Publisher="lifetxt"/></Metadata></PackageManifest>',
            "extension/package.json": json.dumps({
                "name": "lifetxt", "version": self.version,
                "main": "./extension.js",
                "contributes": {
                    "languages": [{"id": "lifetxt"}],
                    "configuration": {"properties": {
                        "lifetxt.languageServer.enabled": {"default": False}
                    }},
                },
            }).encode(),
            "extension/release.json": json.dumps(editor.metadata(self.candidate, self.version)).encode(),
            "extension/extension.js": b"exports.activate = function () {};",
            "extension/language-configuration.json": b"{}",
            "extension/syntaxes/lifetxt.tmLanguage.json": b"{}",
            "extension/snippets/lifetxt.code-snippets": b"{}",
            "extension/node_modules/vscode-languageclient/package.json": b"{}",
        }
        self.nvim_files = {
            "lifetxt.lua": (
                b"vim.filetype.add({})\n"
                b"vim.lsp.config('lifetxt', {cmd={'python', '-m', 'lifetxt.lsp', '--stdio'}})\n"
                b"vim.lsp.enable('lifetxt')\n"
            ),
            "INSTALL-WINDOWS.md": b"Windows Python: init.lua. Disable LSP and uninstall.",
            "release.json": json.dumps(editor.metadata(self.candidate, self.version)).encode(),
        }
        self.pack(self.vsix, self.vsix_files)
        self.pack(self.nvim, self.nvim_files)

    @staticmethod
    def pack(path, files):
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for key, value in files.items():
                archive.writestr(key, value)

    def test_valid_bytes_have_independent_editor_version(self):
        self.assertEqual(editor.validate_payload(self.candidate, self.payload), "0.2.0")
        self.assertTrue(self.vsix.name.endswith("1.0.4.2.vsix"))
        self.assertNotEqual(self.candidate["version"], self.version)

    def test_missing_language_client_and_provenance_are_rejected(self):
        for victim in (
            "extension/node_modules/vscode-languageclient/package.json",
            "extension/release.json",
        ):
            entries = dict(self.vsix_files)
            del entries[victim]
            self.pack(self.vsix, entries)
            with self.assertRaises(ValueError):
                editor.validate_payload(self.candidate, self.payload)
        self.pack(self.vsix, self.vsix_files)
        entries = dict(self.nvim_files)
        entries["release.json"] = json.dumps(
            {**editor.metadata(self.candidate, self.version), "source_sha": "f" * 40}
        ).encode()
        self.pack(self.nvim, entries)
        with self.assertRaises(ValueError):
            editor.validate_payload(self.candidate, self.payload)

    def test_bundle_extras_paths_and_wrong_version_rejected(self):
        cases = ("../escape", "lifetxt.lua", r"bad\windows", "/absolute")
        for bad in cases:
            files = dict(self.nvim_files)
            files[bad] = b"evil"
            self.pack(self.nvim, files)
            with self.assertRaises(ValueError):
                editor.validate_payload(self.candidate, self.payload)
        self.pack(self.nvim, self.nvim_files)
        different = copy.deepcopy(self.candidate)
        different["version"] = "1.0.5"
        different = proof.sealed({k: v for k, v in different.items() if k != "digest"})
        with self.assertRaises(ValueError):
            editor.validate_payload(different, self.payload)
        self.nvim.unlink()
        with self.assertRaises(ValueError):
            editor.validate_payload(self.candidate, self.payload)

    def test_checksum_and_report_rechecked_after_artifact_write(self):
        expected = editor.names(self.candidate)
        report = proof.sealed({
            "schema_version": 1, "candidate_digest": self.candidate["digest"],
            **{k: self.candidate[k] for k in ("source_sha", "controller_sha", "run_id", "run_attempt")},
            "target": editor.TARGET, "observed_version": self.candidate["version"],
            "editor_version": self.version, "toolchain": {"vsce": editor.VSCE_VERSION},
            "checks": dict.fromkeys(editor.CHECKS, "passed"),
            "files": [
                {"path": name, "role": role, "sha256": proof.file_digest(self.payload / name),
                 "bytes": (self.payload / name).stat().st_size}
                for name, role in sorted(expected.items())
            ],
        })
        artifact = {"id": 1234, "name": "editor-payload-123-1", "sha256": "f" * 64}
        # Isolated producer must not be mistaken for the full preflight verification.
        with self.assertRaises(ValueError):
            editor.finish(self.candidate, report, self.payload, artifact)
        self.assertEqual(editor.validate_payload(self.candidate, self.payload), self.version)
        # Future full-proof tests use the strict TARGETS contract with all 14 rows.
        self.assertNotIn("editor-windows", proof.TARGETS)


if __name__ == "__main__":
    unittest.main()
