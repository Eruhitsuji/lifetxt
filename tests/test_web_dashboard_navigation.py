"""Dashboard agenda titles reuse source-record navigation (#1461)."""

import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class DashboardNavigationTests(unittest.TestCase):
    def test_dashboard_render_links_limits_and_handlers(self):
        helper_start = HTML_PAGE.index("    function agendaRecordTitleHtml(")
        helper_end = HTML_PAGE.index("    async function loadAgenda()", helper_start)
        start = HTML_PAGE.index("    async function loadDashboard()")
        end = HTML_PAGE.index("    function dashNavigate(", start)
        harness = r"""
const assert = require('node:assert/strict');
function escapeHtml(s) {return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');}
function query() {return new URLSearchParams('view=dashboard&project=Work&from=2030-01-01&line=9');}
const opened=[];function openItemById(id){opened.push(id);}
const id='source "<&/id';
const records=[
  {title:'<img src=x>',source_id:id,when:'2030-01-01T10:00',blocked:true,occurrence_index:2},
  {title:'IDなし',when:'2030-01-01T11:00',line:9},
  {title:'Repeat',source_id:id,occurrence_index:3},
  {title:'Outside limit',source_id:'hidden'}
];
const calls=[];
async function api(url){calls.push(url);return url.startsWith('/api/agenda?')?{records}:{};}
function dashboardLimit(name,fallback){assert.equal(name,'today');assert.equal(fallback,7);return 3;}
function _fmtDate(){return '2030-01-01';}
function itemDueSoonClass(){throw Error('no items');}
let rendered='',links=[];
const todayEl={
  set innerHTML(value){
    rendered=value;
    links=[...value.matchAll(/data-agenda-id="([^"]+)"/g)].map(()=>({
      dataset:{agendaId:id},handlers:[],
      addEventListener(type,handler){this.handlers.push({type,handler});}
    }));
  },
  querySelectorAll(selector){assert.equal(selector,'[data-agenda-id]');return links;}
};
const document={getElementById(id){return id==='dash-today'?todayEl:null;},querySelector(){return null;}};
const window={};
(async()=>{
  await loadDashboard();
  assert.equal(calls.length,5);
  assert.ok(calls.includes('/api/agenda?around=now&window=1d&open_only=true'));
  assert.equal(links.length,2);
  assert.ok(rendered.includes('&lt;img src=x&gt;'));
  assert.ok(!rendered.includes('<img'));
  assert.ok(rendered.includes('<span class="dash-row-title">IDなし</span>'));
  assert.ok(rendered.includes('2030-01-01 10:00'));
  assert.ok(rendered.includes('blocked-badge'));
  assert.ok(rendered.indexOf('&lt;img')<rendered.indexOf('IDなし'));
  assert.ok(rendered.indexOf('IDなし')<rendered.indexOf('Repeat'));
  assert.ok(!rendered.includes('Outside limit'));
  assert.ok(rendered.includes('View all 4'));
  const href=rendered.match(/href="([^"]+)"/)[1].replaceAll('&amp;','&');
  const params=new URLSearchParams(href.slice(1));
  assert.equal(params.get('id'),id);
  assert.equal(params.get('view'),'dashboard');
  assert.equal(params.get('project'),'Work');
  assert.equal(params.get('from'),'2030-01-01');
  assert.equal(params.has('line'),false);
  for(const link of links){
    assert.equal(link.handlers.length,1);
    assert.equal(link.handlers[0].type,'click');
    let prevented=0;
    const event={button:0,currentTarget:link,preventDefault(){prevented++;}};
    link.handlers[0].handler(event);
    assert.equal(prevented,1);
    for(const modifier of [{ctrlKey:true},{metaKey:true},{shiftKey:true},{altKey:true},{button:1}]){
      link.handlers[0].handler({...event,...modifier});
    }
    assert.equal(prevented,1);
  }
  assert.deepEqual(opened,[id,id]);
  // Refresh binds exactly once to new nodes, and empty results have no links.
  await loadDashboard();assert.equal(links.length,2);
  assert.ok(links.every(link=>link.handlers.length===1));
  records.length=0;
  await loadDashboard();assert.equal(links.length,0);
  assert.ok(rendered.includes('Nothing scheduled around now.'));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result = subprocess.run(
            [
                "node",
                "-e",
                HTML_PAGE[helper_start:helper_end] + HTML_PAGE[start:end] + harness,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)
