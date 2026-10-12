"""Execute Mini workflow shell steps against disposable artifacts and fake gh."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.check_release_tag_version import project_version

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/lifetxt-mini-release.yml"


@unittest.skipUnless(
    os.name == "posix" and shutil.which("bash") and shutil.which("sha256sum"),
    "Mini Linux shell fixtures require Bash and sha256sum",
)
class MiniReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dist = self.root / "dist/lifetxt-mini"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.workflow = WORKFLOW.read_text()
        self.version = project_version(ROOT)
        (self.root / "scripts").mkdir()
        for name in ("merge_sha256sums.py", "check_lifetxt_mini_version.py"):
            shutil.copyfile(ROOT / "scripts" / name, self.root / "scripts" / name)
        shutil.copyfile(ROOT / "pyproject.toml", self.root / "pyproject.toml")
        (self.root / "lifetxt-mini").mkdir()
        shutil.copyfile(
            ROOT / "lifetxt-mini/Cargo.toml", self.root / "lifetxt-mini/Cargo.toml"
        )
        shutil.copyfile(
            ROOT / "lifetxt-mini/Cargo.lock", self.root / "lifetxt-mini/Cargo.lock"
        )
        (self.root / "lifetxt").mkdir()
        (self.root / "lifetxt/__init__.py").write_text("")
        shutil.copyfile(
            ROOT / "lifetxt/versioning.py", self.root / "lifetxt/versioning.py"
        )
        self.env = dict(
            os.environ,
            TAG="v" + self.version,
            PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
        )
        self.executable("rustc", '#!/bin/sh\nprintf "fixture rustc\\n"\n')
        self.executable(
            "gh",
            "#!"
            + sys.executable
            + "\n"
            + textwrap.dedent("""
            import json, os, sys
            from pathlib import Path
            root=Path(os.environ['FIXTURE_ROOT'])
            args=sys.argv[1:]
            with (root/'gh-calls.jsonl').open('a') as out: out.write(json.dumps(args)+'\\n')
            if args[:2]==['release','view']:
                if not (root/'release-exists').exists(): sys.exit(1)
                if '--json' in args: print(os.environ.get('MANIFEST_PRESENT','true'))
            elif args[:2]==['release','create']:
                (root/'release-exists').write_text('created')
            elif args[:2]==['release','download']:
                if os.environ.get('DOWNLOAD_FAIL'): sys.exit(1)
                Path(args[args.index('--output')+1]).write_bytes((root/'remote-manifest').read_bytes())
            elif args[:2]==['release','upload']:
                (root/'uploaded-manifest').write_bytes((root/'dist/lifetxt-mini/SHA256SUMS').read_bytes())
            else: sys.exit('Unexpected fake gh command')
        """),
        )
        self.env["FIXTURE_ROOT"] = str(self.root)

    def executable(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)
        return path

    def step(self, job, name):
        # Extract the workflow's literal block scalars, without an optional YAML
        # dependency that would silently skip these regressions in the CI lane.
        section = re.split(
            r"^  " + re.escape(job) + r":\n", self.workflow, maxsplit=1, flags=re.M
        )[1]
        section = re.split(r"\n  [a-zA-Z_-]+:\n", section, maxsplit=1)[0]
        block = section.split("      - name: " + name + "\n", 1)[1]
        block = block.split("      - ", 1)[0]
        run = block.split("        run: |\n", 1)[1]
        lines = []
        for line in run.splitlines():
            if line and not line.startswith("          "):
                break
            lines.append(line[10:] if line else "")
        directory = re.search(r"^        working-directory: (.+)$", block, re.M)
        return {
            "run": "\n".join(lines),
            "working-directory": directory[1] if directory else None,
        }

    def run_shell(self, script, cwd=None, env=None):
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
            cwd=cwd or self.root,
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def package(self):
        for target in ("x86_64-unknown-linux-musl", "aarch64-unknown-linux-musl"):
            binary = self.root / "lifetxt-mini/target" / target / "release/lifetxt-mini"
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(("fixture " + target).encode())
            result = self.run_shell(
                self.step("build", "Package and checksum")["run"],
                env=dict(self.env, TARGET=target),
            )
            self.assertEqual(0, result.returncode, result.stderr)
        return sorted(self.dist.glob("*.sha256"))

    def publish(self, existing=True, manifest="true", failure=False, remote=None):
        if existing:
            (self.root / "release-exists").write_text("existing")
        (self.root / "remote-manifest").write_text(
            remote
            or "a" * 64 + "  lifetxt-core.whl\n" + "b" * 64 + "  lifetxt-linux-x86_64\n"
        )
        env = dict(self.env, MANIFEST_PRESENT=manifest)
        if failure:
            env["DOWNLOAD_FAIL"] = "1"
        return self.run_shell(
            self.step("publish", "Verify checksums and publish")["run"], env=env
        )

    def calls(self):
        p = self.root / "gh-calls.jsonl"
        return (
            [json.loads(line) for line in p.read_text().splitlines()]
            if p.exists()
            else []
        )

    def assert_no_upload(self):
        self.assertFalse(
            any(args[:2] == ["release", "upload"] for args in self.calls())
        )

    @unittest.skipUnless(
        sys.version_info >= (3, 11),
        "Existing Mini build checker uses tomllib (build runner Python 3.11+)",
    )
    def test_native_checker_runs_from_actual_working_directory(self):
        step = self.step("build", "Verify native static artifact")
        checker = next(
            line.strip()
            for line in step["run"].splitlines()
            if "check_lifetxt_mini_version.py" in line
        )
        self.executable(
            "fixture-mini",
            "#!" + sys.executable + '\nprint("lifetxt-mini ' + self.version + '")\n',
        )
        # Execute the actual checker command, with workflow substitutions and binary var.
        checker = checker.replace(
            "${{ inputs.tag || github.ref_name }}", "v" + self.version
        )
        result = self.run_shell(
            "binary=../bin/fixture-mini\n" + checker,
            cwd=self.root / step["working-directory"],
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("version consistent", result.stdout)

    def test_both_packaged_checksums_verify_in_download_directory(self):
        checksums = self.package()
        self.assertEqual(2, len(checksums))
        for checksum in checksums:
            entry = checksum.read_text().split()
            self.assertEqual(checksum.name.removesuffix(".sha256"), entry[1])
            self.assertEqual(
                hashlib.sha256((self.dist / entry[1]).read_bytes()).hexdigest(),
                entry[0],
            )
            result = self.run_shell("sha256sum -c " + checksum.name, cwd=self.dist)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_existing_core_and_standalone_manifest_survives_publish(self):
        self.package()
        result = self.publish()
        self.assertEqual(0, result.returncode, result.stderr)
        manifest = (self.root / "uploaded-manifest").read_text()
        self.assertIn("lifetxt-core.whl", manifest)
        self.assertIn("lifetxt-linux-x86_64", manifest)
        self.assertEqual(4, len(manifest.splitlines()))
        uploads = [a for a in self.calls() if a[:2] == ["release", "upload"]]
        self.assertEqual(1, len(uploads))
        self.assertFalse(any("existing-SHA256SUMS" in path for path in uploads[0]))

    def test_first_publish_and_existing_release_without_manifest(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                self.package()
                result = self.publish(existing=existing, manifest="false")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(
                    2, len((self.root / "uploaded-manifest").read_text().splitlines())
                )
                if not existing:
                    self.assertTrue(
                        any(a[:2] == ["release", "create"] for a in self.calls())
                    )

    def test_failed_declared_manifest_download_stops_upload(self):
        self.package()
        result = self.publish(failure=True)
        self.assertNotEqual(0, result.returncode)
        self.assert_no_upload()

    def test_malformed_manifest_and_inventory_stop_upload(self):
        for inventory, remote in (("true", "broken\n"), ("unexpected", None)):
            with self.subTest(inventory=inventory):
                self.package()
                result = self.publish(manifest=inventory, remote=remote)
                self.assertNotEqual(0, result.returncode)
                self.assert_no_upload()

    def test_tampered_binary_stops_before_any_release_call(self):
        self.package()
        next(p for p in self.dist.iterdir() if p.name.endswith("x86_64")).write_bytes(
            b"tampered"
        )
        result = self.publish()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], self.calls())

    def test_publish_checks_out_tag_for_existing_merger(self):
        publish = re.split(r"^  publish:\n", self.workflow, maxsplit=1, flags=re.M)[1]
        self.assertRegex(
            publish,
            r"actions/checkout@v[0-9]+\n        with:\n          ref: \$\{\{ github.ref_name \}\}",
        )
        # Publication authorization remains tag-push-only.
        self.assertIn(
            "    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')",
            publish,
        )
