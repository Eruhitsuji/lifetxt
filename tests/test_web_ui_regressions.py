"""Always-on disclosure state and shared semantic-control regression contracts."""

import json
import re
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


class WebUIRegressionsTests(unittest.TestCase):
    def test_raw_import_starts_hidden_and_has_accessible_guidance(self):
        self.assertRegex(HTML_PAGE, r'<div id="import-raw-row"[^>]*\bhidden>')
        self.assertIn('aria-controls="import-raw-row" aria-expanded="false"', HTML_PAGE)
        self.assertIn('aria-describedby="import-raw-help"', HTML_PAGE)
        self.assertIn('id="import-raw-help"', HTML_PAGE)
        self.assertIn("Review the form before creating the record.", HTML_PAGE)
        self.assertNotRegex(HTML_PAGE, r"#import-raw-row\s*\{[^}]*display\s*:\s*none")

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_first_toggle_cancel_and_reopen_follow_hidden_state_and_focus(self):
        function = re.search(
            r"    function toggleImportRaw\(show\) \{.*?(?=    async function importRawLine)",
            HTML_PAGE,
            re.S,
        ).group(0)
        script = """
const vm = require('node:vm');
const input = {focus() {document.activeElement = this;}};
const toggle = {expanded: 'false', setAttribute(key, value) {this.expanded = value;},
  focus() {document.activeElement = this;}};
const row = {hidden: true, contains(el) {return el === input;}};
const document = {activeElement: toggle, getElementById(id) {
  return {'import-raw-row': row, 'import-raw-input': input, 'import-raw-toggle': toggle}[id];
}};
const context = vm.createContext({document});
vm.runInContext(FUNCTION, context);
const results = [];
for (const call of ['toggleImportRaw()', 'toggleImportRaw(false)',
                    'toggleImportRaw()', 'toggleImportRaw()', 'toggleImportRaw(true)']) {
  vm.runInContext(call, context);
  results.push({hidden: row.hidden, expanded: toggle.expanded,
    focused: document.activeElement === input ? 'input' : 'toggle'});
}
process.stdout.write(JSON.stringify(results));
""".replace("FUNCTION", json.dumps(function))
        run = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=10
        )
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual(
            [
                {"hidden": False, "expanded": "true", "focused": "input"},
                {"hidden": True, "expanded": "false", "focused": "toggle"},
                {"hidden": False, "expanded": "true", "focused": "input"},
                {"hidden": True, "expanded": "false", "focused": "toggle"},
                {"hidden": False, "expanded": "true", "focused": "input"},
            ],
            json.loads(run.stdout),
        )

    def test_static_and_rebuilt_drawer_summaries_share_secondary_control_contract(self):
        self.assertEqual(
            2,
            HTML_PAGE.count('<summary class="button-control secondary"'),
        )
        self.assertIn("button.secondary, .button-control.secondary {", HTML_PAGE)
        self.assertIn(
            "button.secondary:hover, .button-control.secondary:hover {", HTML_PAGE
        )
        self.assertIn(
            "button:active, .button-control:active, .workspace-tab:active", HTML_PAGE
        )
        self.assertIn(".drawer-overflow > summary::-webkit-details-marker", HTML_PAGE)

    def test_native_more_links_use_shared_workspace_geometry_on_phone(self):
        for href in ("/planner", "/capture"):
            self.assertIn(
                f'<a class="workspace-tab surface-link" href="{href}">', HTML_PAGE
            )
        self.assertIn(".surface-link { text-decoration: none; }", HTML_PAGE)
        self.assertNotIn(".nav-advanced > .surface-link {", HTML_PAGE)
        self.assertIn(".nav-advanced .workspace-tab { width: 100%; }", HTML_PAGE)
        self.assertIn("min-height: max(44px, var(--control-height));", HTML_PAGE)
