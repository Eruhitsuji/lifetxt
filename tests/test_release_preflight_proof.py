"""Offline fault injection for the non-authorizing preflight proof contract."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_proof as proof  # noqa: E402


class PreflightProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.candidate = proof.candidate(
            "Eruhitsuji/lifetxt", "1.0.4.2", "a" * 40, "b" * 40, 123, 1
        )
        self.components = []
        for index, target in enumerate(proof.TARGETS, start=1):
            roles, checks = proof.contract(target)
            folder = self.root / target
            folder.mkdir()
            files = []
            for role in sorted(roles):
                name = role + ".bin"
                (folder / name).write_bytes((target + ":" + role).encode())
                files.append({"path": name, "role": role})
            spec = {
                "target": target,
                "artifact": {"id": index, "name": target, "sha256": "f" * 64},
                "observed_version": "1.0.4.2",
                "toolchain": {"runner": "fixture", "compiler": "fixture-1"},
                "checks": dict.fromkeys(checks, "passed"),
                "files": files,
                "oci_digest": "sha256:" + "e" * 64
                if target.startswith("oci-")
                else None,
            }
            self.components.append(proof.component(self.candidate, spec, folder))

    def aggregate(self, rows=None):
        return proof.aggregate(
            self.candidate, self.components if rows is None else rows, self.root
        )

    def changed(self, index=0, **changes):
        result = copy.deepcopy(self.components)
        result[index].update(changes)
        result[index] = proof.sealed(
            {key: value for key, value in result[index].items() if key != "digest"}
        )
        return result

    def test_all_targets_bind_bytes_without_publication_authority(self):
        result = self.aggregate()
        self.assertEqual(len(result["components"]), 13)
        self.assertEqual(result["status"], "preflight_verified")
        self.assertIs(result["publication_authorized"], False)
        self.assertEqual(result, self.aggregate(list(reversed(self.components))))
        payload = {key: value for key, value in result.items() if key != "digest"}
        self.assertEqual(result["digest"], proof.digest(payload))

    def test_optional_zero_and_manual_correction_identity(self):
        args = ("Eruhitsuji/lifetxt",)
        tail = ("a" * 40, "b" * 40, 123, 1)
        plain = proof.candidate(*args, "1.0.4", *tail)
        zero = proof.candidate(*args, "1.0.4.0", *tail)
        self.assertEqual(plain, zero)
        self.assertEqual(self.candidate["tag"], "v1.0.4.2")
        self.assertEqual(self.candidate["metadata_version"], "1.0.4+2")
        self.assertNotEqual(self.candidate["digest"], plain["digest"])

    def test_invalid_candidate_and_changed_policy_fail_closed(self):
        for key, value in (
            ("source_sha", "main"),
            ("controller_sha", "A" * 40),
            ("run_id", True),
            ("run_attempt", 0),
            ("version", "1.0.04"),
        ):
            args = dict(
                repository="Eruhitsuji/lifetxt",
                version="1.0.4",
                source_sha="a" * 40,
                controller_sha="b" * 40,
                run_id=123,
                run_attempt=1,
            )
            args[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                proof.candidate(**args)
        for targets in ([], list(proof.TARGETS)[1:], list(reversed(proof.TARGETS))):
            row = dict(self.candidate, targets=targets)
            row = proof.sealed(
                {key: value for key, value in row.items() if key != "digest"}
            )
            with self.assertRaisesRegex(ValueError, "target set"):
                proof.validate_candidate(row)

    def test_missing_duplicate_and_unexpected_target(self):
        with self.assertRaisesRegex(ValueError, "missing required targets"):
            self.aggregate(self.components[:-1])
        with self.assertRaisesRegex(ValueError, "duplicate target"):
            self.aggregate(self.components + self.components[:1])
        with self.assertRaisesRegex(ValueError, "unexpected target"):
            self.aggregate(self.changed(target="unknown"))

    def test_candidate_sha_run_and_attempt_mismatch(self):
        for key, value in (
            ("candidate_digest", "0" * 64),
            ("source_sha", "c" * 40),
            ("controller_sha", "d" * 40),
            ("run_id", 124),
            ("run_attempt", 2),
            ("run_attempt", True),
            ("observed_version", "1.0.4.3"),
        ):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "mismatch"):
                self.aggregate(self.changed(**{key: value}))

    def test_digest_tamper_and_unknown_fields(self):
        rows = copy.deepcopy(self.components)
        rows[0]["source_sha"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.aggregate(rows)
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            self.aggregate(self.changed(approved=True))

    def test_payload_modified_deleted_or_empty(self):
        item = self.components[0]["files"][0]
        path = self.root / "core-any" / item["path"]
        old = path.read_bytes()
        for content in (b"tampered", b"", b"x" * len(old)):
            path.write_bytes(content)
            with self.assertRaisesRegex(ValueError, "bytes/digest mismatch"):
                self.aggregate()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "missing or non-file"):
            self.aggregate()

    def test_path_traversal_aliases_and_absolute_paths(self):
        for path in (
            "../outside",
            "/tmp/absolute",
            "a//b",
            "./binary.bin",
            "a/../binary.bin",
            "C:/binary.bin",
            "a\\b",
            "a\nb",
            "binary.bin.",
        ):
            rows = copy.deepcopy(self.components[0]["files"])
            rows[0]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.aggregate(self.changed(files=rows))

    def test_symlink_payload_and_symlink_directory_rejected(self):
        folder = self.root / "core-any"
        name = self.components[0]["files"][0]["path"]
        path = folder / name
        stored = self.root / "stored.bin"
        path.rename(stored)
        try:
            path.symlink_to(stored)
        except OSError:
            self.skipTest("host cannot create symlinks")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.aggregate()
        path.unlink()
        stored.rename(path)
        actual = self.root / "actual"
        folder.rename(actual)
        folder.symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "payload root"):
            self.aggregate()

    def test_failed_skipped_or_missing_smoke_and_toolchain(self):
        for status in ("failed", "skipped", "not_run", True):
            checks = dict(self.components[0]["checks"], cli=status)
            with self.assertRaisesRegex(ValueError, "smoke"):
                self.aggregate(self.changed(checks=checks))
        with self.assertRaisesRegex(ValueError, "checks"):
            self.aggregate(self.changed(checks={"cli": "passed"}))
        with self.assertRaisesRegex(ValueError, "toolchain"):
            self.aggregate(self.changed(toolchain={}))

    def test_artifact_reference_missing_or_reused(self):
        for artifact in (
            {"id": 0, "name": "artifact", "sha256": "f" * 64},
            {"id": 99, "name": "", "sha256": "f" * 64},
            {"id": 99, "name": "artifact", "sha256": "fake"},
        ):
            with self.assertRaises(ValueError):
                self.aggregate(self.changed(artifact=artifact))
        with self.assertRaisesRegex(ValueError, "duplicate artifact id"):
            self.aggregate(
                self.changed(index=1, artifact=self.components[0]["artifact"])
            )

    def test_roles_and_duplicate_payload_paths(self):
        rows = copy.deepcopy(self.components[0]["files"])
        rows[0]["role"] = "binary"
        with self.assertRaisesRegex(ValueError, "unexpected payload role"):
            self.aggregate(self.changed(files=rows))
        with self.assertRaisesRegex(ValueError, "missing required payload role"):
            self.aggregate(self.changed(files=self.components[0]["files"][:-1]))
        with self.assertRaisesRegex(ValueError, "duplicate payload path"):
            self.aggregate(self.changed(files=self.components[0]["files"] * 2))

    def test_unlisted_payload_and_case_alias_rejected(self):
        folder = self.root / "core-any"
        (folder / "extra.bin").write_bytes(b"unexpected")
        with self.assertRaisesRegex(ValueError, "unlisted payload"):
            self.aggregate()
        (folder / "extra.bin").unlink()
        rows = copy.deepcopy(self.components[0]["files"])
        path = folder / rows[0]["path"]
        upper = rows[0]["path"].upper()
        (folder / upper).write_bytes(path.read_bytes())
        if (folder / upper).samefile(path):
            self.skipTest("case-insensitive host cannot create two case aliases")
        with self.assertRaisesRegex(ValueError, "case alias"):
            self.aggregate()
        rows.append(dict(rows[0], path=upper))
        with self.assertRaisesRegex(ValueError, "duplicate payload path"):
            self.aggregate(self.changed(files=rows))

    def test_reserved_device_paths_rejected_before_file_access(self):
        for name in ("CON", "nul.txt", "COM1.bin", "lpt9/output"):
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(ValueError, "unsafe payload path"),
            ):
                proof.payload_path(self.root, name)

    def test_oci_digest_required_only_for_oci(self):
        for index, value in ((0, "sha256:" + "e" * 64), (11, None), (12, "latest")):
            with self.assertRaisesRegex(ValueError, "OCI digest"):
                self.aggregate(self.changed(index=index, oci_digest=value))

    def cli(self, *args):
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/release_preflight_proof.py"),
                *map(str, args),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

    def test_cli_roundtrip_and_reject_existing_output(self):
        candidate_path = self.root / "candidate.json"
        run = self.cli(
            "candidate",
            "--repository",
            "Eruhitsuji/lifetxt",
            "--version",
            "1.0.4.2",
            "--source-sha",
            "a" * 40,
            "--controller-sha",
            "b" * 40,
            "--run-id",
            123,
            "--run-attempt",
            1,
            "--output",
            candidate_path,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(proof.load(candidate_path), self.candidate)
        component_args = []
        for index, row in enumerate(self.components):
            source = self.root / ("component-%d.json" % index)
            source.write_text(json.dumps(row))
            component_args += ["--component", source]
        output = self.root / "proof.json"
        args = (
            "aggregate",
            "--candidate",
            candidate_path,
            "--root",
            self.root,
            *component_args,
            "--output",
            output,
        )
        run = self.cli(*args)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(proof.load(output), self.aggregate())
        before = output.read_bytes()
        run = self.cli(*args)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(output.read_bytes(), before)
        self.assertIn("fresh output", run.stderr)

    def test_cli_component_and_failure_never_writes_success(self):
        candidate_path = self.root / "candidate.json"
        candidate_path.write_text(json.dumps(self.candidate))
        row = self.components[0]
        spec = {
            key: row[key]
            for key in (
                "target",
                "artifact",
                "observed_version",
                "toolchain",
                "checks",
                "oci_digest",
            )
        }
        spec["files"] = [
            {key: item[key] for key in ("path", "role")} for item in row["files"]
        ]
        spec_path = self.root / "spec.json"
        spec_path.write_text(json.dumps(spec))
        output = self.root / "component.json"
        args = (
            "component",
            "--candidate",
            candidate_path,
            "--spec",
            spec_path,
            "--root",
            self.root / row["target"],
            "--output",
            output,
        )
        run = self.cli(*args)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(proof.load(output), row)
        output.unlink()
        spec["checks"]["cli"] = "failed"
        spec_path.write_text(json.dumps(spec))
        run = self.cli(*args)
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse(output.exists())

    def test_json_duplicate_keys_rejected(self):
        path = self.root / "duplicate.json"
        path.write_text('{"run_id":1,"run_id":2}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            proof.load(path)


if __name__ == "__main__":
    unittest.main()
