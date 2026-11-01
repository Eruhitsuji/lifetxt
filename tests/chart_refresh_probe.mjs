// Run shipped chart handlers with a transport/DOM adapter; no layout claims.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const [assetPath,statePath]=process.argv.slice(2);
const asset=await readFile(assetPath,'utf8'),state=await readFile(statePath,'utf8');
const handlers=asset.slice(asset.indexOf('    async function loadChart('),asset.indexOf('    function exportChartCsv('));
const chartState=state.slice(state.indexOf('    let currentChartType'),state.indexOf('    // ── Status filter bar URL sync'));
const labels={en:['Tasks','Habits','Heatmap','Mood','Elapsed'],ja:['タスク','習慣','ヒートマップ','気分','経過時間']};
const types=['tasks','habits','habits-heatmap','mood','elapsed'];
let cases=0;
for(const language of ['en','ja'])for(const group of ['daily','weekly','monthly'])for(const [index,type] of types.entries()){
  const calls=[],charts=[];let destroyed=0,fail=false;
  const container={innerHTML:''},bar={style:{}},canvas={getContext:()=>({})};
  const tab={textContent:labels[language][index],classList:{add(){},remove(){}}};
  const sandbox={console,Date,Set,encodeURIComponent,mainChart:null,CHART_COLORS:['#123456'],
    ensureChartJs:async()=>{},escapeHtml:value=>String(value).replaceAll('<','&lt;').replaceAll('>','&gt;'),
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
  assert.match(container.innerHTML,/error: &lt;temporary&gt;/);
  cases++;
}
// The initial refresh must retain the existing tasks default without a tab.
const calls=[];const sandbox={document:{querySelector:()=>null},loadChart:async type=>calls.push(type),currentChartType:'tasks'};
vm.createContext(sandbox);
vm.runInContext(asset.slice(asset.indexOf('    async function refreshCharts('),asset.indexOf('    function exportChartCsv(')),sandbox);
await vm.runInContext('refreshCharts()',sandbox);assert.deepEqual(calls,['tasks']);
process.stdout.write(JSON.stringify({cases,initial:'tasks'}));
