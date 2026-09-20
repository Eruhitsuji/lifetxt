"""Behavioral and responsive checks for the Web backup status panel."""

import json
import re
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


def _script_under_test():
    script = re.search(r"<script>(.*)</script>", HTML_PAGE, re.S).group(1)
    start = script.index("function backupStateCopy(")
    end_anchor = script.index("async function loadServerBackupStatus(", start)
    end = script.index("\n    }", end_anchor) + len("\n    }")
    return script[start:end]


_HARNESS = r"""
const escapeHtml = value => String(value).replace(/[&<>"']/g, ch => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[ch]));
%s
const node = {
  innerHTML: "", attributes: {},
  setAttribute(name, value) { this.attributes[name] = value; },
};
global.document = {getElementById: id => id === "server-backup-status" ? node : null};
global.t = text => text;
let apiResult = null;
let apiError = null;
global.api = async path => {
  if (path !== "/api/backup/status") throw new Error("wrong API");
  if (apiError) throw apiError;
  return apiResult;
};

async function main() {
  const states = {};
  for (const state of ["unconfigured", "disabled", "never_run", "local_failure", "remote_failure", "healthy", "unavailable"]) {
    states[state] = renderServerBackupStatus({
      state, enabled: state !== "disabled", backup_count: 0,
      local: {last_attempt_result: "never_run"},
      remote: {configured: false, last_upload_result: "not_configured"},
    });
  }
  apiResult = {
    state: "remote_failure", enabled: true, backup_count: 2,
    latest_local_backup: "backup-2.ltbackup",
    local: {last_attempt_result: "success", last_attempt_at: "2026-09-20T01:00:00Z", last_success_at: "2026-09-20T01:00:00Z"},
    remote: {configured: true, last_upload_result: "failure", last_upload_at: "2026-09-20T01:01:00Z", last_error_summary: "Remote upload failed."},
  };
  await loadServerBackupStatus();
  const successHtml = node.innerHTML;
  apiError = new Error("offline");
  await loadServerBackupStatus();
  console.log(JSON.stringify({states, successHtml, errorHtml: node.innerHTML, busy: node.attributes["aria-busy"]}));
}
main().catch(error => { console.error(error); process.exit(1); });
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class WebBackupStatusJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            ["node", "-e", _HARNESS % _script_under_test()],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        if proc.returncode:
            raise AssertionError(proc.stderr or proc.stdout)
        cls.result = json.loads(proc.stdout)

    def test_all_operational_states_have_understandable_rendering(self):
        for state in (
            "unconfigured",
            "disabled",
            "never_run",
            "local_failure",
            "remote_failure",
            "healthy",
            "unavailable",
        ):
            self.assertIn("backup-summary", self.result["states"][state])
        self.assertIn(
            "Ubuntu Server backup guide", self.result["states"]["unconfigured"]
        )

    def test_local_and_remote_status_are_separate_and_failure_is_visible(self):
        html = self.result["successHtml"]
        self.assertIn("Local backup", html)
        self.assertIn("Off-host upload", html)
        self.assertIn("backup-2.ltbackup", html)
        self.assertIn("Remote upload failed.", html)
        self.assertIn("Failed", html)
        self.assertIn("Not configured", self.result["states"]["healthy"])
        self.assertNotIn(">failure<", html)

    def test_api_failure_is_accessible_and_clears_busy_state(self):
        self.assertIn('role="alert"', self.result["errorHtml"])
        self.assertIn("offline", self.result["errorHtml"])
        self.assertEqual("false", self.result["busy"])

    def test_panel_has_a_single_column_mobile_layout(self):
        style = re.search(r"<style>(.*?)</style>", HTML_PAGE, re.S).group(1)
        self.assertRegex(
            style,
            r"@media \(max-width: 680px\) \{[^}]*\.backup-summary[^}]*\}[^}]*"
            r"\.backup-panel-grid \{ grid-template-columns: 1fr; \}",
        )

    def test_dynamic_status_copy_and_refresh_control_are_translatable(self):
        for text in (
            "Backups not configured",
            "Backup healthy",
            "Success",
            "Failed",
            "Never run",
            "Not configured",
            "Yes",
            "No",
        ):
            self.assertRegex(
                HTML_PAGE, rf'"{re.escape(text)}"\s*:\s*"[^\"]*[ぁ-んァ-ヶ一-龠]'
            )
        self.assertIn(
            'aria-label="Refresh server backup status"',
            HTML_PAGE,
        )


if __name__ == "__main__":
    unittest.main()
