import assert from "node:assert/strict";
import {launch} from "./browser_revision_support.mjs";

const [browserPath, baseURL] = process.argv.slice(2);
assert.ok(browserPath && baseURL, "Usage: node tests/browser_web_help_probe.mjs CHROMIUM URL");
const browser = await launch(browserPath);
const {command, evaluate, wait} = browser;
const click = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
const visible = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).getClientRects().length > 0`);
const key = name => command("Input.dispatchKeyEvent", {
  type: "keyDown", key: name, windowsVirtualKeyCode: name === "Escape" ? 27 : 0,
});
const openSettings = () => click("#view-settings > summary");
const assertHidden = async selector => assert.equal(await visible(selector), false, selector);

try {
  await command("Emulation.setDeviceMetricsOverride", {
    width: 390, height: 844, deviceScaleFactor: 1, mobile: true,
  });
  const url = new URL("/?lang=ja", baseURL).href;
  await command("Page.navigate", {url});
  await wait('document.documentElement.lang === "ja" && document.querySelector(".view-guide-desc")', "Japanese Items");
  assert.ok(await visible("#header-help-btn"));
  assert.ok(await visible(".view-guide-desc"));

  await click("#header-help-btn");
  await wait('document.activeElement.id === "help-title"', "guide focus");
  assert.equal(await evaluate('document.querySelector("#help-getting-started").textContent'), "基本操作");
  await key("Escape");
  await wait('!document.querySelector("#help-modal").classList.contains("open")', "help closed");

  await openSettings();
  await click("#header-help-setting");
  await assertHidden("#header-help-btn");
  assert.ok(await visible(".view-guide-desc"), "header setting leaves hints enabled");
  await click("#context-help-setting");
  await assertHidden(".view-guide-desc");
  assert.ok(await visible(".view-guide-actions button"), "guide actions stay available");
  await click('#view-settings button[onclick="openHelpFromViewSettings()"]');
  await wait('document.activeElement.id === "help-title"', "help opens through settings");
  await click("#help-modal .runtime-build-info summary");
  assert.ok(await visible("#runtime-build-version"));
  await click("#help-modal details:first-of-type summary");
  assert.ok(await visible("#help-modal table"));
  await key("Escape");
  await wait('document.activeElement.matches("#view-settings > summary")', "focus restored to settings");

  await command("Page.reload");
  await wait('document.body?.classList.contains("hide-operation-hints")', "saved preferences restored");
  await assertHidden("#header-help-btn");
  await evaluate('document.querySelector("#primary-create").focus()');
  assert.equal(await evaluate('document.querySelector("#primary-create").hasAttribute("aria-describedby")'), false);
  assert.equal(await evaluate('document.querySelector("#ui-help-tooltip").classList.contains("visible")'), false);
  await click("#primary-create");
  await assertHidden("#editor-modal .field-help");
  await assertHidden(".editor-help-strip");
  assert.ok(await visible("#edit-title"));
  await key("Escape");

  await key("?");
  await wait('document.activeElement.id === "help-command-search"', "keyboard access with hidden header");
  await wait('document.querySelectorAll("#help-command-list .help-command-row").length > 1', "existing command catalog");
  await key("ArrowDown");
  assert.ok(await evaluate('document.querySelector("#help-command-list").children[1].classList.contains("focus")'));
  await key("Escape");

  await openSettings();
  await click("#context-help-setting");
  await click("#header-help-setting");
  await click("#view-settings > summary");
  assert.ok(await visible("#header-help-btn"));
  assert.ok(await visible(".view-guide-desc"));
  await evaluate('document.querySelector("#primary-create").focus()');
  assert.ok(await evaluate('document.querySelector("#ui-help-tooltip").classList.contains("visible")'));
  assert.equal(await evaluate('document.querySelector("#primary-create").getAttribute("aria-describedby")'), "ui-help-tooltip");
  console.log("Web help guide, visibility, reload, focus, and command navigation passed.");
} finally {
  await browser.close();
}
