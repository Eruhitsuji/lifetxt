import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm, writeFile} from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const [browserPath, baseURL, fixtureFile] = process.argv.slice(2);
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

  const wait = async (expression, label) => {
    for (let i = 0; i < 150; i++) {
      if (await evaluate(expression)) return;
      await delay(40);
    }
    throw Error("Timed out: " + label + " " + await evaluate("document.querySelector('.attachment-upload')?.textContent") + JSON.stringify(await evaluate("window.testRequests?.slice(-15)")));
  };
  const mode = async value => { const response = await fetch(`${baseURL}/__test/mode/${value}`, {method:"POST"}); assert(response.ok); };
  const open = async () => {
    await evaluate(`(async () => { const data = await api('/api/items/id/upload-test'); openDrawer(data.item, 'none'); })()`);
    await wait("attachmentUploadView?.ready && !attachmentUploadView.needsRefresh && !attachmentUploadView.input.disabled", "upload ready");
  };
  const select = async (name = "report.txt", size = 8) => evaluate(`(() => {
    const input = document.getElementById('attachment-upload-file');
    const files = new DataTransfer(); files.items.add(new File(['x'.repeat(${size})], ${JSON.stringify(name)}, {type:'text/plain'}));
    input.files = files.files; input.dispatchEvent(new Event('change', {bubbles:true}));
  })()`);
  const click = () => evaluate("document.getElementById('attachment-upload-submit').click()");
  const results = [];
  for (const width of [1280, 390]) {
    for (const lang of ["en", "ja"]) {
      await mode("normal");
      await command("Emulation.setDeviceMetricsOverride", {width, height:900, deviceScaleFactor:1, mobile:width < 500});
      await command("Page.navigate", {url: `${baseURL}/?view=items&lang=${lang}`});
      await wait(`typeof mountAttachmentUpload === 'function' && currentItems.length > 0 && document.documentElement.lang === ${JSON.stringify(lang)}`, "app ready");
      await evaluate(`window.testRequests = []; window.testPosts = []; const originalFetch = window.fetch; window.fetch = async (input, init) => {
        const response = await originalFetch(input, init);
        testRequests.push({path:String(input),status:response.status});
        if (input === '/api/attachments/upload' && init?.method === 'POST') window.testPosts.push({status:response.status, revision:init.headers['X-Lifetxt-Expected-Revision'], marker:init.headers['X-Lifetxt-Upload'], size:init.body.size});
        return response;
      };`);
      await open();
      const layout = await evaluate(`(() => {
        const panel = document.querySelector('.attachment-upload');
        panel.scrollIntoView(); const rect = panel.getBoundingClientRect();
        return {left:rect.left, right:rect.right, width:window.innerWidth,
          buttonHeight:document.getElementById('attachment-upload-submit').getBoundingClientRect().height,
          title:panel.querySelector('h4').textContent};
      })()`);
      assert(layout.left >= 0 && layout.right <= width + 1);
      assert(layout.buttonHeight >= 44);
      assert.equal(layout.title, lang === "ja" ? "添付ファイル" : "Attachments");
      await select("too-large.txt", 65);
      const oversized = await evaluate("attachmentUploadView.file === null && attachmentUploadView.submit.disabled && testPosts.length === 0");
      assert(oversized);
      const hostile = '<img onerror="x">日本語.txt';
      await select(hostile);
      const safeName = await evaluate(`attachmentUploadView.selected.textContent.includes(${JSON.stringify(hostile)}) && !attachmentUploadView.selected.querySelector('img')`);
      assert(safeName);
      await select("bad\u202etxt");
      const bidi = await evaluate("attachmentUploadView.file === null && !attachmentUploadView.selected.textContent.includes('\\u202e')");
      assert(bidi);
      // Exercise the actual native picker with a real file in addition to File fixtures.
      const doc = await command("DOM.getDocument");
      const found = await command("DOM.querySelector", {nodeId:doc.root.nodeId, selector:"#attachment-upload-file"});
      await command("DOM.setFileInputFiles", {nodeId:found.nodeId, files:[fixtureFile]});
      await wait("!!attachmentUploadView.file", "native selection");
      await click();
      await wait("document.getElementById('attachment-upload-receipt')?.textContent.includes('report-日本語.txt') && attachmentUploadView?.ready && !attachmentUploadView.needsRefresh && !attachmentUploadPending", "successful refresh");
      const success = await evaluate(`(() => {
        const root = document.querySelector('.attachment-upload');
        return {status:testPosts.at(-1).status, marker:testPosts.at(-1).marker,
          revision:testPosts.at(-1).revision, receipt:root.querySelector('#attachment-upload-receipt').textContent,
          noPath:!root.textContent.includes('web-uploads') && !root.querySelector('a'),
          cleared:document.getElementById('attachment-upload-file').value === ''};
      })()`);
      assert.equal(success.status, 201); assert.equal(success.marker, "1"); assert.equal(success.revision.length, 64); assert(success.noPath && success.cleared);
      await select(hostile); await click();
      await wait("attachmentUploadView?.ready && !attachmentUploadView.needsRefresh && !attachmentUploadPending", "hostile filename receipt");
      const hostileReceipt = await evaluate(`(() => { const receipt = document.getElementById('attachment-upload-receipt'); return receipt.textContent.includes(${JSON.stringify(hostile)}) && !receipt.querySelector('img, script, a'); })()`);
      assert(hostileReceipt);
      await select();
      await evaluate(`(async () => { const data = await api('/api/items/id/upload-test'); await api('/api/items/id/upload-test', {method:'PUT', headers:{'Content-Type':'application/json', 'X-Test-Time':new Date().toISOString()}, body:JSON.stringify({...data.item, title:data.item.title+' changed'})}); })()`);
      const beforeConflict = await evaluate("testPosts.length");
      await click(); await wait("attachmentUploadView?.needsRefresh && !attachmentUploadPending", "conflict"); await click();
      const conflict = await evaluate(`({status:testPosts.at(-1).status, count:testPosts.length-${beforeConflict}, disabled:attachmentUploadView.input.disabled, feedback:attachmentUploadView.feedback.textContent})`);
      assert.equal(conflict.status, 409); assert.equal(conflict.count, 1); assert(conflict.disabled);
      await evaluate("attachmentUploadView.refresh.click()");
      await wait("attachmentUploadView?.ready && !attachmentUploadView.needsRefresh && !attachmentUploadView.input.disabled", "explicit refresh");
      await select("executable.txt");
      await evaluate(`(() => { const input=attachmentUploadView.input, files=new DataTransfer(); files.items.add(new File(['MZblocked'], 'executable.txt')); input.files=files.files; input.dispatchEvent(new Event('change')); })()`);
      await click(); await wait("attachmentUploadView?.needsRefresh && !attachmentUploadPending", "real content validation");
      const validation = await evaluate("testPosts.at(-1).status"); assert.equal(validation, 415);
      const failures = [];
      for (const status of [401, 403, 503]) {
        await mode("normal"); await open(); await select(); await mode(String(status)); await click();
        await wait("attachmentUploadView?.needsRefresh && !attachmentUploadPending", "failure " + status);
        failures.push(await evaluate("({status:testPosts.at(-1).status, disabled:attachmentUploadView.input.disabled, safe:!attachmentUploadView.feedback.textContent.includes('UNTRUSTED') && !attachmentUploadView.feedback.querySelector('img')})"));
        assert.equal(failures.at(-1).status, status); assert(failures.at(-1).disabled && failures.at(-1).safe);
      }
      await mode("normal"); await open(); await select(); await mode("pending");
      const beforePending = await evaluate("testPosts.length"); await click(); await click();
      const pending = await evaluate("attachmentUploadPending && attachmentUploadView.submit.disabled && attachmentUploadView.refresh.disabled && attachmentUploadView.root.getAttribute('aria-busy') === 'true'");
      assert(pending);
      await evaluate("closeDrawer('none')");
      await evaluate(`(async () => { const data=await api('/api/items/id/upload-test'); openDrawer(data.item, 'none'); })()`);
      await wait("!attachmentUploadPending", "pending completion");
      const onePost = await evaluate(`testPosts.length === ${beforePending + 1}`); assert(onePost);
      await mode("readonly"); await evaluate(`(async () => { const data=await api('/api/items/id/upload-test'); openDrawer(data.item, 'none'); })()`); await wait("attachmentUploadView && !attachmentUploadView.feedback.textContent.includes('…')", "readonly policy");
      const readonly = await evaluate("!attachmentUploadView.ready && attachmentUploadView.input.disabled"); assert(readonly);
      await mode("normal");
      await evaluate("openDrawer({...drawerItem, editable:false}, 'none')");
      const readonlyItem = await evaluate("!document.getElementById('attachment-upload-submit')"); assert(readonlyItem);
      const storage = await evaluate(`JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)])`);
      assert(!storage.includes('report-日本語') && !storage.includes('executable.txt') && !storage.includes(hostile));
      results.push({width, lang, layout, oversized, safeName, bidi, success, hostileReceipt, conflict, validation, failures, pending, onePost, readonly, readonlyItem, noStoredUpload: true});
    }
  }
  process.stdout.write(JSON.stringify({viewports:results}));
} finally {
  if (socket) socket.close();
  if (browser.exitCode === null && browser.signalCode === null) {
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
