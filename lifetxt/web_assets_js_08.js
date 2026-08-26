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
      if (kind) result.set("kind", kind);
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
        "mode", "view", "refresh", "around", "window", "from", "to",
        "workspace", "panel", "theme",
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
      history.replaceState(null, "", `${location.pathname}?${next.toString()}`);
    }
    async function loadItems() {
      updateUrlFromControls();
      const params = itemQueryParams();
      if (!currentItems.length) {
        const root = document.getElementById("items");
        if (root && !root.querySelector(".item")) {
          root.innerHTML = `<div class="skeleton-row"></div>`.repeat(4);
        }
      }
      const data = await api(`/api/items?${params}`);
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
    function renderDiagnostics(diagnostics) {
      document.getElementById("diagnostics").innerHTML = diagnostics
        .map(d => `<div class="diagnostic${d.severity === "warning" ? " warning" : ""}">${escapeHtml(d.severity)} ${escapeHtml(d.code)}: ${escapeHtml(d.message)}</div>`)
        .join("");
    }
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