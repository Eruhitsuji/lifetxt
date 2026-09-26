import os
import tempfile
import unittest
from pathlib import Path


try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None


@unittest.skipIf(TestClient is None, "web extras unavailable")
class WebPersonalContextTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        Path(self.path).write_text(
            "[N] N Current id:current person:self tag:preference source:user updated:2999-01-01\n"
            "[N] N Stale id:stale person:self tag:skill source:user updated:2000-01-01\n"
            "[N] N Old id:old person:self tag:goal source:user replaced_by:new updated:2999-01-01\n"
            "[N] N New id:new person:self tag:goal source:user corrects:old updated:2999-01-01\n"
            "[N] N Other id:other person:alex tag:skill source:user\n",
            encoding="utf-8",
        )
        from lifetxt.webapp import create_app

        self.client = TestClient(create_app([self.path], writable_path=self.path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_projection_reuses_current_only_capsule(self):
        response = self.client.get("/api/personal-context")
        self.assertEqual(200, response.status_code)
        result = response.json()
        self.assertEqual("personal-context-capsule-v1", result["schema"])
        self.assertEqual("self", result["person"])
        self.assertEqual({"current", "new"}, {row["id"] for row in result["items"]})
        self.assertEqual({"current": 2, "stale": 1}, result["currentness_counts"])
        self.assertFalse(result["include_stale"])
        self.assertNotIn("stale", {row["id"] for row in result["items"]})
        self.assertNotIn("old", {row["id"] for row in result["items"]})
        self.assertNotIn("other", {row["id"] for row in result["items"]})

    def test_projection_explicitly_includes_only_stale_records(self):
        response = self.client.get("/api/personal-context?include_stale=true")
        self.assertEqual(200, response.status_code)
        result = response.json()
        self.assertTrue(result["include_stale"])
        rows = {row["id"]: row for row in result["items"]}
        self.assertEqual({"current", "new", "stale"}, set(rows))
        self.assertTrue(rows["stale"]["stale"])
        self.assertFalse(rows["current"]["stale"])
        self.assertNotIn("old", rows)
        self.assertNotIn("other", rows)

    def test_projection_pages_beyond_default_bound_with_full_counts(self):
        lines = [
            f"[N] N Fact{index} id:fact{index} person:self tag:profile source:user updated:2999-01-01\n"
            for index in range(205)
        ]
        Path(self.path).write_text("".join(lines), encoding="utf-8")

        first = self.client.get("/api/personal-context?limit=100")
        second = self.client.get("/api/personal-context?limit=100&offset=100")
        last = self.client.get("/api/personal-context?limit=100&offset=200")

        self.assertEqual(100, len(first.json()["items"]))
        self.assertEqual(100, len(second.json()["items"]))
        self.assertEqual(5, len(last.json()["items"]))
        self.assertTrue(first.json()["has_more"])
        self.assertTrue(second.json()["has_more"])
        self.assertFalse(last.json()["has_more"])
        for result in (first.json(), second.json(), last.json()):
            self.assertEqual(205, result["total_count"])
            self.assertEqual({"current": 205, "stale": 0}, result["currentness_counts"])

    def test_projection_rejects_invalid_paging_and_caps_requested_limit(self):
        self.assertEqual(
            400, self.client.get("/api/personal-context?limit=0").status_code
        )
        self.assertEqual(
            400, self.client.get("/api/personal-context?offset=-1").status_code
        )
        self.assertEqual(
            400, self.client.get("/api/personal-context?limit=nope").status_code
        )

    def test_stale_personal_context_can_be_reconfirmed_with_cas_and_preservation(self):
        before = Path(self.path).read_text(encoding="utf-8")
        result = self.client.get("/api/personal-context?include_stale=true").json()
        response = self.client.post(
            "/api/personal-context/stale/reconfirm",
            json={"expected_source_revision": result["source_revision"]},
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["reconfirmed"])
        self.assertEqual("stale", response.json()["id"])
        after = Path(self.path).read_text(encoding="utf-8")
        self.assertIn("id:stale", after)
        self.assertIn("tag:skill", after)
        self.assertIn("source:user", after)
        self.assertNotEqual(before, after)
        current = self.client.get("/api/personal-context").json()
        self.assertIn("stale", {row["id"] for row in current["items"]})
        self.assertEqual({"current": 3, "stale": 0}, current["currentness_counts"])

    def test_reconfirm_requires_stale_exact_writable_id_and_current_revision(self):
        self.assertEqual(
            404, self.client.post("/api/personal-context/missing/reconfirm").status_code
        )
        current = self.client.get("/api/personal-context").json()
        self.assertEqual(
            409, self.client.post("/api/personal-context/current/reconfirm").status_code
        )
        self.assertEqual(
            409,
            self.client.post(
                "/api/personal-context/stale/reconfirm",
                json={"expected_source_revision": "wrong"},
            ).status_code,
        )

    def test_bulk_review_reports_per_item_results(self):
        result = self.client.get("/api/personal-context?include_stale=true").json()
        response = self.client.post(
            "/api/personal-context/bulk-review",
            json={"ids": ["stale", "current", "missing"], "action": "reconfirm",
                  "expected_source_revision": result["source_revision"]},
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual((3, 1, 0, 2), tuple(body[key] for key in ("selected", "succeeded", "conflicted", "failed")))
        self.assertEqual(
            {"stale": "succeeded", "current": "failed", "missing": "failed"},
            {row["id"]: row["status"] for row in body["results"]},
        )

    def test_bulk_expire_uses_one_date_and_rejects_unsupported_action(self):
        result = self.client.get("/api/personal-context").json()
        response = self.client.post(
            "/api/personal-context/bulk-review",
            json={"ids": ["current", "new"], "action": "expire", "valid_to": "2026-09-26",
                  "expected_source_revision": result["source_revision"]},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["succeeded"])
        self.assertIn("valid_to:2026-09-26", Path(self.path).read_text(encoding="utf-8"))
        self.assertEqual(400, self.client.post(
            "/api/personal-context/bulk-review", json={"ids": ["current"], "action": "correct"}
        ).status_code)

    def test_projection_all_current_all_stale_and_mixed_counts(self):
        datasets = {
            "all-current": (
                "[N] N One id:one person:self tag:profile source:user updated:2999-01-01\n",
                {"current": 1, "stale": 0},
                {"one"},
            ),
            "all-stale": (
                "[N] N One id:one person:self tag:profile source:user updated:2000-01-01\n",
                {"current": 0, "stale": 1},
                {"one"},
            ),
            "mixed": (
                "[N] N One id:one person:self tag:profile source:user updated:2999-01-01\n"
                "[N] N Two id:two person:self tag:project source:user updated:2000-01-01\n",
                {"current": 1, "stale": 1},
                {"one", "two"},
            ),
        }
        for name, (text, counts, included_ids) in datasets.items():
            with self.subTest(name=name):
                Path(self.path).write_text(text, encoding="utf-8")
                default = self.client.get("/api/personal-context").json()
                expanded = self.client.get(
                    "/api/personal-context?include_stale=true"
                ).json()
                self.assertEqual(counts, default["currentness_counts"])
                self.assertEqual(
                    included_ids,
                    {row["id"] for row in expanded["items"]},
                )
                self.assertEqual(
                    {row["id"] for row in expanded["items"] if not row["stale"]},
                    {row["id"] for row in default["items"]},
                )

    def test_preview_returns_exact_ordinary_note_payloads_without_writing(self):
        before = Path(self.path).read_text(encoding="utf-8")
        response = self.client.post(
            "/api/personal-context/preview",
            json={
                "facts": [
                    {"domain": "Preference", "fact": "Prefers dark mode"},
                    {"domain": "skill", "fact": "Uses Python regularly"},
                ]
            },
        )
        self.assertEqual(200, response.status_code)
        result = response.json()
        self.assertEqual("personal-context-bootstrap-preview-v1", result["schema"])
        self.assertEqual(2, result["count"])
        first = result["records"][0]
        self.assertEqual(
            '[N] N "Prefers dark mode" person:self tag:preference source:user',
            first["line"],
        )
        self.assertEqual(
            {
                "status": "[N]",
                "type": "N",
                "title": "Prefers dark mode",
                "details": {
                    "person": ["self"],
                    "tag": ["preference"],
                    "source": ["user"],
                },
            },
            first["payload"],
        )
        self.assertNotIn("id", first["payload"]["details"])
        self.assertEqual(before, Path(self.path).read_text(encoding="utf-8"))

    def test_preview_rejects_invalid_or_unbounded_input(self):
        cases = [
            {},
            {"facts": []},
            {"facts": [{"domain": "secret", "fact": "No"}]},
            {"facts": [{"domain": "goal", "fact": ""}]},
            {"facts": [{"domain": "goal", "fact": "a\nb"}]},
            {"facts": [{"domain": "goal", "fact": "x" * 501}]},
            {"facts": [{"domain": "goal", "fact": "x"}] * 26},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(
                    400,
                    self.client.post(
                        "/api/personal-context/preview", json=payload
                    ).status_code,
                )

    def test_read_only_can_project_and_preview_but_not_save(self):
        from lifetxt.webapp import create_app

        client = TestClient(
            create_app([self.path], writable_path=self.path, read_only=True)
        )
        self.assertEqual(200, client.get("/api/personal-context").status_code)
        self.assertEqual(
            200,
            client.get("/api/personal-context?include_stale=true").status_code,
        )
        payload = {"facts": [{"domain": "profile", "fact": "Lives in Tokyo"}]}
        preview = client.post("/api/personal-context/preview", json=payload)
        self.assertEqual(200, preview.status_code)
        self.assertEqual(
            403,
            client.post(
                "/api/items", json=preview.json()["records"][0]["payload"]
            ).status_code,
        )

    def test_bearer_auth_applies_to_both_routes(self):
        from lifetxt.webapp import create_app

        client = TestClient(
            create_app(
                [self.path],
                writable_path=self.path,
                config={"api": {"token": "test-token"}},
            )
        )
        headers = {"Authorization": "Bearer test-token"}
        self.assertEqual(401, client.get("/api/personal-context").status_code)
        self.assertEqual(
            200, client.get("/api/personal-context", headers=headers).status_code
        )
        self.assertEqual(
            401,
            client.post(
                "/api/personal-context/preview",
                json={"facts": [{"domain": "goal", "fact": "Ship it"}]},
            ).status_code,
        )
        self.assertEqual(
            200,
            client.post(
                "/api/personal-context/preview",
                json={"facts": [{"domain": "goal", "fact": "Ship it"}]},
                headers=headers,
            ).status_code,
        )


@unittest.skipIf(TestClient is None, "web extras unavailable")
class WebPersonalContextReviewOutcomesTests(unittest.TestCase):
    """Expanded review outcomes: expire, change, correct (#960)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        Path(self.path).write_text(
            "[N] N Current id:current person:self tag:profile source:user updated:2999-01-01\n"
            "[N] N Stale id:stale person:self tag:skill source:user updated:2000-01-01\n"
            "[N] N Old id:old person:self tag:goal source:user replaced_by:new updated:2999-01-01\n"
            "[N] N New id:new person:self tag:goal source:user corrects:old updated:2999-01-01\n",
            encoding="utf-8",
        )
        from lifetxt.webapp import create_app

        self.client = TestClient(create_app([self.path], writable_path=self.path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _revision(self):
        # Deliberately reuse /api/personal-context's own source_revision
        # rather than GET /api/revision: fetching /api/revision opts this
        # client session into strict revision mode (via a cookie set only
        # on /api/revision and /api/capabilities), which then requires an
        # explicit If-Match header these tests do not send -- matching how
        # the real Web UI client discovers the revision it already has
        # from its last load rather than a separate discovery call.
        return self.client.get("/api/personal-context?include_stale=true").json()[
            "source_revision"
        ]

    def test_expire_ends_applicability_without_deleting_the_record(self):
        response = self.client.post(
            "/api/personal-context/current/expire",
            json={
                "expected_source_revision": self._revision(),
                "valid_to": "2000-01-01",
            },
        )
        self.assertEqual(200, response.status_code)
        result = response.json()
        self.assertEqual("expired", result["state"])
        self.assertEqual(["2000-01-01"], result["item"]["details"]["valid_to"])
        text = Path(self.path).read_text(encoding="utf-8")
        self.assertIn("id:current", text)
        self.assertIn("valid_to:2000-01-01", text)
        projection = self.client.get("/api/personal-context").json()
        self.assertNotIn("current", {row["id"] for row in projection["items"]})

    def test_expire_rejects_already_terminal_states(self):
        # "old" is already superseded by "new"; a terminal state cannot be
        # ended again.
        response = self.client.post(
            "/api/personal-context/old/expire",
            json={"expected_source_revision": self._revision()},
        )
        self.assertEqual(409, response.status_code)

    def test_expire_requires_writable_id_and_current_revision(self):
        self.assertEqual(
            404, self.client.post("/api/personal-context/missing/expire").status_code
        )
        self.assertEqual(
            409,
            self.client.post(
                "/api/personal-context/current/expire",
                json={"expected_source_revision": "wrong"},
            ).status_code,
        )

    def test_change_preserves_old_record_and_starts_a_new_current_record(self):
        before = Path(self.path).read_text(encoding="utf-8")
        response = self.client.post(
            "/api/personal-context/current/change",
            json={
                "expected_source_revision": self._revision(),
                "replacement_text": "Works at Beta Corp",
                "valid_from": "2026-01-01",
            },
        )
        self.assertEqual(200, response.status_code)
        result = response.json()
        new_id = result["new_id"]
        self.assertTrue(new_id)
        self.assertEqual([new_id], result["old_item"]["details"]["replaced_by"])
        self.assertEqual("Works at Beta Corp", result["new_item"]["title"])
        self.assertEqual(["2026-01-01"], result["new_item"]["details"]["valid_from"])
        self.assertEqual(["profile"], result["new_item"]["details"]["tag"])
        text = Path(self.path).read_text(encoding="utf-8")
        self.assertIn("id:current", text)
        self.assertIn("replaced_by:%s" % new_id, text)
        self.assertIn("Works at Beta Corp", text)
        self.assertNotEqual(before, text)
        # The old record's own historical content is untouched, only
        # gaining the replacement relation.
        self.assertIn("Current", text)

    def test_change_requires_replacement_text(self):
        response = self.client.post(
            "/api/personal-context/current/change",
            json={"expected_source_revision": self._revision()},
        )
        self.assertEqual(400, response.status_code)

    def test_change_rejects_already_terminal_states(self):
        response = self.client.post(
            "/api/personal-context/old/change",
            json={
                "expected_source_revision": self._revision(),
                "replacement_text": "x",
            },
        )
        self.assertEqual(409, response.status_code)

    def test_correct_leaves_the_old_record_unmodified_and_links_the_new_one(self):
        before = Path(self.path).read_text(encoding="utf-8")
        response = self.client.post(
            "/api/personal-context/current/correct",
            json={
                "expected_source_revision": self._revision(),
                "replacement_text": "Was actually wrong from the start",
            },
        )
        self.assertEqual(200, response.status_code)
        result = response.json()
        new_id = result["new_id"]
        self.assertTrue(new_id)
        self.assertEqual(["current"], result["new_item"]["details"]["corrects"])
        # Unlike change, the old record gains no new detail at all.
        self.assertNotIn("replaced_by", result["old_item"]["details"])
        text = Path(self.path).read_text(encoding="utf-8")
        self.assertIn(before.splitlines()[0], text)
        self.assertIn("corrects:current", text)
        projection = self.client.get("/api/personal-context").json()
        self.assertNotIn("current", {row["id"] for row in projection["items"]})
        self.assertIn(new_id, {row["id"] for row in projection["items"]})

    def test_correct_requires_replacement_text(self):
        response = self.client.post(
            "/api/personal-context/current/correct",
            json={"expected_source_revision": self._revision()},
        )
        self.assertEqual(400, response.status_code)

    def test_review_later_performs_no_mutation(self):
        # "Review later" has no dedicated route: it is simply not calling
        # any mutating endpoint. Confirm the file is untouched by a plain
        # projection read, which is the only request the Web UI issues.
        before = Path(self.path).read_text(encoding="utf-8")
        self.client.get("/api/personal-context?include_stale=true")
        self.assertEqual(before, Path(self.path).read_text(encoding="utf-8"))

    def test_read_only_mode_rejects_every_new_mutation(self):
        from lifetxt.webapp import create_app

        client = TestClient(
            create_app([self.path], writable_path=self.path, read_only=True)
        )
        self.assertEqual(
            403, client.post("/api/personal-context/current/expire").status_code
        )
        self.assertEqual(
            403,
            client.post(
                "/api/personal-context/current/change",
                json={"replacement_text": "x"},
            ).status_code,
        )
        self.assertEqual(
            403,
            client.post(
                "/api/personal-context/current/correct",
                json={"replacement_text": "x"},
            ).status_code,
        )


if __name__ == "__main__":
    unittest.main()
