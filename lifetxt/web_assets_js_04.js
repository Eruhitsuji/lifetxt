      if (appConfig?.notifications?.enabled === false || appConfig?.notifications?.web === false) return;
      const fallback = appConfig?.web?.notification_poll_seconds || appConfig?.notifications?.poll_seconds || 30;
      const seconds = Number(firstParam(query(), ["notify_refresh"], String(fallback)));
      if (Number.isFinite(seconds) && seconds > 0) {
        notificationTimer = setInterval(loadNotifications, seconds * 1000);
      }
    }
    function itemQueryParams() {
      const params = query();
      const result = new URLSearchParams();
      const passthrough = [
        "status", "project", "tag", "tag_all", "exclude_tag", "user", "team",
        "person", "owner", "assignee", "attendee",
        "sender", "recipient", "after", "before"
      ];
      for (const key of passthrough) {
        if (params.has(key)) result.set(key, params.get(key));
      }
      const kind = document.getElementById("kind").value || firstParam(params, ["kind", "type"], "");
      const text = document.getElementById("search").value || firstParam(params, ["text", "q"], "");
      const limit = document.getElementById("limit").value || firstParam(params, ["limit"], "");
      result.set("sort", document.getElementById("sort").value || firstParam(params, ["sort"], "line"));
      result.set("order", document.getElementById("order").value || firstParam(params, ["order"], "asc"));
      if (kind === "ordinary-notes") result.set("ordinary_notes", "true");
      else if (kind) result.set("kind", kind);
      if (text) result.set("text", text);
      if (limit) result.set("limit", limit);
      if (document.getElementById("open-only").checked || boolParam(params, ["open", "open_only"])) {
        result.set("open_only", "true");
      }
      if (params.get("blocked") === "true") result.set("blocked", "true");
      applyKioskFilterParams(result, params);
      return result;
    }
    function updateUrlFromControls() {
      const current = query();
      const next = new URLSearchParams();
      for (const key of [
        "mode", "view", "id", "line", "refresh", "around", "window", "from", "to",
        "workspace", "panel", "theme", "lang",
        "kiosk_cols", "kiosk_filter", "kiosk_title",
        "status", "project", "tag", "tag_all", "exclude_tag", "user", "team",
        "person", "owner", "assignee", "attendee",
        "sender", "recipient", "after", "before"
      ]) {
        if (current.has(key)) next.set(key, current.get(key));
      }
      const text = document.getElementById("search").value;
      const kind = document.getElementById("kind").value;
      const limit = document.getElementById("limit").value;
      const groupBy = document.getElementById("group-by")?.value || "";
      if (text) next.set("text", text);
      if (kind) next.set("kind", kind);
      if (document.getElementById("open-only").checked) next.set("open_only", "true");
      if (limit) next.set("limit", limit);
      if (groupBy) next.set("group_by", groupBy);
      next.set("sort", document.getElementById("sort").value);
      next.set("order", document.getElementById("order").value);
      if (query().has("agenda_blocked")) next.set("agenda_blocked", query().get("agenda_blocked"));
      history.replaceState(history.state, "", `${location.pathname}?${next.toString()}`);
    }
    let itemsLoadGeneration = 0;
    async function loadItems() {
      const generation = ++itemsLoadGeneration;
      updateUrlFromControls();
      const params = itemQueryParams();
      if (!currentItems.length) {
        const root = document.getElementById("items");
        if (root && !root.querySelector(".item")) {
          root.innerHTML = `<div class="skeleton-row"></div>`.repeat(4);
        }
      }
      let data;
      try {
        data = await api(`/api/items?${params}`);
      } catch (error) {
        renderActionableError(document.getElementById("items"), "Could not load items from the lifetxt server.", error, () => loadItems());
        return;
      }
      if (generation !== itemsLoadGeneration) return;
      currentItems = data.items;
      renderDiagnostics(data.diagnostics);
      renderItems(data.items);
      updateTagSuggestions(data.items);
      syncStatusFilterBtns();
      if (selectedItem) {
        const match = data.items.find(item => item.line === selectedItem.line && item.editable);
        if (match) selectItem(match);
      }
    }

    function initItemFilterControls() {
      const search = document.getElementById("search");
      const controls = ["kind", "sort", "order", "open-only"]
        .map(id => document.getElementById(id)).filter(Boolean);
      const limit = document.getElementById("limit");
      let timer = null;
      const schedule = () => {
        clearTimeout(timer);
        timer = setTimeout(() => loadItems(), 280);
      };
      search?.addEventListener("input", schedule);
      search?.addEventListener("keydown", event => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        clearTimeout(timer);
        loadItems();
      });
      controls.forEach(control => control.addEventListener("change", () => loadItems()));
      limit?.addEventListener("change", () => loadItems());
      limit?.addEventListener("keydown", event => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        loadItems();
      });
    }
    document.addEventListener("DOMContentLoaded", initItemFilterControls);
    async function populateSavedViewsAndAreas() {
      try {
        const [views, areas] = await Promise.all([api("/api/saved-views"), api("/api/areas")]);
        const viewSel = document.getElementById("saved-view-select");
        if (viewSel) {
          for (const view of (views.views || [])) {
            const opt = document.createElement("option");
            opt.value = view.name;
            opt.textContent = view.name;
            viewSel.appendChild(opt);
          }
        }
        const areaSel = document.getElementById("area-select");
        if (areaSel) {
          for (const area of (areas.areas || [])) {
            const opt = document.createElement("option");
            opt.value = area.name;
            opt.textContent = `${area.name} (${area.task_done}/${area.task_total})`;
            areaSel.appendChild(opt);
          }
        }
      } catch (_) {}
    }
    // /saved and /area apply a saved view or an area as the active row
    // filter, the same "apply as the row set" semantics the TUI's /saved
    // and /area commands use -- not a second query engine reimplemented
    // in the browser.
    async function applySavedView(name) {
      const areaSel = document.getElementById("area-select");
      if (areaSel) areaSel.value = "";
      if (!name) { loadItems(); return; }
      const data = await api(`/api/saved-views/${encodeURIComponent(name)}`);
      currentItems = data.items;
      renderDiagnostics(data.query_diagnostics || []);
      renderItems(data.items);
      updateTagSuggestions(data.items);
      syncStatusFilterBtns();
    }
    async function applyArea(name) {
      const viewSel = document.getElementById("saved-view-select");
      if (viewSel) viewSel.value = "";
      if (!name) { loadItems(); return; }
      const [area, full] = await Promise.all([
        api(`/api/areas/${encodeURIComponent(name)}`),
        api("/api/items?"),
      ]);
      const keys = new Set((area.open_items || []).map(ref => `${ref.source}\u0000${ref.line}`));
      const filtered = full.items.filter(item => keys.has(`${item.source}\u0000${item.line}`));
      currentItems = filtered;
      renderDiagnostics([]);
      renderItems(filtered);
      updateTagSuggestions(filtered);
      syncStatusFilterBtns();
    }
    // Diagnostics (#1073): show where each diagnostic comes from (the stable
    // contract already carries source/line/column/hint), let the user open the
    // affected record without touching the current filters, and collapse two or
    // more diagnostics behind a summary. Buttons carry only an index into
    // renderedDiagnostics, never diagnostic text, so nothing is interpolated
    // into executable markup.
    let renderedDiagnostics = [];
    function diagnosticLocationLabel(d) {
      if (!d || d.line == null) return "";
      const column = d.column != null ? `:${d.column}` : "";
      if (d.source) {
        // Basename for both POSIX "/" and Windows backslash (char 92) paths.
        const src = String(d.source);
        const cut = Math.max(src.lastIndexOf("/"), src.lastIndexOf(String.fromCharCode(92)));
        return `${src.slice(cut + 1)}:${d.line}${column}`;
      }
      return `${t("Line")} ${d.line}${column}`;
    }
    function diagnosticMatchesItem(d, item) {
      return !!item && d.line != null && Number(item.line) === Number(d.line)
        && String(item.source || "") === String(d.source || "");
    }
    function diagnosticRowHtml(d, index) {
      const location = diagnosticLocationLabel(d);
      let extra = "";
      if (location) {
        const fullLocation = d.source ? `${d.source}:${d.line}` : location;
        extra += `<span class="diagnostic-location" title="${escapeHtml(fullLocation)}">${escapeHtml(location)}</span>`;
        if (!(currentItems || []).some(item => diagnosticMatchesItem(d, item))) {
          extra += `<span class="diagnostic-hidden">${escapeHtml(t("Not shown by the current filter"))}</span>`;
        }
        extra += `<button type="button" class="secondary diagnostic-open" data-diagnostic-index="${index}">${escapeHtml(t("Open record"))}</button>`;
      }
      const hint = d.hint ? `<div class="diagnostic-hint">${escapeHtml(d.hint)}</div>` : "";
      return `<div class="diagnostic${d.severity === "warning" ? " warning" : ""}">` +
        `<div class="diagnostic-head"><span class="diagnostic-text">${escapeHtml(d.severity)} ${escapeHtml(d.code)}: ${escapeHtml(d.message)}</span>${extra}</div>` +
        `${hint}</div>`;
    }
    function renderDiagnostics(diagnostics) {
      const root = document.getElementById("diagnostics");
      if (!root) return;
      const previous = root.querySelector("details.diagnostics-summary");
      const wasOpen = previous ? previous.open : null;
      renderedDiagnostics = Array.isArray(diagnostics) ? diagnostics : [];
      if (!renderedDiagnostics.length) { root.innerHTML = ""; return; }
      const rows = renderedDiagnostics.map(diagnosticRowHtml).join("");
      if (renderedDiagnostics.length === 1) { root.innerHTML = rows; return; }
      const errors = renderedDiagnostics.filter(d => d.severity !== "warning").length;
      const warnings = renderedDiagnostics.length - errors;
      const counts =
        (errors ? `<span class="diagnostic-count error">${escapeHtml(t("Errors"))}: ${errors}</span>` : "") +
        (warnings ? `<span class="diagnostic-count warning">${escapeHtml(t("Warnings"))}: ${warnings}</span>` : "");
      // Keep the user's expand/collapse choice across reloads; errors start open.
      const open = wasOpen === null ? errors > 0 : wasOpen;
      root.innerHTML = `<details class="diagnostics-summary"${open ? " open" : ""}>` +
        `<summary><span class="diagnostics-summary-title">${escapeHtml(t("Diagnostics"))} (${renderedDiagnostics.length})</span>${counts}</summary>` +
        `<div class="diagnostics-list">${rows}</div></details>`;
    }
    async function openDiagnosticRecord(d) {
      if (!d || d.line == null) return;
      let item = (currentItems || []).find(candidate => diagnosticMatchesItem(d, candidate));
      if (!item) {
        // The record may be hidden by the current filter: look it up in the
        // unfiltered list instead of changing the user's filters.
        try {
          const data = await api("/api/items");
          item = (data.items || []).find(candidate => diagnosticMatchesItem(d, candidate));
        } catch (error) {
          showToast(`${t("Could not load the record")}: ${error.message || error}`, "error");
          return;
        }
      }
      if (!item) {
        showToast(`${t("No record found at")} ${diagnosticLocationLabel(d)}`, "error");
        return;
      }
      selectItem(item);
      openDrawer(item);
    }
    document.getElementById("diagnostics")?.addEventListener("click", event => {
      const button = event.target.closest(".diagnostic-open");
      if (!button) return;
      openDiagnosticRecord(renderedDiagnostics[Number(button.dataset.diagnosticIndex)]);
    });
    function safeMarkdownHtml(value, fallback = "") {
      return typeof value === "string" ? value : escapeHtml(fallback);
    }
    function firstMarkdownDetail(item, key) {
      const values = item?.markdown?.details?.[key];
      return Array.isArray(values) && values.length ? values[0] : "";
    }
    const STATUS_CLASS = {
      "[ ]": "status-open",
      "[/]": "status-active",
      "[x]": "status-done",
      "[-]": "status-cancel",
      "[>]": "status-defer",
      "[?]": "status-maybe",
      "[N]": "status-note",
    };
    const STATUS_LABEL = {
      "[ ]": "open", "[/]": "active", "[x]": "done",
      "[-]": "cancelled", "[>]": "deferred", "[?]": "maybe", "[N]": "note",
    };
    const ITEM_TYPE_NAMES = {
      T: "Task", H: "Habit", E: "Event", R: "Reminder",
      J: "Journal", S: "Status", M: "Message", N: "Note",
      G: "Goal", P: "Project", K: "Checklist", L: "Log",
    };
    function dueSoonDays() {
      return Number((appConfig?.web?.due_soon_days) ?? 3);
    }
    function itemDueSoonClass(item) {
      const dueVals = item?.details?.due;
      if (!dueVals || !dueVals.length) return "";
      const due = new Date(dueVals[0]);
      if (isNaN(due)) return "";
      const today = new Date(); today.setHours(0,0,0,0);
      const dueMid = new Date(due); dueMid.setHours(0,0,0,0);
      const diffDays = Math.floor((dueMid - today) / 86400000);
      if (diffDays < 0 && item.status !== "[x]" && item.status !== "[-]") return "overdue";
      if (diffDays >= 0 && diffDays <= dueSoonDays() && item.status !== "[x]" && item.status !== "[-]") return "due-soon";
      return "";
    }
    function renderSummary(items) {
      const el = document.getElementById("stats-summary");
      const total = items.length;
      const open = items.filter(i => !["[x]", "[-]"].includes(i.status)).length;
      const done = items.filter(i => i.status === "[x]").length;
      const overdue = items.filter(i => itemDueSoonClass(i) === "overdue").length;
      if (!total) { el.style.display = "none"; return; }
      el.style.display = "";
      el.innerHTML = `
        <div class="stats-count"><span class="n">${total}</span> total</div>
        <div class="stats-count"><span class="n">${open}</span> open</div>
        <div class="stats-count"><span class="n">${done}</span> done</div>
        <div class="stats-count overdue-count"><span class="n">${overdue}</span> overdue</div>
      `;
      // Build per-project mini-table from current items
      const projMap = {};
      for (const item of items) {
        if (item.type !== "T") continue;
        const projs = item?.details?.project?.length ? item.details.project : ["(none)"];
        for (const p of projs) {
          if (!projMap[p]) projMap[p] = {done: 0, total: 0};
          projMap[p].total++;
          if (item.status === "[x]") projMap[p].done++;
        }
      }
      const sorted = Object.entries(projMap).sort((a,b) => b[1].total - a[1].total).slice(0,6);
      if (!sorted.length) return;
      const maxT = Math.max(...sorted.map(([,v]) => v.total), 1);
      let table = `<div style="margin-top:.45rem;overflow-x:auto"><table class="proj-stats-table"><thead><tr><th>Project</th><th>✓</th><th>N</th><th></th></tr></thead><tbody>`;
      for (const [proj, v] of sorted) {
        const barW = Math.round(v.total / maxT * 56);
        const opacity = (0.4 + 0.6 * (v.done / Math.max(v.total, 1))).toFixed(2);
        table += `<tr><td>${escapeHtml(proj)}</td><td>${v.done}</td><td>${v.total}</td><td><span class="proj-stats-bar" style="width:${barW}px;opacity:${opacity}"></span></td></tr>`;
      }
      table += `</tbody></table></div>`;
      el.insertAdjacentHTML("beforeend", table);
    }
    function renderFilterChips() {
      const params = query();
      const el = document.getElementById("filter-chips");
      el.innerHTML = "";
      const filterKeys = [
        ["kind", "type"], ["status"], ["project"], ["tag"], ["user"], ["team"],
        ["person"], ["assignee"], ["owner"], ["after"], ["before"],
      ];
      const shown = new Set();
      for (const keys of filterKeys) {
        for (const k of keys) {
          if (shown.has(k)) break;
          const val = params.get(k);
          if (val) {
            shown.add(k);
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.innerHTML = `${escapeHtml(k)}:${escapeHtml(val)} <button title="Remove" onclick="removeFilter(${jsLiteral(k)})">×</button>`;
            el.appendChild(chip);
          }
        }
      }
      if (params.get("open_only") === "true") {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.innerHTML = `open only <button title="Remove" onclick="removeFilter('open_only')">×</button>`;
        el.appendChild(chip);
      }
    }
    function removeFilter(key) {
      const params = query();
      params.delete(key);
      if (key === "open_only") document.getElementById("open-only").checked = false;
      if (key === "kind" || key === "type") document.getElementById("kind").value = "";
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadItems();
    }
    function groupKeyFor(item, groupBy) {
      if (groupBy === "project") return item?.details?.project?.[0] || "(no project)";
      if (groupBy === "type") return ITEM_TYPE_NAMES[item.type] || item.type || "(none)";
      if (groupBy === "status") return STATUS_LABEL[item.status] || item.status || "(none)";
      if (groupBy === "source") return item.source || "(unknown source)";
      return "";
    }
    function buildDueRelLabel(item) {
      const due = item?.details?.due?.[0];
      if (!due || ["[x]", "[-]"].includes(item.status)) return "";
      const d = new Date(due);
      if (isNaN(d)) return "";
      const today = new Date(); today.setHours(0,0,0,0);
      const dm = new Date(d); dm.setHours(0,0,0,0);
      const diff = Math.round((dm - today) / 86400000);
      let text, cls = "";
      if (diff < 0) { text = `${-diff}d overdue`; cls = "overdue"; }
      else if (diff === 0) { text = "due today"; cls = "due-soon"; }
      else if (diff <= dueSoonDays()) { text = `in ${diff}d`; cls = "due-soon"; }
      else if (diff <= 60) { text = `in ${diff}d`; }
      else return "";
      return `<span class="due-rel ${cls}">${escapeHtml(text)}</span>`;
    }
    // ── progress: presentation (#651) ──────────────────────────────
    // Internal Format stays progress: only; this derives a bar+label from
    // the raw percentage/fraction value, mirroring the range checks
    // lifetxt.progress.parse_progress() already applies server-side.
    // Never treats an out-of-range or unparseable value as a bar (an
    // invalid progress: is still shown as plain text via detailText()'s
    // generic key:value dump; this only adds the visual bar/label).
    function progressInfo(raw) {
      if (!raw) return null;
      const text = String(raw);
      const pct = /^(-?\d+(?:\.\d+)?)%$/.exec(text);
      if (pct) {
        const value = parseFloat(pct[1]);
        if (value < 0 || value > 100) return null;
        return {percent: value, label: text};
      }
      const frac = /^(-?\d+)\/(-?\d+)$/.exec(text);
      if (frac) {
        const current = parseInt(frac[1], 10);
        const total = parseInt(frac[2], 10);
        if (total <= 0 || current < 0 || current > total) return null;
        const percent = (current / total) * 100;
        return {percent, label: `${text} (${Math.round(percent)}%)`};
      }
      return null;
    }
    function buildProgressBadge(details) {
      const raw = details?.progress?.[0];
      const info = progressInfo(raw);
      if (!info) return "";
      return `<span class="progress-badge" title="progress:${escapeHtml(String(raw))}">` +
        `<span class="progress-track"><span class="progress-fill" style="width:${info.percent}%"></span></span>` +
        `<span class="progress-label">${escapeHtml(info.label)}</span></span>`;
    }
    function agendaCountdownLabel(record) {
      // Days-remaining countdown for an agenda record, derived from its
      // occurrence date (works for due, do, and event records alike).
      if (["[x]", "[-]"].includes(record?.status)) return "";
      const raw = record?.occurrence_start || record?.when || "";
      const d = new Date(String(raw).replace(" ", "T"));
      if (isNaN(d)) return "";
      const today = new Date(); today.setHours(0, 0, 0, 0);
      const dm = new Date(d); dm.setHours(0, 0, 0, 0);
      const diff = Math.round((dm - today) / 86400000);
      let text, cls = "";
      if (diff < 0) { text = `${-diff}d ago`; cls = "overdue"; }
      else if (diff === 0) { text = "today"; cls = "due-soon"; }
      else if (diff <= dueSoonDays()) { text = `in ${diff}d`; cls = "due-soon"; }
      else if (diff <= 365) { text = `in ${diff}d`; }
      else return "";
      return `<span class="due-rel ${cls}">${escapeHtml(text)}</span>`;
    }
    function guidedEmptyState(icon, title, hint, actions = []) {
      // Shared guided empty state (icon + title + hint + optional action
      // buttons) so Agenda, Team, Status, Notifications, Stats, and Graph give
      // the same actionable guidance as the Items view.
      const btns = actions.map(([label, action]) =>
        `<button type="button" class="secondary" onclick="runViewGuideAction(${escapeHtml(jsLiteral(action))})">${escapeHtml(label)}</button>`
      ).join("");
      return `<div class="empty-state"><div class="empty-icon" aria-hidden="true">${icon}</div>` +
        `<div class="empty-title">${escapeHtml(title)}</div>` +
        (hint ? `<div class="empty-hint">${hint}</div>` : "") +
        (btns ? `<div class="empty-actions">${btns}</div>` : "") + `</div>`;
    }
    function enhanceItemsEmptyState(hasFilters) {
      if (isKioskMode() || isDisplayMode()) return;
      const state = document.querySelector("#items .empty-state");
      if (!state) return;
      state.querySelectorAll(":scope > button, :scope > .empty-actions").forEach(el => el.remove());
      const actions = document.createElement("div");
      actions.className = "empty-actions";
      if (hasFilters) {
        actions.innerHTML =
          `<button type="button" class="secondary" onclick="clearAllFilters()">Clear filters</button>` +
          `<button type="button" onclick="newItem()">New record</button>`;
      } else {
        actions.innerHTML =
          `<button type="button" onclick="newItem()">New record</button>` +
          `<button type="button" class="secondary" onclick="toggleQuickAdd(true)">Quick add</button>` +
          `<button type="button" class="secondary" onclick="openCmdk()">Command palette</button>`;
      }
      state.appendChild(actions);
    }
    function renderItems(items) {
      const root = document.getElementById("items");
      const hasFilters = !!(document.getElementById("search").value.trim() ||
        query().get("status") || query().get("blocked") ||
        document.getElementById("kind").value || document.getElementById("open-only").checked);
      root.innerHTML = items.length ? "" : `
        <div class="empty-state">
          <div class="empty-icon" aria-hidden="true">${hasFilters ? "🔍" : "🌱"}</div>
          <div class="empty-title">${hasFilters ? "No items match the current filters" : "No items yet"}</div>
          <div class="empty-hint">${hasFilters
            ? "Try clearing the search text or status filters above."
            : "Add your first record with the quick-add bar (press q) or the New workspace."}</div>
          ${isKioskMode() || isDisplayMode() ? "" : (hasFilters
            ? `<button type="button" class="secondary" onclick="clearAllFilters()">Clear filters</button>`
            : `<button type="button" onclick="toggleQuickAdd(true)">＋ Quick add</button>`)}
        </div>`;
      if (!items.length) enhanceItemsEmptyState(hasFilters);
      renderSummary(items);
      renderFilterChips();
      updateSearchCount(items.length);
      const kioskNow = isKioskMode();
      const nextFingerprints = new Map();
      _kbIndex = -1;
      const groupBy = kioskNow ? "" : (document.getElementById("group-by")?.value || "");
      const appendItem = (item) => {
        const node = buildItemNode(item, kioskNow, nextFingerprints);
        root.appendChild(node);
      };
      if (groupBy) {
        const groups = new Map();
        for (const item of items) {
          const g = groupKeyFor(item, groupBy);
          if (!groups.has(g)) groups.set(g, []);
          groups.get(g).push(item);
        }
        for (const [name, groupItems] of groups) {
          root.insertAdjacentHTML(
            "beforeend",
            `<div class="group-header">${escapeHtml(name)} <span class="n">(${groupItems.length})</span></div>`
          );
          for (const item of groupItems) appendItem(item);
        }
      } else {
        for (const item of items) appendItem(item);
      }
      if (kioskNow) _kioskLastFingerprints = nextFingerprints;
      else _kioskLastFingerprints = null;
      const queryText = document.getElementById("search").value.trim();
      if (queryText) {
        root.querySelectorAll(".title.markdown, .meta, .body-preview").forEach(el => {
          el.innerHTML = highlightText(el.innerHTML, queryText);
        });
      }
    }
    function buildItemNode(item, kioskNow, nextFingerprints) {
        const titleHtml = safeMarkdownHtml(item?.markdown?.title, item.title);
        const previewHtml = firstMarkdownDetail(item, "body") || firstMarkdownDetail(item, "note");
        const preview = previewHtml ? `<div class="markdown body-preview">${previewHtml}</div>` : "";
        const occurrenceBadge = item.occurrence_start
          ? `<span class="occurrence-badge" title="${escapeHtml(item.occurrence_start)}">occurrence</span>`
          : "";
        const generatedBadge = item.generated && !item.occurrence_start
          ? `<span class="occurrence-badge" title="generated/read-only source file">generated</span>`
          : "";
        const statusCls = STATUS_CLASS[item.status] || "status-note";
        const statusLabel = STATUS_LABEL[item.status] || item.status;
        const typeCls = "type-" + (item.type || "N");
        const dueCls = itemDueSoonClass(item);
        const refLinks = buildRefLinksHtml(item.details);
        const parentInd = buildParentIndicator(item.details);
        const dueRel = buildDueRelLabel(item);
        const progressBadge = buildProgressBadge(item.details);
        const stableKey = itemStableKey(item);
        const fingerprint = itemFingerprint(item);
        nextFingerprints.set(stableKey, fingerprint);
        const node = document.createElement("button");
