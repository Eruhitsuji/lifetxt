      URL.revokeObjectURL(a.href);
    }

    const CHART_COLORS = ["#256b5f","#e07b54","#4a7db5","#8e6bbf","#b5a14a","#5aa876","#c0524a"];

    function ensureChartJs() {
      if (chartJsLoaded) return Promise.resolve();
      return new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js";
        s.onload = () => { chartJsLoaded = true; resolve(); };
        s.onerror = reject;
        document.head.appendChild(s);
      });
    }

    // ── Status quick-filter buttons (multi-select) ────────────────
    function syncStatusFilterBtns(activeValues) {
      const params = query();
      const isBlocked = params.get("blocked") === "true";
      const rawStatus = params.get("status") || "";
      const selected = new Set(rawStatus ? rawStatus.split(",").map(s => s.trim()).filter(Boolean) : []);
      // Count items per status from current loaded items
      const counts = {};
      for (const item of (currentItems || [])) {
        counts[item.status] = (counts[item.status] || 0) + 1;
      }
      const total = (currentItems || []).length;
      document.querySelectorAll("#status-filter-bar .filter-btn").forEach(btn => {
        const sv = btn.dataset.status;
        const label = btn.dataset.label || btn.textContent.replace(/\s*\(\d+\)$/, "").trim();
        btn.dataset.label = label;
        if (sv === "") {
          btn.classList.toggle("active", !isBlocked && selected.size === 0);
          btn.textContent = total ? `${label} (${total})` : label;
        } else if (sv === "__blocked__") {
          btn.classList.toggle("active", isBlocked);
        } else {
          btn.classList.toggle("active", selected.has(sv));
          const n = counts[sv] || 0;
          btn.textContent = n ? `${label} (${n})` : label;
        }
      });
    }

    // ── Search result count ────────────────────────────────────────
    function updateSearchCount(count) {
      const el = document.getElementById("search-count");
      if (!el) return;
      el.textContent = count != null ? `(${count})` : "";
    }

    // ── View presets (config-defined, applied via ?preset= URL) ────
    function configViewPresets() {
      return appConfig?.views && typeof appConfig.views === "object" ? appConfig.views : {};
    }
    function getViewPreset(name) {
      return configViewPresets()[name];
    }

    // ── Clickable ID refs in item rows ────────────────────────────
    const ROW_REF_KEYS = new Set(["depends_on", "parent", "blocks", "related", "ref"]);
    function detailTextWithRefs(details) {
      const parts = [];
      for (const [key, values] of Object.entries(details || {})) {
        const vals = (values || []).map(v => {
          if (ROW_REF_KEYS.has(key)) return String(v);
          return String(v);
        });
        if (vals.length) parts.push(key + ":" + vals.join(","));
      }
      return parts.join("  ");
    }
    // ── Parent indicator in item rows ─────────────────────────────
    function buildParentIndicator(details) {
      const parents = details?.parent;
      if (!parents?.length) return "";
      return `<span class="parent-indicator" title="parent: ${escapeHtml(parents[0])}">↳ ${escapeHtml(parents[0])}</span>`;
    }

    // ── Drawer keyboard navigation ([ / ]) ────────────────────────
    function drawerPrev() {
      if (!drawerItem || !currentItems.length) return;
      const idx = currentItems.findIndex(i => i.line === drawerItem.line);
      if (idx > 0) openDrawer(currentItems[idx - 1]);
    }
    function drawerNext() {
      if (!drawerItem || !currentItems.length) return;
      const idx = currentItems.findIndex(i => i.line === drawerItem.line);
      if (idx >= 0 && idx < currentItems.length - 1) openDrawer(currentItems[idx + 1]);
    }

    // ── Relative time display ─────────────────────────────────────
    function relativeTime(isoString) {
      if (!isoString) return "";
      const d = new Date(isoString);
      if (isNaN(d)) return "";
      const diff = Date.now() - d.getTime();
      const absDiff = Math.abs(diff);
      const future = diff < 0;
      const mins = Math.floor(absDiff / 60000);
      const hours = Math.floor(absDiff / 3600000);
      const days = Math.floor(absDiff / 86400000);
      let label;
      if (mins < 1) label = "just now";
      else if (mins < 60) label = `${mins} min${mins > 1 ? "s" : ""} ${future ? "from now" : "ago"}`;
      else if (hours < 24) label = `${hours} hr${hours > 1 ? "s" : ""} ${future ? "from now" : "ago"}`;
      else label = `${days} day${days > 1 ? "s" : ""} ${future ? "from now" : "ago"}`;
      return label;
    }

    // ── Notification row state display ────────────────────────────
    function notifStateBadge(record) {
      const ack = record?.details?.ack?.[0];
      const snooze = record?.details?.snooze_until?.[0];
      if (ack) return `<span class="notif-state notif-state-ack" title="Acked at ${escapeHtml(ack)}">✓ Acked</span>`;
      if (snooze) return `<span class="notif-state notif-state-snoozed" title="Snoozed until ${escapeHtml(snooze)}">⏱ Snoozed</span>`;
      return `<span class="notif-state notif-state-pending">● Pending</span>`;
    }

    async function gitPull() {
      try {
        const data = await api("/api/git/pull", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
        const out = document.getElementById("git-output");
        out.textContent = (data.stdout || "") + (data.stderr || "");
        out.style.display = out.textContent ? "" : "none";
        if (data.ok) showToast("Pulled.", "success");
        else showToast("Pull failed — see output.", "error");
        const statusEl = document.getElementById("git-status-output");
        if (statusEl) {
          const s = await api("/api/git/status");
          statusEl.textContent = (s.stdout || "(clean)").trim() || "(clean)";
        }
        loadGitStatus();
      } catch(e) { showToast(e.message, "error"); }
    }

    // ── Heatmap: month labels + JS tooltip ───────────────────────
    (function setupHeatmapTooltip() {
      document.addEventListener("mouseover", function(e) {
        const cell = e.target.closest(".heatmap-cell");
        if (!cell || !cell.dataset.date) return;
        const tip = document.getElementById("hm-tooltip");
        if (!tip) return;
        tip.textContent = cell.dataset.date + (cell.classList.contains("done") ? " ✓" : "");
        tip.style.display = "";
        tip.style.left = (e.clientX + 12) + "px";
        tip.style.top = (e.clientY - 28) + "px";
      });
      document.addEventListener("mousemove", function(e) {
        const tip = document.getElementById("hm-tooltip");
        if (tip && tip.style.display !== "none") {
          tip.style.left = (e.clientX + 12) + "px";
          tip.style.top = (e.clientY - 28) + "px";
        }
      });
      document.addEventListener("mouseout", function(e) {
        if (!e.target.closest(".heatmap-cell")) return;
        const tip = document.getElementById("hm-tooltip");
        if (tip) tip.style.display = "none";
      });
    })();

    // ── Chart group selector (daily/weekly/monthly) ───────────────
    let currentChartType = "tasks";
    let currentChartGroup = "daily";
    const GROUP_SUPPORTED = new Set(["tasks", "habits", "mood"]);

    function setChartGroup(group, btn) {
      currentChartGroup = group;
      document.querySelectorAll(".chart-group-btn").forEach(b => b.classList.remove("active"));
      if (btn) btn.classList.add("active");
      loadChart(currentChartType);
    }

    // ── Status filter bar URL sync + `<`/`>` keyboard cycle ──────
    const STATUS_CYCLE = ["", "[ ]", "[/]", "[x]", "[-]", "__blocked__"];
    function syncStatusFilterBarsFromUrl() {
      syncStatusFilterBtns();
    }
    function cycleStatusFilter(direction) {
      const params = query();
      const rawStatus = params.get("status") || "";
      const isBlocked = params.get("blocked") === "true";
      // For cycling, treat multi-select as the first active value (or "All")
      const selected = rawStatus.split(",").map(s => s.trim()).filter(Boolean);
      const current = isBlocked ? "__blocked__" : (selected.length === 1 ? selected[0] : "");
      const idx = STATUS_CYCLE.indexOf(current);
      const next = STATUS_CYCLE[(idx + direction + STATUS_CYCLE.length) % STATUS_CYCLE.length];
      if (next === "__blocked__") {
        // Force blocked on (not toggle) for keyboard cycling
        const params = query();
        params.delete("status");
        params.set("blocked", "true");
        params.set("open_only", "true");
        document.getElementById("open-only").checked = true;
        history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
        loadItems();
        syncStatusFilterBtns();
      } else {
        setStatusFilter(next);
      }
    }

    // ── Clear every list filter (search, kind, status, blocked) ──
    function clearAllFilters() {
      document.getElementById("search").value = "";
      document.getElementById("kind").value = "";
      document.getElementById("open-only").checked = false;
      document.getElementById("limit").value = "";
      const groupSel = document.getElementById("group-by");
      if (groupSel) groupSel.value = "";
      const params = query();
      for (const key of [
        "text", "q", "kind", "type", "status", "blocked", "open", "open_only",
        "project", "tag", "tag_all", "exclude_tag", "user", "team", "person",
        "owner", "assignee", "attendee", "sender", "recipient", "after", "before",
        "limit", "group_by",
      ]) params.delete(key);
      history.replaceState(null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      loadItems();
      syncStatusFilterBtns();
    }

    // ── setStatusFilter: "All" button — clears everything ────────
    function setStatusFilter(statusValue) {
      const params = query();
      params.delete("blocked");
      params.delete("status");
      params.delete("open_only");
      document.getElementById("open-only").checked = false;
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadItems();
      syncStatusFilterBtns();
    }

    // ── toggleStatusFilter: multi-select individual statuses ──────
    function toggleStatusFilter(statusValue) {
      const params = query();
      params.delete("blocked");
      params.delete("open_only");
      document.getElementById("open-only").checked = false;
      const rawStatus = params.get("status") || "";
      const selected = new Set(rawStatus ? rawStatus.split(",").map(s => s.trim()).filter(Boolean) : []);
      if (selected.has(statusValue)) {
        selected.delete(statusValue);
      } else {
        selected.add(statusValue);
      }
      if (selected.size === 0) {
        params.delete("status");
      } else {
        params.set("status", [...selected].join(","));
      }
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadItems();
      syncStatusFilterBtns();
    }

    // ── toggleBlockedFilter: toggle blocked filter ────────────────
    function toggleBlockedFilter() {
      const params = query();
      const isBlocked = params.get("blocked") === "true";
      if (isBlocked) {
        // Turn off blocked filter → go to All
        params.delete("blocked");
        params.delete("status");
        params.delete("open_only");
        document.getElementById("open-only").checked = false;
      } else {
        params.delete("status");
        params.set("blocked", "true");
        params.set("open_only", "true");
        document.getElementById("open-only").checked = true;
      }
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadItems();
      syncStatusFilterBtns();
    }

    // ── Git log display ───────────────────────────────────────────
    let _gitLogOffset = 0;
    const GIT_LOG_PAGE = 10;
    async function loadGitLog(reset) {
      if (!appConfig?.git?.enable_api) return;
      if (reset !== false) _gitLogOffset = 0;
      try {
        const n = _gitLogOffset + GIT_LOG_PAGE;
        const data = await api(`/api/git/log?n=${n}&count=true`);
        const commits = data.commits || [];
        if (!commits.length) return;
        const shown = commits.slice(0, n);
        const hasMore = commits.length >= n;
        const totalLabel = data.total != null ? ` / ${data.total} total` : "";
        const titleEl = document.getElementById("git-modal-title");
        if (titleEl) titleEl.textContent = `Git${data.total != null ? ` (${data.total} commits)` : ""}`;
        const container = document.getElementById("git-log-container");
        const target = container || document.getElementById("git-output");
        if (!target) return;
        let html = `<div id="git-log-container" style="margin-top:.5rem">
          <div class="drawer-section-title" style="font-size:.72rem">Recent commits (${shown.length}${totalLabel})</div>`;
        for (const c of shown) {
          html += `<div class="git-log-entry"><span class="git-log-hash">${escapeHtml(c.hash)}</span><span class="git-log-msg">${escapeHtml(c.message)}</span></div>`;
        }
        if (hasMore) {
          html += `<div style="margin-top:.3rem"><a href="#" class="drawer-link" onclick="event.preventDefault();_gitLogOffset+=10;loadGitLog(false)">Show more…</a></div>`;
        }
        html += `</div>`;
        if (container) container.outerHTML = html;
        else target.insertAdjacentHTML("afterend", html);
      } catch(_) {}
    }


    // ── Ref-link count badge (multiple refs → dep_on(2)) ─────────
    function buildRefLinksHtml(details) {
      const counts = {};
      const firstIds = {};
      for (const [key, values] of Object.entries(details || {})) {
        if (!ROW_REF_KEYS.has(key)) continue;
        const valid = (values || []).filter(v => String(v).trim());
        if (!valid.length) continue;
        counts[key] = valid.length;
        firstIds[key] = String(valid[0]);
      }
      return Object.entries(counts).map(([key, count]) => {
        const label = count > 1 ? `${key.slice(0,3)}(${count})` : `${key.slice(0,3)}:${firstIds[key]}`;
        const nav = count === 1 ? escapeHtml(jsLiteral(firstIds[key])) : escapeHtml(jsLiteral(""));
        const onclick = count === 1
          ? `event.stopPropagation();drawerNavigate(${nav})`
          : `event.stopPropagation();(function(){const it=currentItems.find(i=>i.line===${Number(details?._line||0)});if(it)openDrawer(it);setTimeout(scrollDrawerDepsIntoView,200);})()`;
        return `<span class="ref-link" onclick="${onclick}" title="${escapeHtml(key)}: ${count} item(s)">${escapeHtml(label)}</span>`;
      }).join("");
    }
    function scrollDrawerDepsIntoView() {
      const deps = document.getElementById("drawer-deps");
      const body = document.getElementById("drawer-body");
      if (!deps || !body) return;
      try {
        body.scrollTop = Math.max(0, deps.offsetTop - body.offsetTop - 12);
      } catch(_) {
        deps.scrollIntoView({behavior: "smooth", block: "start"});
      }
    }

    // ── Notification: inline snooze with custom duration ─────────
    function snoozeInline(id) {
      const row = document.querySelector(`.notif-snooze-${CSS.escape(id)}`);
      if (!row) return;
      row.style.display = row.style.display === "none" ? "" : "none";
    }
    async function snoozeMessageCustom(id, inputId) {
      const input = document.getElementById(inputId);
      const duration = input ? input.value.trim() : "10m";
      if (!duration) { showToast("Enter a duration (e.g. 30m, 1h)", "error"); return; }
      await snoozeMessage(id, duration);
    }

    // ── Editor: Import raw line ───────────────────────────────────
    function toggleImportRaw(show) {
      const row = document.getElementById("import-raw-row");
      if (!row) return;
      const visible = show !== undefined ? show : row.style.display === "none";
      row.style.display = visible ? "" : "none";
      if (visible) document.getElementById("import-raw-input").focus();
    }
    async function importRawLine() {
      const input = document.getElementById("import-raw-input");
      const line = input ? input.value.trim() : "";
      if (!line) return;
      try {
        const parseData = await api("/api/items/parse", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line}),
        });
        renderRawParsePreview(parseData);
        if (!parseData.ok) {
          const errs = (parseData.diagnostics || []).filter(d => d.severity === "error");
          showToast("Invalid: " + (errs[0]?.message || "parse error"), "error");
          return;
        }
        const item = (parseData.items || [])[0];
        if (!item) { showToast("No item parsed from line.", "error"); return; }
        document.getElementById("edit-status").value = item.status;
        document.getElementById("edit-type").value = item.type;
        document.getElementById("edit-title").value = item.title;
        document.getElementById("edit-details").value = detailsToText(item.details || {});
        selectedItem = null;
        document.getElementById("editor-heading").textContent = "New Record";
        document.getElementById("save-button").textContent = "Create";
        document.getElementById("delete-button").disabled = true;
        updateTypeHints(item.type);
        toggleImportRaw(false);
        if (input) input.value = "";
        const preview = document.getElementById("import-raw-preview");
        if (preview) { preview.style.display = "none"; preview.textContent = ""; preview.className = "parse-preview"; }
        showToast("Form populated from raw line.", "success");
