"""Full 13-target fixture integration; not native-build/Actions runtime evidence."""

import copy
import io
import json
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import yaml

from tests.test_release_preflight_actions import FakeActions
from tests.test_release_preflight_mini import elf
from tests.test_release_preflight_oci import fixture as oci_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight_collect as collect  # noqa: E402
import release_preflight_actions as actions  # noqa: E402
import release_preflight_proof as proof  # noqa: E402


def payload_fixture(candidate, target, payload, image):
    payload.mkdir(parents=True)
    family = target.split("-", 1)[0]
    details = {}
    if family == "core":
        metadata = ("Name: lifetxt\nVersion: " + candidate["version"] + "\n").encode()
        wheel, sdist = payload / "lifetxt.whl", payload / "lifetxt.tar.gz"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("lifetxt.dist-info/METADATA", metadata)
        with tarfile.open(sdist, "w:gz") as archive:
            info = tarfile.TarInfo("lifetxt/PKG-INFO")
            info.size = len(metadata)
            archive.addfile(info, io.BytesIO(metadata))
        proof.write_new(
            payload / "sbom.cdx.json",
            {
                "metadata": {
                    "component": {"name": "lifetxt", "version": candidate["version"]}
                }
            },
        )
        proof.write_new(
            payload / "provenance.json",
            {
                "schema": "lifetxt-release-provenance-v1",
                "package": {"name": "lifetxt", "version": candidate["version"]},
                "source": {"commit": candidate["source_sha"]},
                "workflow_run": str(candidate["run_id"]),
                "artifacts": [
                    {
                        "file": p.name,
                        "sha256": proof.file_digest(p),
                        "bytes": p.stat().st_size,
                    }
                    for p in (sdist, wheel)
                ],
            },
        )
        roles = {
            wheel.name: "wheel",
            sdist.name: "sdist",
            "sbom.cdx.json": "sbom",
            "provenance.json": "provenance",
        }
    elif family == "standalone":
        binary = payload / collect.standalone.TARGETS[target][3]
        binary.write_bytes(b"fixture frozen bytes, not runnable")
        sums = payload / (binary.name + ".sha256")
        sums.write_text(collect.standalone.checksum(binary))
        roles = {binary.name: "binary", sums.name: "checksum"}
    elif family == "mini":
        roles = collect.mini.names(candidate, target)
        binary = payload / next(
            name for name, role in roles.items() if role == "binary"
        )
        binary.write_bytes(elf(machine=collect.mini.TARGETS[target][2]))
        (payload / (binary.name + ".sha256")).write_text(
            collect.standalone.checksum(binary)
        )
        (payload / (binary.name + ".build-info")).write_text("fixture rustc\n")
        (payload / "RELEASE-NOTES.md").write_text(collect.mini.notes(candidate))
        details["static_elf"] = collect.mini.static_elf(binary, target)
    elif family == "desktop":
        suffix, data = (
            (".msi", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
            if "windows" in target
            else (".dmg", b"koly" + bytes(508))
            if "macos" in target
            else (".deb", b"!<arch>\n")
        )
        installer = payload / ("installer-001" + suffix)
        installer.write_bytes(data)
        runtime = "bundled-core.exe" if "windows" in target else "bundled-core"
        (payload / runtime).write_bytes(b"fixture bundled Core, not runnable")
        roles = {installer.name: "installer", runtime: "bundled-core"}
        details = {
            "metadata": {
                "release_version": candidate["version"],
                "mapped_version": candidate["metadata_version"],
                "resource_mapping": {"resources/bin/*": "bin/"},
                "apple_version": ".".join(map(str, candidate["version_parts"][:3])),
            },
            "runtime_sha256": proof.file_digest(payload / runtime),
            "runtime_checks": dict.fromkeys(proof.CONTRACTS["standalone"][1], "passed"),
            "installers": [
                {
                    "path": installer.name,
                    "public_name": "lifetxt "
                    + candidate["version"]
                    + " "
                    + target
                    + suffix,
                    "format": suffix,
                }
            ],
            "not_verified": list(collect.desktop.NOT_VERIFIED),
        }
    else:
        oci_fixture(image, candidate, collect.layout.TARGETS[target])
        archive = payload / collect.oci.archive_name(candidate, target)
        with tarfile.open(archive, "w") as stream:
            for relative in collect.layout.inventory(image):
                stream.add(image / relative, arcname=relative)
        roles = {archive.name: "oci-layout"}
        details["oci"] = collect.layout.validate(image, candidate, target)
    return roles, details


class PreflightCollectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.candidate = proof.candidate(
            actions.REPOSITORY, "1.0.4.2", "a" * 40, "b" * 40, 123, 1
        )
        self.api = FakeActions(self.candidate)
        self.ci = actions.main_ci(self.api, "a" * 40, 900)
        self.needs = {
            name: {"result": "success"} for name in ("prepare", *actions.FAMILIES)
        }
        self.context = {
            "GITHUB_REPOSITORY": actions.REPOSITORY,
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW_REF": actions.REPOSITORY
            + "/"
            + actions.WORKFLOW
            + "@refs/heads/main",
            "GITHUB_WORKFLOW_SHA": "b" * 40,
            "GITHUB_SHA": "b" * 40,
        }
        self.components = []
        for target in proof.TARGETS:
            family = target.split("-", 1)[0]
            payload, reports = (
                self.root / "payloads" / target,
                self.root / "proofs" / target,
            )
            reports.mkdir(parents=True)
            roles, details = payload_fixture(
                self.candidate, target, payload, self.root / "images" / target
            )
            report = {
                "schema_version": 1,
                "candidate_digest": self.candidate["digest"],
                **{
                    key: self.candidate[key]
                    for key in ("source_sha", "controller_sha", "run_id", "run_attempt")
                },
                "observed_version": self.candidate["version"],
                "toolchain": {"python": "fixture, not native"},
                "checks": dict.fromkeys(proof.CONTRACTS[family][1], "passed"),
                "files": [
                    {
                        "path": p.name,
                        "role": roles[p.name],
                        "sha256": proof.file_digest(p),
                        "bytes": p.stat().st_size,
                    }
                    for p in sorted(payload.iterdir())
                ],
                **details,
            }
            if family != "core":
                report["target"] = target
            if family == "desktop":
                report.pop("observed_version")
                stage = {key: report[key] for key in collect.desktop.STAGE_FIELDS}
                proof.write_new(reports / "desktop-stage.json", proof.sealed(stage))
                report["toolchain"] = {**report["toolchain"], "cargo": "fixture"}
            report = proof.sealed(report)
            artifact, proof_artifact = [
                next(
                    row
                    for row in self.api.artifacts
                    if row["name"]
                    == actions.artifact_name(self.candidate, target, kind)
                )
                for kind in ("payload", "proof")
            ]
            self.api.pack(artifact, payload)
            producer = collect.PRODUCERS[family]
            arguments = (self.candidate, report, payload, collect.reference(artifact))
            component = (
                producer.finish(*arguments)
                if family == "core"
                else producer.finish(*arguments, target)
            )
            self.components.append(component)
            proof.write_new(reports / "candidate.json", self.candidate)
            proof.write_new(reports / (family + "-component.json"), component)
            proof.write_new(
                reports
                / (
                    family
                    + (
                        "-bundle-report.json"
                        if family == "desktop"
                        else "-build-report.json"
                    )
                ),
                report,
            )
            self.api.pack(proof_artifact, reports)

    def collect(self, output=None):
        with patch.object(collect, "trusted_context"):
            return collect.collect(
                self.candidate,
                self.ci,
                ROOT,
                output or self.root / "verified",
                self.needs,
                self.context,
                self.api,
            )

    def repack(self, target, kind):
        row = next(
            row
            for row in self.api.artifacts
            if row["name"] == actions.artifact_name(self.candidate, target, kind)
        )
        self.api.pack(
            row, self.root / ("payloads" if kind == "payload" else "proofs") / target
        )

    def test_all_13_real_validators_and_final_index_are_bound(self):
        result = self.collect()
        bundle = self.root / "verified"
        self.assertIs(result["publication_authorized"], False)
        self.assertEqual(result["status"], "preflight_verified")
        self.assertEqual(len(result["artifacts"]), 13)
        self.assertEqual(result["main_ci"], self.ci)
        self.assertEqual(
            result["oci_index_digest"],
            "sha256:" + proof.file_digest(bundle / "oci/index.json"),
        )
        aggregate = proof.load(bundle / "components.json")
        self.assertEqual(
            aggregate["components"],
            sorted(self.components, key=lambda row: row["target"]),
        )
        self.assertEqual(result["aggregate_digest"], aggregate["digest"])
        for row in result["files"]:
            self.assertEqual(row["sha256"], proof.file_digest(bundle / row["path"]))
        self.assertNotIn(
            "preflight-bundle.json", {row["path"] for row in result["files"]}
        )
        desktop = bundle / "proofs/desktop-macos-arm64/desktop-bundle-report.json"
        self.assertIn(" ", proof.load(desktop)["installers"][0]["public_name"])

    def test_missing_failed_skipped_dependencies_cannot_leave_success(self):
        for status in ("failure", "skipped", "cancelled"):
            self.needs["core"]["result"] = status
            with self.assertRaises(ValueError):
                self.collect()
            self.assertFalse((self.root / "verified").exists())

    def test_changed_main_ci_attempt_and_controller_context_fail(self):
        self.api.ci["run_attempt"] = 2
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse((self.root / "verified").exists())

    def test_payload_tamper_after_upload_is_rejected(self):
        row = self.api.artifacts[0]
        self.api.archives[row["id"]] += b"tamper"
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse((self.root / "verified").exists())

    def test_wrong_producer_candidate_and_extra_proof_file_rejected(self):
        target = "core-any"
        path = self.root / "proofs" / target / "candidate.json"
        path.write_text(
            json.dumps(
                proof.candidate(actions.REPOSITORY, "1.0.4", "a" * 40, "b" * 40, 123, 1)
            )
        )
        self.repack(target, "proof")
        with self.assertRaises(ValueError):
            self.collect()
        path.write_text(json.dumps(self.candidate))
        (path.parent / "extra.json").write_text("{}")
        self.repack(target, "proof")
        with self.assertRaises(ValueError):
            self.collect()

    def test_component_artifact_digest_cannot_be_rebound(self):
        target = "standalone-linux-x86_64"
        path = self.root / "proofs" / target / "standalone-component.json"
        row = proof.load(path)
        row.pop("digest")
        row["artifact"]["sha256"] = "f" * 64
        path.write_text(json.dumps(proof.sealed(row)))
        self.repack(target, "proof")
        with self.assertRaises(ValueError):
            self.collect()

    def test_desktop_stage_disagreement_is_rejected(self):
        target = "desktop-linux-x86_64"
        path = self.root / "proofs" / target / "desktop-stage.json"
        row = proof.load(path)
        row.pop("digest")
        row["runtime_sha256"] = "f" * 64
        path.write_text(json.dumps(proof.sealed(row)))
        self.repack(target, "proof")
        with self.assertRaises(ValueError):
            self.collect()

    def test_api_state_change_during_download_cannot_emit_success(self):
        original = self.api.download

        def download(row, destination):
            original(row, destination)
            self.api.artifacts[-1]["expired"] = True

        self.api.download = download
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse((self.root / "verified").exists())

    def test_archive_order_does_not_change_final_index(self):
        first = self.collect(self.root / "first")
        self.api.jobs.reverse()
        self.api.artifacts.reverse()
        second = self.collect(self.root / "second")
        self.assertEqual(first, second)

    def test_prepare_pins_explicit_version_and_checks_main_ancestry(self):
        with (
            patch.object(collect.core, "validate_context"),
            patch.object(collect.core, "git") as git,
        ):
            candidate = collect.prepare(
                "a" * 40,
                "1.0.4.2",
                900,
                ROOT,
                self.root / "candidate.json",
                self.root / "outputs",
                self.context,
                self.api,
            )
        self.assertEqual(candidate, self.candidate)
        git.assert_called_once_with(
            ROOT, "merge-base", "--is-ancestor", "a" * 40, "origin/main"
        )
        self.assertIn("candidate_json=", (self.root / "outputs").read_text())
        self.assertIn("main_ci_json=", (self.root / "outputs").read_text())

    def test_foreign_ref_fork_and_workflow_context_rejected(self):
        for key, value in (
            ("GITHUB_REF", "refs/heads/other"),
            ("GITHUB_EVENT_NAME", "pull_request"),
            (
                "GITHUB_WORKFLOW_REF",
                "fork/lifetxt/.github/workflows/release-preflight.yml@refs/heads/main",
            ),
            ("GITHUB_WORKFLOW_SHA", "c" * 40),
        ):
            context = {**self.context, key: value}
            with (
                patch.object(collect.core, "validate_context"),
                self.assertRaises(ValueError),
            ):
                collect.trusted_context(self.candidate, ROOT, context)

    def test_workflow_dependency_permissions_and_no_automatic_trigger(self):
        raw = (ROOT / ".github/workflows/release-preflight.yml").read_text()
        workflow = yaml.load(raw, Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(
            workflow["permissions"], {"contents": "read", "actions": "read"}
        )
        jobs = workflow["jobs"]
        self.assertEqual(set(jobs["collect"]["needs"]), {"prepare", *actions.FAMILIES})
        self.assertIn("always()", jobs["collect"]["if"])
        for family in actions.FAMILIES:
            self.assertIn("prepare", jobs[family]["needs"])
            self.assertEqual(jobs[family]["permissions"], {"contents": "read"})
            self.assertNotIn("secrets", jobs[family])
        self.assertIn("standalone", jobs["desktop"]["needs"])
        for forbidden in (
            ": write",
            "secrets.",
            "environment:",
            "id-token",
            "workflow_run:",
            "pull_request:",
            "push:",
        ):
            self.assertNotIn(forbidden, raw)


if __name__ == "__main__":
    unittest.main()
