"""Read projection, authentication, bounds and non-mutation at the HTTP boundary."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

from tests.test_procedure_definition import SAMPLE


@unittest.skipIf(TestClient is None, "web extras unavailable")
class ProcedureWebTests(unittest.TestCase):
    def setUp(self):
        from lifetxt import bootstrap_legacy_surfaces

        bootstrap_legacy_surfaces()
        from lifetxt.webapp import create_app

        self.create_app = create_app
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "private-definition.txt"
        self.source.write_text(SAMPLE, encoding="utf-8")
        self.app = create_app(paths=[str(self.source)], writable_path=str(self.source))
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def detail_url(self, client=None):
        data = (client or self.client).get("/api/procedures").json()
        row = data["procedures"][0]
        return "/api/procedures/%s/%s" % (row["source"], row["id"])

    def test_projection_is_same_definition_and_formats_as_cli(self):
        from lifetxt.procedure_cli import read_definition
        from lifetxt.procedure_graph import render_procedure

        before = self.source.read_bytes()
        existing = set(Path(self.temp.name).iterdir())
        response = self.client.get(self.detail_url())
        self.assertEqual(200, response.status_code, response.text)
        data = response.json()
        self.assertEqual(("procedure-v1", "definition"), (data["schema"], data["mode"]))
        graph = read_definition(str(self.source), "r")
        self.assertEqual(graph.projection.template_revision, data["template_revision"])
        self.assertEqual("a", data["start"])
        self.assertTrue(data["cyclic"])
        self.assertEqual("PG201", data["diagnostics"][0]["code"])
        self.assertEqual(
            ["a", "q", "retry", "e"], [step["id"] for step in data["steps"]]
        )
        self.assertEqual("decision", data["steps"][1]["kind"])
        self.assertEqual("r", data["steps"][0]["parent"])
        for format in ("text", "mermaid", "dot"):
            self.assertEqual(render_procedure(graph, format), data["formats"][format])
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertNotIn(str(self.source), response.text)
        self.assertNotIn("private-definition", response.text)
        self.assertEqual(before, self.source.read_bytes())
        self.assertEqual(existing, set(Path(self.temp.name).iterdir()))

    def test_read_only_and_existing_bearer_auth_apply(self):
        for read_only in (False, True):
            with TestClient(
                self.create_app(
                    paths=[str(self.source)],
                    writable_path=str(self.source),
                    read_only=read_only,
                    config={"api": {"token": "test-token"}},
                )
            ) as client:
                url = self.detail_url()
                for route in ("/procedures", "/api/procedures", url):
                    self.assertEqual(401, client.get(route).status_code)
                    self.assertEqual(
                        200,
                        client.get(
                            route, headers={"Authorization": "Bearer test-token"}
                        ).status_code,
                    )
                    self.assertEqual(
                        401,
                        client.get(
                            route, headers={"Authorization": "Bearer wrong"}
                        ).status_code,
                    )

    def test_all_unsafe_methods_refuse_without_revision_or_mutation(self):
        before = self.source.read_bytes()
        for route in ("/procedures", "/api/procedures", self.detail_url()):
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                self.assertEqual(
                    405,
                    self.client.request(
                        method, route, json={"actor": "forged"}
                    ).status_code,
                )
        self.assertEqual(before, self.source.read_bytes())

    def test_unknown_paths_invalid_profile_and_deleted_source_are_safe(self):
        url = self.detail_url()
        self.assertEqual(
            404, self.client.get("/api/procedures/not-allowlisted/r").status_code
        )
        self.assertEqual(
            404, self.client.get("/api/procedures/etc%2Fpasswd/r").status_code
        )
        self.source.write_text(
            SAMPLE.replace("proc_next:q", "proc_next:missing"), encoding="utf-8"
        )
        listing = self.client.get("/api/procedures").json()
        self.assertFalse(listing["procedures"][0]["valid"])
        response = self.client.get(url)
        self.assertEqual(422, response.status_code)
        self.assertIn("diagnostics", response.json())
        self.assertNotIn(self.temp.name, response.text)
        self.source.unlink()
        self.assertEqual(404, self.client.get(url).status_code)
        self.assertEqual(
            "PROCEDURE_SOURCE_UNAVAILABLE",
            self.client.get("/api/procedures").json()["failures"][0]["error"],
        )

    def test_multi_source_selection_does_not_merge_same_root_ids(self):
        other = Path(self.temp.name) / "other.txt"
        other.write_text(SAMPLE.replace("Root", "Other"), encoding="utf-8")
        # Existing workspace writes forbid duplicate IDs, but read-only sources
        # can still be unambiguously browsed with source + root.
        with TestClient(
            self.create_app(paths=[str(self.source), str(other)], read_only=True)
        ) as client:
            rows = client.get("/api/procedures").json()["procedures"]
            self.assertEqual(2, len(rows))
            self.assertNotEqual(rows[0]["source"], rows[1]["source"])
            for row in rows:
                data = client.get("/api/procedures/%s/r" % row["source"]).json()
                self.assertEqual(row["title"], data["root"]["title"])

    def test_bounds_on_sources_roots_output_and_bytes(self):
        from lifetxt import procedure_web

        url = self.detail_url()
        for name in ("MAX_SOURCES", "MAX_ROOTS", "MAX_CATALOG_BYTES"):
            with self.subTest(name=name), patch.object(procedure_web, name, 0):
                self.assertEqual(422, self.client.get("/api/procedures").status_code)
        with patch.object(procedure_web, "MAX_OUTPUT_BYTES", 1):
            self.assertEqual(422, self.client.get(url).status_code)
        with patch("lifetxt.procedure_cli.MAX_SOURCE_BYTES", 2):
            self.assertEqual(422, self.client.get(url).status_code)
        with patch("lifetxt.procedure_cli.MAX_RECORDS", 1):
            self.assertEqual(422, self.client.get(url).status_code)
        self.assertEqual(SAMPLE, self.source.read_text(encoding="utf-8"))

    def test_unsafe_text_is_data_and_page_contains_no_instructions(self):
        malicious = '<img src=x onerror="window.pwned=1">'
        self.source.write_text(SAMPLE + "| " + malicious + "\n", encoding="utf-8")
        data = self.client.get(self.detail_url()).json()
        self.assertIn(malicious, data["steps"][-1]["body"])
        page = self.client.get("/procedures")
        self.assertEqual(200, page.status_code)
        self.assertNotIn(malicious, page.text)
        self.assertNotIn("innerHTML", page.text)
        self.assertIn("frame-ancestors 'none'", page.headers["content-security-policy"])
        self.assertIn('href="/procedures"', self.client.get("/").text)
        self.assertEqual(200, self.client.get("/planner").status_code)
        self.assertEqual(200, self.client.get("/api/items").status_code)

    def test_revision_changes_and_empty_ordinary_sources(self):
        url = self.detail_url()
        revision = self.client.get(url).json()["template_revision"]
        self.source.write_text(SAMPLE + "# edit\n", encoding="utf-8")
        self.assertNotEqual(revision, self.client.get(url).json()["template_revision"])
        self.source.write_text("[ ] T Ordinary id:task\n", encoding="utf-8")
        self.assertEqual([], self.client.get("/api/procedures").json()["procedures"])
        self.assertEqual(200, self.client.get("/api/items").status_code)
