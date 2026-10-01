import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const [browser, file] = process.argv.slice(2);
const mock = `window.__notesCalls=[];window.__notesMode='normal';window.__delayMore=false;window.__agendaCalls=[];window.fetch=async input=>{const url=String(input);if(url.includes('/api/notes?')){window.__notesCalls.push(url);const params=new URL(url,location.href).searchParams,offset=Number(params.get('offset')||0),limit=Number(params.get('limit')||5),date=params.get('date');if(window.__notesMode==='error'&&offset>0)return new Response(JSON.stringify({detail:'temporary error'}),{status:500});const total=window.__notesMode==='empty'?0:12,items=Array.from({length:total},(_,i)=>({id:'n'+i,title:date+' Note '+i+' '+'x'.repeat(80),type:'N',editable:true,details:{body:['Note body']}})).slice(offset,offset+limit),page={items,count:items.length,total,has_more:offset+items.length<total,next_offset:offset+items.length<total?offset+items.length:null,revision:window.__notesMode==='changed'?'r2':'r1'};if(window.__delayMore&&offset>0)return new Promise(resolve=>{window.__releaseNotes=()=>resolve(new Response(JSON.stringify(page),{status:200}))});return new Response(JSON.stringify(page),{status:200})}if(url.includes('/api/agenda')){window.__agendaCalls.push(url);return new Response(JSON.stringify({records:[{type:'E',title:'Daily Standup',matches:[{start:'2031-02-03T09:00'},{start:'2031-02-04T09:00'}]},{type:'R',title:'Water Plants',matches:[{start:'2031-02-03'}]},{type:'D',title:'Submit Grant',matches:[{start:'2031-02-05'}]},{type:'T',title:'Finish Report',matches:[{start:'2031-02-06T14:00'}]},{type:'T',title:'Very_Long_Unbroken_Title_'+'x'.repeat(120),matches:[{start:'2031-02-07T14:00'}]}]}),{status:200,headers:{'Content-Type':'application/json'}})}return new Response(JSON.stringify(url.includes('/api/config')?{today:'2031-02-03',web:{language:'en'}}:url.includes('/api/health')?{read_only:new URL(location.href).searchParams.has('readonly'),writable_path:'life.txt'}:url.includes('/api/command-center')?{due_today:[],next_actions:[],blocked:[]}:{items:[]}),{status:200,headers:{'Content-Type':'application/json'}})};`;
const html = (await readFile(file, "utf8")).replace("<script>(() =>", `<script>${mock}</script><script>(() =>`);
const server = http.createServer((req, res) => {
  res.writeHead(200, {"Content-Type": "text/html"});
  res.end(html);
});
await new Promise(ok => server.listen(0, "127.0.0.1", ok));
const profile = await mkdtemp(path.join(os.tmpdir(), "planner-chrome-"));
const proc = spawn(browser, ["--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run", "--no-default-browser-check", "--disable-dev-shm-usage", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], {stdio: "ignore"});
const wait = ms => new Promise(ok => setTimeout(ok, ms));
async function port() {
  for (let i = 0; i < 300; i++) {
    try { return +(await readFile(path.join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; }
    catch {
      if (proc.exitCode !== null) throw Error(`Chromium exited before DevTools started (code ${proc.exitCode})`);
      await wait(100);
    }
  }
  throw Error("DevTools unavailable after 30 seconds");
}
let id = 0;
const pending = new Map();
let ws;
function cmd(method, params = {}) {
  const n = ++id;
  ws.send(JSON.stringify({id: n, method, params}));
  return new Promise((resolve, reject) => pending.set(n, {resolve, reject}));
}
async function evaljs(expression) {
  return (await cmd("Runtime.evaluate", {expression, returnByValue: true, awaitPromise: true})).result.value;
}
async function openPage(url, week = false) {
  await cmd("Page.navigate", {url});
  for (let i = 0; i < 100; i++) {
    const ready = week
      ? "document.readyState==='complete' && document.querySelectorAll('.week-day').length===7"
      : "document.readyState==='complete' && document.querySelector('#schedule')?.previousElementSibling?.textContent";
    if (await evaljs(ready)) return;
    await wait(50);
  }
  await wait(500);
}
try {
  const dp = await port(), tabs = await (await fetch(`http://127.0.0.1:${dp}/json/list`)).json();
  ws = new WebSocket(tabs.find(x => x.type === "page").webSocketDebuggerUrl);
  await new Promise((ok, no) => { ws.addEventListener("open", ok, {once: true}); ws.addEventListener("error", no, {once: true}); });
  ws.addEventListener("message", e => {
    const m = JSON.parse(e.data), p = pending.get(m.id);
    if (p) { pending.delete(m.id); m.error ? p.reject(Error(m.error.message)) : p.resolve(m.result); }
  });
  await cmd("Page.enable");
  await cmd("Runtime.enable");
  await cmd("Emulation.setTouchEmulationEnabled", {enabled: true, maxTouchPoints: 5});
  const matrix = [];
  for (const [width, height, lang] of [[320, 640, "en"], [360, 720, "ja"], [390, 844, "en"], [430, 932, "ja"], [667, 320, "ja"], [390, 360, "en"]]) {
    await cmd("Emulation.setDeviceMetricsOverride", {width, height, deviceScaleFactor: 2, mobile: true, screenWidth: width, screenHeight: height});
    await openPage(`http://127.0.0.1:${server.address().port}/planner?lang=${lang}`);
    matrix.push(await evaljs(`(()=>{const rect=id=>{const r=document.querySelector(id).getBoundingClientRect();return {top:r.top,bottom:r.bottom,width:r.width,height:r.height}};return {width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dateHeight:document.querySelector('#date').getBoundingClientRect().height,captureHeight:document.querySelector('#open-capture').getBoundingClientRect().height,schedule:document.querySelector('#schedule').previousElementSibling.textContent.trim(),label:rect('.date-row label'),prev:rect('#prev'),date:rect('#date'),next:rect('#next')}})()`));
  }
  const notesMatrix = [];
  async function notesReady(count){
    for(let i=0;i<100;i++){if(await evaljs(`document.querySelectorAll('#notes .card').length===${count}&&!document.querySelector('#more-notes').disabled`))return;await wait(30)}
    throw Error('Notes did not reach '+count+' rows');
  }
  for (const [width,lang] of [[320,'en'],[360,'ja'],[390,'en'],[430,'ja']]) {
    await cmd('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:2,mobile:true,screenWidth:width,screenHeight:844});
    await openPage(`http://127.0.0.1:${server.address().port}/planner?lang=${lang}&readonly=1`);
    await notesReady(5);
    const initial=await evaljs(`({count:document.querySelectorAll('#notes .card').length,total:document.querySelector('#notes-count').textContent,label:document.querySelector('#more-notes').textContent,moreHeight:document.querySelector('#more-notes').getBoundingClientRect().height,editButtons:document.querySelectorAll('#notes button').length,newDisabled:document.querySelector('#new-note').disabled})`);
    await evaljs("document.querySelector('#more-notes').click();document.querySelector('#more-notes').click()");
    await notesReady(10);
    const middle=await evaljs("({rows:[...document.querySelectorAll('#notes strong')].map(x=>x.textContent),calls:window.__notesCalls.length})");
    await evaljs("document.querySelector('#more-notes').click()");
    await notesReady(12);
    notesMatrix.push(await evaljs(`({width:innerWidth,lang:'${lang}',initial:${JSON.stringify(initial)},middle:${JSON.stringify(middle)},final:[...document.querySelectorAll('#notes strong')].map(x=>x.textContent),moreHidden:document.querySelector('#more-notes').hidden,calls:window.__notesCalls,scrollWidth:document.documentElement.scrollWidth})`));
  }
  // Retry errors without losing already-displayed rows.
  await openPage(`http://127.0.0.1:${server.address().port}/planner?lang=en`);await notesReady(5);
  await evaljs("window.__notesMode='error';document.querySelector('#more-notes').click()");await wait(100);
  const notesError=await evaljs("({rows:document.querySelectorAll('#notes .card').length,enabled:!document.querySelector('#more-notes').disabled,feedback:document.querySelector('#feedback').textContent})");
  await evaljs("window.__notesMode='normal';document.querySelector('#more-notes').click()");await notesReady(10);
  // Workspace revision changes restart the bounded page, rather than mix snapshots.
  await openPage(`http://127.0.0.1:${server.address().port}/planner?lang=en`);await notesReady(5);
  await evaljs("window.__notesMode='changed';document.querySelector('#more-notes').click()");await wait(100);
  const notesRevision=await evaljs("({rows:document.querySelectorAll('#notes .card').length,calls:window.__notesCalls.length,total:document.querySelector('#notes-count').textContent})");
  // A delayed old page must never append after changing the selected day.
  await openPage(`http://127.0.0.1:${server.address().port}/planner?lang=en`);await notesReady(5);
  await evaljs("window.__delayMore=true;document.querySelector('#more-notes').click()");
  await evaljs("document.querySelector('#next').click()");await notesReady(5);
  await evaljs("window.__releaseNotes()");await wait(100);
  const notesRace=await evaljs("({rows:[...document.querySelectorAll('#notes strong')].map(x=>x.textContent),date:document.querySelector('#date').value,total:document.querySelector('#notes-count').textContent})");
  await evaljs("window.__notesMode='empty';document.querySelector('#today').click()");await notesReady(0);
  const notesEmpty=await evaljs("({total:document.querySelector('#notes-count').textContent,moreHidden:document.querySelector('#more-notes').hidden,empty:document.querySelector('#notes .empty').textContent})");
  const weekMatrix = [];
  for (const [width, lang] of [[320, "en"], [360, "ja"], [390, "en"], [430, "ja"]]) {
    await cmd("Emulation.setDeviceMetricsOverride", {width, height: 844, deviceScaleFactor: 2, mobile: true, screenWidth: width, screenHeight: 844});
    await openPage(`http://127.0.0.1:${server.address().port}/planner?view=week&date=2031-02-03&lang=${lang}`, true);
    weekMatrix.push(await evaljs(`(()=>{const rect=id=>{const r=document.querySelector(id).getBoundingClientRect();return {top:r.top,bottom:r.bottom,width:r.width,height:r.height}};return {lang:'${lang}',width:innerWidth,scrollWidth:document.documentElement.scrollWidth,days:document.querySelectorAll('.week-day').length,controls:[document.querySelector('#view-week').getBoundingClientRect().height,document.querySelector('#prev').getBoundingClientRect().height,document.querySelector('#next').getBoundingClientRect().height],dateNav:{label:rect('.date-row label'),prev:rect('#prev'),date:rect('#date'),next:rect('#next')},eventText:document.querySelector('#week-days').innerText,today:document.querySelector('.week-day.is-today')?.innerText,selected:document.querySelector('.week-day.is-selected')?.innerText,agendaRequests:window.__agendaCalls.length,timeCount:document.querySelectorAll('.week-record time').length,contentFits:[...document.querySelectorAll('.week-record')].every(node=>node.scrollWidth<=node.clientWidth),longTitle:document.querySelector('#week-days').innerText.includes('Very_Long_Unbroken_Title')}})()`));
  }
  const monthMatrix = [];
  for (const [width, lang] of [[320, "en"], [360, "ja"], [390, "en"], [430, "ja"]]) {
    await cmd("Emulation.setDeviceMetricsOverride", {width, height: 844, deviceScaleFactor: 2, mobile: true, screenWidth: width, screenHeight: 844});
    await cmd("Page.navigate", {url:`http://127.0.0.1:${server.address().port}/planner?view=month&date=2031-02-03&lang=${lang}`});
    for (let i=0;i<100;i++){if(await evaljs("document.readyState==='complete'&&document.querySelectorAll('.month-day').length===35"))break;await wait(50)}
    monthMatrix.push(await evaljs(`({width:innerWidth,lang:'${lang}',scrollWidth:document.documentElement.scrollWidth,days:document.querySelectorAll('.month-day').length,outside:document.querySelectorAll('.month-day.is-outside').length,today:document.querySelectorAll('.month-day.is-today').length,selected:document.querySelectorAll('.month-day.is-selected').length,minHeight:Math.min(...[...document.querySelectorAll('.month-day')].map(x=>x.getBoundingClientRect().height)),agendaRequests:window.__agendaCalls.length,labels:[...document.querySelectorAll('.month-day')].map(x=>x.getAttribute('aria-label')),monthText:document.querySelector('#month-heading').textContent})`));
  }
  await evaljs("document.querySelector('#next').click()");
  const monthNext = await evaljs("({url:location.search,request:window.__agendaCalls.at(-1),heading:document.querySelector('#month-heading').textContent})");
  await evaljs("document.querySelector('.month-day[aria-current=date]').click()");
  const monthDayTransition = await evaljs("({url:location.search,monthHidden:document.querySelector('#month-view').hidden,dayVisible:!document.querySelector('#day-view').hidden})");
  await openPage(`http://127.0.0.1:${server.address().port}/planner?view=week&date=2031-02-03&lang=ja`, true);
  await evaljs("document.querySelector('#next').click()");
  const nav = await evaljs("({url:location.search,request:window.__agendaCalls.at(-1)})");
  await evaljs("document.querySelector('#prev').click()");
  const navBack = await evaljs("({url:location.search,request:window.__agendaCalls.at(-1)})");
  await evaljs("document.querySelector('#today').click()");
  const returnToToday = await evaljs("({url:location.search,request:window.__agendaCalls.at(-1)})");
  await evaljs("document.querySelector('#next').click()");
  await evaljs("document.querySelector('.week-day-link[aria-current=date]').click()");
  const dayTransition = await evaljs("({url:location.search,weekHidden:document.querySelector('#week-view').hidden,dayVisible:!document.querySelector('#day-view').hidden})");
  await openPage(`http://127.0.0.1:${server.address().port}/planner?view=week&date=2032-01-01&lang=en`, true);
  const yearBoundary = await evaljs("({request:window.__agendaCalls.at(-1),days:document.querySelectorAll('.week-day').length,emptyDays:document.querySelectorAll('.week-empty').length,selected:document.querySelector('.week-day-link[aria-current=date]').textContent})");
  await openPage(`http://127.0.0.1:${server.address().port}/planner?view=week&date=2031-03-01&lang=en`, true);
  const monthBoundary = await evaljs("({request:window.__agendaCalls.at(-1),days:document.querySelectorAll('.week-day').length,emptyDays:document.querySelectorAll('.week-empty').length})");
  await openPage(`http://127.0.0.1:${server.address().port}/planner?view=week&date=2031-02-03&lang=ja&readonly=1`, true);
  const readOnly = await evaljs("({days:document.querySelectorAll('.week-day').length,dockHidden:document.querySelector('#dock').hidden,captureDisabled:document.querySelector('#open-capture').disabled})");
  process.stdout.write(JSON.stringify({matrix, notesMatrix, notesError, notesRevision, notesRace, notesEmpty, weekMatrix, monthMatrix, monthNext, monthDayTransition, nav, navBack, returnToToday, dayTransition, yearBoundary, monthBoundary, readOnly}));
} finally {
  if (ws) ws.close();
  if (proc.exitCode === null) { proc.kill("SIGTERM"); await new Promise(ok => proc.once("exit", ok)); }
  await new Promise(ok => server.close(ok));
  await rm(profile, {recursive: true, force: true, maxRetries: 5, retryDelay: 100});
}
