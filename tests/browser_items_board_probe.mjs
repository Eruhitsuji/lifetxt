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

async function click(expression) {
  const point = await browser.evaluate(`(() => {
    const node = ${expression};
    node.scrollIntoView({block: "center"});
    const rect = node.getBoundingClientRect();
    return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2};
  })()`);
  await browser.command("Input.dispatchMouseEvent", {type: "mousePressed", ...point, button: "left", clickCount: 1});
  await browser.command("Input.dispatchMouseEvent", {type: "mouseReleased", ...point, button: "left", clickCount: 1});
}

try {
  await browser.command("Emulation.setDeviceMetricsOverride", {
    width: 390, height: 844, deviceScaleFactor: 1, mobile: true,
  });
  await browser.command("Page.navigate", {url: `${baseUrl}/?view=items&lang=ja&text=Board`});
  await browser.wait('!!document.querySelector("#items .item .title")', "filtered list");
  await browser.evaluate('document.getElementById("items-filter-disclosure").open = false');
  const layoutSelector = mode => `#items-layout-${mode}`;
  const activeLayout = mode => `document.querySelector('${layoutSelector(mode)}').getAttribute('aria-pressed') === 'true'`;
  for (const [mode, label] of [["list", "一覧"], ["board", "カンバン"]]) {
    assert(await browser.evaluate(`(() => {
      const button = document.querySelector('${layoutSelector(mode)}');
      return button.textContent.trim() === '${label}' && button.getBoundingClientRect().width > 0;
    })()`));
  }
  await click('document.querySelector("#items-layout-board")');
  await browser.wait(`!!(${fixtureCard}) && (${activeLayout("board")})`, "visible Kanban with filter");
  await click('document.querySelector("#items-layout-list")');
  await browser.wait(`!!document.querySelector("#items .item") && (${activeLayout("list")})`, "return to list");
  assert.equal(await browser.evaluate('new URL(location.href).searchParams.get("text")'), "Board");
  await browser.evaluate("history.back()");
  await browser.wait(`!!(${fixtureCard}) && (${activeLayout("board")})`, "Back restores Kanban");
  await browser.evaluate("history.forward()");
  await browser.wait(`!!document.querySelector("#items .item") && (${activeLayout("list")})`, "Forward restores list");
  await browser.command("Emulation.clearDeviceMetricsOverride");
  for (const theme of ["light", "dark"]) {
    await browser.command("Page.navigate", {url: `${baseUrl}/?view=items&text=Board&theme=${theme}`});
    await browser.wait('!!document.querySelector("#items .item .title")', "item to hover");
    const position = await browser.evaluate(`(() => {
      const node = document.querySelector("#items .item");
      node.scrollIntoView({block: "center"});
      const rect = node.getBoundingClientRect();
      return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2};
    })()`);
    await browser.command("Input.dispatchMouseEvent", {type: "mouseMoved", x: 0, y: 0});
    const colors = `(() => {
      const node = document.querySelector("#items .item");
      const style = getComputedStyle(node);
      return {text: getComputedStyle(node.querySelector(".title")).color, background: style.backgroundColor,
        opacity: getComputedStyle(node.querySelector(".item-check")).opacity};
    })()`;
    const before = await browser.evaluate(colors);
    await browser.command("Input.dispatchMouseEvent", {type: "mouseMoved", ...position});
    await browser.wait(`document.querySelector("#items .item").matches(":hover") &&
      ${colors}.opacity === "1" && ${colors}.background !== ${JSON.stringify(before.background)}`, "mouse hover highlights item");
    const after = await browser.evaluate(colors);
    assert.equal(after.text, before.text);
    assert.notEqual(after.background, before.background);
    await browser.command("Input.dispatchMouseEvent", {type: "mouseMoved", x: 0, y: 0});
    await browser.evaluate('document.querySelector("#items .item .item-check").focus()');
    await browser.wait(`document.querySelector("#items .item").matches(":focus-within") &&
      ${colors}.opacity === "1" && ${colors}.background !== ${JSON.stringify(before.background)}`, "keyboard focus highlights item");
  }
  await browser.command("Page.navigate", {url: `${baseUrl}/?view=items&items_layout=board`});
  await browser.wait(`!!(${fixtureCard})`, "board card");

  await browser.evaluate(`(${fixtureCard}).closest(".items-board-card").insertAdjacentHTML("beforeend", "<p class='test-metadata'>Metadata</p>")`);
  await click('document.querySelector(".test-metadata")');
  await browser.wait(focused(`${drawer} .drawer-close-btn`), "detail from card metadata");
  await pressKey("Escape", 27);
  await browser.wait(`document.activeElement === (${fixtureCard})`, "mouse opener restores card title focus");
  const cardControl = selector => `(${fixtureCard}).closest('.items-board-card').querySelector('${selector}')`;
  await click(cardControl(".items-board-drag-handle"));
  assert.equal(await browser.evaluate(`!!document.querySelector('${drawer}')`), false);
  await browser.evaluate(`(${cardControl(".items-board-move")}).click()`);
  assert.equal(await browser.evaluate(`!!document.querySelector('${drawer}')`), false);

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
    await browser.wait(filteredOut ? focused("#items-layout-board") : `document.activeElement === (${fixtureCard})`, "focus after detail closes");
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
    const card = source.querySelector('.items-board-drag-handle');
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
  await browser.wait(focused("#items-layout-board"), "focus after a completed card leaves the filtered board");
  assert.equal(await browser.evaluate("document.querySelectorAll('.items-board-card').length"), 0);
  assert(await browser.evaluate("document.getElementById('toast-container').textContent.includes('Task moved. The card is outside the current board results.')"));
  assert.equal(writes().length, 3);
  const creates = () => browser.events.filter(event =>
    event.method === "Network.requestWillBeSent" && event.params.request.method === "POST"
    && new URL(event.params.request.url).pathname === "/api/items");
  const notStartedAdd = ".items-board-column:nth-child(1) .items-board-add";
  const inProgressAdd = ".items-board-column:nth-child(2) .items-board-add";
  await browser.evaluate(`document.querySelector('${notStartedAdd}').focus()`);
  await pressKey("Enter", 13, "\r");
  await browser.wait(focused("#edit-title"), "board task editor");
  await browser.evaluate("reloadItemsBoard()");
  assert(await browser.evaluate(focused("#edit-title")));
  await pressKey("Escape", 27);
  await browser.wait(focused(notStartedAdd), "focus after cancelling board task creation");
  assert.equal(creates().length, 0);

  await browser.evaluate(`document.querySelector('${inProgressAdd}').focus()`);
  await pressKey("Enter", 13, "\r");
  await browser.wait(focused("#edit-title"), "in-progress task editor");
  assert.equal(await browser.evaluate("document.getElementById('edit-status').value"), "[/]");
  await browser.evaluate(`document.getElementById('edit-title').value = 'Created on board';
    document.getElementById('save-button').focus();`);
  await pressKey("Enter", 13, "\r");
  await browser.wait(`document.querySelector('.items-board-column:nth-child(2) .items-board-title')
    ?.textContent === 'Created on board' && ${focused(inProgressAdd)}`, "created task and restored add-button focus");
  assert.equal(creates().length, 1);

  const calendarUrl = `${baseUrl}/?view=calendar&calmode=month&cal=2026-11-21`;
  const day = '[data-calendar-day="2026-11-21"]';
  const findDay = selector => `document.querySelector(${JSON.stringify(day + selector)})`;
  const agendaDate = `new URLSearchParams(location.search).get("view") === "calendar"
    && new URLSearchParams(location.search).get("calmode") === "day"
    && new URLSearchParams(location.search).get("cal") === "2026-11-21"`;
  await browser.command("Emulation.setDeviceMetricsOverride", {
    width: 320, height: 720, deviceScaleFactor: 1, mobile: true,
  });
  await browser.command("Page.navigate", {url: calendarUrl});
  await browser.wait(findDay(" .cal-more") + " !== null", "calendar overflow");
  const geometry = await browser.evaluate(`(() => {
    const button = ${findDay(" .cal-daylink")};
    const rect = button.getBoundingClientRect();
    const row = button.closest(".cal-week");
    const span = row.querySelector(".cal-span-bar").getBoundingClientRect();
    const entry = ${findDay(" .cal-entry")}.getBoundingClientRect();
    return {
      buttonHeight: rect.height,
      fillsDateHeader: rect.width >= button.parentElement.clientWidth - 1,
      lanesDoNotOverlap: rect.bottom <= span.top && span.bottom <= entry.top,
      monthFits: document.getElementById("calendar").scrollWidth <= document.getElementById("calendar").clientWidth,
      badgeIsPartOfButton: button.contains(document.getElementById(button.getAttribute("aria-describedby"))),
    };
  })()`);
  assert.ok(geometry.buttonHeight >= 44, JSON.stringify(geometry));
  assert.ok(geometry.fillsDateHeader && geometry.lanesDoNotOverlap &&
    geometry.monthFits && geometry.badgeIsPartOfButton, JSON.stringify(geometry));
  await click(findDay(" .cal-more"));
  await browser.wait("!!document.querySelector('.cal-popover')", "popover without navigating");
  await browser.evaluate(`document.querySelector('.cal-popover .cal-entry').focus()`);
  await pressKey("Enter", 13, "\r");
  await browser.wait(`!!document.querySelector('${drawer}')`, "calendar entry detail");
  await pressKey("Escape", 27);
  await browser.evaluate("document.querySelector('.cal-popover') && calClosePopover()");
  await click(findDay(" .cal-count"));
  await browser.wait(agendaDate, "clicking the count inside the date button opens the day");
  await browser.command("Page.navigate", {url: calendarUrl});
  await browser.wait(findDay(" .cal-daylink") + " !== null", "calendar day button");
  await browser.evaluate(`${findDay(" .cal-daylink")}.focus()`);
  await pressKey("Enter", 13, "\r");
  await browser.wait(agendaDate, "opening the day from the keyboard");
} finally {
  await browser.close();
}
