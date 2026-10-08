"""Daily Flow Web contract, parity and non-disclosure regressions."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

from lifetxt import webapp
from lifetxt.daily_flow import build_daily_flow
from lifetxt.daily_flow_cli import _parse, _read

CLOCK = datetime(2031, 2, 2, 0, 0, tzinfo=timezone.utc)
PARAMS = {"date": "2031-02-03", "day_start": "09:00", "day_end": "17:00"}


@unittest.skipIf(TestClient is None, "FastAPI web extras unavailable")
class DailyFlowWebTests(unittest.TestCase):  # pragma: no cover -- Web extras CI
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "life.txt"
        self.text = (
            "#! timezone: Asia/Tokyo\n"
            "[ ] E Meeting id:meeting from:2031-02-03T09:00 to:2031-02-03T10:00\n"
            "[ ] T Work id:work est:1h\n"
        )
        self.path.write_text(self.text, encoding="utf-8")
        self.config = {"defaults": {"timezone": "Asia/Tokyo"}}
        self.client = self.make_client()

    def make_client(self, paths=None, config=None, read_only=True):
        return TestClient(
            webapp.create_app(
                paths=paths or [str(self.path)],
                config=self.config if config is None else config,
                read_only=read_only,
            )
        )

    def get(self, client=None, **params):
        with patch("lifetxt.daily_flow_web.now", return_value=CLOCK):
            return (client or self.client).get(
                "/api/daily-flow", params={**PARAMS, **params}
            )

    def test_exact_shared_model_parity_deterministic_read_only(self):
        original = self.path.read_bytes()
        files_before = {p.name for p in self.path.parent.iterdir()}
        response = self.get()
        self.assertEqual(200, response.status_code)
        snapshots = {str(self.path): _read(str(self.path))}
        items, notes = _parse(snapshots, None, self.config)
        expected = build_daily_flow(
            items,
            **PARAMS,
            timezone="Asia/Tokyo",
            evaluated_at=CLOCK,
            occupancy_complete=True,
            config=self.config,
            source_revisions={str(self.path): snapshots[str(self.path)].content_hash},
            input_diagnostics=notes,
        )
        self.assertEqual(expected, response.json())
        self.assertEqual(response.json(), self.get().json())
        self.assertEqual(original, self.path.read_bytes())
        self.assertEqual(files_before, {p.name for p in self.path.parent.iterdir()})
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertNotIn(str(self.path), response.text)
        self.assertEqual("candidate", response.json()["timeline"][1]["kind"])
        self.assertTrue(response.json()["timeline"][1]["start"].endswith("+09:00"))

    def test_auth_rejects_before_source_read_and_remote_credentials_are_not_local_auth(
        self,
    ):
        client = self.make_client(
            config={**self.config, "api": {"token": "local-token"}}
        )
        with patch("lifetxt.daily_flow_web._read", side_effect=AssertionError("read")):
            for headers in ({}, {"Authorization": "Bearer remote-principal-token"}):
                self.assertEqual(
                    401,
                    client.get(
                        "/api/daily-flow", params=PARAMS, headers=headers
                    ).status_code,
                )
        self.assertEqual(
            200,
            client.get(
                "/api/daily-flow",
                params=PARAMS,
                headers={"Authorization": "Bearer local-token"},
            ).status_code,
        )

    def test_method_and_required_schema(self):
        self.assertEqual(403, self.client.post("/api/daily-flow").status_code)
        self.assertEqual(
            405, self.make_client(read_only=False).post("/api/daily-flow").status_code
        )
        self.assertEqual(422, self.client.get("/api/daily-flow").status_code)
        route = self.client.get("/openapi.json").json()["paths"]["/api/daily-flow"]
        self.assertEqual({"get"}, set(route))
        required = {p["name"] for p in route["get"]["parameters"] if p.get("required")}
        self.assertEqual({"date", "day_start", "day_end"}, required)

    def test_invalid_date_window_and_scope_have_safe_error(self):
        for params in (
            {"date": "2031-02-30"},
            {"date": "2031-2-03"},
            {"day_start": "9:00"},
            {"day_end": "08:00"},
            {"day_end": "24:00"},
            {"area": "a", "saved_view": "b"},
            {"saved_view": str(self.path)},
        ):
            with self.subTest(params=params):
                response = self.get(**params)
                self.assertEqual(400, response.status_code)
                self.assertNotIn(str(self.path), response.text)
        self.assertEqual(200, self.get(day_end="00:00").status_code)
        self.assertEqual(422, self.get(area="a" * 257).status_code)

    def test_candidate_selector_never_discards_fixed_occupancy(self):
        config = {**self.config, "saved_views": {"tasks": {"query": "type:T"}}}
        client = self.make_client(config=config)
        response = self.get(client, saved_view="tasks")
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual("fixed", response.json()["timeline"][0]["kind"])
        self.assertEqual("Meeting", response.json()["timeline"][0]["item"]["title"])
        self.assertIn("10:00", response.json()["timeline"][1]["start"])

    def test_missing_member_and_unreadable_member_disclose_nothing(self):
        missing = self.path.parent / "secret.txt"
        response = self.get(self.make_client(paths=[str(self.path), str(missing)]))
        self.assertEqual(200, response.status_code)
        self.assertEqual("blocked", response.json()["completeness"]["state"])
        for text in ("Meeting", "Work", "secret", str(self.path.parent)):
            self.assertNotIn(text, response.text)
        self.assertEqual([], response.json()["timeline"])
        self.assertEqual([], response.json()["free"])
        self.path.write_bytes(b"\xff")
        self.assertEqual("blocked", self.get().json()["completeness"]["state"])

    def test_unsupported_occupancy_and_capacity_are_distinct(self):
        self.path.write_text(
            self.text + "[ ] E Unknown id:unknown at:2031-02-03T12:00\n"
        )
        blocked = self.get().json()
        self.assertEqual("blocked", blocked["completeness"]["state"])
        self.assertEqual([], blocked["free"])
        self.path.write_text(self.text)
        complete = self.get(day_end="10:00").json()
        self.assertEqual("complete", complete["completeness"]["state"])
        self.assertTrue(complete["unplaced"])

    def test_revision_changes_and_snapshot_race(self):
        first = self.get().json()["source_revision"]
        self.path.write_text(self.text + "[ ] T Extra id:extra est:10m\n")
        self.assertNotEqual(first, self.get().json()["source_revision"])
        from lifetxt import daily_flow_web

        real_read = daily_flow_web._read
        count = 0

        def changing(path):
            nonlocal count
            count += 1
            self.path.write_text(self.text + "[N] J Revision id:rev body:%s\n" % count)
            return real_read(path)

        with patch("lifetxt.daily_flow_web._read", side_effect=changing):
            result = self.get().json()
        self.assertEqual(4, count)
        self.assertEqual("blocked", result["completeness"]["state"])
        self.assertIn("source_changed", result["completeness"]["reasons"])
        self.assertEqual([], result["timeline"])

    def test_bounds_and_invalid_timezone(self):
        with patch(
            "lifetxt.daily_flow_web.HARD_LIMITS", {"context": 10000, "text_chars": 2}
        ):
            result = self.get().json()
        self.assertEqual("blocked", result["completeness"]["state"])
        self.assertEqual([], result["unplaced"])
        self.path.write_text("[ ] T Work id:work est:1h\n")
        self.client.app.state.config["defaults"]["timezone"] = "bad/zone"
        response = self.get()
        self.assertEqual(400, response.status_code)

    def test_workspace_archive_and_unregistered_sources_are_not_read(self):
        archive = self.path.parent / "archive.txt"
        archive.write_bytes(b"\xff")
        other = self.path.parent / "outside.txt"
        other.write_text("[ ] T Outside id:outside est:1h\n")
        config = {
            **self.config,
            "default_workspace": "daily",
            "workspaces": {
                "daily": {
                    "sources": [
                        {"path": str(self.path), "role": "primary"},
                        {"path": str(archive), "role": "archive"},
                        {"path": str(other), "role": "include"},
                    ]
                }
            },
        }
        client = self.make_client(paths=[str(self.path), str(archive)], config=config)
        from lifetxt import daily_flow_web

        real_read = daily_flow_web._read
        seen = []

        def tracked(path):
            seen.append(path)
            return real_read(path)

        with patch("lifetxt.daily_flow_web._read", side_effect=tracked):
            response = self.get(client)
        self.assertEqual(200, response.status_code)
        self.assertEqual("complete", response.json()["completeness"]["state"])
        self.assertEqual({str(self.path)}, set(seen))
        self.assertNotIn("Outside", response.text)

    def test_denied_auth_does_not_read_revision_or_leak_headers(self):
        client = self.make_client(config={**self.config, "api": {"token": "token"}})
        with patch(
            "lifetxt.mutation.read_text_snapshot",
            side_effect=AssertionError("unauthorized read"),
        ):
            response = client.get("/api/daily-flow", params=PARAMS)
        self.assertEqual(401, response.status_code)
        self.assertNotIn("etag", response.headers)
        self.assertNotIn("x-lifetxt-revision", response.headers)
        self.assertNotIn("Meeting", response.text)

    def test_future_current_and_dst_boundaries(self):
        with patch(
            "lifetxt.daily_flow_web.now",
            return_value=datetime(2031, 2, 3, 1, 30, tzinfo=timezone.utc),
        ):
            result = self.client.get("/api/daily-flow", params=PARAMS).json()
        self.assertIn("10:30", result["window"]["effective_start"])
        self.path.write_text(
            "#! timezone: America/New_York\n[ ] T Work id:work est:1h\n"
        )
        result = self.get(date="2031-03-09").json()
        self.assertEqual("blocked", result["completeness"]["state"])
        self.assertIn("unsupported_timezone_window", result["completeness"]["reasons"])

    def test_parse_error_and_partial_inventory_are_not_free_time(self):
        self.path.write_text(self.text + "invalid line\n")
        result = self.get().json()
        self.assertEqual("blocked", result["completeness"]["state"])
        self.assertIn("input_parse_error", result["completeness"]["reasons"])
        self.assertEqual([], result["free"])
        self.path.write_text(self.text + "[ ] T Missing id:missing\n")
        result = self.get().json()
        self.assertEqual("partial", result["completeness"]["state"])
        self.assertEqual("certified", result["completeness"]["occupancy"])

    def test_restricted_principal_and_path_query_do_not_admit_sources(self):
        with (
            patch(
                "lifetxt.remote_resource_download.authenticate_token",
                return_value=({"disclosure_mode": "restricted-resource"}, None),
            ),
            patch(
                "lifetxt.mutation.read_text_snapshot",
                side_effect=AssertionError("restricted read"),
            ),
        ):
            response = self.client.get(
                "/api/daily-flow",
                params=PARAMS,
                headers={"Authorization": "Bearer restricted"},
            )
        self.assertEqual(404, response.status_code)
        self.assertNotIn("Meeting", response.text)
        self.assertNotIn("etag", response.headers)
        outside = self.path.parent / "private.txt"
        outside.write_text("[ ] E Hidden id:hidden on:2031-02-03\n")
        response = self.get(path=str(outside), timezone="UTC", break_minutes="60")
        self.assertEqual(200, response.status_code)
        self.assertNotIn("Hidden", response.text)
        self.assertEqual("Asia/Tokyo", response.json()["timezone"])
        self.assertEqual(0, response.json()["policy"]["break_minutes"])

    def test_single_race_retries_complete_snapshot_and_rejected_post_is_read_only(self):
        from lifetxt import daily_flow_web

        real_read = daily_flow_web._read
        count = 0

        def once(path):
            nonlocal count
            count += 1
            if count == 2:
                self.path.write_text(self.text + "[ ] T New id:new est:10m\n")
            return real_read(path)

        with patch("lifetxt.daily_flow_web._read", side_effect=once):
            result = self.get().json()
        self.assertEqual(4, count)
        self.assertEqual("complete", result["completeness"]["state"])
        self.assertIn("New", str(result))
        before = {p.name: p.read_bytes() for p in self.path.parent.iterdir()}
        client = self.make_client(read_only=False)
        # Existing startup artifacts are allowed; request must add/change none.
        before = {p.name: p.read_bytes() for p in self.path.parent.iterdir()}
        self.assertEqual(405, client.post("/api/daily-flow").status_code)
        self.assertEqual(
            before, {p.name: p.read_bytes() for p in self.path.parent.iterdir()}
        )

    def test_docs_have_usage_and_security_contract(self):
        for language in ("en", "ja"):
            text = Path("docs/%s/web.md" % language).read_text()
            self.assertIn(
                "/api/daily-flow?date=2031-02-03&day_start=09:00&day_end=17:00", text
            )
            self.assertIn("daily-flow-lite-v1", text)
            self.assertIn("occupancy_unavailable", text)
