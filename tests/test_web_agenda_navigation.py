"""Agenda links reuse canonical source IDs and the existing drawer (#1457)."""

import shutil
import subprocess
import unittest
from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class AgendaNavigationTests(unittest.TestCase):
    def test_links_preserve_context_escape_content_and_open_only_on_normal_click(self):
        start = HTML_PAGE.index("    function agendaRecordTitleHtml(")
        end = HTML_PAGE.index("    async function loadAgenda()", start)
        harness = r"""
const assert=require('node:assert/strict');
function escapeHtml(s) {return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');}
function query() {return new URLSearchParams('view=agenda&from=2030-01-01&kind=E&line=42');}
const opened=[];function openItemById(id){opened.push(id);}
const id='source "<&/id';
const html=agendaRecordTitleHtml({title:'<img src=x>',source_id:id,occurrence_index:7});
assert.ok(html.includes('&lt;img src=x&gt;'));assert.ok(!html.includes('<img'));
assert.ok(html.includes('data-agenda-id="source &quot;&lt;&amp;/id"'));
const href=html.match(/href="([^"]+)"/)[1].replaceAll('&amp;','&');
const params=new URLSearchParams(href.slice(1));
assert.equal(params.get('id'),id);assert.equal(params.get('view'),'agenda');
assert.equal(params.get('from'),'2030-01-01');assert.equal(params.get('kind'),'E');assert.equal(params.has('line'),false);
assert.equal(agendaRecordTitleHtml({title:'No ID'}),'No ID');
let prevented=0;
const click={button:0,currentTarget:{dataset:{agendaId:id}},preventDefault(){prevented++}};
openAgendaRecord(click);assert.deepEqual(opened,[id]);assert.equal(prevented,1);
for(const extra of [{ctrlKey:true},{metaKey:true},{shiftKey:true},{altKey:true},{button:1}])openAgendaRecord({...click,...extra});
assert.deepEqual(opened,[id]);assert.equal(prevented,1);
"""
        result = subprocess.run(
            ["node", "-e", HTML_PAGE[start:end] + harness],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_agenda_renderer_uses_link_and_binds_handler(self):
        start = HTML_PAGE.index("    async function loadAgenda()")
        end = HTML_PAGE.index("    // ── Presence rendering", start)
        source = HTML_PAGE[start:end]
        self.assertIn("${agendaRecordTitleHtml(record)}", source)
        self.assertIn('link.addEventListener("click", openAgendaRecord)', source)

    def test_show_all_link_and_row_limit_input_use_same_url_setting(self):
        agenda = HTML_PAGE[
            HTML_PAGE.index("    function _temporalDisplayLabel(") : HTML_PAGE.index(
                "    // ── Presence rendering"
            )
        ]
        controls_start = HTML_PAGE.index("    function setAgendaLimit(n)")
        controls_end = HTML_PAGE.index("    // ── Context menu", controls_start)
        spinner_start = HTML_PAGE.index("      // Sync agenda limit spinner")
        spinner_end = HTML_PAGE.index("\n    });", spinner_start)
        harness = r"""
const assert = require("node:assert/strict");
const agendaNode = {
  innerHTML: "",
  insertAdjacentHTML: (_position, html) => { agendaNode.innerHTML += html; },
  querySelectorAll: () => [],
};
let onChange;
const input = {value: "8", addEventListener: (event, fn) => {
  assert.equal(event, "change");
  onChange = fn;
}};
const document = {getElementById: id => ({
  "agenda": agendaNode, "open-only": {checked: false}, "agenda-limit-spinner": input
})[id]};
const location = new URL("http://localhost/?view=agenda&from=2030-01-01&kind=E&limit=20");
const history = {replaceState: (_state, _title, url) => { location.href = new URL(url, location); }};
const query = () => new URLSearchParams(location.search);
const firstParam = (params, [key], fallback) => params.get(key) || fallback;
const boolParam = () => false;
const agendaBlockedMode = () => "";
const _syncAgendaBlockedBtn = () => {};
const escapeHtml = value => String(value);
const t = escapeHtml;
const agendaDueSoonClass = () => "";
const agendaCountdownLabel = () => "";
const updateAgendaOverdueBadge = () => {};
const api = async url => {
  const params = new URL(url, location).searchParams;
  assert.equal(params.get("from"), "2030-01-01");
  assert.equal(params.get("kind"), "E");
  assert.equal(params.get("limit"), "20");
  assert.equal(params.has("agenda_limit"), false);
  return {records: Array.from({length: 10}, (_, i) => ({
    title: "Appointment " + (i + 1), when: "2030-01-01",
  }))};
};
"""
        checks = r"""
const countRows = () => (agendaNode.innerHTML.match(/class="title"/g) || []).length;
const flush = () => new Promise(resolve => setImmediate(resolve));
async function main() {
  await loadAgenda();
  assert.equal(countRows(), 8);
  const link = agendaNode.innerHTML.match(/onclick="([^"]+)"[^>]*>View all 10/);
  assert.ok(link);
  const event = {preventDefault() {}};
  eval(link[1]);
  await flush();
  assert.equal(query().get("agenda_limit"), "0");
  assert.equal(input.value, "0");
  assert.equal(countRows(), 10);
  assert.doesNotMatch(agendaNode.innerHTML, /View all/);

  for (const [value, expectedParam, expectedValue, expectedRows] of [
    ["3", "3", "3", 3], ["0", "0", "0", 10], ["", null, "8", 8],
  ]) {
    input.value = value;
    onChange();
    await flush();
    assert.equal(query().get("agenda_limit"), expectedParam);
    assert.equal(input.value, expectedValue);
    assert.equal(countRows(), expectedRows);
  }

  location.search += "&agenda_limit=0";
  await loadAgenda();
  assert.equal(input.value, "0");
  assert.equal(countRows(), 10);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
"""
        script = (
            harness
            + agenda
            + HTML_PAGE[controls_start:controls_end]
            + HTML_PAGE[spinner_start:spinner_end]
            + checks
        )
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=15
        )
        self.assertEqual(0, result.returncode, result.stderr)
