      const input = document.getElementById("cmdk-input");
      backdrop.classList.add("open");
      syncBackgroundInert();
      input.value = "";
      renderCmdk("");
      input.focus();
    }
    function closeCmdk() {
      document.getElementById("cmdk-backdrop").classList.remove("open");
      syncBackgroundInert();
    }
    function renderCmdk(qText) {
      const list = document.getElementById("cmdk-list");
      const raw = String(qText || "").trim();
      if (raw.startsWith("/")) { renderCmdkCommands(raw, list); return; }
      const q = raw.toLowerCase();
      const idKey = appConfig?.ids?.key || "id";
      const actions = CMDK_ACTIONS.filter(a => fuzzyMatch(a.label, q));
      const items = q
        ? (currentItems || []).filter(i =>
            fuzzyMatch(i.title || "", q) ||
            fuzzyMatch(String(i?.details?.[idKey]?.[0] || i?.id || ""), q)
          ).slice(0, 8)
        : [];
      const recent = q ? [] : loadRecentItems()
        .map(r => (currentItems || []).find(i => recentItemKey(i) === r.key) || r)
        .filter(Boolean)
        .slice(0, 6);
      _cmdkEntries = [
        ...recent.map(i => ({kind: i.type || "recent", label: i.title || "(untitled)", hint: i?.details?.[idKey]?.[0] || (i.line ? `line ${i.line}` : "recent"), section: "Recently Opened", run: () => {
          const live = (currentItems || []).find(x => recentItemKey(x) === (i.key || recentItemKey(i)));
          if (live) { selectItem(live); openDrawer(live); }
          else if (i.line) openItemByLine(Number(i.line));
        }})),
        ...items.map(i => ({kind: i.type || "item", label: i.title, hint: i?.details?.[idKey]?.[0] || `line ${i.line}`, section: "Items", run: () => { selectItem(i); openDrawer(i); }})),
        ...actions.map(a => ({kind: "action", label: a.label, hint: "", section: "Actions", run: a.run})),
      ];
      _cmdkIndex = 0;
      if (!_cmdkEntries.length) {
        list.innerHTML = `<div class="cmdk-empty">No matches.</div>`;
        return;
      }
      list.innerHTML = "";
      let lastSection = "";
      _cmdkEntries.forEach((entry, i) => {
        if (entry.section && entry.section !== lastSection) {
          const section = document.createElement("div");
          section.className = "cmdk-section";
          section.textContent = entry.section;
          list.appendChild(section);
          lastSection = entry.section;
        }
        const row = document.createElement("div");
        row.className = "cmdk-row" + (i === _cmdkIndex ? " focus" : "");
        row.innerHTML = `<span class="cmdk-kind">${escapeHtml(entry.kind)}</span><span>${escapeHtml(entry.label)}</span>` +
          (entry.hint ? `<span style="margin-left:auto;color:var(--muted);font-size:.78rem">${escapeHtml(entry.hint)}</span>` : "");
        row.addEventListener("click", () => { closeCmdk(); entry.run(); });
        list.appendChild(row);
      });
    }
    function _cmdkMoveFocus(delta) {
      if (!_cmdkEntries.length) return;
      _cmdkIndex = (_cmdkIndex + delta + _cmdkEntries.length) % _cmdkEntries.length;
      const rows = document.querySelectorAll("#cmdk-list .cmdk-row");
      rows.forEach((row, i) => row.classList.toggle("focus", i === _cmdkIndex));
      if (rows[_cmdkIndex]) rows[_cmdkIndex].scrollIntoView({block: "nearest"});
    }
    document.addEventListener("DOMContentLoaded", () => {
      loadCommandCatalog();
      const input = document.getElementById("cmdk-input");
      if (!input) return;
      input.addEventListener("input", () => renderCmdk(input.value));
      input.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); _cmdkMoveFocus(1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); _cmdkMoveFocus(-1); }
        else if (e.key === "Enter") {
          e.preventDefault();
          const typed = input.value.trim();
          if (typed.startsWith("/")) {
            // Run exactly what was typed so arguments survive; the highlighted
            // row only matters when the name itself is incomplete.
            const name = typed.slice(1).split(/\s+/)[0].toLowerCase();
            const resolved = commandByName(name)
              ? typed
              : "/" + ((matchingCommands(typed)[0] || {}).name || name) + " " + typed.split(/\s+/).slice(1).join(" ");
            closeCmdk();
            runWebCommand(resolved);
            return;
          }
          const entry = _cmdkEntries[_cmdkIndex];
          if (entry) { closeCmdk(); entry.run(); }
        } else if (e.key === "Escape") {
          e.preventDefault();
          closeCmdk();
        }
      });
    });

    // ── Help modal ─────────────────────────────────────────────────
    function renderHelpModalShortcuts() {
      const table = document.querySelector("#help-modal table");
      if (!table) return;
      table.innerHTML = SHORTCUT_HELP_ROWS.map(([key, text]) =>
        `<tr><td>${escapeHtml(key)}</td><td>${escapeHtml(text)}</td></tr>`
      ).join("");
    }
    let _helpCmdEntries = [];
    let _helpCmdIndex = 0;
    async function renderHelpModalCommands() {
      const list = document.getElementById("help-command-list");
      if (!list) return;
      if (!COMMAND_CATALOG.length) await loadCommandCatalog();
      const typed = document.getElementById("help-command-search")?.value || "";
      const matches = matchingCommands(typed);
      _helpCmdEntries = matches;
      _helpCmdIndex = matches.length ? 0 : -1;
      if (!matches.length) {
        list.innerHTML = `<div class="help-command-empty">No command matches. Try a different search.</div>`;
        return;
      }
      list.innerHTML = matches.map((command, i) => {
        const usage = "/" + command.name + (command.usage ? " " + command.usage : "");
        const alias = command.alias ? ` (/${command.alias})` : "";
        const badge = command.web ? "" : `<span class="help-command-badge">TUI only</span>`;
        return `<div class="help-command-row${i === _helpCmdIndex ? " focus" : ""}">` +
          // Literal command syntax, not prose -- see the cmdk-row comment above.
          `<span class="help-command-usage" data-no-i18n>${escapeHtml(usage)}${escapeHtml(alias)}</span>${badge}` +
          `<span class="help-command-summary">${escapeHtml(command.summary || "")}</span>` +
          `</div>`;
      }).join("");
      Array.from(list.children).forEach((row, i) => {
        row.addEventListener("click", () => _runHelpModalCommand(i));
      });
    }
    function _runHelpModalCommand(index) {
      const command = _helpCmdEntries[index];
      if (!command) return;
      // Matches the command palette's own behavior: close first, then let
      // runWebCommand's existing "/x is terminal-only" toast explain a
      // TUI-only pick rather than silently doing nothing.
      closeHelpModal();
      runWebCommand("/" + command.name);
    }
    function _helpCmdMoveFocus(delta) {
      if (!_helpCmdEntries.length) return;
      _helpCmdIndex = (_helpCmdIndex + delta + _helpCmdEntries.length) % _helpCmdEntries.length;
      const rows = document.querySelectorAll("#help-command-list .help-command-row");
      rows.forEach((row, i) => row.classList.toggle("focus", i === _helpCmdIndex));
      if (rows[_helpCmdIndex]) rows[_helpCmdIndex].scrollIntoView({block: "nearest"});
    }
    function openHelpModal() {
      renderHelpModalShortcuts();
      const search = document.getElementById("help-command-search");
      if (search) search.value = "";
      renderHelpModalCommands();
      // Focus the search box (not the first button) so arrow-key/Enter
      // command navigation works immediately without an extra click.
      openManagedModal(document.getElementById("help-modal"), "#help-command-search");
    }
    function closeHelpModal() { closeManagedModal(document.getElementById("help-modal")); }
    document.addEventListener("DOMContentLoaded", () => {
      const search = document.getElementById("help-command-search");
      if (!search) return;
      search.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); _helpCmdMoveFocus(1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); _helpCmdMoveFocus(-1); }
        else if (e.key === "Enter") { e.preventDefault(); _runHelpModalCommand(_helpCmdIndex); }
      });
    });

    // ── Contextual hover/focus help ────────────────────────────────
    function clampNumber(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }
    function positionUiHelpTooltip(anchor, tooltip) {
      if (!anchor || !tooltip) return;
      const margin = 8;
      const rect = anchor.getBoundingClientRect();
      const tipRect = tooltip.getBoundingClientRect();
      const left = clampNumber(
        rect.left + rect.width / 2 - tipRect.width / 2,
        margin,
        Math.max(margin, window.innerWidth - tipRect.width - margin)
      );
      let top = rect.bottom + margin;
      if (top + tipRect.height > window.innerHeight - margin) {
        top = rect.top - tipRect.height - margin;
      }
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${clampNumber(top, margin, Math.max(margin, window.innerHeight - tipRect.height - margin))}px`;
    }
    function showUiHelp(anchor) {
      const tooltip = document.getElementById("ui-help-tooltip");
      const text = anchor?.dataset?.help || "";
      if (!tooltip || !text) return;
      // dataset.help is the canonical English source and is never mutated;
      // translating here at display time means a later language change
      // (or a target text without a dictionary entry yet) never needs the
      // source string rewritten.
      tooltip.textContent = t(text);
      tooltip.setAttribute("aria-hidden", "false");
      tooltip.classList.add("visible");
      window.requestAnimationFrame(() => positionUiHelpTooltip(anchor, tooltip));
    }
    function hideUiHelp() {
      const tooltip = document.getElementById("ui-help-tooltip");
      if (!tooltip) return;
      tooltip.classList.remove("visible");
      tooltip.setAttribute("aria-hidden", "true");
    }
    function setupContextualHelp() {
      installContextualHelpTargets();
      document.querySelectorAll(".help-target[data-help], .field-help[data-help]").forEach(el => {
        if (el.dataset.helpBound === "true") return;
        el.dataset.helpBound = "true";
        el.setAttribute("aria-describedby", "ui-help-tooltip");
        el.addEventListener("mouseenter", () => showUiHelp(el));
        el.addEventListener("focus", () => showUiHelp(el));
        el.addEventListener("mouseleave", hideUiHelp);
        el.addEventListener("blur", hideUiHelp);
      });
      if (document.body.dataset.helpViewportBound !== "true") {
        document.body.dataset.helpViewportBound = "true";
        window.addEventListener("resize", hideUiHelp);
        window.addEventListener("scroll", hideUiHelp, {passive: true});
      }
    }
    function installContextualHelpTargets() {
      for (const [id, text] of Object.entries(CONTROL_HELP)) {
        const el = document.getElementById(id);
        if (!el) continue;
        el.classList.add("help-target");
        if (!el.dataset.help) el.dataset.help = text;
      }
      document.querySelectorAll(".workspace-tab[data-view]").forEach(el => {
        el.classList.add("help-target");
        const view = el.dataset.view || "";
        if (!el.dataset.help && VIEW_HELP[view]) el.dataset.help = VIEW_HELP[view];
      });
      document.querySelectorAll(".tl-controls button[data-range]").forEach(el => {
        el.classList.add("help-target");
        if (!el.dataset.help) el.dataset.help = "Change the Timeline range and keep the choice in the URL.";
      });
      document.querySelectorAll(".cal-controls button").forEach(el => {
        el.classList.add("help-target");
        if (!el.dataset.help) el.dataset.help = "Navigate the Calendar month/week view; URL parameters keep the visible period stable.";
      });
    }

    // ── Toast system ────────────────────────────────────────────────
    function showToast(message, type = "info", duration = 3500) {
      const container = document.getElementById("toast-container");
      const el = document.createElement("div");
      el.className = "toast " + type;
      el.textContent = message;
      container.appendChild(el);
      setTimeout(() => el.remove(), duration);
    }

    // ── Record detail modal ────────────────────────────────────────
    let drawerItem = null;
    let drawerEditing = false;

    function _drawerRestoreButtons(item) {
      const isDone = ["[x]", "[-]"].includes(item.status);
      const idKey = (typeof appConfig !== "undefined" && appConfig?.ids?.key) || "id";
      const hasId = !!(item?.details?.[idKey]?.[0] || item?.id);
      const isRepeat = !!(item?.details?.repeat?.length && hasId);
      document.getElementById("drawer-head-btns").innerHTML =
        `<button class="secondary" onclick="drawerMarkDone()" id="drawer-done-btn"${!item.editable || isDone ? " disabled" : ""}>Done</button>` +
        (isRepeat
          ? `<button class="secondary" onclick="drawerComplete()" id="drawer-complete-btn" title="Complete this instance and materialize the next occurrence"${!item.editable || isDone ? " disabled" : ""}>✓ Complete + repeat</button>`
          : "") +
        `<button class="secondary" id="drawer-edit-btn" onclick="drawerEdit()"${!item.editable ? " disabled" : ""}>Edit</button>` +
        `<button class="secondary" id="drawer-copy-id" onclick="drawerCopyId()" title="Copy item ID to clipboard"${hasId ? "" : ' style="display:none"'}>Copy ID</button>` +
        `<button class="secondary" id="drawer-share-btn" onclick="drawerShareLink()" title="Copy deep link to this item">Share</button>` +
        `<button class="secondary" onclick="drawerCopyMarkdown()" title="Copy item as Markdown">MD</button>` +
        `<button class="danger" onclick="drawerDelete()" id="drawer-delete-btn"${!item.editable ? " disabled" : ""}>Delete</button>`;
    }

    function openDrawer(item) {
      drawerEditing = false;
      drawerItem = item;
      const drawer = document.getElementById("detail-drawer");
      const body = document.getElementById("drawer-body");
      const title = document.getElementById("drawer-title");
      const isDone = ["[x]", "[-]"].includes(item.status);
      const statusCls = STATUS_CLASS[item.status] || "status-note";
      const statusLbl = STATUS_LABEL[item.status] || item.status;
      const typeCls = "type-" + (item.type || "N");
      const typeFullName = ITEM_TYPE_NAMES[item.type] || item.type;
      title.innerHTML = `<span class="status-badge ${statusCls}">${escapeHtml(statusLbl)}</span>` +
        `<span class="type-badge ${typeCls}" style="margin-left:.35rem" title="${escapeHtml(typeFullName)}">${escapeHtml(item.type)}</span>` +
        `<span style="margin-left:.25rem;font-size:.78rem;color:var(--muted)">${escapeHtml(typeFullName)}</span>` +
        `<span style="margin-left:.4rem;font-weight:700">${escapeHtml(item.title)}</span>`;
      _drawerRestoreButtons(item);
      const REF_KEYS = new Set(["depends_on", "parent", "blocks", "related", "ref"]);
      let fieldsHtml = `<div class="drawer-section-title">Fields</div><div class="drawer-fields">`;
      for (const [key, values] of Object.entries(item.details || {})) {
        const valHtml = (values || []).map(v => {
          if (REF_KEYS.has(key)) {
            return `<a class="drawer-link" onclick="drawerNavigate(${escapeHtml(jsLiteral(String(v)))})">${escapeHtml(String(v))}</a>`;
          }
          return escapeHtml(String(v));
        }).join(", ");
        fieldsHtml += `<div class="drawer-field"><span class="key">${escapeHtml(key)}</span><span class="val">${valHtml}</span></div>`;
      }
      fieldsHtml += `</div>`;
      const bodyHtml = item?.markdown?.details?.body?.[0]
        ? `<div class="drawer-section-title">Body</div><div class="markdown">${item.markdown.details.body[0]}</div>` : "";
      const sourceHtml = `<div class="drawer-section-title">Source</div>` +
        `<div style="font-size:.82rem;color:var(--muted)">${escapeHtml(item.source || "")} line ${escapeHtml(String(item.line || ""))}</div>`;
      const rawHtml = item?.raw
        ? `<details class="drawer-raw-details"><summary>Raw line</summary><pre class="drawer-raw-pre">${escapeHtml(item.raw || "")}</pre></details>`
        : "";
      const idKey = appConfig?.ids?.key || "id";
      const itemId = item?.id || item?.details?.[idKey]?.[0] || "";
      const threadHtml = item.type === "M" && itemId
        ? `<div id="drawer-thread"><div class="drawer-section-title">Message Thread</div><div class="empty">Loading…</div></div>`
        : "";
      const replyHtml = item.type === "M" && itemId
        ? `<form class="message-reply-form" onsubmit="event.preventDefault();replyToMessage(${escapeHtml(jsLiteral(itemId))})">` +
          `<div class="drawer-section-title">Reply</div>` +
          `<input id="message-reply-title" placeholder="Reply title" autocomplete="off">` +
          `<textarea id="message-reply-body" placeholder="Message body"></textarea>` +
          `<div class="actions"><button type="submit">Send Reply</button><button type="button" class="secondary" onclick="document.getElementById('message-reply-title').value='';document.getElementById('message-reply-body').value=''">Clear</button></div>` +
          `</form>`
        : "";
      const progressHtml = buildEstProgressHtml(item);
      const canDue = item.editable && ["T", "D", "R", "E", "H"].includes(item.type);
      const dueQuickHtml = canDue
        ? `<div class="due-quick-bar"><span style="font-size:.78rem;color:var(--muted)">Due:</span>` +
          `<button type="button" class="secondary" onclick="drawerPostpone('today')" title="Set due to today">Today</button>` +
          `<button type="button" class="secondary" onclick="drawerPostpone('+1d')" title="Postpone by one day">+1d</button>` +
          `<button type="button" class="secondary" onclick="drawerPostpone('+1w')" title="Postpone by one week">+1w</button>` +
          (item?.details?.due?.length ? `<button type="button" class="secondary" onclick="drawerPostpone('clear')" title="Remove due date">Clear</button>` : "") +
          `</div>`
        : "";
      body.innerHTML = fieldsHtml + progressHtml + dueQuickHtml + bodyHtml +
        `<div id="drawer-blockers"></div>` +
        `<div id="drawer-deps"><div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty dep-loading">Loading…</div></div>` +
        threadHtml + replyHtml +
        sourceHtml + rawHtml;
      rememberRecentItem(item);
      openManagedModal(drawer, ".drawer-close-btn");
      loadDependencyLinks(item);
      loadBlockerChain(item);
      if (item.type === "M" && itemId) loadDrawerMessageThread(item);
    }

    // ── "Why is this blocked?" chain in detail modal ───────────────
    async function loadBlockerChain(item) {
      const container = document.getElementById("drawer-blockers");
      if (!container) return;
      container.innerHTML = "";
      const idKey = appConfig?.ids?.key || "id";
      const itemId = item?.id || item?.details?.[idKey]?.[0];
      if (!itemId || ["[x]", "[-]"].includes(item.status)) return;
      try {
        const data = await api(`/api/blockers?id=${encodeURIComponent(itemId)}`);
        if (!data.blocked) return;
        let html = `<div class="drawer-section-title" style="color:var(--danger)">⚡ Why is this blocked?</div><div class="blocker-chain">`;
        for (const entry of data.chain || []) {
          const indent = Math.min(entry.level - 1, 4) * 0.85;
          const statusIcon = STATUS_ICON[entry.blocker_status] || "·";
          const statusCls = STATUS_CLASS[entry.blocker_status] || "status-note";
          const nav = escapeHtml(jsLiteral(entry.blocker_id || ""));
          const relation = entry.level === 1
            ? (entry.relation === "blocks" ? "blocked by" : "waiting on")
            : "which waits on";
          html += `<div class="blocker-chain-row" style="margin-left:${indent}rem">` +
            `<span>${entry.level === 1 ? "⚡" : "↳"}</span>` +
            `<span class="status-badge ${statusCls}" style="font-size:.7rem;padding:.1rem .35rem">${escapeHtml(statusIcon)}</span>` +
            `<span style="color:var(--muted);font-size:.78rem;white-space:nowrap">${escapeHtml(relation)}</span>` +
            `<a class="drawer-link" onclick="drawerNavigate(${nav})">${escapeHtml(entry.blocker_title || entry.blocker_id || "?")}</a>` +
            `</div>`;
        }
        html += `</div>`;
        container.innerHTML = html;
      } catch(_) {
        container.innerHTML = "";
      }
    }

    const DEP_RELATION_LABEL = {
      depends_on: "depends on", blocks: "blocks", parent: "child of",
      related: "related", ref: "ref",
    };
    const STATUS_ICON = {"[ ]": "○", "[x]": "✓", "[-]": "✕", "[/]": "◑", "[>]": "→", "[?]": "?", "[!]": "!"};

    function graphColor(type) {
      return {
        T: "#2563eb", E: "#16a34a", D: "#dc2626", R: "#f59e0b",
        H: "#7c3aed", N: "#64748b", S: "#0891b2", M: "#db2777", J: "#9333ea",
      }[type || ""] || "#475569";
    }

    function truncateLabel(value, maxLen = 16) {
      const text = String(value || "");
      return text.length > maxLen ? text.slice(0, maxLen - 1) + "…" : text;
