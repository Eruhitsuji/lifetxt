"""OCI offline graph, exact-import smoke orchestration and workflow faults."""

import copy
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_oci as oci  # noqa: E402
import release_preflight_oci_layout as layout  # noqa: E402
import release_preflight_proof as proof  # noqa: E402


def fixture(root, candidate, arch="amd64", mutate=None):
    root.mkdir(parents=True)

    def blob(data, media):
        digest = hashlib.sha256(data).hexdigest()
        path = root / "blobs/sha256" / digest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"mediaType": media, "digest": "sha256:" + digest, "size": len(data)}

    layer = blob(b"fixture layer bytes", "application/vnd.oci.image.layer.v1.tar")
    config = {
        "architecture": arch,
        "os": "linux",
        "config": {
            "User": "lifetxt",
            "Entrypoint": ["lifetxt"],
            "Labels": {
                "org.opencontainers.image.version": candidate["version"],
                "org.opencontainers.image.revision": candidate["source_sha"],
            },
        },
        "rootfs": {"type": "layers", "diff_ids": [layer["digest"]]},
    }
    if mutate:
        mutate(config)
    descriptor = blob(layout.encode(config), layout.CONFIG)
    manifest = blob(
        layout.encode(
            {
                "schemaVersion": 2,
                "mediaType": layout.MANIFEST,
                "config": descriptor,
                "layers": [layer],
            }
        ),
        layout.MANIFEST,
    )
    (root / "index.json").write_bytes(
        layout.encode(
            {"schemaVersion": 2, "mediaType": layout.INDEX, "manifests": [manifest]}
        )
    )
    (root / "oci-layout").write_bytes(layout.encode({"imageLayoutVersion": "1.0.0"}))
    return manifest


class OciPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = self.root / "payload"
        self.candidate = proof.candidate(
            "Eruhitsuji/lifetxt", "1.0.4.2", "a" * 40, "b" * 40, 103, 1
        )
        self.target = "oci-linux-amd64"
        fixture(self.payload, self.candidate)
        self.retained = self.root / "retained"
        self.retained.mkdir()
        self.pack()
        self.artifact = {"id": 55, "name": "fixture-oci", "sha256": "e" * 64}

    def pack(self):
        with tarfile.open(
            self.retained / oci.archive_name(self.candidate, self.target), "w"
        ) as stream:
            for relative in sorted(layout.inventory(self.payload)):
                stream.add(self.payload / relative, arcname=relative)

    def graph(self):
        return layout.validate(self.payload, self.candidate, self.target)

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
                "observed_version": self.candidate["version"],
                "toolchain": {"buildx": "fixture"},
                "checks": dict.fromkeys(proof.CONTRACTS["oci"][1], "passed"),
                "oci": self.graph(),
                "files": oci.files(self.retained),
            }
        )

    def finish(self, report):
        return oci.finish(
            self.candidate, report, self.retained, self.artifact, self.target
        )

    def test_native_arches_and_full_graph_component(self):
        self.assertEqual(
            set(layout.TARGETS),
            {target for target in proof.TARGETS if target.startswith("oci-")},
        )
        for target, arch in layout.TARGETS.items():
            with patch.object(oci.standalone, "validate_host") as host:
                oci.validate_target(target)
            host.assert_called_once_with(
                "standalone-linux-" + ("x86_64" if arch == "amd64" else "arm64")
            )
        result = self.finish(self.report())
        proof.validate_component(self.candidate, result, self.retained)
        self.assertEqual(result["oci_digest"], self.graph()["manifest_digest"])
        self.assertNotEqual(
            self.graph()["manifest_digest"], self.graph()["config_digest"]
        )

    def test_wrong_arch_version_revision_user_and_entrypoint_rejected(self):
        mutations = [
            lambda c: c.update(architecture="arm64"),
            lambda c: c["config"]["Labels"].update(
                {"org.opencontainers.image.version": "1.0.4"}
            ),
            lambda c: c["config"]["Labels"].update(
                {"org.opencontainers.image.revision": "c" * 40}
            ),
            lambda c: c["config"].update(User="root"),
            lambda c: c["config"].update(Entrypoint=["sh"]),
        ]
        for index, mutate in enumerate(mutations):
            root = self.root / str(index)
            fixture(root, self.candidate, mutate=mutate)
            with self.assertRaises(ValueError):
                layout.validate(root, self.candidate, self.target)

    def test_missing_tampered_extra_symlink_and_unknown_files_rejected(self):
        blob = next((self.payload / "blobs/sha256").iterdir())
        original = blob.read_bytes()
        blob.write_bytes(original + b"changed")
        with self.assertRaises(ValueError):
            self.graph()
        blob.unlink()
        with self.assertRaises(ValueError):
            self.graph()
        blob.write_bytes(original)
        for relative in ("blobs/sha256/" + "f" * 64, "extra"):
            extra = self.payload / relative
            extra.write_bytes(b"unreferenced")
            with self.assertRaises(ValueError):
                self.graph()
            extra.unlink()
        alias = self.payload / "alias"
        alias.symlink_to(blob)
        with self.assertRaises(ValueError):
            self.graph()

    def test_bad_descriptor_size_digest_platform_url_and_index_count(self):
        path = self.payload / "index.json"
        original = proof.load(path)
        for change in (
            {"size": True},
            {"size": 1},
            {"digest": "sha256:bad"},
            {"platform": {"os": "linux", "architecture": "arm64"}},
            {"urls": ["https://example.invalid/blob"]},
        ):
            index = copy.deepcopy(original)
            index["manifests"][0].update(change)
            path.write_bytes(layout.encode(index))
            with self.assertRaises(ValueError):
                self.graph()
        for manifests in ([], original["manifests"] * 2):
            path.write_bytes(layout.encode({**original, "manifests": manifests}))
            with self.assertRaises(ValueError):
                self.graph()

    def test_duplicate_json_key_rejected(self):
        (self.payload / "oci-layout").write_text(
            '{"imageLayoutVersion":"1.0.0","imageLayoutVersion":"1.0.0"}'
        )
        with self.assertRaises(ValueError):
            self.graph()

    def test_archive_paths_links_and_duplicates_rejected(self):
        for index, (name, kind, duplicate) in enumerate(
            [
                ("../escape", tarfile.REGTYPE, False),
                ("index.json", tarfile.SYMTYPE, False),
                ("blobs/sha256/" + "a" * 64, tarfile.LNKTYPE, False),
                ("index.json", tarfile.REGTYPE, True),
            ]
        ):
            archive = self.root / (str(index) + ".tar")
            with tarfile.open(archive, "w") as stream:
                for _ in range(2 if duplicate else 1):
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.size = 1 if kind == tarfile.REGTYPE else 0
                    stream.addfile(member, io.BytesIO(b"x"))
            with self.assertRaises(ValueError):
                layout.extract(archive, self.root / ("out" + str(index)))
        self.assertFalse((self.root / "escape").exists())

    def test_archive_round_trip(self):
        archive = self.root / "valid.tar"
        with tarfile.open(archive, "w") as stream:
            for relative in sorted(layout.inventory(self.payload)):
                stream.add(self.payload / relative, arcname=relative)
        output = self.root / "restored"
        layout.extract(archive, output)
        self.assertEqual(
            layout.validate(output, self.candidate, self.target), self.graph()
        )

    def test_report_identity_checks_and_post_smoke_bytes_rejected(self):
        original = self.report()
        for key, value in (
            ("candidate_digest", "d" * 64),
            ("run_id", 104),
            ("schema_version", True),
            ("target", "oci-linux-arm64"),
            ("checks", {"native": "passed"}),
            ("observed_version", "1.0.4"),
        ):
            row = {k: v for k, v in original.items() if k != "digest"}
            row[key] = value
            with self.assertRaises(ValueError):
                self.finish(proof.sealed(row))
        # Valid graph semantically, different retained bytes must still fail.
        path = self.payload / "index.json"
        path.write_bytes(path.read_bytes() + b"\n")
        self.pack()
        with self.assertRaises(ValueError):
            self.finish(original)

    def runner(self, fault=None):
        graph = self.graph()
        commands = []

        def run(command, cwd):
            commands.append(command)
            if fault == "copy" and "copy" in command:
                raise subprocess.CalledProcessError(1, command)
            if "inspect" in command:
                return json.dumps(
                    [
                        {
                            "Id": graph["config_digest"],
                            "Digest": "sha256:" + "f" * 64
                            if fault == "digest"
                            else graph["manifest_digest"],
                            "Os": "linux",
                            "Architecture": "amd64",
                        }
                    ]
                )
            if "--version" in command:
                return "lifetxt " + (
                    "9.9.9" if fault == "version" else self.candidate["version"]
                )
            if "--help" in command:
                return "check serve"
            if "id" in command:
                return "0" if fault == "uid" else "1000"
            if "check" in command and fault == "cli":
                raise subprocess.CalledProcessError(1, command)
            return "fixture"

        return run, commands

    def test_exact_digest_import_smoke_and_no_registry_or_rebuild(self):
        run, commands = self.runner()
        with (
            patch.object(oci.core, "run", side_effect=run),
            patch.object(oci, "health") as health,
        ):
            oci.smoke(self.payload, self.graph(), ROOT, self.candidate)
        health.assert_called_once()
        self.assertIn("--preserve-digests", commands[0])
        self.assertTrue(commands[0][-1].startswith("containers-storage:"))
        self.assertEqual(commands[-1][2:4], ["rm", "-f"])
        self.assertFalse(
            any(
                "docker" in c or "push" in c or "login" in c or "build" in c
                for c in commands
            )
        )
        for command in commands:
            if "run" in command:
                self.assertIn("--pull=never", command)
                self.assertIn(self.graph()["config_digest"], command)

    def test_import_version_uid_cli_and_web_failure_fail_closed(self):
        for fault in ("copy", "digest", "version", "uid", "cli", "web"):
            run, commands = self.runner(fault)
            with (
                patch.object(oci.core, "run", side_effect=run),
                patch.object(
                    oci,
                    "health",
                    side_effect=ValueError("web fault") if fault == "web" else None,
                ),
            ):
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    oci.smoke(self.payload, self.graph(), ROOT, self.candidate)
            if fault == "web":
                self.assertEqual(commands[-1][2:4], ["rm", "-f"])

    def test_health_requires_http_and_json_success(self):
        response = MagicMock()
        response.__enter__.return_value = io.StringIO('{"ok":true,"read_only":true}')
        response.__enter__.return_value.status = 200
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(oci.urllib.request, "build_opener", return_value=opener):
            oci.health()
        opener.open.assert_called_once_with(
            "http://127.0.0.1:18321/api/health", timeout=2
        )
        response.__enter__.return_value = io.StringIO('{"ok":false,"read_only":true}')
        response.__enter__.return_value.status = 200
        with (
            patch.object(oci.urllib.request, "build_opener", return_value=opener),
            self.assertRaises(ValueError),
        ):
            oci.health()

    def test_multiarch_index_deterministic_without_blob_changes(self):
        arm = self.root / "arm"
        fixture(arm, self.candidate, "arm64")
        inputs = {self.target: self.payload, "oci-linux-arm64": arm}
        first, second = self.root / "multi1", self.root / "multi2"
        digest = layout.assemble(self.candidate, inputs, first)
        self.assertEqual(
            digest,
            layout.assemble(
                self.candidate, dict(reversed(list(inputs.items()))), second
            ),
        )
        self.assertEqual(
            (first / "index.json").read_bytes(), (second / "index.json").read_bytes()
        )
        index = proof.load(first / "index.json")
        self.assertEqual(
            [row["platform"]["architecture"] for row in index["manifests"]],
            ["amd64", "arm64"],
        )
        for root in inputs.values():
            for relative in layout.inventory(root) - {"index.json", "oci-layout"}:
                self.assertEqual(
                    (root / relative).read_bytes(), (first / relative).read_bytes()
                )
        with self.assertRaises(ValueError):
            layout.assemble(
                self.candidate, {self.target: self.payload}, self.root / "incomplete"
            )
        with self.assertRaises(ValueError):
            layout.assemble(self.candidate, inputs, first)

    def test_build_once_fixture_then_component_and_failure_no_report(self):
        archive = self.root / "built.tar"
        with tarfile.open(archive, "w") as stream:
            for relative in layout.inventory(self.payload):
                stream.add(self.payload / relative, arcname=relative)
        commands = []

        def run(command, cwd):
            commands.append(command)
            if "--output" in command:
                destination = Path(
                    command[command.index("--output") + 1].split("dest=", 1)[1]
                )
                destination.write_bytes(archive.read_bytes())
            return "fixture-tool"

        output, payload = self.root / "report.json", self.root / "build"
        with (
            patch.object(oci.core, "validate_context"),
            patch.object(oci.core, "validate_source"),
            patch.object(oci, "validate_target"),
            patch.object(oci.core, "run", side_effect=run),
            patch.object(oci, "smoke"),
        ):
            report = oci.build(
                self.candidate, ROOT, ROOT, payload, output, self.target, {}
            )
        result = oci.finish(self.candidate, report, payload, self.artifact, self.target)
        proof.validate_component(self.candidate, result, payload)
        build = [c for c in commands if "--output" in c]
        self.assertEqual(len(build), 1)
        self.assertIn("--provenance=false", build[0])
        self.assertEqual(build[0][build[0].index("--platform") + 1], "linux/amd64")
        with (
            patch.object(oci.core, "validate_context"),
            patch.object(oci.core, "validate_source"),
            patch.object(oci, "validate_target"),
            patch.object(oci.core, "run", side_effect=run),
            patch.object(oci, "smoke", side_effect=ValueError("fault")),
        ):
            with self.assertRaises(ValueError):
                oci.build(
                    self.candidate,
                    ROOT,
                    ROOT,
                    self.root / "failed",
                    self.root / "failed.json",
                    self.target,
                    {},
                )
        self.assertFalse((self.root / "failed.json").exists())

    def test_workflow_only_native_read_only_and_separate_evidence(self):
        raw = (ROOT / ".github/workflows/release-preflight-oci.yml").read_text()
        workflow = yaml.load(raw, Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow["on"]), {"workflow_call"})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        job = workflow["jobs"]["oci"]
        self.assertEqual(job["permissions"], {"contents": "read"})
        self.assertEqual(
            {row["os"] for row in job["strategy"]["matrix"]["include"]},
            {"ubuntu-24.04", "ubuntu-24.04-arm"},
        )
        uploads = [
            s
            for s in job["steps"]
            if s.get("uses", "").startswith("actions/upload-artifact@")
        ]
        self.assertEqual(len(uploads), 2)
        self.assertTrue(all(s["with"]["retention-days"] == "30" for s in uploads))
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                self.assertEqual(step["with"]["persist-credentials"], "false")
        for forbidden in (
            "packages:",
            "secrets.",
            "environment:",
            "login-action",
            "setup-qemu",
            "push: true",
        ):
            self.assertNotIn(forbidden, raw)


if __name__ == "__main__":
    unittest.main()
