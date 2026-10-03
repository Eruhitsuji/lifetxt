      if (!("Notification" in window)) { if (bar) { bar.textContent = "Browser notifications not supported."; bar.style.display = ""; } return; }
      const perm = Notification.permission;
      const classes = {granted: "notif-perm-granted", denied: "notif-perm-denied", default: "notif-perm-default"};
      const labels = {
        granted: "Notifications: granted",
        denied: "Notifications: blocked. Re-enable them from the browser site settings for this page.",
        default: "Notifications: not yet requested",
      };
      if (bar) {
        bar.className = "notif-permission " + (classes[perm] || "");
        if (perm === "denied") {
          bar.innerHTML = `<span>${escapeHtml(labels.denied)}</span><button class="secondary" type="button" onclick="showNotificationSettingsHelp()">How</button>`;
        } else {
          bar.textContent = labels[perm] || perm;
        }
        bar.style.display = "";
      }
    }
    function showNotificationSettingsHelp() {
      showToast("Use the browser lock/site icon, open Site settings, and allow Notifications for this URL.", "info", 8000);
    }

    // ── Git status badge + modal ─────────────────────────────────
    let gitPollTimer = null;
    function startGitPolling() {
      if (!appConfig?.git?.enable_api || appConfig?.git?.ui_poll === false) return;
      const seconds = appConfig?.git?.ui_poll_seconds || 60;
      loadGitStatus();
      gitPollTimer = setInterval(loadGitStatus, seconds * 1000);
    }
    async function loadGitStatus() {
      const badge = document.getElementById("git-status-badge");
      if (!badge) return;
      try {
        const data = await api("/api/git/status");
        badge.style.display = "";
        const out = (data.stdout || "").trim();
        if (!out) { badge.className = "git-badge git-clean"; badge.textContent = "git: clean"; }
        else { badge.className = "git-badge git-modified"; badge.textContent = "git: modified"; }
      } catch(e) {
        badge.style.display = "";
        badge.className = "git-badge git-error";
        badge.textContent = "git: error";
      }
    }
    async function openGitModal() {
      document.getElementById("git-output").style.display = "none";
      document.getElementById("git-output").textContent = "";
      openManagedModal(document.getElementById("git-modal"), "#git-commit-msg");
      const statusEl = document.getElementById("git-status-output");
      if (statusEl) {
        statusEl.textContent = "Loading…";
        try {
          const data = await api("/api/git/status");
          statusEl.textContent = (data.stdout || "(clean)").trim() || "(clean)";
        } catch(e) { statusEl.textContent = "Could not load status: " + e.message; }
      }
    }
    function closeGitModal() { closeManagedModal(document.getElementById("git-modal")); }
    async function gitCommit() {
      const msg = document.getElementById("git-commit-msg").value.trim();
      if (!msg) { showToast("Enter a commit message.", "error"); return; }
      try {
        const data = await api("/api/git/commit", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({message: msg}),
        });
        const out = document.getElementById("git-output");
        out.textContent = (data.stdout || "") + (data.stderr || "");
        out.style.display = out.textContent ? "" : "none";
        if (data.ok) { showToast("Committed.", "success"); await loadGitLog(); }
        else showToast("Commit failed — see output.", "error");
        loadGitStatus();
      } catch(e) { showToast(e.message, "error"); }
    }
    async function gitPush() {
      try {
        const data = await api("/api/git/push", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
        const out = document.getElementById("git-output");
        out.textContent = (data.stdout || "") + (data.stderr || "");
        out.style.display = out.textContent ? "" : "none";
        if (data.ok) showToast("Pushed.", "success");
        else showToast("Push failed — see output.", "error");
        loadGitStatus();
      } catch(e) { showToast(e.message, "error"); }
    }

    // ── Statistics / Chart.js panel ────────────────────────────────
    let chartJsLoaded = false;
    let mainChart = null;
    let statsLoaded = false;

    // ── Kiosk mode (bulletin board / 掲示板モード) ────────────────
    let _kioskScrollTimer = null;
    let _kioskAutoScroll = null;

    function _kioskApply() {
      const active = isKioskMode();
      const clock = document.getElementById("kiosk-clock");
      const exitBtn = document.getElementById("kiosk-exit-btn");
      const list = document.getElementById("items");
      const h1 = document.querySelector("header h1");
      if (!clock || !exitBtn) return;
      clock.style.display = active ? "flex" : "none";
      exitBtn.style.display = active ? "inline-flex" : "none";
      if (active) {
        if (h1 && _kioskDefaultTitle === null) _kioskDefaultTitle = h1.textContent;
        const title = firstParam(query(), ["kiosk_title"], "");
        if (h1 && title) h1.textContent = title;
        const cols = parseInt(firstParam(query(), ["kiosk_cols"], ""), 10);
        if (list && Number.isFinite(cols) && cols > 0) {
          list.style.gridTemplateColumns = `repeat(${Math.min(cols, 8)}, minmax(0, 1fr))`;
        } else if (list) {
          list.style.gridTemplateColumns = "";
        }
        _kioskStartClock();
        _kioskStartScroll();
        _kioskAddProgressBar();
      } else {
        if (h1 && _kioskDefaultTitle !== null) h1.textContent = _kioskDefaultTitle;
        if (list) list.style.gridTemplateColumns = "";
        _kioskStopClock();
        _kioskStopScroll();
        _kioskRemoveProgressBar();
      }
    }

    // One browser-local time source and timer serve both Top and Kiosk.
    const TOP_CLOCK_FORMATS = ["HH:mm", "HH:mm:ss", "h:mm a", "h:mm:ss a"];
    let _webClockTimer = null;

    function _topClockSettings() {
      const raw = appConfig?.web?.top_clock;
      const settings = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
      return {
        enabled: typeof settings.enabled === "boolean" ? settings.enabled : true,
        format: TOP_CLOCK_FORMATS.includes(settings.format) ? settings.format : "HH:mm",
        showDate: settings.show_date === true,
      };
    }

    function _formatWebClock(now, settings = null) {
      if (!settings) {
        const date = now.toLocaleDateString(undefined, { weekday:"short", month:"short", day:"numeric" });
        const time = now.toLocaleTimeString(undefined, { hour:"2-digit", minute:"2-digit" });
        return date + "  " + time;
      }
      const pad = value => String(value).padStart(2, "0");
      const format = TOP_CLOCK_FORMATS.includes(settings.format) ? settings.format : "HH:mm";
      const hour = now.getHours();
      const twelveHour = format.startsWith("h:");
      let text = (twelveHour ? String(hour % 12 || 12) : pad(hour)) + ":" + pad(now.getMinutes());
      if (format.includes("ss")) text += ":" + pad(now.getSeconds());
      if (twelveHour) text += hour < 12 ? " AM" : " PM";
      if (settings.showDate) text = now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate()) + " " + text;
      return text;
    }

    function _updateWebClocks() {
      const now = new Date();
      const settings = _topClockSettings();
      const top = document.getElementById("top-clock");
      const kiosk = document.getElementById("kiosk-clock");
      if (top && !top.hidden) {
        top.textContent = _formatWebClock(now, settings);
        top.dateTime = now.toISOString();
      }
      if (kiosk && isKioskMode()) {
        kiosk.textContent = _formatWebClock(now);
        kiosk.dateTime = now.toISOString();
      }
    }

    function _syncWebClocks() {
      if (_webClockTimer !== null) clearInterval(_webClockTimer);
      _webClockTimer = null;
      const settings = _topClockSettings();
      const top = document.getElementById("top-clock");
      const kioskActive = isKioskMode();
      const topActive = settings.enabled && !kioskActive && !isDisplayMode() && !document.body.classList.contains("capture-mode") && location.pathname.replace(/\/+$/, "") !== "/capture";
      if (top) {
        top.hidden = !topActive;
        top.style.minWidth = (settings.showDate ? 11 : 0) + (settings.format.includes("ss") ? 8 : 5) + (settings.format.startsWith("h:") ? 3 : 0) + "ch";
      }
      _updateWebClocks();
      if ((top && topActive) || kioskActive) _webClockTimer = setInterval(_updateWebClocks, 1000);
    }

    function _kioskStartClock() { _syncWebClocks(); }

    function _kioskStopClock() {
      const el = document.getElementById("kiosk-clock");
      if (el) { el.textContent = ""; el.removeAttribute("datetime"); }
      _syncWebClocks();
    }

    function _kioskStartScroll() {
      _kioskStopScroll();
      const list = document.getElementById("items");
      if (!list) return;
      const intervalValue = document.documentElement.style.getPropertyValue("--kiosk-interval") || "60";
      const intervalMs = (parseFloat(intervalValue) || 60) * 1000;
      const scrollStep = () => {
        if (!isKioskMode()) { _kioskStopScroll(); return; }
        const { scrollTop, scrollHeight, clientHeight } = list;
        if (scrollTop + clientHeight >= scrollHeight - 2) {
          list.scrollTo({ top: 0, behavior: "smooth" });
        } else {
          list.scrollBy({ top: Math.ceil(clientHeight * 0.8), behavior: "smooth" });
        }
      };
      _kioskScrollTimer = setInterval(scrollStep, intervalMs);
    }

    function _kioskStopScroll() {
      if (_kioskScrollTimer) { clearInterval(_kioskScrollTimer); _kioskScrollTimer = null; }
    }

    function _kioskAddProgressBar() {
      if (document.querySelector(".kiosk-progress-bar")) return;
      const bar = document.createElement("div");
      bar.className = "kiosk-progress-bar";
      document.body.appendChild(bar);
      const secs = firstParam(query(), ["refresh"], "60");
      document.documentElement.style.setProperty("--kiosk-interval", secs + "s");
    }

    function _kioskRemoveProgressBar() {
      const bar = document.querySelector(".kiosk-progress-bar");
      if (bar) bar.remove();
    }

    function toggleKioskMode() {
      const params = query();
      const active = isKioskMode();
      if (active) {
        params.delete("mode");
        params.delete("view");
      } else {
        params.set("mode", "kiosk");
      }
      history.pushState(null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      applyUrlToControls();
      refreshAll();
    }

    function toggleStats() {
      switchWorkspace("stats");
    }

    async function loadStatsBreakdown() {
      const el = document.getElementById("stats-breakdown");
      if (!el) return;
      try {
        const fromVal = (document.getElementById("breakdown-from") || {}).value || "";
        const toVal = (document.getElementById("breakdown-to") || {}).value || "";
        const qs = (fromVal ? `from=${encodeURIComponent(fromVal)}&` : "") + (toVal ? `to=${encodeURIComponent(toVal)}` : "");
        const data = await api("/api/stats/summary" + (qs ? "?" + qs : ""));
        const STATUS_EMOJI = {"[ ]": "○", "[/]": "◑", "[x]": "✓", "[-]": "✕", "[>]": "→"};
        const typeRows = Object.entries(data.by_type || {})
          .sort((a,b) => b[1]-a[1])
          .map(([k,v]) => `<div style="display:flex;justify-content:space-between"><span>${escapeHtml(ITEM_TYPE_NAMES[k]||k)}</span><span style="color:var(--muted)">${v}</span></div>`)
          .join("");
        const statusRows = Object.entries(data.by_status || {})
          .sort((a,b) => b[1]-a[1])
          .map(([k,v]) => `<div style="display:flex;justify-content:space-between"><span>${escapeHtml(STATUS_EMOJI[k]||"")} ${escapeHtml(STATUS_LABEL[k]||k)}</span><span style="color:var(--muted)">${v}</span></div>`)
          .join("");
        el.innerHTML = `
          <div>
            <div class="drawer-section-title" style="font-size:.72rem;margin-bottom:.3rem">By Type</div>
            <div style="font-size:.82rem;display:grid;gap:.2rem">${typeRows || "<em>none</em>"}</div>
          </div>
          <div>
            <div class="drawer-section-title" style="font-size:.72rem;margin-bottom:.3rem">By Status</div>
            <div style="font-size:.82rem;display:grid;gap:.2rem">${statusRows || "<em>none</em>"}</div>
          </div>`;
        el.style.display = "grid";
      } catch(e) {
        if (el) el.style.display = "none";
      }
    }

    function toggleNotifPanel() {
      switchWorkspace("notifications");
      updateNotifBtnLabel();
      if (("Notification" in window) && Notification.permission === "default") {
        enableBrowserNotifications();
      }
    }

    function updateNotifBtnLabel() {
      const btn = document.getElementById("notif-btn");
      if (!btn) return;
      const perm = ("Notification" in window) ? Notification.permission : "unsupported";
      const indicator = perm === "granted" ? " ●" : perm === "denied" ? " ✕" : " ○";
      // "Notifications ✕" is not itself a dictionary key and the suffix-peel
      // rule only handles a trailing "(...)", so a compound assignment would
      // stay English forever even with a "Notifications" dictionary entry;
      // translate the label at construction time instead.
      btn.textContent = t("Notifications") + indicator;
    }

    async function triggerRefresh() {
      const btn = document.getElementById("refresh-btn");
      if (btn) { btn.classList.add("btn-active"); btn.textContent = "…"; btn.disabled = true; }
      try { await refreshAll(); } finally {
        if (btn) { btn.classList.remove("btn-active"); btn.textContent = "Refresh"; btn.disabled = false; }
      }
    }

    async function loadChart(type) {
      const container = document.getElementById("chart-container");
      if (type === "habits-heatmap") {
        renderHeatmap(container);
        return;
      }
      await ensureChartJs();
      container.innerHTML = `<div class="chart-panel"><canvas id="main-chart"></canvas></div>`;
      const canvas = document.getElementById("main-chart");
      if (mainChart) { mainChart.destroy(); mainChart = null; }
      try {
        const groupParam = GROUP_SUPPORTED.has(type) ? `?group=${encodeURIComponent(currentChartGroup)}` : "";
        const data = await api("/api/chart/" + encodeURIComponent(type) + groupParam);
        const ctx = canvas.getContext("2d");
        const isBar = ["tasks", "habits", "elapsed"].includes(type);
        mainChart = new Chart(ctx, {
          type: isBar ? "bar" : "line",
          data: {
            labels: data.labels || [],
            datasets: (data.datasets || []).map((ds, i) => ({
              label: ds.label,
              data: ds.data,
              backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + "88",
              borderColor: CHART_COLORS[i % CHART_COLORS.length],
              borderWidth: 1.5,
              fill: !isBar,
              spanGaps: true,
              pointRadius: 2,
            })),
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {legend: {position: "top"}},
            scales: {
              y: {
                beginAtZero: true,
                title: {
                  display: GROUP_SUPPORTED.has(type) && currentChartGroup !== "daily",
                  text: currentChartGroup === "weekly" ? "completions / week"
                      : currentChartGroup === "monthly" ? "completions / month" : "",
                },
              },
            },
          },
        });
      } catch(err) {
        container.innerHTML = `<div class="diagnostic">Chart error: ${escapeHtml(err.message)}</div>`;
      }
    }

    async function renderHeatmap(container) {
      container.innerHTML = `<div class="empty">Loading heatmap…</div>`;
      try {
        const data = await api("/api/chart/habits-heatmap");
        const today = new Date().toISOString().slice(0, 10);
        const rangeStart = new Date(data.range?.from || new Date().getFullYear() + "-01-01");
        if (!data.habits?.length) { container.innerHTML = `<div class="empty">No habit data.</div>`; return; }

        // Build month labels array (one per week column)
        const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
        function buildMonthLabels(start, end) {
          const labels = [];
          let col = 0;
          const d = new Date(start);
          const startPad = d.getDay();
          for (let pad = 0; pad < startPad; pad++) { labels.push(""); col++; }
          let lastMonth = -1;
          while (d <= end) {
            const mo = d.getMonth();
            if (d.getDay() === 0) {
              labels.push(mo !== lastMonth ? MONTHS[mo] : "");
              lastMonth = mo;
            }
            d.setDate(d.getDate() + 1);
          }
          return labels;
        }

        const endDate = new Date();
        const monthLabels = buildMonthLabels(new Date(rangeStart), endDate);

        let html = `<div class="heatmap-section" style="padding:.5rem 1rem">`;
        for (const habit of data.habits) {
          html += `<div class="heatmap-habit">
            <div class="heatmap-title">${escapeHtml(habit.title)}<span class="heatmap-streak">🔥 ${habit.streak} day streak</span></div>
            <div class="heatmap-months">${monthLabels.map(m => `<div class="heatmap-month-cell">${escapeHtml(m)}</div>`).join("")}</div>
            <div class="heatmap-grid">`;
          const start = new Date(rangeStart);
          const startDay = start.getDay();
          for (let pad = 0; pad < startDay; pad++) html += `<div class="heatmap-cell" style="visibility:hidden"></div>`;
          const d = new Date(start);
          while (d <= endDate) {
            const ds = d.toISOString().slice(0, 10);
            const isDone = !!(habit.dates && habit.dates[ds]);
            const isToday = ds === today;
            html += `<div class="heatmap-cell${isDone ? " done" : ""}${isToday ? " today" : ""}" data-date="${ds}"></div>`;
            d.setDate(d.getDate() + 1);
          }
          html += `</div></div>`;
        }
        html += `</div>`;
        container.innerHTML = html;
      } catch(e) {
        container.innerHTML = `<div class="diagnostic">Heatmap error: ${escapeHtml(e.message)}</div>`;
      }
    }

    function showChart(type, btn) {
      document.querySelectorAll(".chart-tab").forEach(t => t.classList.remove("active"));
      if (btn) btn.classList.add("active");
      currentChartType = type;
      const groupBar = document.getElementById("chart-group-bar");
      if (groupBar) groupBar.style.display = GROUP_SUPPORTED.has(type) ? "" : "none";
      loadChart(type);
    }

    async function refreshCharts() {
      const active = document.querySelector(".chart-tab.active");
      const type = active ? active.textContent.trim().toLowerCase() : "tasks";
      await loadChart(type);
    }

    function exportChartCsv() {
      if (!mainChart) { showToast("No chart data to export.", "error"); return; }
      const labels = mainChart.data.labels || [];
      const datasets = mainChart.data.datasets || [];
      const header = ["label", ...labels].join(",");
      const rows = datasets.map(ds => {
        const vals = (ds.data || []).map(v => v == null ? "" : String(v));
        return [JSON.stringify(ds.label || ""), ...vals].join(",");
      });
      const csv = [header, ...rows].join("\n");
      const blob = new Blob([csv], {type: "text/csv"});
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `lifetxt-chart-${currentChartType}-${currentChartGroup}.csv`;
      a.click();
