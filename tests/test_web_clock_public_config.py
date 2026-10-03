"""Real public-config, persisted reload, and API-to-JavaScript clock regressions."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lifetxt import bootstrap_legacy_surfaces

bootstrap_legacy_surfaces()
from lifetxt.config import load_config
from lifetxt.config_validation import validate_config
from lifetxt.webapp import public_web_config, create_app
from lifetxt.web_clock_config import valid_clock_format, valid_clock_timezone

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

ROOT = Path(__file__).resolve().parents[1]


def clock_script():
    source = (ROOT / "lifetxt/web_assets_js_13.js").read_text()
    return source[
        source.index("    const TOP_CLOCK_FORMATS") : source.index(
            "    function _kioskStartScroll"
        )
    ]


def render_clock(payload, instant, timezone="UTC", language="en"):
    source = "const assert = require('node:assert/strict');\n"
    source += "const appConfig = " + json.dumps(payload) + ";\n"
    source += "const currentLanguage = () => " + json.dumps(language) + ";\n"
    source += clock_script()
    source += (
        "console.log(JSON.stringify(_formatWebClock(new Date("
        + json.dumps(instant)
        + "), _topClockSettings())));"
    )
    result = subprocess.run(
        ["node", "-e", source],
        env={**os.environ, "TZ": timezone},
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class ClockPublicationTests(unittest.TestCase):
    def test_public_web_config_exports_requested_settings_and_main_timezone(self):
        clock = public_web_config(
            {
                "defaults": {"timezone": "Asia/Tokyo"},
                "web": {"top_clock": {"format": "HH:mm:ss", "show_date": True}},
            }
        )["top_clock"]
        self.assertEqual("HH:mm:ss", clock["format"])
        self.assertTrue(clock["show_date"])
        self.assertEqual("main", clock["timezone"])
        self.assertEqual("Asia/Tokyo", clock["resolved_timezone"])
        fallback = public_web_config({"defaults": {"timezone": "UTC"}})["top_clock"]
        self.assertEqual("HH:mm", fallback["format"])
        self.assertFalse(fallback["show_date"])

    def test_unknown_invalid_and_secret_fields_are_never_public(self):
        raw = {
            "enabled": "secret",
            "format": "password-secret",
            "show_date": "secret",
            "date_separator": "secret",
            "timezone": "private-token",
            "show_timezone": "secret",
            "password": "private",
            "token": "private",
            "main_timezone": "private",
            "main_utc_offset_minutes": "private",
        }
        clock = public_web_config(
            {"defaults": {"timezone": "UTC"}, "web": {"top_clock": raw}}
        )["top_clock"]
        self.assertNotIn("secret", json.dumps(clock))
        self.assertNotIn("private", json.dumps(clock))
        self.assertEqual("main", clock["timezone"])
        self.assertEqual("UTC", clock["resolved_timezone"])
        self.assertEqual("HH:mm", clock["format"])
        self.assertFalse(clock["show_timezone"])

    def test_dotted_clock_settings_use_existing_web_override_convention(self):
        clock = public_web_config(
            {
                "defaults": {"timezone": "UTC"},
                "web": {
                    "top_clock": {"format": "HH:mm"},
                    "top_clock.format": "YYYY/MM/DD HH:mm:ss",
                    "top_clock.timezone": "America/New_York",
                },
            }
        )["top_clock"]
        self.assertEqual("YYYY/MM/DD HH:mm:ss", clock["format"])
        self.assertEqual("America/New_York", clock["resolved_timezone"])

    def test_custom_formats_and_timezone_validation_are_dependency_free(self):
        for value in (
            "HH:mm",
            "h:mm:ss a",
            "YYYY/MM/DD HH:mm:ss (z)",
            "YYYY年M月D日 dddd",
            "GGGG-[W]WW-E",
            "dddd, MMMM D YYYY",
            "[literal text] HH:mm Z",
        ):
            self.assertTrue(valid_clock_format(value), value)
        for value in (
            None,
            [],
            "",
            "YYYY/MM/DD %Q",
            "[unclosed",
            "HH:mm\n",
            "X" * 129,
            "password",
            "YYYY/DDD/foo",
        ):
            self.assertFalse(valid_clock_format(value), value)
            errors = validate_config(
                {"web": {"top_clock": {"format": value}}}, use_jsonschema=False
            )
            self.assertIn("C010", [row["code"] for row in errors])
        for value in (
            "main",
            "browser-local",
            "Asia/Tokyo",
            "America/New_York",
            "Pacific/Chatham",
            "UTC",
        ):
            self.assertTrue(valid_clock_timezone(value), value)
        for value in ("Mars/Nowhere", "local", "../UTC", "private", [], None):
            self.assertFalse(valid_clock_timezone(value), value)
            self.assertTrue(
                validate_config(
                    {"web": {"top_clock": {"timezone": value}}}, use_jsonschema=False
                )
            )

    def test_server_local_main_publishes_its_own_offset(self):
        from datetime import datetime, timezone, timedelta
        from lifetxt.timezone_policy import clock_context

        with (
            patch(
                "lifetxt.timezone_policy.resolve_timezone_name", return_value="local"
            ),
            patch(
                "lifetxt.timezone_policy.timezone_info",
                return_value=timezone(timedelta(hours=9)),
            ),
            clock_context(datetime(2026, 10, 3, tzinfo=timezone.utc)),
        ):
            clock = public_web_config({})["top_clock"]
        self.assertEqual("local", clock["main_timezone"])
        self.assertEqual(540, clock["main_utc_offset_minutes"])


@unittest.skipIf(TestClient is None, "FastAPI Web extras unavailable")
class ClockConfigApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / ".lifetxt.json"
        self.item_path = Path(self.temp.name) / "life.txt"
        self.item_path.write_text("", encoding="utf-8")
        self.initial = {
            "defaults": {"timezone": "UTC"},
            "web": {"top_clock": {"format": "HH:mm"}},
        }
        self.save(self.initial)
        self.config = load_config(str(self.path))
        self.app = create_app(
            paths=[str(self.item_path)],
            writable_path=str(self.item_path),
            config=self.config,
        )
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def save(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_cli_edits_reach_same_running_app_after_page_config_reload(self):
        from tests.test_lifetxt import run_cli

        first = self.client.get("/api/config")
        self.assertEqual(200, first.status_code)
        self.assertEqual("HH:mm", first.json()["web"]["top_clock"]["format"])
        for key, value in (
            ("format", "YYYY/MM/DD HH:mm:ss (z)"),
            ("timezone", "Asia/Tokyo"),
            ("show_date", True),
        ):
            out, err, code = run_cli(
                "--config",
                str(self.path),
                "config",
                "set",
                "web.top_clock." + key,
                json.dumps(value),
            )
            self.assertEqual(0, code, err or out)
        second = self.client.get("/api/config")
        self.assertEqual("no-store", second.headers.get("cache-control"))
        clock = second.json()["web"]["top_clock"]
        self.assertEqual("YYYY/MM/DD HH:mm:ss (z)", clock["format"])
        self.assertEqual("Asia/Tokyo", clock["resolved_timezone"])
        self.assertTrue(clock["show_date"])
        self.assertEqual("HH:mm", self.app.state.config["web"]["top_clock"]["format"])
        self.assertEqual("UTC", clock["main_timezone"])

    def test_reload_does_not_change_other_runtime_web_or_main_settings(self):
        self.save(
            {
                "defaults": {"timezone": "Asia/Tokyo"},
                "web": {"default_order": "asc", "top_clock": {"enabled": False}},
                "api": {"token": "new-secret"},
                "write_file": "/private/new-target",
            }
        )
        data = self.client.get("/api/config").json()
        self.assertFalse(data["web"]["top_clock"]["enabled"])
        self.assertEqual("UTC", data["web"]["top_clock"]["main_timezone"])
        self.assertEqual("desc", data["web"]["default_order"])
        self.assertEqual(str(self.item_path), data["writable_path"])
        self.assertNotIn("new-secret", json.dumps(data))
        self.assertNotIn("/private/new-target", json.dumps(data))

    def test_unset_invalid_and_unknown_values_are_safely_normalized(self):
        self.save({})
        clock = self.client.get("/api/config").json()["web"]["top_clock"]
        self.assertEqual("HH:mm", clock["format"])
        self.assertEqual("main", clock["timezone"])
        self.save(
            {
                "web": {
                    "top_clock": {
                        "format": ["secret"],
                        "timezone": "private",
                        "token": "private",
                    }
                }
            }
        )
        data = self.client.get("/api/config").json()["web"]["top_clock"]
        self.assertNotIn("private", json.dumps(data))
        self.assertEqual("HH:mm", data["format"])

    def test_malformed_missing_or_unreadable_file_returns_sanitized_503_and_recovers(
        self,
    ):
        self.path.write_text('{"secret": "private-value"', encoding="utf-8")
        response = self.client.get("/api/config")
        self.assertEqual(503, response.status_code)
        self.assertNotIn("private-value", response.text)
        self.assertNotIn(str(self.path), response.text)
        self.path.unlink()
        self.assertEqual(503, self.client.get("/api/config").status_code)
        self.save(self.initial)
        with patch(
            "lifetxt.config.load_config", side_effect=PermissionError("private-error")
        ):
            response = self.client.get("/api/config")
            self.assertEqual(503, response.status_code)
            self.assertNotIn("private-error", response.text)
        self.assertEqual(200, self.client.get("/api/config").status_code)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_actual_api_payload_renders_custom_jst_independent_of_viewer_timezone(self):
        self.save(
            {
                "web": {
                    "top_clock": {
                        "format": "YYYY/MM/DD HH:mm:ss (z)",
                        "timezone": "Asia/Tokyo",
                    }
                }
            }
        )
        payload = self.client.get("/api/config").json()
        for viewer in ("UTC", "America/New_York", "Asia/Tokyo"):
            for instant, expected in (
                ("2026-10-03T13:12:34Z", "2026/10/03 22:12:34 (JST)"),
                ("2026-10-03T14:59:59Z", "2026/10/03 23:59:59 (JST)"),
                ("2026-10-03T15:00:00Z", "2026/10/04 00:00:00 (JST)"),
            ):
                with self.subTest(viewer=viewer, instant=instant):
                    self.assertEqual(expected, render_clock(payload, instant, viewer))


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class CustomClockRenderingTests(unittest.TestCase):
    def render(self, clock, instant, main="UTC", viewer="UTC", language="en"):
        payload = {
            "web": public_web_config(
                {"defaults": {"timezone": main}, "web": {"top_clock": clock}}
            )
        }
        return render_clock(payload, instant, viewer, language)

    def test_main_zone_override_and_explicit_viewer_local(self):
        instant = "2026-10-03T13:12:34Z"
        for zone, expected in (
            ("main", "22:12"),
            ("America/New_York", "09:12"),
            ("browser-local", "13:12"),
        ):
            self.assertEqual(
                expected, self.render({"timezone": zone}, instant, main="Asia/Tokyo")
            )

    def test_iso_week_year_weekday_and_literal_do_not_duplicate_date(self):
        clock = {"format": "YYYY/MM/DD dddd GGGG-[W]WW-E", "show_date": True}
        self.assertEqual(
            "2021/01/01 Friday 2020-W53-5", self.render(clock, "2021-01-01T00:00:00Z")
        )
        self.assertEqual(
            "2021/01/01 金曜日 2020-W53-5",
            self.render(clock, "2021-01-01T00:00:00Z", language="ja"),
        )
        self.assertEqual(
            "2024/02/29", self.render({"format": "YYYY/MM/DD"}, "2024-02-29T23:59:59Z")
        )

    def test_dst_and_non_whole_hour_offsets(self):
        clock = {"timezone": "America/New_York", "format": "HH:mm Z"}
        self.assertEqual("01:59 -05:00", self.render(clock, "2026-03-08T06:59:00Z"))
        self.assertEqual("03:00 -04:00", self.render(clock, "2026-03-08T07:00:00Z"))
        self.assertEqual(
            "18:57 +05:45 +0545",
            self.render(
                {"timezone": "Asia/Kathmandu", "format": "HH:mm Z ZZ"},
                "2026-10-03T13:12:34Z",
            ),
        )

    def test_convenience_date_separator_and_zone_label(self):
        self.assertEqual(
            "2026/10/03 22:12 (JST)",
            self.render(
                {
                    "timezone": "Asia/Tokyo",
                    "show_date": True,
                    "date_separator": "/",
                    "show_timezone": True,
                },
                "2026-10-03T13:12:34Z",
            ),
        )
        payload = {
            "web": {
                "top_clock": {
                    "timezone": "main",
                    "main_timezone": "local",
                    "main_utc_offset_minutes": 540,
                    "format": "YYYY/MM/DD HH:mm (z)",
                }
            }
        }
        self.assertEqual(
            "2026/10/03 22:12 (UTC+09:00)",
            render_clock(payload, "2026-10-03T13:12:34Z", "America/New_York"),
        )
