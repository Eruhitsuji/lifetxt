import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const [browserPath, htmlPath] = process.argv.slice(2);
const html = await readFile(htmlPath);
const requests = [];
const server = http.createServer((request, response) => {
  requests.push({url: request.url, method: request.method});
  response.writeHead(200, {"content-type": request.url.startsWith("/api/") ? "application/json" : "text/html; charset=utf-8"});
  response.end(request.url.startsWith("/api/") ? JSON.stringify({items: [], diagnostics: [], records: [], views: [], areas: []}) : html);
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
  const key = async name => {
    const code = {Tab: 9, Enter: 13, " ": 32}[name];
    await command("Input.dispatchKeyEvent", {type: "keyDown", key: name, code: name === " " ? "Space" : name, text: name === "Enter" ? "\r" : name === " " ? " " : "", windowsVirtualKeyCode: code});
    await command("Input.dispatchKeyEvent", {type: "keyUp", key: name, windowsVirtualKeyCode: code});
  };
  const state = () => evaluate(`(() => {
    const d = document.getElementById("items-filter-disclosure");
    const ids = ["kind", "sort", "order", "group-by", "limit", "saved-view-select", "area-select", "export-select"];
    return {open: d.open, visible: ids.filter(id => document.getElementById(id).checkVisibility()),
      values: ids.map(id => document.getElementById(id).value), url: location.search,
      summaryVisible: d.firstElementChild.checkVisibility()};
  })()`);
  const results = [];
  for (const width of [1280, 681, 680, 390]) {
    await resize(width);
    await command("Page.navigate", {url: `http://127.0.0.1:${port}/?view=items&sort=title&order=desc&kind=T`});
    for (let i = 0; i < 100; i++) {
      if (await evaluate('document.readyState === "complete" && document.getElementById("sort")?.value === "title"')) break;
      await delay(25);
    }
    const initial = await state();
    assert.equal(initial.open, width > 680, `initial state at ${width}`);
    assert.equal(initial.summaryVisible, width <= 680);
    if (width <= 680) {
      assert.equal(initial.visible.length, 0);
      await evaluate('document.querySelector("#items-filter-disclosure > summary").focus()');
      await key("Tab");
      assert.equal(await evaluate('!!document.activeElement.closest(".items-controls")'), false);
      await evaluate('document.querySelector("#items-filter-disclosure > summary").focus()');
      await key("Enter");
      assert.equal((await state()).open, true);
      await key(" ");
      assert.equal((await state()).open, false);
      const point = await evaluate('(() => {const s = document.querySelector("#items-filter-disclosure > summary"); s.scrollIntoView(); const r = s.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2};})()');
      await command("Input.dispatchMouseEvent", {type: "mousePressed", ...point, button: "left", clickCount: 1});
      await command("Input.dispatchMouseEvent", {type: "mouseReleased", ...point, button: "left", clickCount: 1});
      assert.equal((await state()).open, true);
    }
    assert.equal((await state()).visible.length, 8);
    // Verify the native Tab order, rather than programmatically focusing hidden controls.
    await evaluate('document.getElementById("items-export-life").focus()');
    if (width <= 680) await key("Tab"); // summary precedes the controls on mobile
    for (const id of ["kind", "sort", "order", "group-by", "limit", "saved-view-select", "area-select", "export-select"]) {
      await key("Tab");
      assert.equal(await evaluate("document.activeElement.id"), id, `Tab target at ${width}`);
    }
    // Existing change handlers must still forward selected values to URL and list API.
    const before = requests.length;
    await evaluate('document.getElementById("kind").value="E"; document.getElementById("sort").value="time"; document.getElementById("order").value="asc"; document.getElementById("sort").dispatchEvent(new Event("change", {bubbles:true}))');
    for (let i = 0; i < 100 && !requests.slice(before).some(r => r.url.startsWith("/api/items?")); i++) await delay(25);
    const list = requests.slice(before).find(r => r.url.startsWith("/api/items?"));
    assert.ok(list, "filter change sends list request");
    for (const query of [new URL(list.url, "http://fixture").searchParams, new URLSearchParams((await state()).url)]) {
      assert.equal(query.get("kind"), "E"); assert.equal(query.get("sort"), "time"); assert.equal(query.get("order"), "asc");
    }
    const saved = await state();
    await resize(width <= 680 ? 1280 : 390);
    assert.equal((await state()).open, width <= 680);
    await resize(width);
    const restored = await state();
    assert.equal(restored.open, width > 680);
    assert.deepEqual(restored.values, saved.values);
    assert.equal(restored.url, saved.url);
    results.push({width, initial, restored});
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
