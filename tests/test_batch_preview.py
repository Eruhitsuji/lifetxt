"""Contextual review contract, privacy, compatibility and bounded failures."""

import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

from lifetxt import webapp
from lifetxt.workspace_context_snapshot import WorkspaceContextUnavailable

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "Web dependencies unavailable")
class BatchPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.main = os.path.join(self.temp.name, "private-main.txt")
        self.other = os.path.join(self.temp.name, "private-other.txt")
        self.write(self.main, "[ ] T Existing id:existing\n")
        self.write(self.other, "[ ] T Other id:other\n")
        self.client = TestClient(
            webapp.create_app(paths=[self.main, self.other], writable_path=self.main)
        )
        self.addCleanup(self.client.close)

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def preview(self, text, client=None):
        response = (client or self.client).post(
            "/api/items/preview", json={"text": text}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(self.temp.name, response.text)
        self.assertNotIn("private-main.txt", response.text)
        return response.json()

    def test_existing_and_forward_references(self):
        data = self.preview(
            "[ ] T A id:a depends_on:existing ref:other related:b\n[ ] T B id:b\n"
        )
        self.assertTrue(data["ok"])
        self.assertFalse(any(d["code"] == "W215" for d in data["diagnostics"]))
        self.assertEqual(data["review_scope"]["source_count"], 2)

    def test_warning_kinds_and_full_body_details(self):
        text = '[ ] T A id:a depends_on:b due:2026-02-30 custom_flag:yes\n[ ] T B id:b depends_on:a ref:missing\n[N] N Note body:"full body"\n'
        data = self.preview(text)
        self.assertTrue(data["ok"])
        codes = {d["code"] for d in data["diagnostics"]}
        self.assertTrue({"W215", "W227", "W203", "W106"} <= codes, codes)
        self.assertTrue(all(d["severity"] == "warning" for d in data["diagnostics"]))
        self.assertEqual(data["items"][2]["details"]["body"], ["full body"])
        self.assertEqual(data["items"][0]["details"]["depends_on"], ["b"])

    def test_ambiguous_reference_and_all_id_values_block(self):
        for text in [
            "[ ] T A id:one id:other ref:other\n",
            "[ ] T A id:a id:a\n",
            "[ ] T A id:a\n[ ] T B id:a\n",
        ]:
            data = self.preview(text)
            self.assertFalse(data["ok"])
            self.assertTrue(
                any(
                    d["code"] == "DUPLICATE_ID" and d["severity"] == "error"
                    for d in data["diagnostics"]
                )
            )
        data = self.preview("[ ] T A id:other\n[ ] T B ref:other\n")
        self.assertIn("W218", {d["code"] for d in data["diagnostics"]})

    def test_context_token_binds_exact_input_and_nonwritable_source(self):
        text = "[ ] T A id:a\n"
        first = self.preview(text)
        self.assertEqual(first["context_token"], self.preview(text)["context_token"])
        self.assertEqual(
            first["input_digest"], hashlib.sha256(text.encode()).hexdigest()
        )
        self.assertNotEqual(
            first["context_token"], self.preview(text + "\n")["context_token"]
        )
        self.write(self.other, "[ ] T Changed id:changed\n")
        changed = self.preview(text)
        self.assertEqual(first["source_revision"], changed["source_revision"])
        self.assertNotEqual(first["context_token"], changed["context_token"])

    def test_workspace_errors_and_cross_source_cycle(self):
        self.write(self.other, "[ ] T Other id:other depends_on:a\n")
        data = self.preview("[ ] T A id:a depends_on:other\n")
        self.assertIn("W227", {d["code"] for d in data["diagnostics"]})
        self.write(self.other, "#! format_version: 2\n[ ] T Other id:other\n")
        data = self.preview("[ ] T A\n")
        self.assertFalse(data["ok"])
        self.assertTrue(
            any(
                d["scope"] == "workspace" and d["severity"] == "error"
                for d in data["diagnostics"]
            )
        )

    def test_limits_invalid_input_and_format(self):
        for payload, status in [
            (None, 400),
            ({"text": 1}, 400),
            ({"text": "あ" * 180000}, 413),
            ({"text": "[ ] T A\n" * 501}, 422),
            ({"text": "#! format_version: 2\n[ ] T A\n"}, 422),
        ]:
            response = self.client.post("/api/items/preview", json=payload)
            # Null is a missing required JSON body at the framework boundary.
            self.assertEqual(
                response.status_code, 422 if payload is None else status, response.text
            )
        data = self.preview("[ ] T A\n" * 500)
        self.assertEqual(len(data["items"]), 500)
        self.assertEqual(data["review_scope"]["omitted_records"], 0)
        self.assertFalse(self.preview("")["ok"])

    def test_all_records_diagnostics_and_exact_byte_limit(self):
        text = "".join(
            '[N] N Note%d body:"body %d" ref:missing%d\n' % (i, i, i) for i in range(12)
        )
        data = self.preview(text)
        self.assertEqual(len(data["items"]), 12)
        self.assertEqual(data["items"][-1]["details"]["body"], ["body 11"])
        self.assertEqual(sum(d["code"] == "W215" for d in data["diagnostics"]), 12)
        text = "[ ] T A\n#" + "a" * (512 * 1024 - 9)
        self.assertEqual(len(text.encode()), 512 * 1024)
        self.assertTrue(self.preview(text)["ok"])
        self.assertEqual(
            self.client.post(
                "/api/items/preview", json={"text": text + "a"}
            ).status_code,
            413,
        )

    def test_fail_closed_and_no_source_path_leak(self):
        os.remove(self.other)
        response = self.client.post("/api/items/preview", json={"text": "[ ] T A\n"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(self.temp.name, response.text)
        self.assertNotIn("context_token", response.json())
        for reason in [
            "snapshot_unstable",
            "manifest_unavailable",
            "source_membership_changed",
        ]:
            with patch(
                "lifetxt.batch_preview.read_workspace_context",
                side_effect=WorkspaceContextUnavailable(reason),
            ):
                response = self.client.post(
                    "/api/items/preview", json={"text": "[ ] T A\n"}
                )
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["reason"], reason)

    def test_read_only_and_legacy_compatibility(self):
        with TestClient(webapp.create_app(paths=[self.main], read_only=True)) as client:
            data = self.preview("[ ] T A ref:missing\n", client)
            self.assertTrue(data["read_only"])
            self.assertTrue(data["ok"])
            self.assertEqual(
                client.post("/api/items/batch", json={"text": "[ ] T A"}).status_code,
                403,
            )
        legacy = self.client.post(
            "/api/items/parse", json={"line": "[ ] T A ref:missing\n"}
        ).json()
        self.assertTrue(legacy["ok"])
        self.assertNotIn("context_token", legacy)
        self.assertNotIn("W215", {d["code"] for d in legacy["diagnostics"]})

    def test_custom_id_key_and_preview_needs_no_write_revision(self):
        self.write(self.main, "[ ] T Existing uid:existing\n")
        with TestClient(
            webapp.create_app(
                paths=[self.main],
                config={
                    "ids": {"key": "uid"},
                },
            )
        ) as client:
            data = self.preview("[ ] T A uid:a ref:existing\n", client)
            self.assertTrue(data["ok"])
            self.assertNotIn("W215", {d["code"] for d in data["diagnostics"]})
            self.assertFalse(self.preview("[ ] T A uid:existing\n", client)["ok"])

    def test_manifest_membership_change_requires_resolution(self):
        config = {
            "workspaces": {
                "default": {"sources": [self.main, self.other], "write_file": self.main}
            }
        }
        with TestClient(
            webapp.create_app(
                paths=[self.main, self.other], writable_path=self.main, config=config
            )
        ) as client:
            self.assertTrue(self.preview("[ ] T A\n", client)["ok"])
            client.app.state.config["workspaces"]["default"]["sources"] = [self.main]
            response = client.post("/api/items/preview", json={"text": "[ ] T A\n"})
            self.assertEqual(response.status_code, 503, response.text)
            self.assertEqual(response.json()["reason"], "source_membership_changed")

    def test_legacy_dynamic_glob_membership_is_rechecked(self):
        config = {
            "paths": [os.path.join(self.temp.name, "*.txt")],
            "write_file": self.main,
        }
        with TestClient(
            webapp.create_app(
                paths=[self.main, self.other], writable_path=self.main, config=config
            )
        ) as client:
            self.assertTrue(self.preview("[ ] T A\n", client)["ok"])
            self.write(
                os.path.join(self.temp.name, "z-added.txt"), "[ ] T Added id:added\n"
            )
            response = client.post("/api/items/preview", json={"text": "[ ] T A\n"})
            self.assertEqual(response.status_code, 503, response.text)
            self.assertEqual(response.json()["reason"], "source_membership_changed")

    def test_existing_bearer_auth_and_readonly_clock_exemption(self):
        config = {
            "api": {"token": "synthetic-test-token"},
            "clock": {"require_remote_write_time": True},
        }
        with TestClient(webapp.create_app(paths=[self.main], config=config)) as client:
            response = client.post("/api/items/preview", json={"text": "[ ] T A\n"})
            self.assertEqual(response.status_code, 401)
            response = client.post(
                "/api/items/preview",
                json={"text": "[ ] T A\n"},
                headers={"Authorization": "Bearer synthetic-test-token"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["ok"])
