import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const [browserPath, htmlPath] = process.argv.slice(2);
if (!browserPath || !htmlPath) throw new Error("browser path and HTML path are required");

const html = await readFile(htmlPath);
let requests = 0;
const server = http.createServer((request, response) => {
  if (request.url === "/" || request.url.startsWith("/?")) {
    response.writeHead(200, {"content-type": "text/html; charset=utf-8"});
    response.end(html);
    return;
  }
  requests++;
  response.writeHead(200, {"content-type": "application/json"});
  const data = request.url === "/api/config" ? {web: {top_clock: {enabled: true, format: "h:mm:ss a", show_date: true}}, notifications: {enabled: false}} : {items: [], records: [], projects: [], contexts: [], tags: [], areas: [], completion: {}, warnings: []};
  response.end(JSON.stringify(data));
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const profile = await mkdtemp(path.join(os.tmpdir(), "lifetxt-browser-probe-"));
const browser = spawn(browserPath, [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
  "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`,
  "about:blank",
], {stdio: "ignore"});

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function devtoolsPort() {
  const file = path.join(profile, "DevToolsActivePort");
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (browser.exitCode !== null) throw new Error(`Chrome exited before publishing its DevTools port (${browser.exitCode})`);
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
  await command("Emulation.setTouchEmulationEnabled", {enabled: true, maxTouchPoints: 5});


  const evaluate = async expression => {
    const value = await command("Runtime.evaluate", {expression, returnByValue: true, awaitPromise: true});
    if (value.exceptionDetails) throw new Error(value.exceptionDetails.text);
    return value.result.value;
  };
  const results = [];
  for (const width of [320, 360, 390, 430]) {
    for (const lang of ["en", "ja"]) {
      for (const dark of [false, true]) {
        await command("Emulation.setDeviceMetricsOverride", {width, height: 844, deviceScaleFactor: 2, mobile: true});
        await command("Page.navigate", {url: `http://127.0.0.1:${port}/?lang=${lang}`});
        let ready = false;
        for (let attempt = 0; attempt < 100; attempt++) {
          ready = await evaluate("!!document.getElementById('top-clock')?.textContent");
          if (ready) break;
          await delay(50);
        }
        if (!ready) throw new Error("Top clock did not initialize");
        await evaluate(`document.body.classList.toggle("dark", ${dark})`);
        const result = await evaluate(`(() => {
          const el = document.getElementById("top-clock");
          const rect = el.getBoundingClientRect();
          const header = document.querySelector("header").getBoundingClientRect();
          const nav = document.getElementById("workspace-tabs").getBoundingClientRect();
          return {text: el.textContent, dateTime: el.dateTime, hidden: el.hidden,
            live: el.getAttribute("aria-live"), tag: el.tagName,
            numerals: getComputedStyle(el).fontVariantNumeric,
            rect: rect.toJSON(), header: header.toJSON(), nav: nav.toJSON(),
            scrollWidth: document.documentElement.scrollWidth,
            primaryButtons: document.querySelectorAll(".nav-primary button").length};
        })()`);
        results.push({width, lang, dark, ...result});
      }
    }
  }
  const before = await evaluate("document.getElementById('top-clock').textContent");
  // Let initial non-clock requests settle, then ensure seconds update without traffic.
  await delay(500);
  const count = requests;
  await delay(2100);
  const ticking = {before, after: await evaluate("document.getElementById('top-clock').textContent"), requests: requests - count};
  const modes = await evaluate(`(() => {
    appConfig.web.top_clock.enabled = false;
    _syncWebClocks();
    const disabled = document.getElementById("top-clock").hidden && _webClockTimer === null;
    switchWorkspace("kiosk");
    const kiosk = document.getElementById("kiosk-clock").textContent && document.getElementById("top-clock").hidden;
    switchWorkspace("");
    const returnedDisabled = document.getElementById("top-clock").hidden && _webClockTimer === null;
    appConfig.web.top_clock.enabled = true;
    _syncWebClocks();
    const returnedEnabled = !document.getElementById("top-clock").hidden && _webClockTimer !== null;
    return {disabled, kiosk: !!kiosk, returnedDisabled, returnedEnabled};
  })()`);
  process.stdout.write(JSON.stringify({viewports: results, ticking, modes}));
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
