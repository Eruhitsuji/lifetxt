"""Notification permission presentation across languages (#1501)."""

import json
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE
from tests.test_web_i18n import _ja_dictionary


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class NotificationPermissionTests(unittest.TestCase):
    def test_notification_controls_delivery_and_permission(self):
        start = HTML_PAGE.index("    function notificationsDisabled()")
        end = HTML_PAGE.index("    function escapeHtml(", start)
        controls = HTML_PAGE.index("    function browserAlertsPermissionLabel(")
        controls_end = HTML_PAGE.index("    // ── Git status badge", controls)
        retry = HTML_PAGE.index("    async function retryBrowserNotification(")
        retry_end = HTML_PAGE.index("    // ── Dashboard view", retry)
        declarations = HTML_PAGE[
            HTML_PAGE.index("    let browserAlertsPaused") : HTML_PAGE.index(
                "    let appConfig"
            )
        ]
        occurrence = HTML_PAGE[
            HTML_PAGE.index(
                "    function notificationOccurrenceKey("
            ) : HTML_PAGE.index("    async function loadNotifications()")
        ]
        script = r"""
const vm = require("node:vm");
const assert = require("node:assert/strict");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));

function fixture(storage = new Map(), lang = "en") {
  const calls = [], toasts = [], nodes = new Map();
  function element(id) {
    if (!nodes.has(id)) nodes.set(id, {
      textContent: "", classList: {add() {}},
      insertAdjacentHTML(_, html) { this.textContent += html; }
    });
    return nodes.get(id);
  }
  const record = {id: "m1", notification_id: "m1:notify_at:t1", title: "First", details: {}};
  class Notification {
    static permission = "granted";
    static async requestPermission() { calls.push("permission"); }
    constructor(title) {
      if (this.constructor.fail) throw Error("delivery failed");
      calls.push(title);
    }
  }
  const sandbox = {
    window: {Notification, isSecureContext: true, _lastNotifRecords: [record],
      localStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value)}},
    document: {documentElement: {lang}, getElementById: element},
    appConfig: {}, record, escapeHtml: s => s, updateNotifBtnLabel() {},
    loadNotifications: async () => calls.push("refresh"),
    t: s => lang === "ja" ? (input.dictionary[s] || s) : s,
    showToast: (...args) => toasts.push(args),
  };
  vm.createContext(sandbox);
  vm.runInContext(input.source, sandbox);
  return {run: source => vm.runInContext(source, sandbox), sandbox, Notification,
    calls, toasts, element, storage};
}

(async () => {
  for (const lang of ["en", "ja"]) {
    const f = fixture(new Map(), lang);
    f.run("syncNotificationControls()");
    assert.equal(f.element("notif-alert-toggle").checked, true);
    assert.equal(await f.run("showBrowserNotification(record)"), true);
    assert.equal(await f.run("showBrowserNotification(record)"), false);
    assert.equal(await fixture(f.storage).run("showBrowserNotification(record)"), false);
    f.sandbox.record.details.snooze_until = ["later"];
    assert.equal(await f.run("showBrowserNotification(record)"), true);

    await f.run("setAutomaticAlerts(false)");
    assert.equal(fixture(f.storage).run("automaticAlertsEnabled()"), false);
    await f.run("sendTestNotification()");
    assert.equal(f.toasts.at(-1)[1], "success");

    f.Notification.permission = "denied";
    f.run("syncNotificationControls()");
    assert.equal(f.element("notif-alert-toggle").disabled, true);
    assert.match(f.element("notif-permission-bar").textContent, /blocked|ブロック/);
    await f.run("retryBrowserNotification(record.notification_id)");
    assert.equal(f.toasts.at(-1)[1], "info");
    assert.equal(f.calls.includes("permission"), false);
    f.Notification.permission = "default";
    await f.run("sendTestNotification()");
    assert.equal(f.calls.at(-1), "permission");
    assert.equal(f.toasts.at(-1)[1], "warning");
    f.Notification.permission = "granted";
    f.Notification.fail = true;
    await f.run("retryBrowserNotification(record.notification_id)");
    assert.equal(f.toasts.at(-1)[1], "error");
    f.Notification.fail = false;
    await f.run("retryBrowserNotification(record.notification_id)");
    assert.equal(f.toasts.at(-1)[1], "success");
    await f.run("setAutomaticAlerts(true)");
    assert.equal(f.element("notif-alert-toggle").checked, true);
    assert.equal(f.calls.at(-1), "refresh");
    f.sandbox.window.isSecureContext = false;
    f.run("syncNotificationControls()");
    assert.match(f.element("notif-permission-bar").textContent, /HTTPS/);
  }

  const desktop = fixture();
  const bridge = {enabled: false, async setEnabled(value) { this.enabled = value; },
    async send(...args) { desktop.calls.push(args); }};
  desktop.sandbox.window.Notification = undefined;
  desktop.sandbox.window.lifetxtDesktopAlerts = bridge;
  assert.equal(await desktop.run("showBrowserNotification(record)"), false);
  await desktop.run("sendTestNotification()");
  await desktop.run("retryBrowserNotification(record.notification_id)");
  await desktop.run("setAutomaticAlerts(true)");
  assert.equal(await desktop.run("showBrowserNotification(record)"), false);
  desktop.sandbox.record.notification_id = "another occurrence";
  assert.equal(await desktop.run("showBrowserNotification(record)"), true);
  assert.deepEqual(desktop.calls, [[true, false, false], [false, true, false], "refresh", [false, false, false]]);
  desktop.sandbox.appConfig.notifications = {web: false};
  await desktop.run("sendTestNotification()");
  assert.equal(desktop.calls.length, 4);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(
                {
                    "source": declarations
                    + occurrence
                    + HTML_PAGE[start:end]
                    + HTML_PAGE[controls:controls_end]
                    + HTML_PAGE[retry:retry_end],
                    "dictionary": _ja_dictionary(),
                }
            ),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
