"""Contextual save, legacy compatibility and deterministic race boundaries."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from lifetxt import mutation, webapp
from lifetxt.workspace_context_snapshot import WorkspaceContextUnavailable
from tests import test_batch_preview as fixture


@unittest.skipIf(fixture.TestClient is None, "Web dependencies unavailable")
class BatchSaveTests(unittest.TestCase):
    setUp = fixture.BatchPreviewTests.setUp
    write = fixture.BatchPreviewTests.write
    preview = fixture.BatchPreviewTests.preview

    def save(self, text, review, client=None, **overrides):
        payload = {
            "text": text,
            "context_token": review["context_token"],
            "expected_source_revision": review["source_revision"],
            **overrides,
        }
        return (client or self.client).post(
            "/api/items/batch",
            json=payload,
            headers={"If-Match": payload["expected_source_revision"]},
        )

    def assert_rejected(self, response, before, code="CONTEXT_CHANGED", status=409):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json()["error"], code)
        self.assertEqual(response.json()["saved"], 0)
        self.assertEqual(Path(self.main).read_bytes(), before)
        self.assertNotIn(self.temp.name, response.text)
        self.assertNotIn("batch-preview-v1:", response.text)

    def test_unchanged_context_saves_once_and_old_token_cannot_replay(self):
        text = "[ ] T A id:a ref:existing\n[ ] T B id:b depends_on:a\n"
        review = self.preview(text)
        response = self.save(text, review)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["saved"], 2)
        before = Path(self.main).read_bytes()
        fresh = self.client.get("/api/health").json()["source_revision"]
        self.assert_rejected(
            self.save(text, review, expected_source_revision=fresh), before
        )

    def test_fresh_health_never_bypasses_old_preview(self):
        text = "[ ] T A id:a\n"
        review = self.preview(text)
        self.write(self.main, "[ ] T Replaced id:replaced\n")
        fresh = self.client.get("/api/health").json()["source_revision"]
        self.assert_rejected(
            self.save(text, review, expected_source_revision=fresh),
            Path(self.main).read_bytes(),
        )

    def test_other_source_change_wins_over_new_duplicate(self):
        text = "[ ] T A id:a\n"
        review = self.preview(text)
        self.write(self.other, "[ ] T Other id:other id:a\n")
        before = Path(self.main).read_bytes()
        self.assert_rejected(self.save(text, review), before)
        latest = self.preview(text)
        self.assertFalse(latest["ok"])
        self.assert_rejected(self.save(text, latest), before, "DUPLICATE_ID", 422)

    def test_exact_input_effective_config_order_and_scope_changes(self):
        text = "[ ] T A id:a\n"
        review = self.preview(text)
        before = Path(self.main).read_bytes()
        self.assert_rejected(self.save(text + "\n", review), before)
        self.client.app.state.config["ids"] = {"key": "uid"}
        self.assert_rejected(self.save(text, review), before)
        review = self.preview(text)
        self.client.app.state.paths.reverse()
        self.assert_rejected(self.save(text, review), before)
        review = self.preview(text)
        self.client.app.state.paths = [self.main]
        self.assert_rejected(self.save(text, review), before)

    def test_missing_unreadable_and_unstable_sources_fail_closed(self):
        text = "[ ] T A id:a\n"
        review = self.preview(text)
        before = Path(self.main).read_bytes()
        os.remove(self.other)
        self.assert_rejected(self.save(text, review), before)
        for reason in (
            "source_unavailable",
            "snapshot_unstable",
            "manifest_unavailable",
        ):
            with patch(
                "lifetxt.batch_preview.read_workspace_context",
                side_effect=WorkspaceContextUnavailable(reason),
            ):
                response = self.save(text, review)
                self.assert_rejected(response, before)
                self.assertEqual(response.json()["reason"], reason)

    def test_new_glob_source_requires_restart(self):
        config = {
            "paths": [os.path.join(self.temp.name, "*.txt")],
            "write_file": self.main,
        }
        with fixture.TestClient(
            webapp.create_app(
                paths=[self.main, self.other], writable_path=self.main, config=config
            )
        ) as client:
            text = "[ ] T A id:a\n"
            review = self.preview(text, client)
            self.write(os.path.join(self.temp.name, "z-new.txt"), "[ ] T New\n")
            response = self.save(text, review, client)
            self.assert_rejected(response, Path(self.main).read_bytes())
            self.assertEqual(response.json()["reason"], "source_membership_changed")

    def test_invalid_batch_and_warnings_do_not_partially_save(self):
        before = Path(self.main).read_bytes()
        text = "[ ] T A id:a\ninvalid record\n"
        review = self.preview(text)
        self.assert_rejected(self.save(text, review), before, "VALIDATION_ERROR", 422)
        text = "[ ] T A id:a depends_on:b\n[ ] T B id:b depends_on:a ref:missing\n"
        review = self.preview(text)
        self.assertTrue(review["ok"])
        self.assertEqual(self.save(text, review).status_code, 201)

    def test_readonly_limits_and_token_shape(self):
        text = "[ ] T A id:a\n"
        review = self.preview(text)
        before = Path(self.main).read_bytes()
        self.assert_rejected(
            self.save(text, review, context_token=None),
            before,
            "CONTEXT_TOKEN_INVALID",
            400,
        )
        self.assert_rejected(
            self.save("a" * (512 * 1024 + 1), review), before, "INPUT_TOO_LARGE", 413
        )
        self.assert_rejected(
            self.save("[ ] T A\n" * 501, review), before, "TOO_MANY_RECORDS", 422
        )
        with fixture.TestClient(
            webapp.create_app(paths=[self.main], read_only=True)
        ) as client:
            response = self.save(text, review, client)
            self.assertEqual(response.status_code, 403)
        response = self.client.post(
            "/api/items/batch",
            json={"text": text, "context_token": review["context_token"]},
            headers={"If-Match": review["source_revision"]},
        )
        self.assert_rejected(response, before, "REVISION_REQUIRED", 428)

    def test_legacy_all_value_uniqueness_and_no_token_required(self):
        revision = self.client.get("/api/health").json()["source_revision"]
        for text in ("[ ] T A id:a id:other\n", "[ ] T A id:a\n[ ] T B id:a\n"):
            response = self.client.post(
                "/api/items/batch",
                json={"text": text, "expected_source_revision": revision},
                headers={"If-Match": revision},
            )
            self.assertEqual(response.status_code, 422, response.text)
        response = self.client.post(
            "/api/items/batch",
            json={"text": "[ ] T A id:a\n", "expected_source_revision": revision},
            headers={"If-Match": revision},
        )
        self.assertEqual(response.status_code, 201, response.text)

    def test_stale_if_match_is_still_rejected_by_middleware(self):
        text = "[ ] T A id:a\n"
        review = self.preview(text)
        self.write(self.main, "[ ] T Changed id:changed\n")
        self.assert_rejected(
            self.save(text, review), Path(self.main).read_bytes(), "CONFLICT"
        )

    def test_late_writable_race_preserves_cas(self):
        text = "[ ] T A id:a\n"
        review = self.preview(text)
        write = mutation.write_text
        external = b"[ ] T Concurrent id:concurrent\n"

        def race(path, *args, **kwargs):
            Path(self.main).write_bytes(external)
            return write(path, *args, **kwargs)

        with patch("lifetxt.batch_save.mutation.write_text", side_effect=race):
            self.assert_rejected(self.save(text, review), external, "CONFLICT")

    def test_nonwritable_change_after_final_scan_is_remaining_race(self):
        text = "[ ] T A id:a\n"
        review = self.preview(text)
        write = mutation.write_text

        def race(path, *args, **kwargs):
            self.write(self.other, "[ ] T Late collision id:a\n")
            return write(path, *args, **kwargs)

        with patch("lifetxt.batch_save.mutation.write_text", side_effect=race):
            response = self.save(text, review)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIn(b"id:a", Path(self.main).read_bytes())
        self.assertIn(b"id:a", Path(self.other).read_bytes())

    def test_middleware_preconditions_do_not_disclose_private_paths(self):
        text = "[ ] T A id:a\n"
        review = self.preview(text)
        payload = {"text": text, "context_token": review["context_token"]}
        response = self.client.post(
            "/api/items/batch",
            json=payload,
            headers={"X-Lifetxt-Require-Revision": "1"},
        )
        self.assert_rejected(
            response, Path(self.main).read_bytes(), "PRECONDITION_REQUIRED", 428
        )
        self.write(self.main, "#! format_version: 2\n[ ] T Existing\n")
        fresh = mutation.read_text_snapshot(self.main).content_hash
        response = self.save(text, review, expected_source_revision=fresh)
        self.assert_rejected(
            response, Path(self.main).read_bytes(), "UNSUPPORTED_FORMAT_VERSION", 409
        )

    def test_header_revision_cannot_be_replaced_by_later_body_snapshot(self):
        from lifetxt.batch_save import review_batch

        text = "[ ] T A id:a\n"
        reviewed_bytes = Path(self.main).read_bytes()
        review = self.preview(text)
        self.write(self.main, "[ ] T Intermediate id:intermediate\n")
        header_revision = mutation.read_text_snapshot(self.main).content_hash

        def restore_context(*args, **kwargs):
            Path(self.main).write_bytes(reviewed_bytes)
            return review_batch(*args, **kwargs)

        with patch("lifetxt.batch_save.review_batch", side_effect=restore_context):
            response = self.client.post(
                "/api/items/batch",
                json={
                    "text": text,
                    "context_token": review["context_token"],
                    "expected_source_revision": review["source_revision"],
                },
                headers={"If-Match": header_revision},
            )
        self.assert_rejected(response, reviewed_bytes, "CONFLICT")
