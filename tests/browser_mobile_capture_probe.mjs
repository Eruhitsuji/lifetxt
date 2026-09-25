import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const [browserPath, htmlPath] = process.argv.slice(2);
if (!browserPath || !htmlPath) throw new Error("browser path and HTML path are required");

const html = await readFile(htmlPath);
const captureBodies = [];
const server = http.createServer((request, response) => {
  if (request.url.startsWith("/capture") || request.url.startsWith("/?")) {
    response.writeHead(200, {"content-type": "text/html; charset=utf-8", "cache-control": "no-store"});
    response.end(html);
    return;
  }
  if (request.method === "POST") {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", async () => {
      captureBodies.push(body);
      if (body.includes("Fail me")) {
        response.writeHead(403, {"content-type": "application/json"});
        response.end(JSON.stringify({error: "READ_ONLY", message: "Rejected"}));
        return;
      }
      if (body.includes("Only once")) await delay(250);
      response.writeHead(200, {"content-type": "application/json"});
      response.end(JSON.stringify({item: {title: "Saved", details: {id: ["T-1"]}}}));
    });
    return;
  }
  response.writeHead(200, {"content-type": "application/json"});
  response.end("{}");
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

  const cases = [
    {name: "phone-320", width: 320, height: 640, lang: "en"},
    {name: "phone-360", width: 360, height: 720, lang: "ja"},
    {name: "phone-390", width: 390, height: 844, lang: "en"},
    {name: "phone-430", width: 430, height: 932, lang: "ja"},
    {name: "landscape-keyboard", width: 667, height: 320, lang: "ja"},
    {name: "reduced-keyboard", width: 390, height: 360, lang: "en"},
  ];
  const results = [];
  for (const testCase of cases) {
    await command("Emulation.setDeviceMetricsOverride", {
      width: testCase.width, height: testCase.height, deviceScaleFactor: 2, mobile: true,
      screenWidth: testCase.width, screenHeight: testCase.height,
    });
    await command("Page.navigate", {url: `http://127.0.0.1:${port}/capture?lang=${testCase.lang}`});
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const ready = await command("Runtime.evaluate", {
        expression: "document.body?.classList.contains('capture-mode') && document.activeElement?.id === 'capture-text'",
        returnByValue: true,
      });
      if (ready.result.value) break;
      await delay(50);
    }
    const evaluated = await command("Runtime.evaluate", {
      expression: `(() => {
        const rect = id => { const value = document.getElementById(id).getBoundingClientRect(); return {left: value.left, right: value.right, top: value.top, bottom: value.bottom, width: value.width, height: value.height}; };
        return {
          viewport: {width: innerWidth, height: innerHeight},
          scrollWidth: document.documentElement.scrollWidth,
          bodyMode: document.body.classList.contains("capture-mode"),
          activeElement: document.activeElement?.id,
          input: rect("capture-text"), button: rect("capture-submit"),
          back: document.querySelector(".capture-back").getBoundingClientRect().toJSON(),
          card: document.querySelector(".capture-card").getBoundingClientRect().toJSON(),
          documentHeight: document.documentElement.scrollHeight,
          coarsePointer: matchMedia("(pointer: coarse)").matches,
          heading: document.getElementById("capture-heading").textContent.trim(),
          introDisplay: getComputedStyle(document.querySelector(".capture-intro")).display,
        };
      })()`,
      returnByValue: true,
    });
    results.push({...testCase, ...evaluated.result.value});
  }
  const contextResults = [];
  for (const testCase of cases.slice(0, 4)) {
    await command("Emulation.setDeviceMetricsOverride", {
      width: testCase.width, height: testCase.height, deviceScaleFactor: 2, mobile: true,
      screenWidth: testCase.width, screenHeight: testCase.height,
    });
    await command("Page.navigate", {url: `http://127.0.0.1:${port}/?view=context&lang=${testCase.lang}`});
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const ready = await command("Runtime.evaluate", {
        expression: "document.querySelector('[data-page=context]')?.classList.contains('page-active') && document.querySelector('.personal-context-fact')",
        returnByValue: true,
      });
      if (ready.result.value) break;
      await delay(50);
    }
    const evaluated = await command("Runtime.evaluate", {
      expression: `(() => {
        const section = document.querySelector("[data-page=context]");
        const input = document.querySelector(".personal-context-fact").getBoundingClientRect();
        const select = document.querySelector(".personal-context-domain").getBoundingClientRect();
        return {
          viewport: {width: innerWidth, height: innerHeight},
          scrollWidth: document.documentElement.scrollWidth,
          section: section.getBoundingClientRect().toJSON(),
          input: input.toJSON(), select: select.toJSON(),
          heading: document.getElementById("personal-context-heading").textContent.trim(),
        };
      })()`,
      returnByValue: true,
    });
    contextResults.push({...testCase, ...evaluated.result.value});
  }
  await command("Emulation.setDeviceMetricsOverride", {width: 390, height: 360, deviceScaleFactor: 2, mobile: true});
  await command("Page.navigate", {url: `http://127.0.0.1:${port}/capture?lang=en`});
  await delay(300);
  await command("Runtime.evaluate", {expression: "document.getElementById('capture-text').focus(); document.getElementById('capture-text').value = 'Keyboard save'"});
  await command("Input.dispatchKeyEvent", {type: "rawKeyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13});
  await command("Input.dispatchKeyEvent", {type: "char", key: "Enter", code: "Enter", text: "\r", windowsVirtualKeyCode: 13});
  await command("Input.dispatchKeyEvent", {type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13});
  await delay(150);
  const success = await command("Runtime.evaluate", {expression: `({value: document.getElementById("capture-text").value, focused: document.activeElement?.id, feedback: document.getElementById("capture-feedback").textContent, feedbackHeight: document.getElementById("capture-feedback").getBoundingClientRect().height})`, returnByValue: true});
  await command("Runtime.evaluate", {expression: "document.getElementById('capture-text').value = 'Fail me'; document.getElementById('capture-form').requestSubmit()"});
  await delay(150);
  const failure = await command("Runtime.evaluate", {expression: `({value: document.getElementById("capture-text").value, focused: document.activeElement?.id, feedback: document.getElementById("capture-feedback").textContent, feedbackHeight: document.getElementById("capture-feedback").getBoundingClientRect().height})`, returnByValue: true});
  const beforePending = captureBodies.length;
  await command("Runtime.evaluate", {expression: "document.getElementById('capture-text').value = 'Only once'; document.getElementById('capture-form').requestSubmit(); document.getElementById('capture-form').requestSubmit()"});
  const pendingState = await command("Runtime.evaluate", {expression: `({disabled: document.getElementById("capture-submit").disabled, busy: document.getElementById("capture-submit").getAttribute("aria-busy")})`, returnByValue: true});
  await delay(350);
  process.stdout.write(JSON.stringify({viewports: results, contextViewports: contextResults, interactions: {success: success.result.value, failure: failure.result.value, pending: pendingState.result.value, pendingRequestCount: captureBodies.length - beforePending}}));
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
