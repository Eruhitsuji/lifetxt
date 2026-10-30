"""Dashboard distinguishes failed reads from successful zero results (#1473)."""

import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class DashboardLoadErrorTests(unittest.TestCase):
    def test_partial_failures_recovery_and_late_responses(self):
        start = HTML_PAGE.index("    let _dashChart = null;")
        end = HTML_PAGE.index("    // ── Today view", start)
        harness = r"""
const assert=require('node:assert/strict');
let language='en';
function t(s){return language==='ja'?'日本語:'+s:s;}
function escapeHtml(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');}
function jsLiteral(s){return JSON.stringify(s);}
const STATUS_CLASS={}, STATUS_ICON={};
function buildDueRelLabel(){return '';}
function itemDueSoonClass(item){return item.overdue?'overdue':'';}
function _fmtDate(){return '2030-01-01';}
function dashboardLimit(){return 7;}
function agendaRecordTitleHtml(record){return escapeHtml(record.title);}
function query(){return new URLSearchParams('view=dashboard&lang=ja');}
const nodes=Object.fromEntries(['dash-date','dash-load-status','dash-kpis','dash-today','dash-overdue','dash-projects','dash-chart-status','dash-chart'].map(id=>[id,{innerHTML:'',textContent:'',hidden:false,querySelectorAll(){return [];},getContext(){return {};}}]));
let chartHidden=false;
const document={getElementById(id){return nodes[id]||null;},querySelector(){return {classList:{contains(){return chartHidden;}}};}};
const window={};
const CHART_COLORS=['#123456'];
let charts=[],destroyed=0,chartConstructFails=false;
class Chart{constructor(ctx,config){if(chartConstructFails)throw Error('render');this.config=config;charts.push(this);}destroy(){destroyed++;}}
let ensureImpl=async()=>{},ensureCalls=0;
async function ensureChartJs(){ensureCalls++;await ensureImpl();}
const open={id:'open',line:1,title:'Overdue <item>',type:'T',status:'[ ]',overdue:true,details:{}};
const blocked={id:'blocked',line:2,title:'Blocked item',type:'T',status:'[ ]',details:{}};
const payloads=[{items:[open]},{items:[blocked]},{records:[{title:'Agenda <record>',source_id:'agenda'}]},{labels:['2030-01-01'],datasets:[{label:'Done',data:[3]}]},{by_project:[{project:'Project <one>',total:5,done:2}]}];
const empty=[{items:[]},{items:[]},{records:[]},{labels:[],datasets:[]},{by_project:[]}];
function sourceIndex(url){
 if(url==='/api/items?open_only=true')return 0;
 if(url==='/api/items?blocked=true&open_only=true')return 1;
 if(url.startsWith('/api/agenda?'))return 2;
 if(url.startsWith('/api/chart/tasks?'))return 3;
 if(url==='/api/stats/summary')return 4;
 throw Error('Unexpected API '+url);
}
let calls=[],failures=new Set(),responsePayloads=payloads,errorStatus=503;
let apiImpl=async index=>{
 if(failures.has(index))throw Object.assign(Error('<private failure>'),{status:errorStatus});
 return responsePayloads[index];
};
async function api(url,options){assert.ok(!options || !options.method || options.method==='GET');calls.push(url);return apiImpl(sourceIndex(url));}
function snapshot(){return JSON.stringify(Object.fromEntries(Object.entries(nodes).map(([id,node])=>[id,{html:node.innerHTML,text:node.textContent,hidden:node.hidden}])));}
function assertHealthy(){
 assert.deepEqual(window._dashKpis.map(k=>k.n),[1,0,1,1,3]);
 assert.ok(!window._dashKpis.some(k=>k.unavailable));
 assert.ok(nodes['dash-today'].innerHTML.includes('Agenda &lt;record&gt;'));
 assert.ok(nodes['dash-projects'].innerHTML.includes('Project &lt;one&gt;'));
 assert.ok(nodes['dash-overdue'].innerHTML.includes('Overdue &lt;item&gt;'));
 assert.equal(nodes['dash-load-status'].innerHTML,'');
 assert.equal(nodes['dash-chart-status'].innerHTML,'');
 assert.equal(nodes['dash-chart'].hidden,false);
}
(async()=>{
 await loadDashboard();assertHealthy();assert.equal(calls.length,5);
 // Each API can fail independently; only dependent values become unavailable.
 for(errorStatus of [403,503,0])for(const failed of [0,1,2,3,4]){
  failures=new Set([failed]);
  const before=calls.length;
  await loadDashboard();assert.equal(calls.length-before,5);
  const kpis=window._dashKpis;
  const absent=failed===0?[0,1,2]:failed===1?[3]:failed===3?[4]:[];
  kpis.forEach((k,i)=>{assert.equal(!!k.unavailable,absent.includes(i));if(absent.includes(i))assert.equal(k.n,'—');});
  const tiles=[...nodes['dash-kpis'].innerHTML.matchAll(/<button ([^>]+)>(.*?)<\/button>/g)];
  assert.equal(tiles.length,5);
  tiles.forEach((tile,i)=>{
   assert.equal(tile[1].includes('disabled'),absent.includes(i));
   assert.equal(tile[1].includes('onclick='),!absent.includes(i));
   assert.equal(tile[2].includes('Unavailable'),absent.includes(i));
  });
  assert.ok(nodes['dash-load-status'].innerHTML.includes('Some dashboard data could not be loaded.'));
  assert.ok(nodes['dash-load-status'].innerHTML.includes('onclick="loadDashboard()"'));
  assert.ok(!snapshot().includes('private failure')); // raw server text not displayed
  if(failed===0||failed===1){
   assert.ok(nodes['dash-overdue'].innerHTML.includes('Could not load dashboard data.'));
   assert.ok(nodes['dash-overdue'].innerHTML.includes(failed===0?'Blocked item':'Overdue &lt;item&gt;'));
   assert.ok(!nodes['dash-overdue'].innerHTML.includes('Nothing overdue or blocked'));
  }
  if(failed===2){assert.ok(!nodes['dash-today'].innerHTML.includes('Nothing scheduled'));assert.ok(nodes['dash-today'].innerHTML.includes('Could not load dashboard data.'));}
  else assert.ok(nodes['dash-today'].innerHTML.includes('Agenda &lt;record&gt;'));
  if(failed===4){assert.ok(!nodes['dash-projects'].innerHTML.includes('No project data'));assert.ok(nodes['dash-projects'].innerHTML.includes('Could not load dashboard data.'));}
  else assert.ok(nodes['dash-projects'].innerHTML.includes('Project &lt;one&gt;'));
  if(failed===3){assert.equal(nodes['dash-chart'].hidden,true);assert.equal(_dashChart,null);assert.ok(nodes['dash-chart-status'].innerHTML.includes('Could not load dashboard data.'));}
  failures.clear();await loadDashboard();assertHealthy();
 }
 // Failure of all reads never reports a healthy empty state or zero counts.
 failures=new Set([0,1,2,3,4]);await loadDashboard();
 assert.ok(window._dashKpis.every(k=>k.unavailable));
 assert.ok(!snapshot().includes('Nothing overdue or blocked'));
 assert.ok(!snapshot().includes('Nothing scheduled around now'));
 assert.ok(!snapshot().includes('No project data.'));
 failures.clear();responsePayloads=empty;await loadDashboard();
 assert.deepEqual(window._dashKpis.map(k=>k.n),[0,0,0,0,0]);
 assert.ok(nodes['dash-overdue'].innerHTML.includes('Nothing overdue or blocked'));
 assert.ok(nodes['dash-today'].innerHTML.includes('Nothing scheduled around now'));
 assert.ok(nodes['dash-projects'].innerHTML.includes('No project data.'));
 assert.equal(nodes['dash-load-status'].innerHTML,'');
 // A partial result with no known rows still cannot claim all is well.
 failures.add(1);await loadDashboard();
 assert.ok(nodes['dash-overdue'].innerHTML.includes('Could not load dashboard data.'));
 assert.ok(!nodes['dash-overdue'].innerHTML.includes('Nothing overdue or blocked'));
 failures.clear();responsePayloads=payloads;await loadDashboard();assertHealthy();
 // A late older response cannot replace the newest dashboard.
 const waiting=[];apiImpl=index=>new Promise(resolve=>waiting.push(()=>resolve(empty[index])));
 const older=loadDashboard();
 assert.equal(nodes['dash-load-status'].textContent,'Refreshing dashboard…');
 apiImpl=async index=>payloads[index];
 await loadDashboard();const current=snapshot();const count=charts.length;
 waiting.forEach(resolve=>resolve());await older;
 assert.equal(snapshot(),current);assert.equal(charts.length,count);
 // Late Chart.js load cannot resurrect a stale chart after a failed newer read.
 let release;
 ensureImpl=()=>new Promise(resolve=>{release=resolve;});
 const oldChart=loadDashboard();
 while(!release)await new Promise(resolve=>setImmediate(resolve));
 failures.add(3);apiImpl=async index=>{if(failures.has(index))throw Error('network');return payloads[index];};
 await loadDashboard();const failedSnapshot=snapshot();
 release();await oldChart;assert.equal(snapshot(),failedSnapshot);assert.equal(_dashChart,null);
 failures.clear();ensureImpl=async()=>{throw Error('Chart.js unavailable');};
 await loadDashboard();
 assert.equal(nodes['dash-chart'].hidden,true);
 assert.ok(nodes['dash-chart-status'].innerHTML.includes('Dashboard chart could not be displayed.'));
 assert.equal(window._dashKpis[4].n,3); // data is known even if drawing fails
 ensureImpl=async()=>{};chartConstructFails=true;await loadDashboard();
 assert.equal(nodes['dash-chart'].hidden,true);
 assert.ok(nodes['dash-chart-status'].innerHTML.includes('Dashboard chart could not be displayed.'));
 chartConstructFails=false;await loadDashboard();assertHealthy();assert.ok(destroyed>0);
 chartHidden=true;const previousEnsures=ensureCalls;await loadDashboard();assert.equal(ensureCalls,previousEnsures);
 chartHidden=false;language='ja';failures.add(2);await loadDashboard();
 assert.ok(nodes['dash-load-status'].innerHTML.includes('日本語:Some dashboard data could not be loaded.'));
 assert.ok(nodes['dash-today'].innerHTML.includes('日本語:Could not load dashboard data.'));
 // Unavailable KPI cannot navigate even through a stale/direct invocation.
 failures.add(0);await loadDashboard();dashNavigate(0);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result = subprocess.run(
            ["node", "-e", HTML_PAGE[start:end] + harness],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stderr)
