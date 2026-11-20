import assert from "node:assert/strict";
import {launch} from "./browser_revision_support.mjs";

const [browserPath, baseUrl] = process.argv.slice(2);
const browser = await launch(browserPath);
const card = ".items-board-title";
const fixtureCard = `[...document.querySelectorAll('${card}')].find(button => button.textContent === 'Board fixture')`;
const drawer = "#detail-drawer.open";
const focused = selector => `document.activeElement.matches(${JSON.stringify(selector)})`;

async function pressKey(key, windowsVirtualKeyCode, text) {
  const params = {key, code: key, windowsVirtualKeyCode};
  await browser.command("Input.dispatchKeyEvent", {type: "keyDown", ...params, text});
  await browser.command("Input.dispatchKeyEvent", {type: "keyUp", ...params});
}

try {
  await browser.command("Page.navigate", {url: `${baseUrl}/?view=items&items_layout=board`});
  await browser.wait(`!!(${fixtureCard})`, "board card");

  for (const filteredOut of [false, true]) {
    await browser.evaluate(`window.originalCard = ${fixtureCard}; originalCard.focus();`);
    await pressKey("Enter", 13, "\r");
    await browser.wait(focused(`${drawer} .drawer-close-btn`), "detail close button");

    if (filteredOut) await browser.evaluate("document.getElementById('search').value = 'Unrelated'");
    await browser.evaluate("reloadItemsBoard()");
    assert.equal(await browser.evaluate("originalCard.isConnected"), false);
    assert.equal(await browser.evaluate(`!!(${fixtureCard})`), !filteredOut);
    assert(await browser.evaluate(focused(`${drawer} .drawer-close-btn`)));

    await pressKey("Escape", 27);
    await browser.wait(filteredOut ? focused("#items-layout") : `document.activeElement === (${fixtureCard})`, "focus after detail closes");
  }
  await browser.command("Emulation.setDeviceMetricsOverride", {
    width: 390, height: 844, deviceScaleFactor: 1, mobile: true,
  });
  await browser.evaluate("document.getElementById('search').value = ''; reloadItemsBoard()");
  const fixtureControl = selector => `(${fixtureCard}).closest('.items-board-card').querySelector('${selector}')`;
  const picker = fixtureControl(".items-board-move");
  const confirm = fixtureControl(".items-board-move-confirm");
  const writes = () => browser.events.filter(event =>
    event.method === "Network.requestWillBeSent" && event.params.request.method === "PUT");
  await browser.evaluate(`(${picker}).focus()`);
  await pressKey("ArrowDown", 40);
  await pressKey("ArrowDown", 40);
  assert.equal(await browser.evaluate(`(${picker}).value`), "[x]");
  assert.equal(await browser.evaluate(`(${fixtureCard}).closest('.items-board-card')._lifetxtItem.status`), "[ ]");
  assert.equal(writes().length, 0);
  assert(await browser.evaluate(`(${confirm}).getBoundingClientRect().height >= 44`));
  await pressKey("Tab", 9);
  assert(await browser.evaluate(`document.activeElement === (${confirm})`));
  await pressKey("Enter", 13, "\r");
  await browser.wait(`document.activeElement === (${picker}) && !boardMovePending`, "focus after confirmed move");
  assert.equal(await browser.evaluate(`(${fixtureCard}).closest('.items-board-card')._lifetxtItem.status`), "[x]");
  assert.equal(writes().length, 1);
} finally {
  await browser.close();
}
