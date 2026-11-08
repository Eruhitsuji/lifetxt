// Run shipped chart handlers with a transport/DOM adapter; no layout claims.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const [assetPath,statePath]=process.argv.slice(2);
const asset=await readFile(assetPath,'utf8'),state=await readFile(statePath,'utf8');
const handlers=asset.slice(asset.indexOf('    let chartLoadGeneration ='),asset.indexOf('    function exportChartCsv('));
const chartState=state.slice(state.indexOf('    let currentChartType'),state.indexOf('    // ── Status filter bar URL sync'));
const labels={en:['Tasks','Habits','Heatmap','Mood','Elapsed'],ja:['タスク','習慣','ヒートマップ','気分','経過時間']};
const types=['tasks','habits','habits-heatmap','mood','elapsed'];
let cases=0;
for(const language of ['en','ja'])for(const group of ['daily','weekly','monthly'])for(const [index,type] of types.entries()){
  const calls=[],charts=[];let destroyed=0,fail=false;
  const container={innerHTML:''},bar={style:{}},canvas={getContext:()=>({})};
  const tab={textContent:labels[language][index],classList:{add(){},remove(){}}};
  const sandbox={console,Date,Set,encodeURIComponent,mainChart:null,CHART_COLORS:['#123456'],
    ensureChartJs:async()=>{},t:text=>text,escapeHtml:value=>String(value).replaceAll('<','&lt;').replaceAll('>','&gt;'),
    document:{getElementById:id=>({'chart-container':container,'main-chart':canvas,'chart-group-bar':bar})[id],querySelector:()=>tab,querySelectorAll:()=>[tab]},
    api:async url=>{calls.push(url);if(fail)throw Error('<temporary>');return {labels:['Day'],datasets:[{label:'Completed',data:[2]}],habits:[]}},
    Chart:function(ctx,config){charts.push(config);this.destroy=()=>destroyed++}
  };
  vm.createContext(sandbox);vm.runInContext(chartState+handlers,sandbox);
  const settle=()=>new Promise(resolve=>setImmediate(resolve));
  vm.runInContext(`showChart('${type}',document.querySelector('.chart-tab.active'));setChartGroup('${group}',null)`,sandbox);
  await settle();calls.length=0;
  await vm.runInContext('refreshCharts()',sandbox);await settle();
  const expected='/api/chart/'+type+(['tasks','habits','mood'].includes(type)?'?group='+group:'');
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
  const chartData = {labels: ["Day"], datasets: [{label: "Completed", data: [2]}]};
  let failLibrary = false;
  const sandbox = {
    mainChart: null, CHART_COLORS: ["#123456"], t: text => text, escapeHtml: String,
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
  assert.equal(requests[0].url, "/api/chart/tasks?group=daily");
  assert.equal(requests[1].url, "/api/chart/tasks?group=weekly");
  requests[1].resolve(chartData);
  await weekly;
  assert.equal(charts[0].options.scales.y.title.text, "completions / week");

  const heatmap = run('currentChartType = "habits-heatmap"; refreshCharts()');
  assert.match(container.innerHTML, /Loading statistics chart/);
  assert.ok(charts[0].destroyed);
  run("exportChartCsv()");
  assert.deepEqual(notices, [["No chart data to export.", "error"]]);
  requests[2].resolve({habits: []});
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
  assert.equal(requests[4].url, "/api/chart/mood?group=monthly");
  requests[4].resolve(chartData);
  await retry;
  const result = container.innerHTML;
  requests[3].reject(Error("obsolete heatmap failure"));
  await outdatedHeatmap;
  assert.equal(container.innerHTML, result);
  assert.match(result, /main-chart/);
  assert.equal(charts.length, 2);
}
// The initial refresh must retain the existing tasks default without a tab.
const calls=[];const sandbox={document:{querySelector:()=>null},loadChart:async type=>calls.push(type),currentChartType:'tasks'};
vm.createContext(sandbox);
vm.runInContext(asset.slice(asset.indexOf('    async function refreshCharts('),asset.indexOf('    function exportChartCsv(')),sandbox);
await vm.runInContext('refreshCharts()',sandbox);assert.deepEqual(calls,['tasks']);
process.stdout.write(JSON.stringify({cases,initial:'tasks'}));
