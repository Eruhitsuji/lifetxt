import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const [browser, webFile, remoteFile] = process.argv.slice(2);
const mock = "window.__itemCalls=[];window.fetch=async input=>{const url=String(input);let data={};if(url.includes('/api/config'))data={today:'2031-02-03',web:{language:'en'},notifications:{enabled:false}};else if(url.includes('/api/health'))data={read_only:true};else if(url.includes('/api/items?')){window.__itemCalls.push(url);const ordinary=url.includes('ordinary_notes=true');data={items:Array.from({length:ordinary?12:32},(_,i)=>({id:'n'+i,line:i+1,type:'N',title:(ordinary?'Note ':'Raw ')+i,status:'[N]',details:{}})),count:ordinary?12:32}}else if(url.includes('/resources/notes?')){const p=new URL(url,location.href).searchParams,offset=Number(p.get('offset'));data={data:{items:Array.from({length:Math.min(20,24-offset)},(_,i)=>({id:'n'+(offset+i),title:'Note '+(offset+i)})),total:24,has_more:offset===0,next_offset:offset===0?20:null,revision:'r'}}}else if(url.includes('/snapshot'))data={items:[],workspace:{}};else if(url.includes('/session'))data={csrf_token:'test',principal:{id:'reader',role:'reader',scopes:['read']}};else if(url.includes('/capabilities'))data={};else data={items:[],records:[],views:[],areas:[],count:0};return new Response(JSON.stringify(data),{status:200})};";
const web=(await readFile(webFile,'utf8')).replace('<script>',`<script>${mock}</script><script>`);
const remote=(await readFile(remoteFile,'utf8')).replace('<script nonce=',`<script>${mock}</script><script nonce=`);
const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html'});res.end(req.url.startsWith('/remote')?remote:web)});
await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
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

  const results=[];
  for(const [width,lang] of [[320,'en'],[390,'ja']]){
    await cmd('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:2,mobile:true});
    await cmd('Emulation.setLocaleOverride',{locale:lang==='ja'?'ja-JP':'en-US'});
    await cmd('Emulation.setUserAgentOverride',{userAgent:'Chromium ordinary-notes test',acceptLanguage:lang==='ja'?'ja-JP,ja':'en-US,en'});
    await cmd('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/?lang=${lang}`});
    for(let i=0;i<100;i++){if(await evaljs("document.readyState==='complete'&&typeof itemQueryParams==='function'"))break;await wait(30)}
    await evaljs("document.querySelector('#kind').value='ordinary-notes';loadItems()");
    const ordinary=await evaljs("({url:window.__itemCalls.at(-1),count:currentItems.length,label:document.querySelector('#kind').selectedOptions[0].textContent})");
    await evaljs("document.querySelector('#kind').value='N';loadItems()");
    const raw=await evaljs("({url:window.__itemCalls.at(-1),count:currentItems.length})");
    await cmd('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/remote`});
    for(let i=0;i<100;i++){if(await evaljs("document.readyState==='complete'&&!document.querySelector('#session').classList.contains('hidden')"))break;await wait(30)}
    await evaljs("document.querySelector('#notes-refresh').click()");await wait(50);
    const first=await evaljs("({data:JSON.parse(document.querySelector('#output').textContent).data,label:document.querySelector('#notes-refresh').textContent,nextVisible:!document.querySelector('#notes-next').hidden,scrollWidth:document.documentElement.scrollWidth})");
    await evaljs("document.querySelector('#notes-next').click()");await wait(50);
    const next=await evaljs("({data:JSON.parse(document.querySelector('#output').textContent).data,nextHidden:document.querySelector('#notes-next').hidden})");
    results.push({width,lang,ordinary,raw,first,next});
  }
  process.stdout.write(JSON.stringify(results));
} finally {
  if (ws) ws.close();
  if (proc.exitCode === null) { proc.kill("SIGTERM"); await new Promise(ok => proc.once("exit", ok)); }
  await new Promise(ok => server.close(ok));
  await rm(profile, {recursive: true, force: true, maxRetries: 5, retryDelay: 100});
}
