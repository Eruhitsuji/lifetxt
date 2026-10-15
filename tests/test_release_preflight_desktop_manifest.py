"""Real-git generated Cargo manifest semantic boundary, without native Tauri."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_desktop as desktop  # noqa: E402
import release_preflight_proof as proof  # noqa: E402
import set_tauri_desktop_version as setter  # noqa: E402


class DesktopManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.target = "desktop-linux-x86_64"
        self.manifest = self.work / desktop.CARGO
        self.manifest.parent.mkdir(parents=True)
        self.original = (ROOT / desktop.CARGO).read_text()
        self.manifest.write_text(self.original)
        config = self.work / desktop.CONFIG
        config.write_bytes((ROOT / desktop.CONFIG).read_bytes())
        (self.manifest.parent / "Cargo.lock").write_text("# locked source fixture\n")
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("add", desktop.CARGO, desktop.CONFIG, "desktop/src-tauri/Cargo.lock")
        self.git("commit", "-qm", "source fixture")
        self.candidate = proof.candidate(
            "Eruhitsuji/lifetxt",
            "1.0.4.2",
            self.git("rev-parse", "HEAD"),
            "b" * 40,
            105,
            1,
        )
        setter.set_version(config, self.candidate["version"])
        runtime = desktop.runtime_path(self.work, self.target)
        runtime.parent.mkdir(parents=True)
        runtime.write_bytes(b"fixture Core; no execution claim")

    def git(self, *arguments):
        return subprocess.run(
            ["git", *arguments],
            cwd=self.work,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def validate(self):
        return desktop.validate_work(self.candidate, self.work, self.target)

    def rewrite(self):
        return self.original.replace(
            'tauri-build = "2.6.3"',
            'tauri-build = { version = "2.6.3", features = [] }',
        )

    def test_unmodified_and_exact_tauri_rewrite_pass_against_git_blob(self):
        self.assertEqual(self.validate()["release_version"], "1.0.4.2")
        self.manifest.write_text(self.rewrite())
        self.assertIn(desktop.CARGO, self.git("diff", "HEAD", "--name-only"))
        self.assertEqual(self.validate()["mapped_version"], "1.0.4+2")
        self.assertEqual(
            self.git("show", self.candidate["source_sha"] + ":" + desktop.CARGO),
            self.original.strip(),
        )

    def test_absent_empty_features_table_and_crlf_are_equivalent(self):
        variants = [
            self.rewrite(),
            self.rewrite().replace(", features = []", ""),
            self.original.replace(
                'tauri-build = "2.6.3"',
                '[build-dependencies.tauri-build]\nversion = "2.6.3"\nfeatures = []',
            ),
        ]
        for text in variants:
            self.manifest.write_bytes(text.replace("\n", "\r\n").encode())
            self.validate()

    def test_dependency_version_source_features_and_package_changes_fail(self):
        for text in (
            self.rewrite().replace('version = "2.6.3"', 'version = "2.6.4"'),
            self.rewrite().replace("features = []", 'features = ["isolation"]'),
            self.rewrite().replace(
                "features = []", 'features = [], path = "../injected"'
            ),
            self.rewrite().replace(
                'features = ["wry"]', 'features = ["wry", "devtools"]'
            ),
            self.rewrite().replace('ureq = "3.4.0"', 'ureq = "3.5.0"'),
            self.rewrite().replace('version = "0.1.0"', 'version = "1.0.4+2"'),
            self.rewrite() + "\n[profile.release]\nopt-level = 0\n",
        ):
            self.manifest.write_text(text)
            with (
                self.subTest(text=text),
                self.assertRaisesRegex(ValueError, "semantic mismatch"),
            ):
                self.validate()

    def test_manifest_delete_malformed_and_symlink_fail(self):
        self.manifest.unlink()
        with self.assertRaises(ValueError):
            self.validate()
        self.manifest.write_text("[invalid")
        with self.assertRaises(ValueError):
            self.validate()
        self.manifest.unlink()
        outside = self.work / "outside.toml"
        outside.write_text(self.rewrite())
        try:
            self.manifest.symlink_to(outside)
        except OSError:
            self.skipTest("host does not permit symlink creation")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.validate()

    def test_other_tracked_file_and_lock_mutation_still_fail(self):
        self.manifest.write_text(self.rewrite())
        lock = self.manifest.parent / "Cargo.lock"
        lock.write_text("# changed lock\n")
        with self.assertRaisesRegex(ValueError, "unexpected tracked"):
            self.validate()

    def test_changed_baseline_is_not_taken_from_worktree_or_index(self):
        self.manifest.write_text(
            self.rewrite().replace('ureq = "3.4.0"', 'ureq = "3.5.0"')
        )
        self.git("add", desktop.CARGO)
        with self.assertRaisesRegex(ValueError, "semantic mismatch"):
            self.validate()

    def test_resource_version_and_plist_checks_are_unchanged(self):
        self.manifest.write_text(self.rewrite())
        path = self.work / desktop.CONFIG
        config = json.loads(path.read_text())
        for key, value in (("version", "9.9.9"), ("bundle", {"resources": {}})):
            changed = copy.deepcopy(config)
            changed[key] = value
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                self.validate()


if __name__ == "__main__":
    unittest.main()
