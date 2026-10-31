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
    async function copyRuntimeInfo() {
      const version = document.getElementById("runtime-build-version")?.textContent.trim() || "—";
      const commit = document.getElementById("runtime-build-commit")?.textContent.trim() || "—";
      const value = `lifetxt version: ${version}\nGit commit: ${commit === "—" ? "unavailable" : commit}`;
      try {
        if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
        await navigator.clipboard.writeText(value);
        showToast(t("Runtime information copied."), "success");
      } catch (_) {
        // Clipboard APIs require a secure context in many browsers. Provide
        // a selectable fallback for local HTTP-based testing environments.
        window.prompt(t("Copy runtime information"), value);
      }
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
    let _drawerNavigationToken = 0;
    document.addEventListener("keydown", event => {
      const overflow = document.getElementById("drawer-overflow");
      if (event.key === "Escape" && overflow?.open) {
        overflow.open = false;
        overflow.querySelector("summary")?.focus();
        event.stopPropagation();
      }
    }, true);
    document.addEventListener("click", event => {
      const overflow = document.getElementById("drawer-overflow");
      if (overflow?.open && !overflow.contains(event.target)) overflow.open = false;
    });

    // UI labels are translated explicitly: the drawer protects record values
    // from the global translation walker with data-no-i18n.
    function drawerText(en, ja) { return currentLanguage() === "ja" ? ja : en; }
    function drawerDateValue(value) {
      const raw = String(value);
      // Date-only and timezone-naive values retain their exact meaning.
      if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(raw)) return escapeHtml(raw);
      const date = new Date(raw);
      if (!Number.isFinite(date.getTime()) || new Date(raw.slice(0, 10) + "T00:00:00Z").toISOString().slice(0, 10) !== raw.slice(0, 10)) return escapeHtml(raw);
      try {
        const settings = _topClockSettings();
        const main = appConfig?.web?.top_clock?.main_timezone;
        if (!main) return escapeHtml(raw);
        const parts = _clockParts(date, {...settings, resolvedTimezone: main});
        const pad = n => String(n).padStart(2, "0");
        const label = `${parts.year}-${pad(parts.month)}-${pad(parts.day)} ${pad(parts.hour)}:${pad(parts.minute)}:${pad(parts.second)} ${parts.label}`;
        return `<time datetime="${escapeHtml(raw)}" title="${escapeHtml(raw)}">${escapeHtml(label)}</time>`;
      } catch (_) { return escapeHtml(raw); }
    }
    function drawerOverviewFields(item) {
      const labels = {
        __proto__: null,
        due: drawerText("Due", "期限"), do: drawerText("Scheduled", "実施予定"),
        done: drawerText("Completed at", "完了日時"), at: drawerText("At", "日時"),
        from: drawerText("From", "開始"), to: drawerText("To", "終了"),
        on: drawerText("On", "日付"), project: drawerText("Project", "プロジェクト"),
        priority: drawerText("Priority", "優先度"), progress: drawerText("Progress", "進捗"),
      };
      const dates = new Set(["due", "do", "done", "at", "from", "to", "on"]);
      const refs = new Set(["depends_on", "parent", "blocks", "related", "ref"]);
      const idKey = appConfig?.ids?.key || "id";
      const important = [], other = [], technical = [];
      for (const key of [...Object.keys(labels).filter(k => k in (item.details || {})), ...Object.keys(item.details || {}).filter(k => !(k in labels))]) {
        const values = item.details[key];
        if (key === "file" || key === "dir" || key === "body") continue;
        const val = (values || []).map(v => {
          if (refs.has(key)) return `<button type="button" class="drawer-link secondary" onclick="drawerNavigate(${escapeHtml(jsLiteral(String(v)))})">${escapeHtml(String(v))}</button>`;
          return dates.has(key) ? drawerDateValue(v) : escapeHtml(String(v));
        }).join(", ");
        const row = `<div class="drawer-field"><span class="key">${escapeHtml(labels[key] || key)}</span><span class="val">${val}</span></div>`;
        (key === idKey ? technical : labels[key] ? important : other).push(row);
      }
      // Even constructed API records without a raw line retain their ID.
      if (!item.details?.[idKey]?.length && item.id)
        technical.push(`<div class="drawer-field"><span class="key">${escapeHtml(idKey)}</span><span class="val">${escapeHtml(item.id)}</span></div>`);
      const group = rows => `<div class="drawer-fields">${rows.join("")}</div>`;
      return {important: important.length ? group(important) : "",
        other: other.length ? `<details class="drawer-disclosure"><summary>${drawerText("Other fields", "その他のフィールド")} (${other.length})</summary>${group(other)}</details>` : "",
        technical: group(technical)};
    }

    function _drawerRestoreButtons(item) {
      const isDone = ["[x]", "[-]"].includes(item.status);
      const idKey = (typeof appConfig !== "undefined" && appConfig?.ids?.key) || "id";
      const hasId = !!(item?.details?.[idKey]?.[0] || item?.id);
      const isRepeat = !!(item?.details?.repeat?.length && hasId);
      document.getElementById("drawer-head-btns").innerHTML =
        (!isDone ? `<button class="secondary" onclick="drawerMarkDone()" id="drawer-done-btn"${!item.editable ? " disabled" : ""}>Done</button>` : "") +
        (item.type === "T" && !isDone
          ? `<button class="secondary" onclick="drawerDoneDate()" id="drawer-done-date-btn"${!item.editable || isDone ? " disabled" : ""}>Done date…</button>`
          : "") +
        (isRepeat && !isDone
          ? `<button class="secondary" onclick="drawerComplete()" id="drawer-complete-btn" title="Complete this instance and materialize the next occurrence"${!item.editable || isDone ? " disabled" : ""}>✓ Complete + repeat</button>`
          : "") +
        `<button class="secondary" id="drawer-edit-btn" onclick="drawerEdit()"${!item.editable ? " disabled" : ""}>Edit</button>` +
        `<button class="secondary" id="drawer-create-related-btn" onclick="drawerCreateRelated()" title="Create a new record related to this one (#770)"${hasId ? "" : " disabled"}>+ Related</button>` +
        `<details class="drawer-overflow" id="drawer-overflow"><summary class="button-control secondary" aria-label="More record actions">More</summary>` +
        `<div class="drawer-overflow-menu" aria-label="More record actions">` +
        `<button class="secondary" id="drawer-copy-id" onclick="drawerCopyId()" title="Copy item ID to clipboard"${hasId ? "" : ' style="display:none"'}>Copy ID</button>` +
        `<button class="secondary" id="drawer-share-btn" onclick="drawerShareLink()" title="Copy deep link to this item">Share</button>` +
        `<button class="secondary" id="drawer-stable-link-btn" onclick="drawerCopyStableLink()" title="Copy host-independent stable link" aria-label="Copy stable link"${hasId ? "" : " disabled"}>Stable link</button>` +
        `<button class="secondary" id="drawer-markdown-btn" onclick="drawerCopyMarkdown()" title="Copy item as Markdown">Copy Markdown</button>` +
        `<div class="drawer-danger-actions"><button class="danger" onclick="drawerDelete()" id="drawer-delete-btn"${!item.editable ? " disabled" : ""}>Delete</button></div></div></details>`;
    }

    // Canonical record deep links (#838): the id: detail is the stable
    // identity, so the URL is kept in sync with whichever record the
    // drawer shows. `urlMode` is "push" for ordinary in-app navigation
    // (each opened record becomes its own Back/Forward stop), "replace"
    // for resolving the drawer state a page load or deep link already
    // implies (no extra history entry), and "none" when the URL is
    // already correct (restoring drawer state from a popstate event).
    function _drawerIdFor(item) {
      const idKey = (typeof appConfig !== "undefined" && appConfig?.ids?.key) || "id";
      return item?.id || item?.details?.[idKey]?.[0] || "";
    }
    function syncDrawerUrlForItem(item, urlMode, context = null) {
      if (urlMode === "none") return;
      const params = query();
      const itemId = _drawerIdFor(item);
      if (itemId) {
        if (params.get("id") === itemId && !params.get("line")) return;
        params.set("id", itemId);
        params.delete("line");
      } else if (item?.line != null) {
        if (params.get("line") === String(item.line) && !params.get("id")) return;
        params.delete("id");
        params.set("line", String(item.line));
      } else {
        return;
      }
      const url = `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`;
      if (urlMode === "replace") history.replaceState({drawerContext:context}, "", url);
      else history.pushState({drawerContext:context}, "", url);
    }

    function openDrawer(item, urlMode = "push", context = null) {
      ++_drawerNavigationToken;
      const alreadyOpen = document.getElementById("detail-drawer").classList.contains("open");
      const opener = _lastFocusedBeforeModal;
      disposeAttachmentUpload();
      disposeWorkSession();
      drawerWorkEditBinding = null;
      drawerEditing = false;
      drawerItem = item;
      syncDrawerUrlForItem(item, urlMode, context);
      const drawer = document.getElementById("detail-drawer");
      const body = document.getElementById("drawer-body");
      const title = document.getElementById("drawer-title");
      const isDone = ["[x]", "[-]"].includes(item.status);
      const statusCls = STATUS_CLASS[item.status] || "status-note";
      const statusLbl = STATUS_LABEL[item.status] || item.status;
      const typeCls = "type-" + (item.type || "N");
      const typeFullName = ITEM_TYPE_NAMES[item.type] || item.type;
      title.dataset.noI18n = "";
      title.innerHTML = `<span class="status-badge ${statusCls}">${escapeHtml(t(statusLbl))}</span>` +
        `<span class="type-badge ${typeCls}" style="margin-left:.35rem" title="${escapeHtml(t(typeFullName))}">${escapeHtml(item.type)}</span>` +
        `<span style="margin-left:.25rem;font-size:.78rem;color:var(--muted)">${escapeHtml(t(typeFullName))}</span>` +
        `<span style="margin-left:.4rem;font-weight:700">${escapeHtml(item.title)}</span>`;
      _drawerRestoreButtons(item);
      const fields = drawerOverviewFields(item);
      const bodyValues = item?.details?.body || [];
      const renderedBodies = item?.markdown?.details?.body || [];
      const bodyHtml = bodyValues.length
        ? `<div class="drawer-section-title">${drawerText("Body", "本文")}</div>` + bodyValues.map((v, i) =>
            renderedBodies[i] ? `<div class="markdown">${renderedBodies[i]}</div>` : `<div class="drawer-plain-body">${escapeHtml(String(v))}</div>`).join("") : "";
      const rawText = item?.text || item?.raw || "";
      const rawHtml = rawText
        ? `<div class="drawer-section-title">${drawerText("Raw line", "原文")}</div><pre class="drawer-raw-pre">${escapeHtml(rawText)}</pre>`
        : "";
      const sourceHtml = `<details class="drawer-disclosure drawer-technical"><summary>${drawerText("Source and technical details", "出典・技術情報")}</summary>` +
        fields.technical + `<div class="drawer-section-title">${drawerText("Source", "出典")}</div>` +
        `<div class="drawer-source">${escapeHtml(item.source || "")} · ${drawerText("Line", "行")} ${escapeHtml(String(item.line ?? ""))}</div>` +
        rawHtml + `</details>`;
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
      const canDue = item.editable && !isDone && ["T", "D", "R", "E", "H"].includes(item.type);
      const dueQuickHtml = canDue
        ? `<div class="due-quick-bar"><span style="font-size:.78rem;color:var(--muted)">${drawerText("Change due date", "期限を変更")}:</span>` +
          `<button type="button" class="secondary" onclick="drawerPostpone('today')" title="${escapeHtml(t("Set due to today"))}">${t("Today")}</button>` +
          `<button type="button" class="secondary" onclick="drawerPostpone('+1d')" title="${escapeHtml(t("Postpone by one day"))}">${drawerText("+1d", "+1日")}</button>` +
          `<button type="button" class="secondary" onclick="drawerPostpone('+1w')" title="${escapeHtml(t("Postpone by one week"))}">${drawerText("+1w", "+1週")}</button>` +
          (item?.details?.due?.length ? `<button type="button" class="secondary" onclick="drawerPostpone('clear')" title="${escapeHtml(t("Remove due date"))}">${t("Clear")}</button>` : "") +
          `</div>`
        : "";
      body.innerHTML =
        drawerContextHtml(item) +
        `<div class="drawer-tabs" role="tablist" aria-label="${drawerText("Item detail sections", "レコードの詳細セクション")}">` +
          `<button type="button" class="drawer-tab active" role="tab" aria-selected="true" aria-controls="drawer-tab-overview" onclick="switchDrawerTab('overview')">${drawerText("Overview", "概要")}</button>` +
          `<button type="button" class="drawer-tab help-target" role="tab" aria-selected="false" aria-controls="drawer-tab-timeline" data-help="See how this item changed over time." onclick="switchDrawerTab('timeline')">${drawerText("Timeline", "履歴")}</button>` +
          `<button type="button" class="drawer-tab help-target" role="tab" aria-selected="false" aria-controls="drawer-tab-relations" data-help="See items connected to this one." onclick="switchDrawerTab('relations')">${drawerText("Relations", "関連")}</button>` +
        `</div>` +
        `<section id="drawer-tab-overview" class="drawer-tab-panel" role="tabpanel">` +
          (!item.editable ? `<p class="drawer-readonly-note">${drawerText("Read-only record. Editing and completion are unavailable.", "読み取り専用のレコードです。編集・完了操作はできません。")}</p>` : "") +
          bodyHtml + fields.important + progressHtml + dueQuickHtml +
          `<div id="drawer-overview-tools"></div>` + fields.other + sourceHtml +
        `</section>` +
        `<section id="drawer-tab-timeline" class="drawer-tab-panel" role="tabpanel" hidden>` +
          `<div id="drawer-native-timeline"><div class="drawer-section-title">Native Timeline</div><div class="empty dep-loading">Loading…</div></div>` +
        `</section>` +
        `<section id="drawer-tab-relations" class="drawer-tab-panel" role="tabpanel" hidden>` +
          `<div id="drawer-blockers"></div>` +
          `<div id="drawer-deps" data-no-i18n><div class="empty dep-loading">${drawerText("Loading links…", "関係を読み込み中…")}</div></div>` +
          threadHtml + replyHtml +
        `</section>`;
      _ntCurrentItemId = itemId || null;
      _ntFilters = {since:"", until:"", event:"", limit:""};
      _ntAdvancedOpen = false;
      ++_ntRequestToken;
      document.getElementById("drawer-native-timeline").innerHTML = renderNativeTimelinePanel(null);
      if (itemId) reloadNativeTimelinePanel();
      rememberRecentItem(item);
      openManagedModal(drawer, ".drawer-close-btn");
      if (alreadyOpen) _lastFocusedBeforeModal = opener;
      mountAttachmentUpload(item, document.getElementById("drawer-overview-tools"));
      mountWorkSession(item, document.getElementById("drawer-overview-tools"));
      loadDependencyLinks(item);
      loadBlockerChain(item);
      if (item.type === "M" && itemId) loadDrawerMessageThread(item);
    }

    // ── "Why is this blocked?" chain in detail modal ───────────────
    async function loadBlockerChain(item) {
      const container = document.getElementById("drawer-blockers");
      if (!container) return;
      container.innerHTML = "";
      container.dataset.noI18n = "";
      const idKey = appConfig?.ids?.key || "id";
      const itemId = item?.id || item?.details?.[idKey]?.[0];
      if (!itemId || ["[x]", "[-]"].includes(item.status)) return;
      try {
        const data = await api(`/api/blockers?id=${encodeURIComponent(itemId)}`);
        if (document.getElementById("drawer-blockers") !== container || drawerItem !== item || drawerEditing || !data.blocked) return;
        let html = `<div class="drawer-section-title" style="color:var(--danger)">⚡ ${drawerText("Why is this blocked?", "ブロックされている理由")}</div><div class="blocker-chain">`;
        for (const entry of data.chain || []) {
          const indent = Math.min(entry.level - 1, 4) * 0.85;
          const statusIcon = STATUS_ICON[entry.blocker_status] || "·";
          const statusCls = STATUS_CLASS[entry.blocker_status] || "status-note";
          const nav = escapeHtml(jsLiteral(entry.blocker_id || ""));
          const relation = entry.level === 1
            ? (entry.relation === "blocks" ? drawerText("blocked by", "妨げている項目") : drawerText("waiting on", "待っている項目"))
            : drawerText("which waits on", "さらに待っている項目");
          html += `<div class="blocker-chain-row" style="margin-left:${indent}rem">` +
            `<span>${entry.level === 1 ? "⚡" : "↳"}</span>` +
            `<span class="status-badge ${statusCls}" style="font-size:.7rem;padding:.1rem .35rem">${escapeHtml(statusIcon)}</span>` +
            `<span style="color:var(--muted);font-size:.78rem;white-space:nowrap">${escapeHtml(relation)}</span>` +
            `<button type="button" class="drawer-link secondary" onclick="drawerNavigate(${nav})">${escapeHtml(entry.blocker_title || entry.blocker_id || "?")}</button>` +
            `</div>`;
        }
        html += `</div>`;
        container.innerHTML = html;
      } catch(_) {
        if (document.getElementById("drawer-blockers") !== container || drawerItem !== item) return;
        container.textContent = drawerText("Blocker details unavailable.", "ブロックの詳細を取得できません。");
      }
    }

    const DEP_RELATION_LABEL = {
      depends_on: "depends on", blocks: "blocks", parent: "child of",
      related: "related", ref: "ref", follows: "follows",
      realizes: "realizes", replaced_by: "replaced by",
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
