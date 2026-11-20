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
  const doneJump = ".items-board-jumps button:last-child";
  const doneHeading = ".items-board-columns > .items-board-column:nth-child(3) > h3";
  const boardUrl = await browser.evaluate("location.href");
  assert.equal(await browser.evaluate(`document.querySelector('${doneJump}').textContent`), "Done (0)");
  assert(await browser.evaluate(`document.querySelector('${doneJump}').getBoundingClientRect().height >= 44`));
  await browser.evaluate(`document.querySelector('${doneJump}').focus(); reloadItemsBoard()`);
  assert(await browser.evaluate(focused(doneJump)));
  await pressKey("Enter", 13, "\r");
  assert(await browser.evaluate(focused(doneHeading)));
  assert(await browser.evaluate(`(() => {
    const rect = document.querySelector('${doneHeading}').getBoundingClientRect();
    return rect.top >= document.querySelector('header').getBoundingClientRect().bottom
      && rect.bottom <= innerHeight;
  })()`));
  await browser.evaluate("reloadItemsBoard()");
  assert(await browser.evaluate(focused(doneHeading)));
  assert.equal(await browser.evaluate("location.href"), boardUrl);
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
  await browser.evaluate("reloadItemsBoard()");
  assert(await browser.evaluate(`document.activeElement === (${picker}) && (${picker}).value === '[x]'`));
  await pressKey("Tab", 9);
  assert(await browser.evaluate(`document.activeElement === (${confirm})`));
  await browser.evaluate("reloadItemsBoard()");
  assert(await browser.evaluate(`document.activeElement === (${confirm}) && !(${confirm}).disabled`));
  assert.equal(await browser.evaluate(`(${picker}).value`), "[x]");
  assert.equal(writes().length, 0);

  // Render a changed snapshot without issuing a write from the browser.
  await browser.evaluate(`renderItems(currentItems.map(item => item.id === 'board-fixture'
    ? {...item, details: {...item.details, project: ['changed']}} : item))`);
  assert(await browser.evaluate(`document.activeElement === (${picker}) && (${confirm}).disabled`));
  assert.equal(await browser.evaluate(`(${picker}).value`), "");
  assert.equal(writes().length, 0);
  await browser.evaluate("reloadItemsBoard()");
  await pressKey("ArrowDown", 40);
  await pressKey("ArrowDown", 40);
  await pressKey("Tab", 9);
  assert(await browser.evaluate(`document.activeElement === (${confirm})`));
  await pressKey("Enter", 13, "\r");
  await browser.wait(`document.activeElement === (${picker}) && !boardMovePending`, "focus after confirmed move");
  assert.equal(await browser.evaluate(`(${fixtureCard}).closest('.items-board-card')._lifetxtItem.status`), "[x]",
    await browser.evaluate("document.getElementById('toast-container').textContent"));
  assert.equal(await browser.evaluate(`(${picker}).value`), "");
  assert.equal(writes().length, 1);

  await browser.command("Emulation.setDeviceMetricsOverride", {
    width: 1280, height: 900, deviceScaleFactor: 1, mobile: false,
  });
  assert.equal(await browser.evaluate("getComputedStyle(document.querySelector('.items-board-jumps')).display"), "none");
  await browser.evaluate(`window.boardDrag = (() => {
    const [source, target, other] = document.querySelectorAll('.items-board-column');
    const card = source.querySelector('.items-board-card');
    const heading = target.querySelector('h3');
    const dataTransfer = new DataTransfer();
    const fire = (node, type, relatedTarget = null) =>
      !node.dispatchEvent(new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer, relatedTarget}));
    const highlighted = node => node.classList.contains('items-board-drop-target');
    return {source, target, other, card, heading, fire, highlighted};
  })()`);
  assert.deepEqual(await browser.evaluate(`(() => {
    const {source, target, other, card, heading, fire, highlighted} = boardDrag;
    const externalIgnored = !fire(heading, 'dragover') && !fire(heading, 'drop') && !highlighted(target);
    fire(card, 'dragstart');
    const sourceIgnored = !fire(source, 'dragover') && !highlighted(source);
    const targetMarked = fire(heading, 'dragover') && highlighted(target)
      && getComputedStyle(target).outlineStyle === 'solid';
    fire(target, 'dragleave', heading);
    const childKeepsHighlight = highlighted(target);
    fire(other, 'dragover');
    const changedColumns = highlighted(other) && !highlighted(target);
    fire(other, 'dragleave', source);
    const leftColumn = !highlighted(other);
    fire(target, 'dragover');
    fire(card, 'dragend');
    const cancelled = !highlighted(target);
    fire(card, 'dragstart');
    const sourceDropIgnored = !fire(source, 'drop');
    return {externalIgnored, sourceIgnored, targetMarked, childKeepsHighlight, changedColumns,
      leftColumn, cancelled, sourceDropIgnored};
  })()`), {
    externalIgnored: true, sourceIgnored: true, targetMarked: true, childKeepsHighlight: true,
    changedColumns: true, leftColumn: true, cancelled: true, sourceDropIgnored: true,
  });
  assert.equal(writes().length, 1);
  assert(await browser.evaluate(`(() => {
    const {card, target, heading, fire, highlighted} = boardDrag;
    fire(card, 'dragstart');
    fire(heading, 'dragover');
    return fire(heading, 'drop') && !highlighted(target);
  })()`));
  await browser.wait(`document.querySelectorAll('.items-board-column')[1]
    .querySelector('.items-board-card')?._lifetxtItem.status === '[/]' && !boardMovePending`,
    "dragged card saved in the destination column");
  assert.equal(writes().length, 2);

  await browser.evaluate("document.getElementById('open-only').checked = true; reloadItemsBoard()");
  const inProgressConfirm = ".items-board-column:nth-child(2) .items-board-move-confirm";
  await browser.evaluate(`(() => {
    const button = document.querySelector('${inProgressConfirm}');
    const picker = button.previousElementSibling;
    picker.value = '[x]';
    picker.dispatchEvent(new Event('change'));
    button.focus();
  })()`);
  await pressKey("Enter", 13, "\r");
  await browser.wait(focused("#items-layout"), "focus after a completed card leaves the filtered board");
  assert.equal(await browser.evaluate("document.querySelectorAll('.items-board-card').length"), 0);
  assert(await browser.evaluate("document.getElementById('toast-container').textContent.includes('Task moved. The card is outside the current board results.')"));
  assert.equal(writes().length, 3);

} finally {
  await browser.close();
}
