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
        self.assertEqual(400, self.client.get("/api/personal-context?limit=0").status_code)
        self.assertEqual(400, self.client.get("/api/personal-context?offset=-1").status_code)
        self.assertEqual(400, self.client.get("/api/personal-context?limit=nope").status_code)

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


if __name__ == "__main__":
    unittest.main()
