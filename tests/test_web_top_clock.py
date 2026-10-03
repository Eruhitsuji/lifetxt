"""Configuration and actual JavaScript behavior for the shared Top/Kiosk clock."""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from lifetxt import bootstrap_legacy_surfaces

bootstrap_legacy_surfaces()
from lifetxt.config import config_template
from lifetxt.config_registry import explain_key
from lifetxt.safety_foundation import schema_bundle
from lifetxt.web_assets import HTML_PAGE

ROOT = Path(__file__).resolve().parents[1]


class TopClockConfigTests(unittest.TestCase):
    def test_defaults_and_explain_metadata(self):
        self.assertEqual(
            {
                "enabled": True,
                "format": "HH:mm",
                "show_date": False,
                "date_separator": "-",
                "timezone": "main",
                "show_timezone": False,
            },
            config_template()["web"]["top_clock"],
        )
        for key, value, kind in (
            ("enabled", True, "boolean"),
            ("format", "HH:mm", "string"),
            ("show_date", False, "boolean"),
            ("date_separator", "-", "string"),
            ("timezone", "main", "string"),
            ("show_timezone", False, "boolean"),
        ):
            entry = explain_key("web.top_clock." + key)
            self.assertEqual(value, entry["default"])
            self.assertEqual(kind, entry["type"])
            self.assertFalse(entry["secret"])
            self.assertFalse(entry["restart_required"])
            self.assertFalse(entry["deprecated"])
        self.assertIsNone(explain_key("web.top_clock.format")["allowed_values"])

    def test_authoritative_schema_matches_published_and_example(self):
        schema = schema_bundle()["config-v1.schema.json"]
        published = json.loads(
            (ROOT / "dist/schemas/config-v1.schema.json").read_text()
        )
        self.assertEqual(schema, published)
        clock = schema["properties"]["web"]["properties"]["top_clock"]
        self.assertEqual("object", clock["type"])
        self.assertIn("pattern", clock["properties"]["format"])
        self.assertEqual(128, clock["properties"]["format"]["maxLength"])
        example = json.loads(
            (ROOT / "examples/config/personal.lifetxt.json").read_text()
        )
        self.assertEqual("main", example["web"]["top_clock"]["timezone"])

    def test_optional_settings_do_not_require_config_migration(self):
        from lifetxt.config_validation import validate_config

        self.assertFalse(validate_config({"config_version": 1}))
        self.assertFalse(validate_config({"web": {"top_clock": {"enabled": False}}}))

    def test_semantics_and_accessibility_markup(self):
        self.assertIn('<time id="top-clock" aria-live="off" hidden>', HTML_PAGE)
        self.assertIn('<time id="kiosk-clock" aria-live="off"', HTML_PAGE)
        self.assertIn("font-variant-numeric: tabular-nums", HTML_PAGE)
        for language in ("en", "ja"):
            documentation = (ROOT / f"docs/{language}/config.md").read_text()
            for key in (
                "enabled",
                "format",
                "show_date",
                "timezone",
                "date_separator",
                "show_timezone",
            ):
                self.assertIn("web.top_clock." + key, documentation)


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class TopClockJavaScriptTests(unittest.TestCase):
    def test_formats_date_rollover_timer_lifecycle_and_no_network(self):
        source = (ROOT / "lifetxt/web_assets_js_13.js").read_text()
        source = source[
            source.index("    const TOP_CLOCK_FORMATS") : source.index(
                "    function _kioskStartScroll"
            )
        ]
        harness = r"""
const assert = require("node:assert/strict");
let appConfig = {};
const currentLanguage = () => "en";
const location = {pathname: "/"};
let kioskMode = false, displayMode = false, captureMode = false;
let callbacks = new Map(), timerId = 0;
const elements = {
  "top-clock": {hidden: true, style: {}, textContent: "", removeAttribute() {}},
  "kiosk-clock": {textContent: "", removeAttribute() {}},
};
const document = {getElementById: id => elements[id], body: {classList: {contains: () => captureMode}}};
const isKioskMode = () => kioskMode;
const isDisplayMode = () => displayMode;
const setInterval = (fn, ms) => { assert.equal(ms, 1000); callbacks.set(++timerId, fn); return timerId; };
const clearInterval = id => callbacks.delete(id);
global.fetch = () => { throw new Error("clock must not make network requests"); };
const RealDate = Date;
let current = new RealDate(2026, 9, 3, 21, 14, 37);
global.Date = class extends RealDate { constructor(...args) { super(...(args.length ? args : [current.getTime()])); } };
"""
        assertions = r"""
const expected = ["21:14", "21:14:37", "9:14 PM", "9:14:37 PM"];
TOP_CLOCK_FORMATS.forEach((format, index) => {
  appConfig = {web: {top_clock: {format, show_date: true, timezone: "browser-local"}}};
  _syncWebClocks();
  assert.equal(elements["top-clock"].textContent, "2026-10-03 " + expected[index]);
  assert.equal(elements["top-clock"].dateTime, current.toISOString());
  assert.equal(elements["top-clock"].hidden, false);
  assert.equal(callbacks.size, 1);
});
for (const raw of [null, [], "bad", {format: "<script>"}, {format: ["HH:mm:ss"]}, {enabled: "false", show_date: "true"}]) {
  appConfig = {web: {top_clock: raw}};
  _syncWebClocks();
  assert.equal(_topClockSettings().format, "HH:mm");
  assert.equal(elements["top-clock"].hidden, false);
}
for (const [hour, expected] of [[0, "12:00:00 AM"], [12, "12:00:00 PM"], [23, "11:00:00 PM"]]) {
  assert.equal(_formatWebClock(new RealDate(2026, 9, 3, hour), {format: "h:mm:ss a"}), expected);
}
appConfig = {web: {top_clock: {format: "HH:mm:ss", show_date: true, timezone: "browser-local"}}};
current = new RealDate(2026, 11, 31, 23, 59, 59);
_syncWebClocks();
assert.equal(elements["top-clock"].textContent, "2026-12-31 23:59:59");
current = new RealDate(2027, 0, 1, 0, 0, 0);
[...callbacks.values()][0]();
assert.equal(elements["top-clock"].textContent, "2027-01-01 00:00:00");
current = new RealDate(2027, 0, 1, 0, 0, 1);
[...callbacks.values()][0]();
assert.equal(elements["top-clock"].textContent, "2027-01-01 00:00:01");
for (let i = 0; i < 5; i++) _syncWebClocks();
assert.equal(callbacks.size, 1);
appConfig.web.top_clock.enabled = false;
_syncWebClocks();
assert.equal(callbacks.size, 0);
assert.equal(elements["top-clock"].hidden, true);
kioskMode = true;
_kioskStartClock();
assert.equal(callbacks.size, 1);
assert.equal(elements["top-clock"].hidden, true);
assert.equal(elements["kiosk-clock"].textContent,
  current.toLocaleDateString(undefined, {weekday:"short", month:"short", day:"numeric"}) + "  " +
  current.toLocaleTimeString(undefined, {hour:"2-digit", minute:"2-digit"}));
assert.equal(elements["kiosk-clock"].dateTime, current.toISOString());
kioskMode = false;
_kioskStopClock();
assert.equal(elements["kiosk-clock"].textContent, "");
assert.equal(callbacks.size, 0);
appConfig.web.top_clock.enabled = true;
_kioskStopClock();
assert.equal(elements["top-clock"].hidden, false);
assert.equal(callbacks.size, 1);
displayMode = true;
_syncWebClocks();
assert.equal(elements["top-clock"].hidden, true);
assert.equal(callbacks.size, 0);
displayMode = false;
captureMode = true;
_syncWebClocks();
assert.equal(elements["top-clock"].hidden, true);
assert.equal(callbacks.size, 0);
captureMode = false;
location.pathname = "/capture/";
_syncWebClocks();
assert.equal(callbacks.size, 0);
assert.equal(elements["top-clock"].hidden, true);
console.log("shared clock behavior passed");
"""
        for timezone in ("UTC", "Asia/Tokyo", "America/New_York"):
            with self.subTest(timezone=timezone):
                process = subprocess.run(
                    ["node", "-e", harness + source + assertions],
                    env={**os.environ, "TZ": timezone},
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(0, process.returncode, process.stderr)
                self.assertIn("shared clock behavior passed", process.stdout)
