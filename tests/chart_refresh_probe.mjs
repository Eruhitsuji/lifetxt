// Run shipped chart handlers with a transport/DOM adapter; no layout claims.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import path from 'node:path';
const [assetPath,statePath]=process.argv.slice(2);
const asset=await readFile(assetPath,'utf8'),state=await readFile(statePath,'utf8');
const helpers=asset.slice(asset.indexOf('    function statsDate('),asset.indexOf('    let statsBreakdownGeneration ='));
const handlers=helpers+asset.slice(asset.indexOf('    let chartLoadGeneration ='),asset.indexOf('    function exportChartCsv('));
const range={from:'2026-06-01',to:'2026-06-30'};
const shared='?from=2026-06-01&to=2026-06-30';
const chartState=state.slice(state.indexOf('    let currentChartType'),state.indexOf('    // ── Status filter bar URL sync'));
const labels={en:['Tasks','Habits','Heatmap','Mood','Elapsed'],ja:['タスク','習慣','ヒートマップ','気分','経過時間']};
const types=['tasks','habits','habits-heatmap','mood','elapsed'];
let cases=0;
for(const language of ['en','ja'])for(const group of ['daily','weekly','monthly'])for(const [index,type] of types.entries()){
  const calls=[],charts=[];let destroyed=0,fail=false;
  const container={innerHTML:''},bar={style:{}},canvas={getContext:()=>({})};
  const tab={textContent:labels[language][index],classList:{add(){},remove(){}}};
  const sandbox={console,Date,Set,encodeURIComponent,appConfig:{today:range.to},mainChart:null,CHART_COLORS:['#123456'],
    ensureChartJs:async()=>{},t:text=>text,escapeHtml:value=>String(value).replaceAll('<','&lt;').replaceAll('>','&gt;'),
    document:{getElementById:id=>({'chart-container':container,'main-chart':canvas,'chart-group-bar':bar})[id],querySelector:()=>tab,querySelectorAll:()=>[tab]},
    api:async url=>{calls.push(url);if(fail)throw Error('<temporary>');return {range,labels:['Day'],datasets:[{label:'Completed',data:[2]}],habits:[]}},
    Chart:function(ctx,config){charts.push(config);this.destroy=()=>destroyed++}
  };
  vm.createContext(sandbox);vm.runInContext(chartState+handlers,sandbox);
  const settle=()=>new Promise(resolve=>setImmediate(resolve));
  vm.runInContext(`showChart('${type}',document.querySelector('.chart-tab.active'));setChartGroup('${group}',null)`,sandbox);
  await settle();calls.length=0;
  await vm.runInContext('refreshCharts()',sandbox);await settle();
  const expected='/api/chart/'+type+shared+(['tasks','habits','mood'].includes(type)?'&group='+group:'');
  assert.deepEqual(calls,[expected],`${language}/${type}/${group}: refresh uses canonical key`);
  if(type==='habits-heatmap')assert.match(container.innerHTML,/No habit data/);
  else {assert.ok(charts.length>=2);assert.ok(destroyed>=1);assert.equal(charts.at(-1).data.datasets[0].label,'Completed')}
  // Presentation changes after selection must not change the API contract.
  tab.textContent='Renamed <label>';calls.length=0;
  await vm.runInContext('refreshCharts()',sandbox);await settle();assert.deepEqual(calls,[expected]);
  fail=true;
  await vm.runInContext('refreshCharts()',sandbox);await settle();
  assert.match(container.innerHTML,/Could not load the statistics chart/);
  assert.match(container.innerHTML,/onclick="refreshCharts\(\)"/);
  assert.doesNotMatch(container.innerHTML,/temporary/);
  cases++;
}
// Real handlers sharing one canvas: stale chart and heatmap responses, a
// failed library load, and CSV availability must all follow the active view.
{
  const requests = [], charts = [], notices = [];
  const container = {innerHTML: ""};
  const canvas = {getContext: () => ({})};
  const chartData = {range,labels: ["Day"], datasets: [{label: "Completed", data: [2]}]};
  let failLibrary = false;
  const sandbox = {
    appConfig:{today:range.to}, mainChart: null, CHART_COLORS: ["#123456"], t: text => text, escapeHtml: String,
    ensureChartJs: async () => { if (failLibrary) throw Error("library unavailable"); },
    document: {getElementById: id => ({"chart-container": container, "main-chart": canvas})[id]},
    api: url => new Promise((resolve, reject) => requests.push({url, resolve, reject})),
    Chart: function (_ctx, config) {
      charts.push(this);
      this.options = config.options;
      this.destroy = () => { this.destroyed = true; };
    },
    showToast: (...args) => notices.push(args),
  };
  const csv = asset.slice(asset.indexOf("    function exportChartCsv("))
    + state.slice(0, state.indexOf("    const CHART_COLORS"));
  vm.createContext(sandbox);
  vm.runInContext(chartState + handlers + csv, sandbox);
  const run = code => vm.runInContext(code, sandbox);
  const settle = () => new Promise(resolve => setImmediate(resolve));
  const daily = run('loadChart("tasks")');
  await settle();
  const weekly = run('currentChartGroup = "weekly"; loadChart("tasks")');
  await settle();
  assert.equal(requests[0].url, "/api/chart/tasks"+shared+"&group=daily");
  assert.equal(requests[1].url, "/api/chart/tasks"+shared+"&group=weekly");
  requests[1].resolve(chartData);
  await weekly;
  assert.equal(charts[0].options.scales.y.title.text, "records / week");

  const heatmap = run('currentChartType = "habits-heatmap"; refreshCharts()');
  assert.match(container.innerHTML, /Loading statistics chart/);
  assert.ok(charts[0].destroyed);
  run("exportChartCsv()");
  assert.deepEqual(notices, [["No chart data to export.", "error"]]);
  requests[2].resolve({range,habits: []});
  await heatmap;
  requests[0].resolve(chartData);
  await daily;
  assert.match(container.innerHTML, /No habit data/);
  assert.equal(charts.length, 1);

  const outdatedHeatmap = run("refreshCharts()");
  failLibrary = true;
  await run('currentChartType = "mood"; currentChartGroup = "monthly"; refreshCharts()');
  assert.match(container.innerHTML, /Reload chart/);
  assert.doesNotMatch(container.innerHTML, /library unavailable/);
  failLibrary = false;
  const retry = run(container.innerHTML.match(/onclick="([^"]+)"/)[1]);
  await settle();
  assert.equal(requests[4].url, "/api/chart/mood"+shared+"&group=monthly");
  requests[4].resolve(chartData);
  await retry;
  const result = container.innerHTML;
  requests[3].reject(Error("obsolete heatmap failure"));
  await outdatedHeatmap;
  assert.equal(container.innerHTML, result);
  assert.match(result, /main-chart/);
  assert.equal(charts.length, 2);
}
// Shared period selection across chart tabs including historical heatmaps.
{
  const calls=[], elements={
    "chart-container":{innerHTML:""}, "main-chart":{getContext:()=>({})},
    "breakdown-from":{value:"2024-02-28"}, "breakdown-to":{value:"2024-03-02"},
    "stats-range-status":{textContent:""}, "chart-applied-range":{textContent:""},
    "chart-date-rule":{textContent:""},
  };
  const context=vm.createContext({
    appConfig:{today:"2031-05-12"}, mainChart:null, CHART_COLORS:["#123456"],
    t:s=>s, escapeHtml:String, ensureChartJs:async()=>{},
    document:{getElementById:id=>elements[id],documentElement:{lang:"ja"}},
    api:async url=>{
      calls.push(url);
      return {range:{from:"2024-02-28",to:"2024-03-02"},habits:[{title:"Example",streak:1,dates:{"2024-02-29":1}}],labels:[],datasets:[]};
    },
    Chart:function(){this.destroy=()=>{};},
  });
  vm.runInContext(chartState+handlers,context);
  for(const type of types) {
    await vm.runInContext(`loadChart('${type}')`,context);
    assert.match(calls.at(-1),new RegExp("/api/chart/"+type+"\\?from=2024-02-28&to=2024-03-02"));
    assert.match(elements["chart-applied-range"].textContent,/2024年/);
    assert.ok(elements["chart-date-rule"].textContent);
    if(type==="habits-heatmap") {
      const cells=[...elements["chart-container"].innerHTML.matchAll(/data-date="([^"]+)"/g)].map(m=>m[1]);
      assert.deepEqual(cells,["2024-02-28","2024-02-29","2024-03-01","2024-03-02"]);
      assert.match(elements["chart-container"].innerHTML,/heatmap-cell done" data-date="2024-02-29"/);
    }
  }
  elements["breakdown-from"].value="2024-03-03";
  await vm.runInContext("loadChart('tasks')",context);
  assert.equal(calls.length,5);
  assert.equal(elements["chart-container"].innerHTML,"");
  assert.equal(elements["chart-applied-range"].textContent,"");
}
// One range change and the reset button refresh both shipped loaders.
{
  const workspace=await readFile(path.join(path.dirname(assetPath),"web_assets_js_03.js"),"utf8");
  const refresh=workspace.slice(workspace.indexOf("    function refreshStatsView("),workspace.indexOf("    function switchWorkspace("));
  const breakdown=asset.slice(asset.indexOf("    let statsBreakdownGeneration ="),asset.indexOf("    function toggleNotifPanel("));
  const calls=[], el={
    "chart-container":{innerHTML:""}, "main-chart":{getContext:()=>({})},
    "stats-breakdown":{innerHTML:""}, "breakdown-from":{value:"2024-05-01"},
    "breakdown-to":{value:"2024-05-03"}, "chart-applied-range":{textContent:""},
    "stats-breakdown-applied":{textContent:""}, "stats-range-status":{textContent:""},
  };
  const ctx=vm.createContext({
    appConfig:{today:"2024-06-30"}, statsLoaded:false, mainChart:null,
    CHART_COLORS:["#123456"], ITEM_TYPE_NAMES:{T:"Task"}, STATUS_LABEL:{},
    t:s=>s, escapeHtml:String, ensureChartJs:async()=>{},
    document:{getElementById:id=>el[id]}, Chart:function(){this.destroy=()=>{};},
    api:async url=>{calls.push(url);const params=new URL(url,"https://example.test").searchParams;
      return {range:{from:params.get("from"),to:params.get("to")},labels:[],datasets:[],by_type:{T:1},by_status:{}};},
  });
  vm.runInContext(chartState+handlers+breakdown+refresh,ctx);
  await vm.runInContext("refreshStatsView()",ctx);
  assert.deepEqual(calls.sort(),["/api/chart/tasks?from=2024-05-01&to=2024-05-03&group=daily","/api/stats/summary?from=2024-05-01&to=2024-05-03"]);
  assert.equal(el["chart-applied-range"].textContent,el["stats-breakdown-applied"].textContent);
  calls.length=0;
  await vm.runInContext("resetStatsRange()",ctx);
  assert.equal(el["breakdown-from"].value,"");
  assert.equal(el["breakdown-to"].value,"");
  assert.deepEqual(calls.sort(),["/api/chart/tasks?from=2024-06-01&to=2024-06-30&group=daily","/api/stats/summary?from=2024-06-01&to=2024-06-30"]);
}
// The initial refresh must retain the existing tasks default without a tab.
const calls=[];const sandbox={document:{querySelector:()=>null},loadChart:async type=>calls.push(type),currentChartType:'tasks'};
vm.createContext(sandbox);
vm.runInContext(asset.slice(asset.indexOf('    async function refreshCharts('),asset.indexOf('    function exportChartCsv(')),sandbox);
await vm.runInContext('refreshCharts()',sandbox);assert.deepEqual(calls,['tasks']);
process.stdout.write(JSON.stringify({cases,initial:'tasks'}));
