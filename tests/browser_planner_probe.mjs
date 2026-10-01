import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const [browser, file] = process.argv.slice(2);
const mock = `window.__agendaCalls=[];window.fetch=async input=>{const url=String(input);if(url.includes('/api/agenda')){window.__agendaCalls.push(url);return new Response(JSON.stringify({records:[{type:'E',title:'Daily Standup',matches:[{start:'2031-02-03T09:00'},{start:'2031-02-04T09:00'}]},{type:'R',title:'Water Plants',matches:[{start:'2031-02-03'}]},{type:'D',title:'Submit Grant',matches:[{start:'2031-02-05'}]},{type:'T',title:'Finish Report',matches:[{start:'2031-02-06T14:00'}]},{type:'T',title:'Very_Long_Unbroken_Title_'+'x'.repeat(120),matches:[{start:'2031-02-07T14:00'}]}]}),{status:200,headers:{'Content-Type':'application/json'}})}return new Response(JSON.stringify(url.includes('/api/config')?{today:'2031-02-03',web:{language:'en'}}:url.includes('/api/health')?{read_only:new URL(location.href).searchParams.has('readonly'),writable_path:'life.txt'}:url.includes('/api/command-center')?{due_today:[],next_actions:[],blocked:[]}:{items:[]}),{status:200,headers:{'Content-Type':'application/json'}})};`;
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
  for (let i = 0; i < 100; i++) {
    try { return +(await readFile(path.join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; }
    catch { await wait(100); }
  }
  throw Error("DevTools unavailable");
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
  const weekMatrix = [];
  for (const [width, lang] of [[320, "en"], [360, "ja"], [390, "en"], [430, "ja"]]) {
    await cmd("Emulation.setDeviceMetricsOverride", {width, height: 844, deviceScaleFactor: 2, mobile: true, screenWidth: width, screenHeight: 844});
    await openPage(`http://127.0.0.1:${server.address().port}/planner?view=week&date=2031-02-03&lang=${lang}`, true);
    weekMatrix.push(await evaljs(`(()=>{const rect=id=>{const r=document.querySelector(id).getBoundingClientRect();return {top:r.top,bottom:r.bottom,width:r.width,height:r.height}};return {lang:'${lang}',width:innerWidth,scrollWidth:document.documentElement.scrollWidth,days:document.querySelectorAll('.week-day').length,controls:[document.querySelector('#view-week').getBoundingClientRect().height,document.querySelector('#prev').getBoundingClientRect().height,document.querySelector('#next').getBoundingClientRect().height],dateNav:{label:rect('.date-row label'),prev:rect('#prev'),date:rect('#date'),next:rect('#next')},eventText:document.querySelector('#week-days').innerText,today:document.querySelector('.week-day.is-today')?.innerText,selected:document.querySelector('.week-day.is-selected')?.innerText,agendaRequests:window.__agendaCalls.length,timeCount:document.querySelectorAll('.week-record time').length,contentFits:[...document.querySelectorAll('.week-record')].every(node=>node.scrollWidth<=node.clientWidth),longTitle:document.querySelector('#week-days').innerText.includes('Very_Long_Unbroken_Title')}})()`));
  }
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
  process.stdout.write(JSON.stringify({matrix, weekMatrix, nav, navBack, returnToToday, dayTransition, yearBoundary, monthBoundary, readOnly}));
} finally {
  if (ws) ws.close();
  if (proc.exitCode === null) { proc.kill("SIGTERM"); await new Promise(ok => proc.once("exit", ok)); }
  await new Promise(ok => server.close(ok));
  await rm(profile, {recursive: true, force: true});
}
