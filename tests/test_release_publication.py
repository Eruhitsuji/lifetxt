"""Execute the release trust boundaries against disposable complete/partial services."""

import base64
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
import zipfile
from pathlib import Path
from unittest.mock import patch

import yaml

from tests.test_release_preflight_collect import PreflightCollectTests
from tests.test_release_preflight_oci import fixture as oci_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_canonical as canonical  # noqa: E402
import release_channels as channels  # noqa: E402
import release_plan as plans  # noqa: E402
import release_orchestrate as orchestrate  # noqa: E402
import release_preflight_proof as proof  # noqa: E402
import release_recovery as recovery  # noqa: E402
import release_remote as remote  # noqa: E402


class CompletePreflight:
    def __init__(self, case):
        self.fixture = PreflightCollectTests()
        self.fixture.setUp()
        case.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.api = self.fixture.api
        self.manifest = self.fixture.collect()
        self.bundle = self.root / "verified"
        self.candidate = self.fixture.candidate
        self.api.run.update(status="completed", conclusion="success")
        self.api.jobs.append(
            {
                "id": 3000,
                "run_id": 123,
                "head_sha": "b" * 40,
                "name": "Verify all 13 targets",
                "status": "completed",
                "conclusion": "success",
                "started_at": "2020-01-01T00:20:00Z",
                "completed_at": "2020-01-01T00:40:00Z",
            }
        )
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for path in sorted(self.bundle.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(self.bundle).as_posix())
        data = stream.getvalue()
        self.artifact = {
            **copy.deepcopy(self.api.artifacts[0]),
            "id": 4000,
            "name": "preflight-verified-123-1",
            "created_at": "2020-01-01T00:30:00Z",
            "size_in_bytes": len(data),
            "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
        }
        self.api.artifacts.append(self.artifact)
        self.api.archives[4000] = data
        original = self.api.get
        self.api.get = lambda path: (
            copy.deepcopy(self.artifact)
            if path == "/actions/artifacts/4000"
            else original(path)
        )

    def prepare(self, name="prepared"):
        with (
            patch.object(plans, "release_context", return_value=("c" * 40, 555, 1)),
            patch.object(plans.core, "git", return_value=""),
        ):
            return plans.prepare(
                self.api, ROOT, self.root / name, 4000, self.manifest["digest"], {}
            )


class ReleasePlanTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CompletePreflight(self)
        self.root = self.fixture.root

    def test_complete_transport_and_original_payloads_create_one_bound_plan(self):
        plan = self.fixture.prepare()
        public = self.root / "prepared/public"
        rows = canonical.staged_rows(public)
        self.assertEqual(
            plan["inventory_digest"],
            proof.load(public / "release-inventory.json")["digest"],
        )
        self.assertEqual(plan["bundle_digest"], self.fixture.manifest["digest"])
        self.assertEqual("1.0.4.2", plan["candidate"]["version"])
        self.assertTrue(any("desktop-windows" in r["name"] for r in rows))
        self.assertFalse(
            any(
                "bundled-core" in r["name"] or r["name"].endswith(".oci.tar")
                for r in rows
            )
        )
        notes = [
            r
            for r in proof.load(public / "release-inventory.json")["assets"]
            if r["role"] == "notes"
        ]
        self.assertEqual(1, len(notes))
        self.assertEqual(2, len(notes[0]["targets"]))
        self.assertNotIn(b"\r", (public / "SHA256SUMS").read_bytes())

    def test_stale_attempt_failure_expiry_and_collector_identity_are_rejected(self):
        for collection, key, value in (
            (self.fixture.api.run, "run_attempt", 2),
            (self.fixture.api.run, "conclusion", "failure"),
            (self.fixture.artifact, "expired", True),
            (self.fixture.api.jobs[-1], "head_sha", "f" * 40),
            (self.fixture.api.jobs[-1], "conclusion", "skipped"),
        ):
            old = collection[key]
            collection[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.fixture.prepare("reject-" + key + str(value))
            collection[key] = old

    def test_changed_payload_zip_and_bundle_digest_are_rejected(self):
        original = self.fixture.api.archives[2000]
        self.fixture.api.archives[2000] = original + b"tamper"
        with self.assertRaises(ValueError):
            self.fixture.prepare()
        self.fixture.api.archives[2000] = original
        self.fixture.manifest["digest"] = "d" * 64
        with self.assertRaises(ValueError):
            self.fixture.prepare("different-digest")

    def test_nested_zip_traversal_aliases_and_symlinks_are_rejected(self):
        for name in (
            "../escape",
            "/absolute",
            "a/../../escape",
            "a\\evil",
            "a/CON",
            "x./file",
        ):
            archive = self.root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as source:
                source.writestr(name, b"payload")
            with self.subTest(name=name), self.assertRaises(ValueError):
                plans.extract_bundle(
                    archive,
                    self.root / ("extract-" + str(len(list(self.root.iterdir())))),
                )
        self.assertFalse((self.root.parent / "escape").exists())

    def test_real_release_context_rejects_branch_workflow_and_sha_drift(self):
        context = {
            "GITHUB_REPOSITORY": "Eruhitsuji/lifetxt",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW_REF": "Eruhitsuji/lifetxt/.github/workflows/release.yml@refs/heads/main",
            "GITHUB_WORKFLOW_SHA": "c" * 40,
            "GITHUB_SHA": "c" * 40,
            "GITHUB_RUN_ID": "555",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        run = {
            **self.fixture.api.run,
            "head_sha": "c" * 40,
            "id": 555,
            "path": ".github/workflows/release.yml",
            "status": "in_progress",
            "run_attempt": 1,
        }
        with (
            patch.object(
                plans.core,
                "git",
                side_effect=lambda root, *args: "" if args[0] == "status" else "c" * 40,
            ),
            patch.object(self.fixture.api, "get", return_value=run),
        ):
            self.assertEqual(
                ("c" * 40, 555, 1),
                plans.release_context(ROOT, context, self.fixture.api),
            )
            for key, value in (
                ("GITHUB_REF", "refs/tags/v1.0.4.2"),
                (
                    "GITHUB_WORKFLOW_REF",
                    "Eruhitsuji/lifetxt/.github/workflows/other.yml@refs/heads/main",
                ),
                ("GITHUB_SHA", "e" * 40),
            ):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    plans.release_context(
                        ROOT, {**context, key: value}, self.fixture.api
                    )

    def test_authority_requires_exact_human_environment_comment_and_attempt(self):
        plan = self.fixture.prepare()
        review = {
            "state": "approved",
            "user": {"login": "Eruhitsuji", "type": "User"},
            "comment": plans.approval_comment(plan),
            "environments": [{"name": "pypi"}],
        }
        with (
            patch.object(plans, "release_context", return_value=("c" * 40, 555, 1)),
            patch.object(self.fixture.api, "get", return_value=[review]),
        ):
            self.assertEqual(
                "Eruhitsuji",
                plans.authorize(self.fixture.api, plan, ROOT, {})["reviewer"],
            )
            for key, value in (
                ("comment", "Ship it"),
                ("state", "rejected"),
                ("user", {"login": "Eruhitsuji", "type": "Bot"}),
                ("environments", [{"name": "other"}]),
            ):
                with (
                    self.subTest(key=key),
                    patch.object(
                        self.fixture.api, "get", return_value=[{**review, key: value}]
                    ),
                    self.assertRaises(ValueError),
                ):
                    plans.authorize(self.fixture.api, plan, ROOT, {})
            with (
                patch.object(self.fixture.api, "get", return_value=[]),
                self.assertRaises(ValueError),
            ):
                plans.authorize(self.fixture.api, plan, ROOT, {})
        with (
            patch.object(plans, "release_context", return_value=("c" * 40, 555, 2)),
            self.assertRaises(ValueError),
        ):
            plans.authorize(self.fixture.api, plan, ROOT, {})


class CanonicalPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CompletePreflight(self)
        self.plan = self.fixture.prepare()
        self.public = self.fixture.root / "prepared/public"
        self.expected = canonical.staged_rows(self.public)

    def test_historical_nine_only_and_missing_desktop_never_finalize(self):
        fixture = proof.load(
            ROOT / "tests/fixtures/release-publication/v1.0.4.1-assets.json"
        )
        expected = [
            {"name": r["name"], "sha256": r["digest"][7:], "bytes": r["size"]}
            for r in fixture["assets"]
        ]
        self.assertEqual(23, len(expected))
        actual = [
            {"name": r["name"], "digest": "sha256:" + r["sha256"], "size": r["bytes"]}
            for r in expected
        ]
        original_nine = [
            r
            for r in actual
            if r["name"].endswith((".whl", ".tar.gz"))
            or (
                r["name"].startswith("lifetxt-")
                and not r["name"].endswith((".build-info", ".sha256"))
            )
        ]
        self.assertEqual(9, len(original_nine))
        without_desktop = [
            r for r in actual if not r["name"].startswith("lifetxt.Desktop")
        ]
        self.assertEqual(6, len(actual) - len(without_desktop))
        for incomplete in (original_nine, without_desktop):
            with self.assertRaises(ValueError):
                canonical.remote_inventory(expected, incomplete, True)
        self.assertEqual(
            [], canonical.remote_inventory(expected, list(reversed(actual)), True)
        )
        self.assertEqual(
            canonical.checksum_bytes(expected),
            canonical.checksum_bytes(list(reversed(expected))),
        )

    def test_duplicate_case_crlf_hash_missing_and_extra_are_closed(self):
        raw = (self.public / "SHA256SUMS").read_bytes()
        for changed in (
            raw.replace(b"\n", b"\r\n"),
            raw + raw.splitlines(keepends=True)[0],
            raw.replace(raw[:64], b"0" * 64, 1),
            raw.split(b"\n", 1)[1],
        ):
            with self.assertRaises(ValueError):
                canonical.validate_checksums(changed, self.expected[:-1])
        with self.assertRaises(ValueError):
            canonical.checksum_bytes(
                [
                    {"name": "Foo", "sha256": "a" * 64},
                    {"name": "foo", "sha256": "a" * 64},
                ]
            )
        actual = [
            {"name": r["name"], "digest": "sha256:" + r["sha256"], "size": r["bytes"]}
            for r in self.expected
        ]
        actual[0]["digest"] = "sha256:" + "0" * 64
        with self.assertRaises(ValueError):
            canonical.remote_inventory(self.expected, actual, False)

    def test_primary_then_one_finalizer_idempotence_and_no_clobber(self):
        api = remote.Remote()
        release = {"id": 99, "tag_name": self.plan["candidate"]["tag"]}
        assets, uploaded = [], []

        def upload(*args, **kwargs):
            self.assertNotIn("--clobber", args)
            path = Path(args[4])
            self.assertNotIn(path.name, {r["name"] for r in assets})
            assets.append(
                {
                    "id": len(assets) + 1,
                    "name": path.name,
                    "size": path.stat().st_size,
                    "digest": "sha256:" + proof.file_digest(path),
                }
            )
            uploaded.append(path.name)

        with (
            patch.object(api, "ensure_release", return_value=release),
            patch.object(api, "assets", side_effect=lambda r: copy.deepcopy(assets)),
            patch.object(
                api,
                "asset_bytes",
                side_effect=lambda r: (self.public / r["name"]).read_bytes(),
            ),
            patch.object(remote, "command", side_effect=upload),
        ):
            with self.assertRaises(ValueError):
                api.upload_missing(self.plan, self.public, finalize=True)
            api.upload_missing(self.plan, self.public)
            self.assertNotIn("SHA256SUMS", uploaded)
            api.upload_missing(self.plan, self.public, finalize=True)
            count = len(uploaded)
            api.upload_missing(self.plan, self.public, finalize=True)
            api.upload_missing(self.plan, self.public)
            self.assertEqual(count, len(uploaded))
            self.assertEqual("SHA256SUMS", uploaded[-1])
            assets[0]["digest"] = "sha256:" + "0" * 64
            with self.assertRaises(ValueError):
                api.upload_missing(self.plan, self.public)
            self.assertEqual(count, len(uploaded))

    def test_tag_identity_and_zero_alias_cannot_be_replaced(self):
        api = remote.Remote()
        candidate = proof.candidate(
            "Eruhitsuji/lifetxt", "1.2.3.0", "a" * 40, "b" * 40, 1, 1
        )
        with (
            patch.object(
                api,
                "tag_source",
                side_effect=lambda tag: "e" * 40 if tag.endswith(".0") else None,
            ),
            patch.object(api, "mutate") as mutation,
            self.assertRaises(ValueError),
        ):
            api.ensure_tag(candidate)
        mutation.assert_not_called()
        with (
            patch.object(api, "tag_source", return_value="e" * 40),
            patch.object(api, "mutate") as mutation,
            self.assertRaises(ValueError),
        ):
            api.ensure_tag(self.plan["candidate"])
        mutation.assert_not_called()

    def test_public_download_not_api_digest_alone_gates_acceptance(self):
        api = remote.Remote()
        expected = self.expected
        prefix = (
            "https://github.com/Eruhitsuji/lifetxt/releases/download/"
            + self.plan["candidate"]["tag"]
            + "/"
        )
        assets = [
            {
                "id": i + 1,
                "name": r["name"],
                "size": r["bytes"],
                "digest": "sha256:" + r["sha256"],
                "browser_download_url": prefix + urllib.parse.quote(r["name"], safe=""),
            }
            for i, r in enumerate(expected)
        ]
        with (
            patch.object(api, "optional", return_value={"id": 5}),
            patch.object(
                api, "tag_source", return_value=self.plan["candidate"]["source_sha"]
            ),
            patch.object(api, "assets", return_value=assets),
            patch.object(
                remote,
                "fetch",
                side_effect=lambda url: (
                    self.public / urllib.parse.unquote(url.rsplit("/", 1)[1])
                ).read_bytes(),
            ),
        ):
            channels.verify_github(
                api, self.plan, self.public, self.fixture.root / "remote-good"
            )
            with (
                patch.object(remote, "fetch", return_value=b"wrong"),
                self.assertRaises(ValueError),
            ):
                channels.verify_github(
                    api, self.plan, self.public, self.fixture.root / "remote-bad"
                )

    def test_pypi_partial_stage_and_conflicting_remote_never_skip_existing(self):
        inventory = proof.load(self.public / "release-inventory.json")
        packages = [r for r in inventory["assets"] if r["role"] in ("wheel", "sdist")]
        one = packages[0]
        published = {
            "info": {"version": self.plan["candidate"]["version"]},
            "urls": [
                {
                    "filename": one["name"],
                    "size": one["bytes"],
                    "digests": {"sha256": one["sha256"]},
                    "yanked": False,
                    "url": "https://files.pythonhosted.org/" + one["name"],
                }
            ],
        }

        def fetch(url, **kwargs):
            return (
                json.dumps(published).encode()
                if url.startswith("https://pypi.org/")
                else (self.public / one["name"]).read_bytes()
            )

        pending = self.fixture.root / "pypi-pending"
        with patch.object(remote, "fetch", side_effect=fetch):
            remote.pypi_files(self.plan["candidate"], self.public, pending)
            self.assertEqual({packages[1]["name"]}, {p.name for p in pending.iterdir()})
            with self.assertRaises(ValueError):
                remote.pypi_files(self.plan["candidate"], self.public)
            published["urls"][0]["digests"]["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                remote.pypi_files(self.plan["candidate"], self.public, pending)

    def test_registry_transport_preserves_the_actual_index_and_original_graph(self):
        registry = object.__new__(remote.Registry)
        root = self.fixture.root / "prepared/oci"
        original = {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file()
        }
        tags, calls = {}, []

        def manifest(tag, missing=False):
            if tag in tags:
                return tags[tag]
            if missing:
                return None
            return (root / "blobs/sha256" / tag[7:]).read_bytes()

        def command(*args, **kwargs):
            calls.append(args)
            self.assertNotIn("build", args)
            if args[1] == "copy":
                self.assertIn("--all", args)
                self.assertIn("--preserve-digests", args)
                transport = self.fixture.root / "prepared/oci-publish"
                index = proof.load(transport / "index.json")
                descriptor = index["manifests"][0]
                self.assertEqual(self.plan["oci_index_digest"], descriptor["digest"])
                raw = (
                    transport / "blobs/sha256" / descriptor["digest"][7:]
                ).read_bytes()
                tags[args[-1].rsplit(":", 1)[1]] = raw

        with (
            patch.object(registry, "manifest", side_effect=manifest),
            patch.object(
                registry,
                "blob",
                side_effect=lambda digest: (
                    root / "blobs/sha256" / digest[7:]
                ).read_bytes(),
            ),
            patch.object(remote, "command", side_effect=command),
            patch.dict(
                os.environ, {"GITHUB_ACTOR": "fixture", "GH_TOKEN": "fixture-only"}
            ),
        ):
            registry.publish(self.plan, root)
            self.assertEqual(2, len(tags))
            self.assertEqual(
                original,
                {
                    p.relative_to(root).as_posix(): p.read_bytes()
                    for p in root.rglob("*")
                    if p.is_file()
                },
            )
            tags[self.plan["candidate"]["tag"]] = b"wrong"
            with self.assertRaises(ValueError):
                registry.publish(self.plan, root)
            self.assertEqual(2, len([args for args in calls if args[1] == "copy"]))


class DownstreamAndRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CompletePreflight(self)
        self.plan = self.fixture.prepare()
        self.public = self.fixture.root / "prepared/public"

    def test_generated_is_distinct_from_external_submission_and_published(self):
        generated = self.fixture.root / "generated"
        state = channels.generate(self.plan, self.public, generated)
        self.assertEqual("generated", state["winget"])
        self.assertEqual("manual_required", state["external_submission"])
        self.assertIn('version "1.0.4.2"', (generated / "lifetxt.rb").read_text())
        self.assertIn('set version = "1.0.4.2"', (generated / "meta.yaml").read_text())

    def test_homebrew_compare_and_swap_noop_conflict_and_remote_confirmation(self):
        generated = self.fixture.root / "generated"
        channels.generate(self.plan, self.public, generated)
        content = (generated / "lifetxt.rb").read_bytes()
        state = {
            "sha": "a" * 40,
            "content": base64.b64encode(b'  version "1.0.4.1"\n').decode(),
        }
        calls = []

        def tap(method, value=None):
            calls.append(method)
            if method == "PUT":
                self.assertEqual("a" * 40, value["sha"])
                state.update(content=value["content"], sha="b" * 40)
            return copy.deepcopy(state)

        with patch.object(channels, "tap_api", side_effect=tap):
            self.assertEqual(
                "verified", channels.publish_homebrew(self.plan, generated)["state"]
            )
            channels.publish_homebrew(self.plan, generated)
            self.assertEqual(1, calls.count("PUT"))
            state["content"] = base64.b64encode(content + b"conflict").decode()
            with self.assertRaises(ValueError):
                channels.publish_homebrew(self.plan, generated)
            self.assertEqual(1, calls.count("PUT"))
        with (
            patch.dict(os.environ, {"HOMEBREW_TAP_TOKEN": ""}),
            self.assertRaises(remote.TransportError),
        ):
            channels.tap_api("GET")
        with (
            patch.dict(os.environ, {"HOMEBREW_TAP_TOKEN": "fixture-only"}),
            patch.object(
                channels.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(
                    1, ["gh"], stderr=b"never-record-this"
                ),
            ),
            self.assertRaises(remote.TransportError) as failure,
        ):
            channels.tap_api("GET")
        self.assertNotIn("never-record-this", str(failure.exception))

    def test_required_channels_and_numeric_latest_order_block_all_writes(self):
        api = remote.Remote()
        registry = unittest.mock.Mock()
        receipt = channels.receipt(
            self.plan,
            "verified",
            {
                "github": "verified",
                "pypi": "verified",
                "ghcr": "verified",
                "native": "verified",
                "homebrew": {"state": "verified"},
                "winget": "generated",
                "scoop": "generated",
                "conda": "generated",
            },
            "downstream_verified",
        )
        for key in (
            "github",
            "pypi",
            "ghcr",
            "native",
            "homebrew",
            "winget",
            "scoop",
            "conda",
        ):
            changed = copy.deepcopy(receipt)
            changed["channels"][key] = (
                {"state": "blocked"} if key == "homebrew" else "failed"
            )
            with (
                self.subTest(key=key),
                patch.object(api, "patch") as mutate,
                self.assertRaises(ValueError),
            ):
                channels.promote(api, registry, self.plan, changed)
            mutate.assert_not_called()
        with (
            patch.object(api, "optional", return_value={"tag_name": "v1.0.4.10"}),
            patch.object(api, "patch") as mutate,
            self.assertRaises(ValueError),
        ):
            channels.promote(api, registry, self.plan, receipt)
        mutate.assert_not_called()
        registry.manifest.assert_not_called()

    def test_failure_policy_published_source_fix_and_unchanged_retry(self):
        self.assertEqual(
            "preflight_failure", recovery.classify(published=False)["kind"]
        )
        self.assertEqual(
            "publish_retryable",
            recovery.classify(published=True, same_bytes=True)["kind"],
        )
        correction = recovery.classify(
            published=True, same_bytes=True, source_defect=True
        )
        self.assertEqual("new_human_selected_version", correction["resume"])
        self.assertFalse(correction["latest_allowed"])
        self.assertEqual(
            "external_manual_required",
            recovery.classify(published=True, external=True)["kind"],
        )
        self.assertEqual(
            "critical_blocker",
            recovery.classify(published=False, external=True, critical=True)["kind"],
        )

    def test_cutover_reads_legacy_v_labels_and_bound_buildkit_attestations(self):
        candidate = proof.candidate(
            "Eruhitsuji/lifetxt", "1.0.4.1", "a" * 40, "b" * 40, 123, 1
        )
        rows, blobs = [], {}
        for arch in ("amd64", "arm64"):
            root = self.fixture.root / ("legacy-" + arch)
            descriptor = oci_fixture(
                root,
                candidate,
                arch,
                mutate=lambda config: config["config"]["Labels"].update(
                    {"org.opencontainers.image.version": "v1.0.4.1"}
                ),
            )
            rows.append(
                {**descriptor, "platform": {"os": "linux", "architecture": arch}}
            )
            if arch == "arm64":
                rows[-1]["platform"]["variant"] = "v8"
            blobs.update(
                {
                    "sha256:" + p.name: p.read_bytes()
                    for p in (root / "blobs/sha256").iterdir()
                }
            )
        for i, manifest in enumerate(list(rows)):
            rows.append(
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": "sha256:" + str(i) * 64,
                    "size": 1,
                    "platform": {"os": "unknown", "architecture": "unknown"},
                    "annotations": {
                        "vnd.docker.reference.type": "attestation-manifest",
                        "vnd.docker.reference.digest": manifest["digest"],
                    },
                }
            )
        registry = unittest.mock.Mock()
        registry.manifest.side_effect = lambda digest: blobs[digest]
        registry.blob.side_effect = lambda digest: blobs[digest]
        data = lambda: json.dumps({"schemaVersion": 2, "manifests": rows}).encode()
        self.assertEqual([(1, 0, 4, 1)] * 2, channels.alias_versions(registry, data()))
        rows[-1]["annotations"]["vnd.docker.reference.digest"] = "sha256:" + "f" * 64
        with self.assertRaises(ValueError):
            channels.alias_versions(registry, data())
        rows.pop()
        rows[-1]["annotations"]["vnd.docker.reference.type"] = "unknown"
        with self.assertRaises(ValueError):
            channels.alias_versions(registry, data())

    def test_partial_alias_failure_repairs_same_digest_without_republishing_completed_alias(
        self,
    ):
        api = remote.Remote()
        registry = object.__new__(remote.Registry)
        root = self.fixture.root / "prepared/oci"
        raw = (root / "index.json").read_bytes()
        aliases, writes = {}, []
        receipt = channels.receipt(
            self.plan,
            "verified",
            {
                "github": "verified",
                "pypi": "verified",
                "ghcr": "verified",
                "native": "verified",
                "homebrew": {"state": "verified"},
                "winget": "generated",
                "scoop": "generated",
                "conda": "generated",
            },
            "downstream_verified",
        )

        def manifest(tag, missing=False):
            if tag.startswith("sha256:"):
                return (root / "blobs/sha256" / tag[7:]).read_bytes()
            return aliases.get(tag)

        fail = [True]

        def transport(*args, **kwargs):
            alias = args[-1].rsplit(":", 1)[1]
            if alias == "1" and fail[0]:
                fail[0] = False
                raise remote.TransportError("fixture outage")
            aliases[alias] = raw
            writes.append(alias)

        with (
            patch.object(
                api,
                "optional",
                side_effect=lambda path: (
                    {"tag_name": "v1.0.4.1"}
                    if path == "/releases/latest"
                    else {"id": 9}
                ),
            ),
            patch.object(
                api, "get", return_value={"tag_name": self.plan["candidate"]["tag"]}
            ),
            patch.object(api, "patch") as latest,
            patch.object(registry, "login"),
            patch.object(registry, "manifest", side_effect=manifest),
            patch.object(
                registry,
                "blob",
                side_effect=lambda digest: (
                    root / "blobs/sha256" / digest[7:]
                ).read_bytes(),
            ),
            patch.object(remote, "command", side_effect=transport),
        ):
            with self.assertRaises(remote.TransportError):
                channels.promote(api, registry, self.plan, receipt)
            latest.assert_not_called()
            self.assertEqual(["latest"], writes)
            channels.promote(api, registry, self.plan, receipt)
            self.assertEqual(["latest", "1", "1.0"], writes)
            latest.assert_called_once_with("/releases/9", {"make_latest": "true"})

    def test_downstream_failure_keeps_generated_and_blocked_states_and_never_accepts(
        self,
    ):
        root = self.fixture.root / "prepared"
        receipt = channels.receipt(
            self.plan,
            "primary_verified",
            dict.fromkeys(("github", "pypi", "ghcr", "native"), "verified"),
            "primary_verified",
        )
        orchestrate.write_receipt(root, receipt)
        with (
            patch.object(orchestrate, "validate_stage", return_value=self.plan),
            patch.object(
                channels,
                "publish_homebrew",
                side_effect=remote.TransportError("fixture permission error"),
            ),
            self.assertRaises(SystemExit),
        ):
            # The verified public fixture stands in for independently downloaded bytes.
            import shutil

            shutil.copytree(self.public, root / "downloaded")
            orchestrate.main(
                ["downstream", "--controller", str(ROOT), "--root", str(root)]
            )
        retained = proof.load(root / "release-receipt.json")
        failure = proof.load(root / "release-failure.json")
        self.assertEqual("downstream_generated", retained["state"])
        self.assertEqual("generated", retained["channels"]["winget"])
        self.assertEqual("blocked", retained["channels"]["homebrew"]["state"])
        self.assertEqual("publish_retryable", failure["recovery"]["kind"])
        self.assertTrue(failure["remote_revalidation_required"])

    def test_external_action_failure_and_critical_blocker_are_recorded_without_secrets(
        self,
    ):
        root = self.fixture.root / "prepared"
        with patch.dict(
            os.environ,
            {
                "RELEASE_STEPS_JSON": json.dumps(
                    {
                        "pypi": {
                            "outcome": "failure",
                            "outputs": {"token": "never-record-this"},
                        }
                    }
                )
            },
        ):
            orchestrate.record_job_failure(root)
        failure = proof.load(root / "release-failure.json")
        self.assertEqual(["pypi"], failure["failed_steps"])
        self.assertNotIn("never-record-this", json.dumps(failure))
        with (
            patch.object(plans, "authorize"),
            patch.dict(
                os.environ, {"RELEASE_CRITICAL_BLOCKER": "known critical fixture"}
            ),
            self.assertRaises(ValueError),
        ):
            orchestrate.validate_stage(root, ROOT, self.fixture.api)

    def test_read_only_verification_never_invokes_any_publication_adapter(self):
        root = self.fixture.root / "prepared"
        api = unittest.mock.Mock()
        registry = unittest.mock.Mock()
        with (
            patch.object(orchestrate, "validate_stage", return_value=self.plan),
            patch.object(remote, "Remote", return_value=api),
            patch.object(remote, "Registry", return_value=registry) as registry_factory,
            patch.object(remote, "pypi_files"),
            patch.object(channels, "verify_github"),
            patch.object(plans.core, "validate_source"),
            patch.object(channels, "public_smoke"),
        ):
            self.assertEqual(
                0,
                orchestrate.main(
                    [
                        "verify",
                        "--controller",
                        str(ROOT),
                        "--root",
                        str(root),
                        "--source",
                        str(ROOT),
                    ]
                ),
            )
        registry_factory.assert_called_once_with()
        registry.publish.assert_not_called()
        registry.login.assert_not_called()
        for name in (
            "mutate",
            "patch",
            "ensure_tag",
            "ensure_release",
            "upload_missing",
        ):
            getattr(api, name).assert_not_called()
        self.assertEqual(
            "primary_verified", proof.load(root / "release-receipt.json")["state"]
        )


class CutoverTests(unittest.TestCase):
    def test_http_auth_failure_is_never_treated_as_absence_and_redirect_strips_credentials(
        self,
    ):
        import urllib.error
        import urllib.request

        opener = unittest.mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://ghcr.io/fixture", 403, "forbidden", {}, None
        )
        with (
            patch.object(urllib.request, "build_opener", return_value=opener),
            self.assertRaises(remote.TransportError),
        ):
            remote.fetch("https://ghcr.io/fixture", missing=True)
        opener.open.side_effect = urllib.error.HTTPError(
            "https://ghcr.io/fixture", 404, "missing", {}, None
        )
        with patch.object(urllib.request, "build_opener", return_value=opener):
            self.assertIsNone(remote.fetch("https://ghcr.io/fixture", missing=True))
        request = urllib.request.Request(
            "https://ghcr.io/fixture",
            headers={"Authorization": "Bearer fixture-secret"},
        )
        redirect = remote.SafeRedirect().redirect_request(
            request, None, 302, "redirect", {}, "https://cdn.example.invalid/blob"
        )
        self.assertIsNone(redirect.get_header("Authorization"))

    def test_only_release_manual_main_entry_can_write_after_one_environment(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
        self.assertEqual({"workflow_dispatch"}, set(workflow[True]))
        policy = next(
            s
            for s in workflow["jobs"]["prepare"]["steps"]
            if s.get("name") == "Preserve strict release policy before human approval"
        )
        self.assertIn("scripts/check_release_policy.py", policy["run"])
        self.assertIn("lifetxt safety release-gate", policy["run"])
        self.assertNotIn("--allow-missing-jsonschema", policy["run"])
        self.assertEqual("policy-source", policy["working-directory"])
        self.assertIn(
            "github.ref == 'refs/heads/main'", workflow["jobs"]["prepare"]["if"]
        )
        job = workflow["jobs"]["publish-pypi"]
        self.assertEqual("prepare", job["needs"])
        self.assertEqual({"name": "pypi"}, job["environment"])
        self.assertEqual("write", job["permissions"]["id-token"])
        verify = workflow["jobs"]["verify"]
        self.assertEqual(["prepare", "publish-pypi"], verify["needs"])
        self.assertEqual(
            {"contents": "read", "actions": "read", "packages": "read"},
            verify["permissions"],
        )
        self.assertNotIn("environment", verify)
        self.assertNotIn("HOMEBREW_TAP_TOKEN", json.dumps(verify))
        finish = workflow["jobs"]["finish"]
        self.assertEqual(["prepare", "verify"], finish["needs"])
        self.assertNotIn("environment", finish)
        self.assertNotIn("id-token", finish["permissions"])
        names = [s.get("name", "") for s in finish["steps"]]
        self.assertLess(
            names.index("Generate winget Scoop conda and verify Homebrew update"),
            names.index("Promote verified aliases and GitHub Latest"),
        )
        pypi = next(s for s in job["steps"] if s.get("uses", "").startswith("pypa/"))
        self.assertFalse(pypi["with"]["skip-existing"])

    def test_legacy_tag_dispatch_and_published_event_paths_are_closed_together(self):
        for name in (
            "docker-publish",
            "standalone-binaries",
            "desktop-installers",
            "lifetxt-mini-release",
            "homebrew-tap",
            "package-manifests",
            "conda-recipe",
        ):
            workflow = yaml.safe_load(
                (ROOT / (".github/workflows/" + name + ".yml")).read_text()
            )
            self.assertEqual({"workflow_call"}, set(workflow[True]), name)
            self.assertEqual({"contents": "read"}, workflow["permissions"])
            result = subprocess.run(
                ["bash", "-c", workflow["jobs"]["retired"]["steps"][0]["run"]],
                capture_output=True,
                timeout=5,
            )
            self.assertNotEqual(0, result.returncode, name)
