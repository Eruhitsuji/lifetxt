"""Dashboard project links reuse the existing Items query (#1471)."""

import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class DashboardProjectNavigationTests(unittest.TestCase):
    def test_projects_link_to_existing_filtered_items_without_mutation(self):
        start = HTML_PAGE.index("    function dashboardProjectItemsUrl(")
        end = HTML_PAGE.index("    function dashNavigate(", start)
        items_start = HTML_PAGE.index("    function itemQueryParams()")
        items_end = HTML_PAGE.index(
            "    function initItemFilterControls()", items_start
        )
        harness = r"""
const assert = require('node:assert/strict');
const special = '日本語 "<&/ #?=+project';
let href = 'https://example.invalid/app?view=dashboard&mode=display&workspace=dashboard&panel=dashboard&id=old&line=99&project=old&tag=keep&status=%5B+%5D&lang=ja&theme=dark&text=find&limit=20&sort=title&order=asc';
function query(){return new URL(href).searchParams;}
function t(s){return s;}
function escapeHtml(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');}
function decode(s){return s.replaceAll('&quot;','"').replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&amp;','&');}
function jsLiteral(s){return JSON.stringify(s);}
function _fmtDate(){return '2030-01-01';}
function itemDueSoonClass(){return '';}
const projects=[{project:'empty',total:0,done:0},{project:special,total:8,done:3},{project:'Second',total:2,done:1},{project:'Outside limit',total:1,done:0}];
function dashboardLimit(name,fallback){assert.equal(name,'projects');assert.equal(fallback,7);return 2;}
let rendered='';
const projectEl={set innerHTML(html){rendered=html;}};
const controls={kind:{value:''},search:{value:'find'},limit:{value:'20'},sort:{value:'title'},order:{value:'asc'},'open-only':{checked:false},'group-by':{value:''}};
const document={getElementById(id){return id==='dash-projects'?projectEl:controls[id]||null;},querySelector(){return null;}};
const window={};
const calls=[];
async function api(url,options){
  assert.ok(!options || !options.method || options.method==='GET');
  calls.push(url);
  if(url==='/api/stats/summary')return {by_project:projects};
  return {items:[],records:[],diagnostics:[]};
}
function firstParam(params,keys,fallback){for(const key of keys)if(params.has(key))return params.get(key);return fallback;}
function boolParam(params,keys){return keys.some(key=>params.get(key)==='true');}
function applyKioskFilterParams(){}
function renderDiagnostics(){}
function renderItems(){}
function updateTagSuggestions(){}
function syncStatusFilterBtns(){}
let currentItems=[],selectedItem=null;
const location={pathname:'/app'};
const history={replaceState(_state,_title,path){href=new URL(path,'https://example.invalid').href;}};
(async()=>{
  await loadDashboard();
  assert.equal(calls.length,5);
  const links=[...rendered.matchAll(/<a class="dash-row-title drawer-link" href="([^"]+)">([^]*?)<\/a>/g)];
  assert.equal(links.length,2);
  assert.equal(decode(links[0][2]),special);
  assert.equal(decode(links[1][2]),'Second');
  assert.ok(!rendered.includes('Outside limit'));
  assert.ok(!rendered.includes('<&'));
  assert.ok(rendered.includes('3/8'));
  assert.ok(rendered.includes('1/2'));
  assert.equal((rendered.match(/onclick="newRelatedItemFromProject\(/g)||[]).length,2);
  assert.ok(!rendered.includes('onclick="dashboardProject'));
  assert.ok(!rendered.includes('data-dash-project')); // native links, no custom click handler
  // Following the first href uses the ordinary Items loader/query.
  href=new URL(decode(links[0][1]),href).href;
  const target=query();
  assert.equal(target.get('project'),special);
  for(const key of ['view','mode','workspace','panel','id','line'])assert.equal(target.has(key),false);
  for(const [key,value] of Object.entries({tag:'keep',status:'[ ]',lang:'ja',theme:'dark',text:'find',limit:'20',sort:'title',order:'asc'}))assert.equal(target.get(key),value);
  await loadItems();
  const request=new URL(calls.at(-1),'https://example.invalid');
  assert.equal(request.pathname,'/api/items');
  assert.equal(request.searchParams.get('project'),special);
  assert.equal(request.searchParams.get('tag'),'keep');
  assert.equal(request.searchParams.get('status'),'[ ]');
  assert.equal(request.searchParams.get('text'),'find');
  assert.equal(query().get('project'),special);
  // Empty projects and refresh do not leave old links.
  projects.length=0;
  await loadDashboard();
  assert.ok(rendered.includes('No project data.'));
  assert.ok(!rendered.includes('<a'));
  for(const count of [1,2,3,20]){
    projects.splice(0,projects.length,...Array.from({length:count},(_,i)=>({project:'Project '+i,total:1,done:0})));
    await loadDashboard();
    assert.equal((rendered.match(/<a /g)||[]).length,Math.min(count,2));
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result = subprocess.run(
            [
                "node",
                "-e",
                HTML_PAGE[start:end] + HTML_PAGE[items_start:items_end] + harness,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stderr)
