import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const [browserPath, htmlPath] = process.argv.slice(2);
const html = await readFile(htmlPath);
const requests = [];
const tasks=[{id:'short',title:'Short'},{id:'long',title:'長いタイトル'.repeat(60)}].map((item,i)=>({...item,type:'T',status:'[ ]',line:i+1,source:'fixture.txt',editable:true,details:{due:['2031-02-03']}}));
const server = http.createServer((request,response)=>{
  requests.push({url:request.url,method:request.method});
  const url=new URL(request.url,'http://localhost');
  let result={items:[]};
  if(url.pathname==='/api/config')result={today:'2031-02-03',web:{language:'en'}};
  if(url.pathname==='/api/health')result={read_only:false,writable_path:'fixture.txt'};
  if(url.pathname==='/api/command-center')result={due_today:tasks.map(i=>({...i,kind:'T'}))};
  if(url.pathname==='/api/items')result={items:url.searchParams.get('type')==='T'?tasks:[]};
  if(url.pathname==='/api/agenda')result={records:[{type:'E',title:'Event',status:'[ ]'}]};
  if(url.pathname==='/api/notes')result={items:[],total:0,has_more:false};
  response.writeHead(200,{'content-type':url.pathname.startsWith('/api/')?'application/json':'text/html; charset=utf-8'});
  response.end(url.pathname.startsWith('/api/')?JSON.stringify(result):html);
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const profile = await mkdtemp(path.join(os.tmpdir(), "lifetxt-items-filters-"));
const browser = spawn(browserPath, [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
  "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`,
  "about:blank",
], {stdio: "ignore"});

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function devtoolsPort() {
  const file = path.join(profile, "DevToolsActivePort");
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try { return Number((await readFile(file, "utf8")).split("\n", 1)[0]); }
    catch { await delay(100); }
  }
  throw new Error("Chrome did not publish its DevTools port");
}

let nextId = 0;
const pending = new Map();
let socket;
function command(method, params = {}) {
  const id = ++nextId;
  socket.send(JSON.stringify({id, method, params}));
  return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
}

try {
  const debugPort = await devtoolsPort();
  const targets = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
  socket = new WebSocket(targets.find(target => target.type === "page").webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, {once: true});
    socket.addEventListener("error", reject, {once: true});
  });
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const waiter = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) waiter.reject(new Error(message.error.message));
    else waiter.resolve(message.result);
  });
  await command("Page.enable");
  await command("Runtime.enable");

  const evaluate = async expression => {
    const result = await command("Runtime.evaluate", {expression, returnByValue: true, awaitPromise: true});
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const resize = async width => {
    await command("Emulation.setDeviceMetricsOverride", {width, height: 850, deviceScaleFactor: 1, mobile: false});
    await evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))");
  };
  const results = [];
  for (const width of [320,390,760,1280]) for(const lang of ['ja','en']) for(const theme of ['light','dark']) {
    await resize(width);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme}]});
    await command('Page.navigate',{url:`http://127.0.0.1:${port}/planner?lang=${lang}`});
    for(let i=0;i<100;i++){if(await evaluate('document.querySelectorAll("#tasks .card").length===2'))break;await delay(30)}
    const result=await evaluate(`(()=>{
      const cards=[...document.querySelectorAll('#tasks .card')];
      const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,height:r.height,width:r.width}};
      return {count:cards.length,scrollWidth:document.documentElement.scrollWidth,
        rows:cards.map(c=>({content:rect(c.querySelector('.card-content')),actions:rect(c.querySelector('.card-actions')),buttons:[...c.querySelectorAll('button')].map(rect)})),
        eventButtons:document.querySelectorAll('#schedule .card-actions button').length,
        labels:cards.map(c=>[...c.querySelectorAll('button')].map(b=>b.textContent))};
    })()`);
    assert.equal(result.count,2);
    assert.ok(result.scrollWidth<=width,JSON.stringify({width,lang,theme,result}));
    for(const row of result.rows){
      assert.equal(row.buttons.length,2);
      assert.ok(row.buttons.every(b=>b.height>=44 && b.width>=44));
      assert.ok(width<=480?row.actions.top>=row.content.bottom:row.actions.left>=row.content.right);
    }
    for(let i=0;i<2;i++)assert.ok(Math.abs(result.rows[0].buttons[i].right-result.rows[1].buttons[i].right)<1,'operation columns align');
    assert.equal(result.eventButtons,1);
    const buttons=result.labels[0];
    assert.deepEqual(buttons,lang==='ja'?['完了を記録','詳細']:['Mark done','Details']);
    const focus=await evaluate(`(()=>{const buttons=document.querySelectorAll('#tasks .card button');buttons[0].focus();return document.activeElement===buttons[0]})()`);
    assert.equal(focus,true);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    assert.equal(await evaluate(`document.activeElement===document.querySelectorAll('#tasks .card button')[1]`),true);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',windowsVirtualKeyCode:13});
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
    assert.equal(await evaluate(`document.querySelector('#detail-dialog').open`),true);
    results.push({width,lang,theme,...result});
  }
  assert.ok(requests.every(r => r.method === "GET"), "fixture never mutates data");
  process.stdout.write(JSON.stringify({viewports: results}));
} finally {
  if (socket) socket.close();
  if (browser.exitCode === null) {
    browser.kill("SIGTERM");
    await new Promise(resolve => browser.once("exit", resolve));
  }
  await new Promise(resolve => server.close(resolve));
  for (let attempt = 0; attempt < 20; attempt += 1) {
    try {
      await rm(profile, {recursive: true, force: true, maxRetries: 3, retryDelay: 50});
      break;
    } catch (error) {
      if (attempt === 19) throw error;
      await delay(100);
    }
  }
}
