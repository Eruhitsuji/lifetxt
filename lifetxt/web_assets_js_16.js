      }
    }

    function cplMove(delta) {
      if (!_cplState || !_cplState.items.length) return;
      const count = _cplState.items.length;
      _cplState.index = (_cplState.index + delta + count) % count;
      const pop = cplPopup();
      pop.querySelectorAll(".cpl-row").forEach((row, i) => {
        row.classList.toggle("focus", i === _cplState.index);
        if (i === _cplState.index && row.scrollIntoView) {
          row.scrollIntoView({block: "nearest"});
        }
      });
    }

    function cplAccept(index) {
      if (!_cplState || !_cplState.items.length) return false;
      const chosen = _cplState.items[index === undefined ? _cplState.index : index];
      if (chosen === undefined) return false;

      const input = _cplState.input;
      const token = _cplState.token;
      const before = input.value.slice(0, token.start);
      const after = input.value.slice(token.end);
      input.value = before + chosen + after;
      const caret = (before + chosen).length;
      input.setSelectionRange(caret, caret);

      cplClose();
      // Let the field's own oninput logic (shorthand preview, validation)
      // see the completed text.
      input.dispatchEvent(new Event("input", {bubbles: true}));
      input.focus();
      return true;
    }

    /**
     * Wire an input for completion.
     * `resolver(value, caret)` returns {kind, prefix, start, end} or null.
     */
    function attachCompletion(input, resolver) {
      if (!input || input.dataset.cplBound === "1") return;
      input.dataset.cplBound = "1";
      input.setAttribute("autocomplete", "off");

      let timer = null;
      const refresh = () => {
        const caret = input.selectionStart === null ? input.value.length : input.selectionStart;
        const token = resolver(input.value, caret);
        if (!token) { cplClose(); return; }
        const seq = ++_cplSeq;
        cplFetch(token.kind, token.prefix).then(values => {
          // A slower earlier request must not overwrite a newer one.
          if (seq !== _cplSeq || document.activeElement !== input) return;
          cplRender(input, token, values);
        });
      };

      input.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(refresh, 90);
      });
      input.addEventListener("keydown", event => {
        if (!cplIsOpen()) {
          // Ctrl+Space asks for suggestions without typing more, matching
          // the habit shells train.
          if (event.key === " " && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            refresh();
          }
          return;
        }
        if (event.key === "ArrowDown") { event.preventDefault(); cplMove(1); }
        else if (event.key === "ArrowUp") { event.preventDefault(); cplMove(-1); }
        else if (event.key === "Tab" || event.key === "Enter") {
          // Enter would otherwise submit the bar before the word is finished.
          if (cplAccept()) event.preventDefault();
        } else if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          cplClose();
        }
      });
      input.addEventListener("blur", () => setTimeout(cplClose, 140));
    }

    document.addEventListener("mousedown", event => {
      const row = event.target.closest && event.target.closest(".cpl-row");
      if (!row) { if (cplIsOpen()) cplClose(); return; }
      // mousedown, not click: blur would close the popup first on a tap.
      event.preventDefault();
      cplAccept(Number(row.dataset.index));
    });

    // ── Token resolvers ───────────────────────────────────────────

    /** The whitespace-delimited word the caret sits in. */
    function cplWordAt(value, caret) {
      let start = caret;
      while (start > 0 && !/\s/.test(value[start - 1])) start--;
      let end = caret;
      while (end < value.length && !/\s/.test(value[end])) end++;
      return {start: start, end: end, text: value.slice(start, caret)};
    }

    //: Detail keys whose values are worth completing, and the kind to use.
    const CPL_KEY_KINDS = {
      project: "project", tag: "tag", context: "context", priority: "priority",
      state: "state", person: "person", owner: "person", assignee: "person",
      attendee: "person", sender: "person", recipient: "person", user: "person",
      team: "team", service: "service", channel: "channel",
      id: "id", parent: "id", depends_on: "id", blocks: "id", related: "id", ref: "id",
      due: "date", do: "date", on: "date", from: "date", to: "date", until: "date",
    };

    /** Shorthand sigils and `key:value` pairs, anywhere in the line. */
    function cplCaptureToken(value, caret) {
      const word = cplWordAt(value, caret);
      const typed = word.text;
      if (!typed) return null;

      const sigils = {"@": "project", "#": "tag", "!": "priority", "^": "date"};
      const kind = sigils[typed[0]];
      if (kind) {
        return {kind: kind, prefix: typed.slice(1), start: word.start + 1, end: word.end};
      }

      const colon = typed.indexOf(":");
      if (colon > 0) {
        const key = typed.slice(0, colon);
        const mapped = CPL_KEY_KINDS[key];
        if (mapped) {
          return {
            kind: mapped,
            prefix: typed.slice(colon + 1),
            start: word.start + colon + 1,
            end: word.end,
          };
        }
        return null;
      }

      // A bare first word is the title, not a key; only offer key names once
      // the user is past it.
      if (word.start === 0) return null;
      return {kind: "key", prefix: typed, start: word.start, end: word.end};
    }

    /** `busy` or `focus Deep work`: only the leading state word completes. */
    function cplPresenceToken(value, caret) {
      const word = cplWordAt(value, caret);
      if (word.start !== 0) return null;
      return {kind: "state", prefix: word.text, start: 0, end: word.end};
    }

    /** A field holding exactly one value of a known kind. */
    function cplWholeValue(kind) {
      return (value, caret) => ({
        kind: kind,
        prefix: value.slice(0, caret),
        start: 0,
        end: value.length,
      });
    }

    /** Attach every field that exists on the current page. */
    function setupCompletion() {
      const byId = (id, resolver) => attachCompletion(document.getElementById(id), resolver);
      byId("quick-line", cplCaptureToken);
      byId("presence-input", cplPresenceToken);
      byId("import-raw-input", cplCaptureToken);
      byId("focus-quick-title", cplCaptureToken);
      byId("edit-details", cplCaptureToken);
      byId("review-project", cplWholeValue("project"));
      byId("graph-root", cplWholeValue("id"));
      // The drawer editor is built on demand, so it is attached again after
      // each render rather than once at startup.
      byId("drawer-edit-details", cplCaptureToken);
    }

    // ── Tag datalist autocomplete ──────────────────────────────────
    function updateTagSuggestions(items) {
      const dl = document.getElementById("tag-suggestions");
      if (!dl) return;
      const tags = new Set();
      for (const item of (items || [])) {
        for (const t of (item?.details?.tag || [])) tags.add(String(t));
      }
      dl.innerHTML = [...tags].sort().map(t => `<option value="${escapeHtml(t)}">`).join("");
    }

    // ── Agenda overdue badge ──────────────────────────────────────
    function updateAgendaOverdueBadge(records) {
      const badge = document.getElementById("agenda-overdue-badge");
      if (!badge) return;
      const today = new Date(); today.setHours(0,0,0,0);
      const count = (records || []).filter(r => {
        if (!r.when) return false;
        const d = new Date(r.when); d.setHours(0,0,0,0);
        return d < today && !["[x]","[-]"].includes(r.status);
      }).length;
      badge.textContent = count > 0 ? String(count) : "";
      badge.style.display = count > 0 ? "" : "none";
    }

    // ── Stats summary: per-project mini-table ────────────────────
    async function loadProjectStats() {
      try {
        const data = await api("/api/stats/summary");
        const projects = (data.by_project || []).filter(p => p.total > 0);
        if (!projects.length) return;
        const el = document.getElementById("stats-summary");
        if (!el || el.style.display === "none") return;
        const maxTotal = Math.max(...projects.map(p => p.total), 1);
        let table = `<div style="margin-top:.5rem"><div class="drawer-section-title" style="font-size:.72rem;margin-bottom:.25rem">Top Projects</div>
          <table class="proj-stats-table"><thead><tr><th>Project</th><th>Done</th><th>Total</th><th style="min-width:4rem"></th></tr></thead><tbody>`;
        for (const p of projects.slice(0, 8)) {
          const barW = Math.round(p.total / maxTotal * 60);
          table += `<tr>
            <td>${escapeHtml(p.project)}</td>
            <td>${p.done}</td>
            <td>${p.total}</td>
            <td><span class="proj-stats-bar" style="width:${barW}px;opacity:${0.4 + 0.6*(p.done/Math.max(p.total,1))}"></span></td>
          </tr>`;
        }
        table += `</tbody></table></div>`;
        el.insertAdjacentHTML("beforeend", table);
      } catch(_) {}
    }

    // ── Notification retry button ─────────────────────────────────
    async function retryBrowserNotification(id) {
      const record = (window._lastNotifRecords || []).find(r => r.id === id || r.notification_id === id);
      if (!record) { showToast("Notification not found.", "error"); return; }
      try {
        if (Notification.permission !== "granted") {
          await enableBrowserNotifications();
        }
        seenNotifications.delete(record.notification_id || record.id || record.text);
        showBrowserNotification(record);
        showToast("Notification resent.", "success");
      } catch(e) {
        showToast("Retry failed: " + e.message, "error");
      }
    }

    // ── Dashboard view ──────────────────────────────────────────────
    let _dashChart = null;
    function _fmtDate(d) {
      const pad = n => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }
    function _dashItemRow(item) {
      const statusCls = STATUS_CLASS[item.status] || "status-note";
      const statusIcon = STATUS_ICON[item.status] || "·";
      const dueRel = buildDueRelLabel(item);
      return `<div class="dash-row">
        <span class="status-badge ${statusCls}" style="font-size:.7rem;padding:.08rem .4rem">${escapeHtml(statusIcon)}</span>
        <span class="type-badge type-${escapeHtml(item.type || "N")}" style="font-size:.68rem;padding:.08rem .4rem">${escapeHtml(item.type || "?")}</span>
        <a class="drawer-link dash-row-title" onclick="openItemByLine(${Number(item.line) || 0})">${escapeHtml(item.title)}</a>
        ${dueRel}
      </div>`;
    }
    async function loadDashboard() {
      const dateEl = document.getElementById("dash-date");
      if (dateEl) dateEl.textContent = new Date().toLocaleDateString(undefined, {weekday: "long", month: "long", day: "numeric"});
      const today = new Date(); today.setHours(0, 0, 0, 0);
      const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 13);
      let openItems = [], blockedItems = [], agendaRecords = [], chartData = null, summary = null;
      try {
        [openItems, blockedItems, agendaRecords, chartData, summary] = await Promise.all([
          api("/api/items?open_only=true").then(d => d.items || []).catch(() => []),
          api("/api/items?blocked=true&open_only=true").then(d => d.items || []).catch(() => []),
          api("/api/agenda?around=now&window=1d&open_only=true").then(d => d.records || []).catch(() => []),
          api(`/api/chart/tasks?from=${_fmtDate(weekAgo)}&to=${_fmtDate(today)}&group=daily`).catch(() => null),
          api("/api/stats/summary").catch(() => null),
        ]);
      } catch(_) {}
      // KPI tiles
      const overdue = openItems.filter(i => itemDueSoonClass(i) === "overdue");
      const dueToday = openItems.filter(i => {
        const due = i?.details?.due?.[0];
        if (!due) return false;
        const d = new Date(due); if (isNaN(d)) return false;
        d.setHours(0, 0, 0, 0);
        return +d === +today;
      });
      let doneRecent = 0;
      if (chartData?.datasets?.length) {
        for (const ds of chartData.datasets) {
          if (/done/i.test(ds.label || "")) doneRecent = (ds.data || []).reduce((a, b) => a + (Number(b) || 0), 0);
        }
        if (!doneRecent) doneRecent = (chartData.datasets[0].data || []).reduce((a, b) => a + (Number(b) || 0), 0);
      }
      const kpis = [
        {n: openItems.length, label: "Open", icon: "○", view: "", params: {open_only: "true"}},
        {n: dueToday.length, label: "Due today", icon: "📅", view: "focus", params: {}},
        {n: overdue.length, label: "Overdue", icon: "⚠️", cls: overdue.length ? "kpi-danger" : "", view: "focus", params: {}},
        {n: blockedItems.length, label: "Blocked", icon: "⚡", cls: blockedItems.length ? "kpi-warn" : "", view: "", params: {blocked: "true", open_only: "true"}},
        {n: doneRecent, label: "Done (14d)", icon: "✓", cls: "kpi-ok", view: "stats", params: {}},
      ];
      const kpiEl = document.getElementById("dash-kpis");
      if (kpiEl) {
        kpiEl.innerHTML = kpis.map((k, i) =>
          `<button type="button" class="kpi-tile ${k.cls || ""}" onclick="dashNavigate(${i})">` +
          `<span class="kpi-icon" aria-hidden="true">${k.icon}</span>` +
          `<span class="kpi-n">${k.n}</span><span class="kpi-label">${escapeHtml(k.label)}</span></button>`
        ).join("");
        window._dashKpis = kpis;
      }
      // Today agenda
      const todayEl = document.getElementById("dash-today");
      if (todayEl) {
        const limit = dashboardLimit("today", 7);
        todayEl.innerHTML = agendaRecords.length
          ? agendaRecords.slice(0, limit).map(r =>
              `<div class="dash-row"><span class="pill">${escapeHtml((r.when || "").replace("T", " "))}</span>` +
              (r.blocked ? `<span class="blocked-badge">⚡</span>` : "") +
              `<span class="dash-row-title">${escapeHtml(r.title)}</span></div>`
            ).join("") + (agendaRecords.length > limit ? `<a class="drawer-link" onclick="switchWorkspace('agenda')">View all ${agendaRecords.length} →</a>` : "")
          : `<div class="empty">Nothing scheduled around now.</div>`;
      }
      // Needs attention: overdue + blocked
      const overdueEl = document.getElementById("dash-overdue");
      if (overdueEl) {
        const attention = [...overdue.map(i => ({...i, _why: "overdue"})),
                           ...blockedItems.filter(b => !overdue.some(o => o.line === b.line && o.source === b.source)).map(i => ({...i, _why: "blocked"}))];
        const limit = dashboardLimit("needs_attention", 7);
        overdueEl.innerHTML = attention.length
          ? attention.slice(0, limit).map(_dashItemRow).join("") +
            (attention.length > limit ? `<a class="drawer-link" onclick="switchWorkspace('focus')">View all ${attention.length} →</a>` : "")
          : `<div class="empty">🎉 Nothing overdue or blocked.</div>`;
      }
      // Projects
      const projEl = document.getElementById("dash-projects");
      if (projEl) {
        const projects = (summary?.by_project || []).filter(p => p.total > 0).slice(0, dashboardLimit("projects", 7));
        const maxTotal = Math.max(...projects.map(p => p.total), 1);
        projEl.innerHTML = projects.length
          ? projects.map(p =>
              `<div class="dash-row"><span class="dash-row-title">${escapeHtml(p.project)}</span>` +
              `<span style="color:var(--muted);font-size:.78rem;font-variant-numeric:tabular-nums">${p.done}/${p.total}</span>` +
              `<span class="proj-stats-bar" style="width:${Math.round(p.total / maxTotal * 70)}px;opacity:${(0.4 + 0.6 * (p.done / Math.max(p.total, 1))).toFixed(2)}"></span></div>`
            ).join("")
          : `<div class="empty">No project data.</div>`;
      }
      // Chart
      const chartCard = document.querySelector('[data-dashboard-card="completions"]');
      if (chartData && !(chartCard && chartCard.classList.contains("card-hidden"))) {
        try {
          await ensureChartJs();
          const canvas = document.getElementById("dash-chart");
          if (canvas) {
            if (_dashChart) { _dashChart.destroy(); _dashChart = null; }
            _dashChart = new Chart(canvas.getContext("2d"), {
              type: "bar",
              data: {
                labels: (chartData.labels || []).map(l => String(l).slice(5)),
                datasets: (chartData.datasets || []).map((ds, i) => ({
                  label: ds.label, data: ds.data,
                  backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + "88",
                  borderColor: CHART_COLORS[i % CHART_COLORS.length],
                  borderWidth: 1.2,
                })),
              },
              options: {responsive: true, maintainAspectRatio: false, plugins: {legend: {display: false}}, scales: {y: {beginAtZero: true}}},
            });
          }
        } catch(_) {}
      }
    }
    function dashNavigate(index) {
      const kpi = (window._dashKpis || [])[index];
      if (!kpi) return;
      const params = query();
      for (const key of ["text", "q", "status", "blocked", "open", "open_only", "kind", "type"]) params.delete(key);
      for (const [key, value] of Object.entries(kpi.params || {})) params.set(key, value);
      history.replaceState(null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      switchWorkspace(kpi.view, "replace");
    }

    // ── Today view (Daily Command Center) ───────────────────────────
    //
    // Renders GET /api/command-center exactly as returned -- the same
    // command_center() aggregation CLI `today`, MCP get_command_center, and
    // the TUI /today view already use. No due/blocked/waiting/next-action/
    // inbox/project-attention calculation happens here.

    const TODAY_ROW_LIMIT = 8;

    function _todayRefRow(ref) {
      const statusCls = STATUS_CLASS[ref.status] || "status-note";
      const statusIcon = STATUS_ICON[ref.status] || "·";
      const project = ref.project ? `<span class="pill">@${escapeHtml(ref.project)}</span>` : "";
      const due = ref.due ? `<span class="pill">due:${escapeHtml(ref.due)}</span>` : "";
      return `<div class="dash-row">
        <span class="status-badge ${statusCls}" style="font-size:.7rem;padding:.08rem .4rem">${escapeHtml(statusIcon)}</span>
        <a class="drawer-link dash-row-title" onclick="openItemByLine(${Number(ref.line) || 0})">${escapeHtml(ref.title)}</a>
        ${project}${due}
