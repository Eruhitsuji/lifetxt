"""Mini ELF/static, smoke, payload and read-only producer fault injection."""

import copy
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_mini as mini  # noqa: E402
import release_preflight_proof as proof  # noqa: E402


def elf(machine=62, interp=False, dynamic=False, needed=False, terminated=True):
    extras = []
    if interp:
        extras.append((3, b"/lib/ld.so\0"))
    if dynamic or needed:
        data = struct.pack("<qQ", 1 if needed else 29, 1)
        if terminated:
            data += struct.pack("<qQ", 0, 0)
        extras.append((2, data))
    count = len(extras) + 1
    offset = 64 + count * 56
    total = offset + sum(len(data) for _, data in extras)
    header = (
        b"\x7fELF\x02\x01\x01"
        + bytes(9)
        + struct.pack(
            "<HHIQQQIHHHHHH", 3, machine, 1, 0, 64, 0, 0, 64, 56, count, 0, 0, 0
        )
    )
    segments = [struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, total, total, 4096)]
    for kind, data in extras:
        segments.append(
            struct.pack("<IIQQQQQQ", kind, 4, offset, 0, 0, len(data), len(data), 8)
        )
        offset += len(data)
    return header + b"".join(segments) + b"".join(data for _, data in extras)


class MiniPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = self.root / "payload"
        self.payload.mkdir()
        self.target = "mini-linux-x86_64"
        self.candidate = proof.candidate(
            "Eruhitsuji/lifetxt", "1.0.4.2", "a" * 40, "b" * 40, 103, 1
        )
        self.binary = self.payload / next(
            name
            for name, role in mini.names(self.candidate, self.target).items()
            if role == "binary"
        )
        self.binary.write_bytes(elf())
        self.sums = self.payload / (self.binary.name + ".sha256")
        self.sums.write_bytes(mini.standalone.checksum(self.binary).encode("ascii"))
        (self.payload / (self.binary.name + ".build-info")).write_text(
            "rustc fixture\n"
        )
        (self.payload / "RELEASE-NOTES.md").write_text(mini.notes(self.candidate))
        self.artifact = {"id": 40, "name": "fixture-mini-payload", "sha256": "e" * 64}

    def report(self):
        return proof.sealed(
            {
                "schema_version": 1,
                "candidate_digest": self.candidate["digest"],
                **{
                    key: self.candidate[key]
                    for key in ("source_sha", "controller_sha", "run_id", "run_attempt")
                },
                "target": self.target,
                "observed_version": "1.0.4.2",
                "toolchain": {"rustc": "fixture"},
                "checks": dict.fromkeys(proof.CONTRACTS["mini"][1], "passed"),
                "static_elf": mini.static_elf(self.binary, self.target),
                "files": [
                    {
                        "path": path.name,
                        "role": mini.names(self.candidate, self.target)[path.name],
                        "sha256": proof.file_digest(path),
                        "bytes": path.stat().st_size,
                    }
                    for path in sorted(self.payload.iterdir())
                ],
            }
        )

    def reseal(self, row):
        return proof.sealed(
            {key: value for key, value in row.items() if key != "digest"}
        )

    def finish(self, row):
        return mini.finish(
            self.candidate, row, self.payload, self.artifact, self.target
        )

    def test_two_native_targets_and_architecture_aliases(self):
        self.assertEqual(
            set(mini.TARGETS),
            {target for target in proof.TARGETS if target.startswith("mini-")},
        )
        for target, (_, arch, machine) in mini.TARGETS.items():
            with patch.object(mini.standalone, "validate_host") as host:
                mini.validate_target(target)
            host.assert_called_once_with("standalone-linux-" + arch)
            binary = self.root / target
            binary.write_bytes(elf(machine=machine))
            self.assertEqual(mini.static_elf(binary, target)["machine"], machine)

    def test_static_pie_dynamic_metadata_without_dependencies_is_allowed(self):
        self.binary.write_bytes(elf(dynamic=True))
        self.assertFalse(mini.static_elf(self.binary, self.target)["interpreter"])

    def test_interpreter_needed_library_and_unterminated_table_rejected(self):
        for data in (
            elf(interp=True),
            elf(needed=True),
            elf(dynamic=True, terminated=False),
        ):
            self.binary.write_bytes(data)
            with self.assertRaises(ValueError):
                mini.static_elf(self.binary, self.target)

    def test_invalid_elf_class_endianness_arch_bounds_and_missing_load_rejected(self):
        samples = [b"not an ELF", elf(machine=183)]
        for offset, value in ((4, 1), (5, 2)):
            data = bytearray(elf())
            data[offset] = value
            samples.append(data)
        data = bytearray(elf())
        struct.pack_into("<Q", data, 32, 2**63)
        samples.append(data)
        data = bytearray(elf())
        struct.pack_into("<I", data, 64, 4)
        samples.append(data)
        for data in samples:
            self.binary.write_bytes(data)
            with self.assertRaises(ValueError):
                mini.static_elf(self.binary, self.target)

    def test_exact_payload_notes_and_common_component(self):
        mini.validate_payload(self.candidate, self.payload, self.target)
        result = self.finish(self.report())
        proof.validate_component(self.candidate, result, self.payload)
        self.assertEqual(
            {row["role"] for row in result["files"]},
            {"binary", "checksum", "build-info", "notes"},
        )
        self.assertIn("strict-subset", mini.notes(self.candidate))
        self.assertEqual(
            mini.notes(self.candidate), mini.notes(copy.deepcopy(self.candidate))
        )

    def test_crlf_checksum_wrong_notes_and_inventory_rejected(self):
        original = self.sums.read_bytes()
        self.sums.write_bytes(original.replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(ValueError, "checksum"):
            mini.validate_payload(self.candidate, self.payload, self.target)
        self.sums.write_bytes(original)
        (self.payload / "RELEASE-NOTES.md").write_text("wrong release")
        with self.assertRaisesRegex(ValueError, "notes identity"):
            mini.validate_payload(self.candidate, self.payload, self.target)
        (self.payload / "extra").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "inventory"):
            mini.validate_payload(self.candidate, self.payload, self.target)

    def test_report_identity_target_schema_role_and_static_evidence_rejected(self):
        for key, value in (
            ("run_id", 104),
            ("schema_version", True),
            ("target", "mini-linux-aarch64"),
            ("static_elf", {}),
        ):
            row = self.report()
            row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.finish(self.reseal(row))
        row = self.report()
        row["files"][0]["role"] = "binary"
        with self.assertRaisesRegex(ValueError, "role mismatch"):
            self.finish(self.reseal(row))

    def test_changed_binary_and_new_checksum_do_not_replace_smoked_bytes(self):
        row = self.report()
        with self.binary.open("ab") as stream:
            stream.write(b"changed")
        self.sums.write_bytes(mini.standalone.checksum(self.binary).encode("ascii"))
        with self.assertRaisesRegex(ValueError, "changed since smoke"):
            self.finish(row)

    def test_required_native_static_conformance_checks_cannot_be_skipped(self):
        for check in ("native", "static", "conformance"):
            row = self.report()
            row["checks"][check] = "skipped"
            with self.subTest(check=check), self.assertRaises(ValueError):
                self.finish(self.reseal(row))

    def test_smoke_runs_existing_version_and_conformance_with_supported_python(self):
        calls = []

        def run(command, cwd, env):
            calls.append((command, cwd, env))
            if command[-1] == "--version":
                return "lifetxt-mini 1.0.4.2"
            if command[-1] == "--help":
                return "Mini Runtime Profile"
            return "OK"

        with (
            patch.object(mini.core, "run", side_effect=run),
            patch.dict(os.environ, {"PYTHONPATH": "wrong"}),
        ):
            mini.smoke(self.binary, ROOT, self.candidate)
        self.assertEqual(len(calls), 6)
        self.assertTrue(
            any(
                "check_lifetxt_mini_version.py" in " ".join(command)
                for command, _, _ in calls
            )
        )
        self.assertTrue(
            any(
                "check_mini_core_conformance.py" in " ".join(command)
                for command, _, _ in calls
            )
        )
        for _, _, env in calls:
            self.assertNotIn("PYTHONPATH", env)
            self.assertEqual(
                env["PATH"].split(os.pathsep)[0], str(Path(sys.executable).parent)
            )

    def test_wrong_python_alias_cannot_silently_run_another_interpreter(self):
        with (
            patch.object(mini.shutil, "which", return_value="/wrong/python"),
            patch.object(mini.core, "run") as run,
            self.assertRaisesRegex(ValueError, "python alias"),
        ):
            mini.smoke(self.binary, ROOT, self.candidate)
        run.assert_not_called()

    def test_wrong_version_or_conformance_failure_stops_smoke(self):
        with (
            patch.object(mini.core, "run", return_value="lifetxt-mini 1.0.4.3"),
            self.assertRaisesRegex(ValueError, "version mismatch"),
        ):
            mini.smoke(self.binary, ROOT, self.candidate)
        with (
            patch.object(
                mini.core,
                "run",
                side_effect=[
                    "lifetxt-mini 1.0.4.2",
                    "OK",
                    "Mini Runtime Profile",
                    "OK",
                    "OK",
                    subprocess.CalledProcessError(1, ["conformance"]),
                ],
            ),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            mini.smoke(self.binary, ROOT, self.candidate)

    def test_fixture_native_build_binds_successful_report_and_fresh_build_dirs(self):
        payload = self.root / "built-payload"
        output = self.root / "build-report.json"
        calls = []

        def run(command, cwd):
            calls.append(command)
            if command[:2] == ["cargo", "zigbuild"] and "--release" in command:
                target_dir = Path(command[command.index("--target-dir") + 1])
                binary = (
                    target_dir / mini.TARGETS[self.target][0] / "release/lifetxt-mini"
                )
                binary.parent.mkdir(parents=True)
                binary.write_bytes(elf())
            return "fixture-tool-version"

        with (
            patch.object(mini.core, "validate_context"),
            patch.object(mini.core, "validate_source"),
            patch.object(mini, "validate_target"),
            patch.object(mini, "smoke"),
            patch.object(mini.core, "run", side_effect=run),
        ):
            row = mini.build(
                self.candidate, ROOT, ROOT, payload, output, self.target, {}
            )
        proof.validate_component(
            self.candidate,
            mini.finish(self.candidate, row, payload, self.artifact, self.target),
            payload,
        )
        build_calls = [
            command
            for command in calls
            if command[:2] in (["cargo", "test"], ["cargo", "zigbuild"])
            and "--target-dir" in command
        ]
        self.assertEqual(len(build_calls), 2)
        self.assertTrue(all("--locked" in command for command in build_calls))

    def test_cargo_failure_never_creates_success_report(self):
        output = self.root / "not-created.json"
        with (
            patch.object(mini.core, "validate_context"),
            patch.object(mini.core, "validate_source"),
            patch.object(mini, "validate_target"),
            patch.object(
                mini.core,
                "run",
                side_effect=subprocess.CalledProcessError(1, ["cargo"]),
            ),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            mini.build(
                self.candidate,
                ROOT,
                ROOT,
                self.root / "new-payload",
                output,
                self.target,
                {},
            )
        self.assertFalse(output.exists())

    def test_workflow_keeps_both_native_targets_read_only(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML unavailable")
        workflow = yaml.load(
            (ROOT / ".github/workflows/release-preflight-mini.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(set(workflow["on"]), {"workflow_call"})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job = workflow["jobs"]["mini"]
        self.assertEqual(job["permissions"], {"contents": "read"})
        self.assertNotIn("environment", job)
        self.assertEqual(
            {
                row["target"]: row["triple"]
                for row in job["strategy"]["matrix"]["include"]
            },
            {target: value[0] for target, value in mini.TARGETS.items()},
        )
        self.assertEqual(job["strategy"]["fail-fast"], "false")
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                self.assertEqual(step["with"]["persist-credentials"], "false")


if __name__ == "__main__":
    unittest.main()
