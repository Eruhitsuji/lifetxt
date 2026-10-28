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
