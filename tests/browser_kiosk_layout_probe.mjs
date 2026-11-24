import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const [browserPath, htmlPath] = process.argv.slice(2);
const html = await readFile(htmlPath);
const requests = [];
const items=Array.from({length:120},(_,i)=>({line:i+1,type:'T',status:'[ ]',title:i%3 ? '長いタイトル'.repeat(25) : 'Short',details:{id:['T-'+i],body:['長い本文'.repeat(35)],url:['https://example.invalid/'+'a'.repeat(150)]},source:'fixture.txt',editable:false}));
const server = http.createServer((request, response) => {
  requests.push({url: request.url, method: request.method});
  response.writeHead(200, {"content-type": request.url.startsWith("/api/") ? "application/json" : "text/html; charset=utf-8"});
  response.end(request.url.startsWith("/api/") ? JSON.stringify({items, diagnostics: [], records: [], views: [], areas: []}) : html);
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
  };
  const waitFor = async (expression, message) => {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await evaluate(expression)) return;
      await delay(30);
    }
    throw new Error(message);
  };
  const results = [];
  for (const width of [1280, 1920]) for (const cols of [0,1,2,3,4,8]) for (const theme of ["light", "dark"]) {
    await resize(width);
    await command("Page.navigate", {url: `http://127.0.0.1:${port}/?mode=kiosk&theme=${theme}${cols ? "&kiosk_cols="+cols : ""}`});
    for(let i=0;i<100;i++) {if(await evaluate('document.readyState === "complete" && document.querySelectorAll("#items .item").length === 120')) break; await delay(25);}
    // Remove entrance animation from measurement; it does not control row sizing.
    await evaluate(`document.querySelectorAll('#items .item').forEach(e=>e.style.animation='none')`);
    const result = await evaluate(`(() => {
      const root=document.getElementById('items'), cards=[...root.querySelectorAll('.item')];
      const boxes=cards.map(e=>e.getBoundingClientRect());
      return {count:cards.length, overflow:cards.filter(e=>e.scrollHeight>e.clientHeight+1).length,
        overlap:boxes.some((r,i)=>boxes.slice(i+1).some(s=>r.left<s.right-1 && r.right>s.left+1 && r.top<s.bottom-1 && r.bottom>s.top+1)),
        reachable:(()=>{root.scrollTop=root.scrollHeight;return cards.at(-1).getBoundingClientRect().bottom<=root.getBoundingClientRect().bottom+1})()};
    })()`);
    assert.equal(result.count,120); assert.equal(result.overflow,0,JSON.stringify({width,cols,theme,result}));
    assert.equal(result.overlap,false); assert.equal(result.reachable,true);
    results.push({width,cols,theme,...result});
  }
  const scrollControls = [];
  for (const [width, lang, pause, resume, off] of [
    [1280, "en", "Pause auto-scroll", "Resume auto-scroll", "Auto-scroll off"],
    [320, "ja", "自動スクロールを停止", "自動スクロールを再開", "自動スクロールはオフ"],
  ]) {
    await resize(width);
    await command("Page.navigate", {url: `http://127.0.0.1:${port}/?mode=kiosk&lang=${lang}&refresh=1`});
    await waitFor(`document.querySelector("#kiosk-scroll-btn")?.textContent === ${JSON.stringify(pause)} &&
      document.querySelectorAll("#items .item").length === 120`, "Kiosk did not initialize");
    const fits = await evaluate(`["kiosk-scroll-btn", "kiosk-exit-btn", "kiosk-clock"].every(id => {
      const box = document.getElementById(id).getBoundingClientRect();
      return box.width > 0 && box.left >= 0 && box.right <= innerWidth;
    }) && document.querySelector("#items").getBoundingClientRect().bottom <= innerHeight`);
    assert.ok(fits, `Kiosk controls and scroll area must fit at ${width}px`);

    await evaluate('document.querySelector("#kiosk-scroll-btn").focus()');
    const space = {key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32};
    await command("Input.dispatchKeyEvent", {type: "keyDown", ...space});
    await command("Input.dispatchKeyEvent", {type: "keyUp", ...space});
    const buttonText = 'document.querySelector("#kiosk-scroll-btn").textContent';
    assert.equal(await evaluate(buttonText), resume);
    assert.equal(await evaluate("document.activeElement.id"), "kiosk-scroll-btn");
    await evaluate('document.querySelector("#items").scrollTop = 120');
    const readCount = () => requests.filter(r => r.url.startsWith("/api/items")).length;
    const before = readCount();
    const clockTime = 'document.querySelector("#kiosk-clock").dateTime';
    const beforeClock = await evaluate(clockTime);
    assert.ok(beforeClock);
    await delay(1500);
    assert.ok(readCount() > before, "Items must refresh while auto-scroll is paused");
    assert.notEqual(await evaluate(clockTime), beforeClock);
    assert.equal(await evaluate('document.querySelector("#items").scrollTop'), 120);
    assert.equal(await evaluate(buttonText), resume);

    await evaluate("applyReducedMotion(true)");
    assert.equal(await evaluate(buttonText), off);
    assert.equal(await evaluate('document.querySelector("#kiosk-scroll-btn").disabled'), true);
    await evaluate("applyReducedMotion(false)");
    assert.equal(await evaluate(buttonText), resume);
    await evaluate('document.querySelector("#kiosk-scroll-btn").click()');
    assert.equal(await evaluate(buttonText), pause);
    await waitFor('document.querySelector("#items").scrollTop > 120', "Auto-scroll did not resume");

    await evaluate('document.querySelector("#kiosk-scroll-btn").click()');
    await evaluate('document.querySelector("#kiosk-exit-btn").click()');
    assert.equal(await evaluate('document.querySelector("#kiosk-scroll-btn").getBoundingClientRect().width'), 0);
    await evaluate("toggleKioskMode()");
    assert.equal(await evaluate(buttonText), pause);
    await evaluate("switchWorkspace('display')");
    assert.equal(await evaluate('document.querySelector("#kiosk-scroll-btn").getBoundingClientRect().width'), 0);
    scrollControls.push({width, lang});
  }
  assert.ok(requests.every(r => r.method === "GET"), "fixture never mutates data");
  process.stdout.write(JSON.stringify({viewports: results, scrollControls}));
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
