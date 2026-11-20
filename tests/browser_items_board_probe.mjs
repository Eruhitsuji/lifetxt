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
} finally {
  await browser.close();
}
