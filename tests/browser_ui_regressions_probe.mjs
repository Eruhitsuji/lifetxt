import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm, writeFile} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const [browserPath, baseURL, otherSource, writableSource] = process.argv.slice(2);
if (!browserPath || !baseURL) throw new Error("browser path and base URL are required");
const profile = await mkdtemp(path.join(os.tmpdir(), "lifetxt-browser-probe-"));
const browser = spawn(browserPath, [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
  "--disable-dev-shm-usage", "--disable-software-rasterizer",
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
  const move = async selector => {
    const rect = await evaluate(`document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect().toJSON()`);
    await command("Input.dispatchMouseEvent", {type: "mouseMoved", x: rect.x + rect.width / 2, y: rect.y + rect.height / 2});
  };
  const key = async name => {
    await command("Input.dispatchKeyEvent", {type: "keyDown", key: name, code: name, text: name === "Enter" ? "\r" : undefined, windowsVirtualKeyCode: name === "Enter" ? 13 : 9});
    await command("Input.dispatchKeyEvent", {type: "keyUp", key: name, code: name, windowsVirtualKeyCode: name === "Enter" ? 13 : 9});
  };
  const styles = selector => evaluate(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)}), s = getComputedStyle(el);
    const keys = ["color", "backgroundColor", "borderColor", "borderWidth", "borderRadius", "fontSize", "fontFamily", "fontWeight", "lineHeight", "minHeight", "padding", "boxSizing", "alignItems", "justifyContent", "transition", "outlineStyle", "outlineWidth", "outlineColor", "outlineOffset", "transform"];
    return Object.fromEntries(keys.map(k => [k, s[k]]));
  })()`);
  const pressedStyles = async selector => {
    const rect = await evaluate(`document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect().toJSON()`);
    const x = rect.x + rect.width / 2, y = rect.y + rect.height / 2;
    await command("Input.dispatchMouseEvent", {type: "mouseMoved", x, y});
    await command("Input.dispatchMouseEvent", {type: "mousePressed", x, y, button: "left", clickCount: 1});
    const result = await styles(selector);
    await evaluate(`window.addEventListener("click", event => { event.preventDefault(); event.stopImmediatePropagation(); }, {capture: true, once: true})`);
    await command("Input.dispatchMouseEvent", {type: "mouseReleased", x, y, button: "left", clickCount: 1});
    await command("Input.dispatchMouseEvent", {type: "mouseMoved", x: 0, y: 0});
    await evaluate("document.activeElement.blur()");
    return result;
  };
  const screenshot = async name => {
    if (!process.env.LIFETXT_BROWSER_SCREENSHOTS) return;
    const shot = await command("Page.captureScreenshot", {format: "png"});
    await writeFile(path.join(process.env.LIFETXT_BROWSER_SCREENSHOTS, name), Buffer.from(shot.data, "base64"));
  };
  for (const width of [1280, 390]) {
    for (const lang of ["en", "ja"]) {
      for (const dark of [false, true]) {
        await command("Emulation.setTouchEmulationEnabled", {enabled: width === 390, maxTouchPoints: 5});
        await command("Emulation.setDeviceMetricsOverride", {width, height: width === 390 ? 844 : 900, deviceScaleFactor: 1, mobile: width === 390});
        await command("Page.navigate", {url: `${baseURL}/?lang=${lang}`});
        let ready = false;
        for (let attempt = 0; attempt < 100; attempt++) {
          ready = await evaluate("!!document.getElementById('top-clock')?.textContent && appConfig !== null");
          if (ready) break;
          await delay(50);
        }
        if (!ready) throw new Error("Web UI did not initialize");
        await evaluate(`document.documentElement.setAttribute("data-theme", ${dark} ? "dark" : "light")`);
        // Turn off transitions only for deterministic style comparisons.
        await evaluate(`document.head.insertAdjacentHTML("beforeend", "<style>* { transition-duration: 0s !important; }</style>")`);
        const raw = await evaluate(`(async () => {
          newItem();
          const row = document.getElementById("import-raw-row");
          const input = document.getElementById("import-raw-input");
          const toggle = document.querySelector('button[onclick="toggleImportRaw()"]');
          const initial = getComputedStyle(row).display === "none";
          toggle.click();
          const opened = getComputedStyle(row).display !== "none" && document.activeElement === input;
          const help = document.getElementById("import-raw-help");
          const guidance = !!help?.textContent && input.getAttribute("aria-describedby") === help?.id;
          row.querySelector('button[onclick="toggleImportRaw(false)"]').click();
          const closed = getComputedStyle(row).display === "none" && document.activeElement === toggle && toggle.getAttribute("aria-expanded") === "false";
          toggle.click();
          const reopened = getComputedStyle(row).display !== "none" && document.activeElement === input;
          input.value = "not a life.txt record";
          await importRawLine();
          const preview = document.getElementById("import-raw-preview");
          const invalid = getComputedStyle(preview).display !== "none" && preview.classList.contains("err") && preview.textContent.includes("ERROR") && !row.hidden;
          input.value = '[ ] T "Imported task" project:work';
          await liveParseRawImport(input.value);
          const validPreview = preview.textContent.includes("Imported task") && preview.classList.contains("ok");
          await importRawLine();
          const populated = document.getElementById("edit-title").value === "Imported task" && document.getElementById("edit-details").value.includes("project:work") && getComputedStyle(row).display === "none";
          closeEditorModal();
          return {initial, opened, guidance, closed, reopened, invalid, validPreview, populated, help: help?.textContent};
        })()`);
        await evaluate(`document.getElementById("nav-more").open = true`);
        const nav = {};
        const sibling = '#nav-advanced button[data-view="agenda"]';
        for (const href of ["/planner", "/capture"]) {
          const link = `#nav-advanced a[href="${href}"]`;
          await evaluate("document.activeElement.blur()");
          await move("header h1");
          nav[href] = {normal: await styles(link), sibling: await styles(sibling)};
          await move(link);
          nav[href].hover = await styles(link);
          await move(sibling);
          nav[href].siblingHover = await styles(sibling);
          await move("header h1");
          await evaluate(`document.querySelector(${JSON.stringify(link)}).focus()`);
          await key("Tab");
          // Force keyboard modality, then focus the control to inspect its ring.
          await evaluate(`document.querySelector(${JSON.stringify(link)}).focus()`);
          nav[href].focus = await styles(link);
          await evaluate(`document.querySelector(${JSON.stringify(sibling)}).focus()`);
          nav[href].siblingFocus = await styles(sibling);
          await evaluate("document.activeElement.blur()");
          nav[href].pressed = await pressedStyles(link);
          nav[href].siblingPressed = await pressedStyles(sibling);
          nav[href].rect = await evaluate(`document.querySelector(${JSON.stringify(link)}).getBoundingClientRect().toJSON()`);
          nav[href].siblingRect = await evaluate(`document.querySelector(${JSON.stringify(sibling)}).getBoundingClientRect().toJSON()`);
        }
        if (lang === "en" && !dark) await screenshot(`nav-${width}.png`);
        const scrollWidth = await evaluate("document.documentElement.scrollWidth");
        await evaluate(`document.getElementById("nav-more").open = false`);
        const drawers = [];
        for (const editable of [true, false]) {
          await evaluate(`openDrawer({status: "[ ]", type: "T", title: "Drawer test", details: {id: ["drawer-test"]}, editable: ${editable}, line: 1})`);
          await delay(50); // Let the modal's initial animation-frame focus settle.
          const summary = "#drawer-overflow > summary";
          const button = "#drawer-create-related-btn";
          await move("#drawer-title");
          const drawer = {editable, normal: await styles(summary), sibling: await styles(button)};
          await move(summary);
          drawer.hover = await styles(summary);
          await move(button);
          drawer.siblingHover = await styles(button);
          await move("#drawer-title");
          await key("Tab");
          await evaluate(`document.querySelector(${JSON.stringify(summary)}).focus()`);
          drawer.focus = await styles(summary);
          drawer.focused = await evaluate(`document.activeElement.matches(${JSON.stringify(summary)}) && document.activeElement.matches(":focus-visible")`);
          await key("Enter");
          await delay(30);
          drawer.keyboardOpened = await evaluate('document.getElementById("drawer-overflow").open');
          await key("Enter");
          await delay(30);
          drawer.keyboardClosed = await evaluate('!document.getElementById("drawer-overflow").open');
          const hit = await evaluate(`document.querySelector(${JSON.stringify(summary)}).getBoundingClientRect().toJSON()`);
          const point = {x: hit.x + hit.width / 2, y: hit.y + hit.height / 2};
          const activate = async () => {
            if (width === 390) {
              await command("Input.dispatchTouchEvent", {type: "touchStart", touchPoints: [point]});
              await command("Input.dispatchTouchEvent", {type: "touchEnd", touchPoints: []});
            } else {
              await command("Input.dispatchMouseEvent", {type: "mousePressed", ...point, button: "left", clickCount: 1});
              await command("Input.dispatchMouseEvent", {type: "mouseReleased", ...point, button: "left", clickCount: 1});
            }
            await delay(30);
          };
          await activate();
          drawer.pointerOpened = await evaluate('document.getElementById("drawer-overflow").open');
          await activate();
          drawer.pointerClosed = await evaluate('!document.getElementById("drawer-overflow").open');
          await evaluate("document.activeElement.blur()");
          drawer.pressed = await pressedStyles(summary);
          if (editable) drawer.siblingPressed = await pressedStyles(button);
          if (lang === "en" && !dark && editable) await screenshot(`drawer-${width}.png`);
          drawer.rect = await evaluate(`document.querySelector(${JSON.stringify(summary)}).getBoundingClientRect().toJSON()`);
          drawers.push(drawer);
          await evaluate("closeDrawer()");
        }
        results.push({width, lang, dark, raw, nav, drawers, scrollWidth});
      }
    }
  }
  const links = {};
  for (const href of ["/planner", "/capture"]) {
    await command("Page.navigate", {url: baseURL + "/"});
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await evaluate('!!document.querySelector("#nav-advanced")')) break;
      await delay(50);
    }
    await evaluate(`document.getElementById("nav-more").open = true; document.querySelector('a[href="${href}"]').focus()`);
    await key("Enter");
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await evaluate("location.pathname") === href) break;
      await delay(50);
    }
    links[href] = await evaluate("location.pathname");
  }
  const bulk = [];
  if (!otherSource || !writableSource) throw new Error("bulk smoke requires isolated source fixture paths");
  for (const lang of ["en", "ja"]) {
    await command("Page.navigate", {url: `${baseURL}/?lang=${lang}`});
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await evaluate("typeof openBulkInput === 'function' && appConfig !== null")) break;
      await delay(50);
    }
    const text = Array.from({length:12}, (_, i) => `[N] N Bulk_${lang}_${i} id:bulk-${lang}-${i} body:"Browser body ${i}" ref:missing-browser`).join("\n") + "\n";
    const setup = await evaluate(`(async () => {
      window.confirm = () => true;
      window.__bulkBatchCalls = 0;
      const originalFetch = window.fetch;
      window.fetch = (url, options) => {
        if (String(url).includes("/api/items/batch")) ++window.__bulkBatchCalls;
        return originalFetch(url, options);
      };
      openBulkInput();
      const input = document.getElementById("bulk-input-text");
      const focused = document.activeElement === input;
      input.value = ${JSON.stringify(text)};
      input.dispatchEvent(new Event("input", {bubbles:true}));
      await previewBulkInput();
      const root = document.getElementById("bulk-input-preview");
      const sections = root.querySelectorAll("details");
      const allRecords = sections.length === 15 && root.textContent.includes("Browser body 11");
      sections[0].querySelector("summary").focus();
      return {focused, allRecords, eligible:!document.getElementById("bulk-input-add").disabled};
    })()`);
    if (!setup.eligible) throw new Error("real contextual Preview did not enable Add all");
    await key("Enter");
    const keyboardDetails = await evaluate('document.querySelector("#bulk-input-preview details").open');
    const before = await readFile(writableSource, "utf8");
    await writeFile(otherSource, `[ ] T "Changed context ${lang}" id:context-other\n`, "utf8");
    const failure = await evaluate(`(async () => {
      await addAllBulkInput();
      const input = document.getElementById("bulk-input-text");
      const disabled = document.getElementById("bulk-input-add").disabled;
      const message = document.getElementById("bulk-input-preview").textContent;
      await addAllBulkInput();
      return {disabled, message, inputRetained:input.value === ${JSON.stringify(text)}, noRetry:window.__bulkBatchCalls === 1};
    })()`);
    const noSave = before === await readFile(writableSource, "utf8");
    const recovery = await evaluate(`(async () => {
      await previewBulkInput();
      const recovered = !document.getElementById("bulk-input-add").disabled;
      await addAllBulkInput();
      return {recovered, closed:document.getElementById("bulk-input-modal").hidden, batchCalls:window.__bulkBatchCalls};
    })()`);
    const saved = await readFile(writableSource, "utf8");
    const savedOnce = Array.from({length:12}, (_, i) => saved.split(`id:bulk-${lang}-${i} `).length - 1).every(count => count === 1);
    await evaluate("openBulkInput()");
    await command("Input.dispatchKeyEvent", {type:"keyDown", key:"Escape", code:"Escape", windowsVirtualKeyCode:27});
    await command("Input.dispatchKeyEvent", {type:"keyUp", key:"Escape", code:"Escape", windowsVirtualKeyCode:27});
    const escapeClosed = await evaluate('document.getElementById("bulk-input-modal").hidden');
    bulk.push({lang, focused:setup.focused, allRecords:setup.allRecords, keyboardDetails, noSave, ...failure, ...recovery, savedOnce, escapeClosed});
  }
  process.stdout.write(JSON.stringify({viewports: results, links, bulk}));

} finally {
  if (socket) socket.close();
  if (browser.exitCode === null) {
    browser.kill("SIGTERM");
    await new Promise(resolve => browser.once("exit", resolve));
  }
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
