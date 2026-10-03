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
    const CLOCK_FORMAT_TOKENS = ["YYYY", "YY", "MMMM", "MMM", "MM", "M", "DD", "D", "dddd", "ddd", "dd", "d", "E", "HH", "H", "hh", "h", "mm", "m", "ss", "s", "A", "a", "GGGG", "WW", "W", "ZZ", "Z", "z"].sort((a, b) => b.length - a.length);
    const CLOCK_CALENDAR_TOKENS = new Set(["YYYY", "YY", "MMMM", "MMM", "MM", "M", "DD", "D", "dddd", "ddd", "dd", "d", "E", "GGGG", "WW", "W"]);
    let _webClockTimer = null;
    const _clockFormatters = new Map();

    function _parseClockFormat(format) {
      if (typeof format !== "string" || !format || Array.from(format).length > 128 || /[\x00-\x1f\x7f]/.test(format)) return null;
      const parts = [];
      for (let i = 0; i < format.length;) {
        if (format[i] === "[") {
          const end = format.indexOf("]", i + 1);
          if (end < 0 || format.slice(i + 1, end).includes("[")) return null;
          parts.push({literal: format.slice(i + 1, end)});
          i = end + 1;
        } else if (/[A-Za-z]/.test(format[i])) {
          const token = CLOCK_FORMAT_TOKENS.find(value => format.startsWith(value, i));
          if (!token) return null;
          parts.push({token});
          i += token.length;
        } else {
          if (format[i] === "]") return null;
          parts.push({literal: format[i++]});
        }
      }
      return parts;
    }

    function _validClockZone(zone) {
      if (typeof zone !== "string" || !zone || zone.length > 128 || !/^[A-Za-z0-9_+./-]+$/.test(zone)) return false;
      try { new Intl.DateTimeFormat("en-US", {timeZone: zone}); return true; }
      catch (_) { return false; }
    }

    function _topClockSettings() {
      const raw = appConfig?.web?.top_clock;
      const settings = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
      const timezone = ["main", "browser-local"].includes(settings.timezone) || _validClockZone(settings.timezone) ? settings.timezone : "main";
      const main = settings.main_timezone;
      const mainZone = ["local", "host"].includes(main) || _validClockZone(main) ? main : "UTC";
      const mainOffset = Number.isInteger(settings.main_utc_offset_minutes) && Math.abs(settings.main_utc_offset_minutes) <= 1440 ? settings.main_utc_offset_minutes : 0;
      return {
        enabled: typeof settings.enabled === "boolean" ? settings.enabled : true,
        format: _parseClockFormat(settings.format) ? settings.format : "HH:mm",
        showDate: settings.show_date === true,
        dateSeparator: ["-", "/"].includes(settings.date_separator) ? settings.date_separator : "-",
        timezone, resolvedTimezone: timezone === "main" ? mainZone : timezone,
        mainOffset, showTimezone: settings.show_timezone === true,
      };
    }

    function _clockOffsetText(minutes, colon = true) {
      const pad = value => String(value).padStart(2, "0");
      return (minutes < 0 ? "-" : "+") + pad(Math.floor(Math.abs(minutes) / 60)) + (colon ? ":" : "") + pad(Math.abs(minutes) % 60);
    }

    function _clockCalendarDate(year, month, day) {
      const value = new Date(0);
      value.setUTCFullYear(year, month - 1, day);
      value.setUTCHours(0, 0, 0, 0);
      return value;
    }

    function _clockParts(now, settings) {
      const zone = settings.resolvedTimezone || "browser-local";
      const serverLocal = zone === "local" || zone === "host";
      const instant = serverLocal ? new Date(now.getTime() + settings.mainOffset * 60000) : now;
      const timeZone = serverLocal ? "UTC" : zone === "browser-local" ? undefined : zone;
      const key = timeZone || "browser-local";
      if (!_clockFormatters.has(key)) _clockFormatters.set(key, new Intl.DateTimeFormat("en-US", {
        timeZone, calendar: "gregory", numberingSystem: "latn", hourCycle: "h23",
        year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", timeZoneName: "short",
      }));
      const formatter = _clockFormatters.get(key);
      const parts = Object.fromEntries(formatter.formatToParts(instant).map(part => [part.type, part.value]));
      const year = Number(parts.year), month = Number(parts.month), day = Number(parts.day);
      const calendar = _clockCalendarDate(year, month, day);
      const weekday = calendar.getUTCDay();
      const thursday = new Date(calendar.getTime());
      thursday.setUTCDate(thursday.getUTCDate() + 4 - (weekday || 7));
      const weekYear = thursday.getUTCFullYear();
      const week = Math.ceil(((thursday - _clockCalendarDate(weekYear, 1, 1)) / 86400000 + 1) / 7);
      const wallInstant = _clockCalendarDate(year, month, day);
      wallInstant.setUTCHours(Number(parts.hour), Number(parts.minute), Number(parts.second));
      const offset = serverLocal ? settings.mainOffset : Math.round((wallInstant.getTime() - Math.floor(now.getTime() / 1000) * 1000) / 60000);
      const canonical = formatter.resolvedOptions().timeZone;
      const label = serverLocal ? "UTC" + _clockOffsetText(offset) : canonical === "Asia/Tokyo" ? "JST" : canonical === "UTC" ? "UTC" : parts.timeZoneName;
      return {year, month, day, weekday, weekYear, week, hour: Number(parts.hour), minute: Number(parts.minute), second: Number(parts.second), offset, label};
    }

    function _formatWebClock(now, settings = null) {
      if (!settings) {
        const date = now.toLocaleDateString(undefined, { weekday:"short", month:"short", day:"numeric" });
        const time = now.toLocaleTimeString(undefined, { hour:"2-digit", minute:"2-digit" });
        return date + "  " + time;
      }
      const pad = value => String(value).padStart(2, "0");
      const parts = _parseClockFormat(settings.format) || _parseClockFormat("HH:mm");
      const value = _clockParts(now, settings);
      const ja = currentLanguage() === "ja";
      const shortDays = ja ? ["日", "月", "火", "水", "木", "金", "土"] : ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const longDays = ja ? shortDays.map(day => day + "曜日") : ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
      const shortMonths = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const longMonths = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
      const ampm = value.hour < 12 ? "AM" : "PM";
      const tokens = {
        YYYY: String(value.year).padStart(4, "0"), YY: pad(value.year % 100),
        MMMM: ja ? value.month + "月" : longMonths[value.month - 1], MMM: ja ? value.month + "月" : shortMonths[value.month - 1], MM: pad(value.month), M: String(value.month),
        DD: pad(value.day), D: String(value.day), dddd: longDays[value.weekday], ddd: shortDays[value.weekday], dd: ja ? shortDays[value.weekday] : shortDays[value.weekday].slice(0, 2), d: String(value.weekday), E: String(value.weekday || 7),
        HH: pad(value.hour), H: String(value.hour), hh: pad(value.hour % 12 || 12), h: String(value.hour % 12 || 12), mm: pad(value.minute), m: String(value.minute), ss: pad(value.second), s: String(value.second), A: ampm, a: ampm,
        GGGG: String(value.weekYear).padStart(4, "0"), WW: pad(value.week), W: String(value.week), z: value.label, Z: _clockOffsetText(value.offset), ZZ: _clockOffsetText(value.offset, false),
      };
      let text = parts.map(part => part.token ? tokens[part.token] : part.literal).join("");
      if (settings.showDate && !parts.some(part => CLOCK_CALENDAR_TOKENS.has(part.token))) {
        const separator = settings.dateSeparator === "/" ? "/" : "-";
        text = tokens.YYYY + separator + tokens.MM + separator + tokens.DD + " " + text;
      }
      if (settings.showTimezone && !parts.some(part => part.token === "z")) text += " (" + value.label + ")";
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
      _clockFormatters.clear();
      const settings = _topClockSettings();
      const top = document.getElementById("top-clock");
      const kioskActive = isKioskMode();
      const topActive = settings.enabled && !kioskActive && !isDisplayMode() && !document.body.classList.contains("capture-mode") && location.pathname.replace(/\/+$/, "") !== "/capture";
      if (top) {
        top.hidden = !topActive;
        const reserve = Math.min(32, settings.format.length + (settings.showDate ? 11 : 0) + (settings.showTimezone ? 12 : 0));
        top.style.minWidth = "min(100%, " + reserve + "ch)";
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
