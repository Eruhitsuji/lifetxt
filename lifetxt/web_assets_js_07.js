      const now = new Date();
      const nowIso = _tlIso(now);
      const today = _fmtDate(now);
      let from, to, label;
      if (timelineRange === "24h") {
        from = nowIso;
        to = _tlIso(new Date(now.getTime() + 24 * 3600 * 1000));
        label = "next 24 hours";
      } else if (timelineRange === "week") {
        const end = new Date(now); end.setDate(end.getDate() + 6);
        from = today;
        to = _fmtDate(end);
        label = `${today} to ${_fmtDate(end)}`;
      } else {
        from = today;
        to = today;
        label = now.toLocaleDateString(undefined, {weekday: "long", month: "long", day: "numeric"});
      }
      const rangeEl = document.getElementById("tl-range-label");
      if (rangeEl) rangeEl.textContent = label;
      let data;
      try {
        data = await api(`/api/agenda?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
      } catch(e) {
        node.innerHTML = `<div class="diagnostic">Timeline error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      const records = (data.records || [])
        .flatMap(record => _tlRecordEntries(record, from, to))
        .sort((a, b) =>
          String(a.display.when || a.record.when || "").localeCompare(String(b.display.when || b.record.when || ""))
        );
      if (!records.length) {
        node.innerHTML = _timelineEmptyState(timelineRange, label, from, to);
        return;
      }
      const multiDay = timelineRange !== "today";
      const dayLabel = (d) => {
        const parsed = new Date(d + "T00:00");
        return isNaN(parsed) ? d : parsed.toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"});
      };
      const hasCurrentOrFuture = records.some(entry => {
        const when = String(entry.display.when || entry.record.when || "");
        if (entry.display.clipped) return true;
        if (!when) return false;
        return when.length > 10 ? when >= nowIso : when.slice(0, 10) >= today;
      });
      let html = hasCurrentOrFuture ? "" : _timelineQuietBanner(timelineRange);
      let lastDay = "";
      let nowInserted = false;
      for (const entry of records) {
        const record = entry.record;
        const when = String(entry.display.when || record.when || "");
        const day = when.slice(0, 10);
        const timed = when.length > 10;
        if (multiDay && day !== lastDay) {
          if (!nowInserted && lastDay === today) { html += _tlNowLine(); nowInserted = true; }
          html += `<div class="tl-day-head">${escapeHtml(dayLabel(day))}${day === today ? " · Today" : ""}</div>`;
          lastDay = day;
        }
        if (!nowInserted && day === today && timed && when > nowIso) {
          html += _tlNowLine();
          nowInserted = true;
        }
        html += _tlRow(record, nowIso, entry.display, entry.match, entry.matchIndex, entry.matchTotal);
        if (!multiDay) lastDay = day;
      }
      if (!nowInserted && lastDay === today) html += _tlNowLine();
      node.innerHTML = html;
    }

    // ── Calendar view (month / week grid) ──────────────────────────
    // Places dated agenda records — including expanded repeat occurrences —
    // on a calendar grid. Reuses /api/agenda so recurrence, blockers, and
    // occurrence badges stay consistent with the Agenda and Timeline views.
    const CAL_MODES = new Set(["month", "week"]);
    const CAL_CELL_LIMIT = 4;
    let calMode = "month";
    let calAnchor = _calStartOfDay(new Date());
    const _calExpandedDays = new Set();

    function _calStartOfDay(d) {
      const c = new Date(d.getFullYear(), d.getMonth(), d.getDate());
      c.setHours(0, 0, 0, 0);
      return c;
    }
    function _calParseAnchor(text) {
      const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(text || "").trim());
      if (!m) return null;
      const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
      return isNaN(d) ? null : _calStartOfDay(d);
    }
    function _calWeekStartIndex() {
      // 0 = Sunday, 1 = Monday (default). Honors web.week_start config.
      return (appConfig?.web?.week_start === "sunday") ? 0 : 1;
    }
    function _calGridStart(anchor) {
      // First visible day: for month mode back up to the configured week start
      // from the 1st of the month; for week mode from the anchor's own week.
      const base = calMode === "week"
        ? new Date(anchor)
        : new Date(anchor.getFullYear(), anchor.getMonth(), 1);
      const ws = _calWeekStartIndex();
      const diff = (base.getDay() - ws + 7) % 7;
      const start = new Date(base);
      start.setDate(base.getDate() - diff);
      return _calStartOfDay(start);
    }
    function _calGridDays(anchor) {
      const start = _calGridStart(anchor);
      let count;
      if (calMode === "week") {
        count = 7;
      } else {
        // Enough full weeks to cover the whole month (5 or 6 rows).
        const monthEnd = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
        const spanDays = Math.round((monthEnd - start) / 86400000) + 1;
        count = Math.ceil(spanDays / 7) * 7;
      }
      const days = [];
      for (let i = 0; i < count; i++) {
        const d = new Date(start);
        d.setDate(start.getDate() + i);
        days.push(_calStartOfDay(d));
      }
      return days;
    }
    function syncCalStateFromUrl() {
      const params = query();
      const mode = firstParam(params, ["calmode"], calMode).toLowerCase();
      calMode = CAL_MODES.has(mode) ? mode : "month";
      const anchor = _calParseAnchor(firstParam(params, ["cal"], ""));
      if (anchor) calAnchor = anchor;
      document.querySelectorAll("#calendar-anchor, .cal-controls [data-calmode]").forEach(btn => {
        if (btn.dataset && btn.dataset.calmode) {
          btn.classList.toggle("active", btn.dataset.calmode === calMode);
        }
      });
    }
    function _calWriteUrl(replace = true) {
      const params = query();
      params.set("view", "calendar");
      params.delete("mode");
      params.set("calmode", calMode);
      params.set("cal", _fmtDate(calAnchor));
      const url = `${location.pathname}?${params.toString()}`;
      if (replace) history.replaceState(null, "", url);
      else history.pushState(null, "", url);
    }
    function setCalMode(mode) {
      calMode = CAL_MODES.has(mode) ? mode : "month";
      _calExpandedDays.clear();
      _calWriteUrl(true);
      syncCalStateFromUrl();
      loadCalendar();
    }
    function calShift(delta) {
      _calExpandedDays.clear();
      if (calMode === "week") {
        calAnchor.setDate(calAnchor.getDate() + delta * 7);
      } else {
        calAnchor.setMonth(calAnchor.getMonth() + delta);
      }
      calAnchor = _calStartOfDay(calAnchor);
      _calWriteUrl(true);
      loadCalendar();
    }
    function calToday() {
      _calExpandedDays.clear();
      calAnchor = _calStartOfDay(new Date());
      _calWriteUrl(true);
      loadCalendar();
    }
    function calOpenDay(dateStr) {
      // Jump to the Agenda view scoped to a single day for a focused list.
      const params = query();
      params.set("view", "agenda");
      params.delete("mode"); params.delete("around"); params.delete("window");
      params.delete("calmode"); params.delete("cal");
      params.set("from", dateStr);
      params.set("to", dateStr);
      history.pushState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadAgenda();
    }
    function _calRecordDayPlacements(record) {
      // A record with more than one match (a multi-day all-day span, or
      // several repeat occurrences visible in one grid) must appear on
      // every matched day, not just the first -- each `on:` value or repeat
      // occurrence produces its own entry in record.matches with its own
      // `start`. matches is the authoritative per-day collection and is
      // checked first: agenda_records() always derives occurrence_start
      // from matches[0] (it is a single-value convenience field, never an
      // independent source), so preferring it here silently collapsed any
      // record with more than one match -- including ordinary multi-day
      // on: spans and multi-occurrence repeats -- down to just its first
      // day. occurrence_start/record.when remain fallbacks for a record
      // shape with no matches array at all (e.g. a plain due:/do: record).
      const matches = record.matches || [];
      if (matches.length) {
        const seen = new Set();
        const placements = [];
        for (const match of matches) {
          const when = match.start || "";
          const day = String(when).slice(0, 10);
          if (!day || seen.has(day)) continue;
          seen.add(day);
          placements.push({day, when});
        }
        if (placements.length) return placements;
      }
      if (record.occurrence_start) {
        return [{day: String(record.occurrence_start).slice(0, 10), when: record.occurrence_start}];
      }
      const raw = record.when || "";
      return raw ? [{day: String(raw).slice(0, 10), when: raw}] : [];
    }
    function _calEntryHtml(record, dayWhen, dayIndex, dayTotal) {
      const type = record.type || "N";
      const when = String(dayWhen || record.occurrence_start || ((record.matches || [])[0] || {}).start || record.when || "");
      const timed = when.length > 10;
      const time = timed ? when.slice(11, 16) + " " : "";
      const dueCls = agendaDueSoonClass(record);
      const clickable = Number.isInteger(record.line);
      const occ = (record.occurrence_start || record.repeat_rule) ? " ↻" : "";
      const blocked = record.blocked ? " ⚡" : "";
      const title = `${time}${record.title}${occ}${blocked}`;
      // A multi-day span (dayTotal > 1) gets a small "day X of Y" badge so
      // the otherwise-independent cells read as one continuous event
      // rather than several unrelated same-title entries.
      const spanBadge = dayTotal > 1
        ? `<span class="cal-entry-span" title="Day ${dayIndex} of ${dayTotal}">${dayIndex}/${dayTotal}</span>`
        : "";
      return `<div class="cal-entry cal-t-${escapeHtml(type)}${dueCls ? " cal-" + dueCls : ""}${clickable ? "" : " cal-static"}"` +
        (clickable ? ` onclick="event.stopPropagation();openItemByLine(${record.line})"` : "") +
        ` title="${escapeHtml((record.status ? record.status + " " : "") + when + " · " + record.title)}">` +
        `<span class="cal-entry-dot t-${escapeHtml(type)}"></span>` +
        `<span class="cal-entry-title">${escapeHtml(title)}</span>${spanBadge}</div>`;
    }
    async function loadCalendar() {
      const node = document.getElementById("calendar");
      if (!node) return;
      syncCalStateFromUrl();
      const days = _calGridDays(calAnchor);
      const from = _fmtDate(days[0]);
      const to = _fmtDate(days[days.length - 1]);
      const titleEl = document.getElementById("cal-title");
      if (titleEl) {
        titleEl.textContent = calMode === "week"
          ? `Week of ${days[0].toLocaleDateString(undefined, {month: "long", day: "numeric", year: "numeric"})}`
          : calAnchor.toLocaleDateString(undefined, {month: "long", year: "numeric"});
      }
      let data;
      try {
        data = await api(`/api/agenda?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
      } catch (e) {
        node.innerHTML = `<div class="diagnostic">Calendar error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      const records = data.records || [];
      const byDay = new Map();
      for (const record of records) {
        const placements = _calRecordDayPlacements(record);
        placements.forEach((placement, i) => {
          if (!byDay.has(placement.day)) byDay.set(placement.day, []);
          byDay.get(placement.day).push({
            record,
            when: placement.when,
            dayIndex: i + 1,
            dayTotal: placements.length,
          });
        });
      }
      for (const list of byDay.values()) {
        list.sort((a, b) => String(a.when || "").localeCompare(String(b.when || "")));
      }
      const total = records.length;
      const ws = _calWeekStartIndex();
      const weekdayNames = [];
      for (let i = 0; i < 7; i++) {
        const d = new Date(2024, 0, 7 + ((ws + i) % 7)); // 2024-01-07 is a Sunday
        weekdayNames.push(d.toLocaleDateString(undefined, {weekday: "short"}));
      }
      if (!total) {
        node.innerHTML = guidedEmptyState("📆", "Nothing scheduled in this period",
          "The calendar plots records with <code>due</code>, <code>do</code>, <code>on</code>, or <code>from</code>/<code>to</code> dates, including repeat occurrences. Move to another period or add a dated record.",
          [["Today", "calToday"], ["New record", "newItem"], ["Agenda", "agenda"], ["Help", "help"]]);
        return;
      }
      const todayStr = _fmtDate(new Date());
      let html = `<div class="cal-summary">${total} record${total === 1 ? "" : "s"} · ${escapeHtml(from)} → ${escapeHtml(to)}</div>`;
      html += `<div class="cal-grid cal-mode-${calMode}">`;
      for (const name of weekdayNames) {
        html += `<div class="cal-weekday">${escapeHtml(name)}</div>`;
      }
      for (const day of days) {
        const dayStr = _fmtDate(day);
        const inMonth = calMode === "week" || day.getMonth() === calAnchor.getMonth();
        const isToday = dayStr === todayStr;
        const entries = byDay.get(dayStr) || [];
        const expanded = _calExpandedDays.has(dayStr);
        const shown = expanded ? entries : entries.slice(0, CAL_CELL_LIMIT);
        const overflow = entries.length - shown.length;
        let cell = `<div class="cal-cell${inMonth ? "" : " cal-out"}${isToday ? " cal-today" : ""}${entries.length ? " cal-has" : ""}">`;
        cell += `<div class="cal-daynum"><a class="cal-daylink" onclick="calOpenDay('${dayStr}')" title="Open ${escapeHtml(dayStr)} in Agenda">${day.getDate()}</a>`;
        cell += entries.length ? `<span class="cal-count">${entries.length}</span>` : "";
        cell += `</div><div class="cal-entries">`;
        cell += shown.map((entry) => _calEntryHtml(entry.record, entry.when, entry.dayIndex, entry.dayTotal)).join("");
        if (overflow > 0) {
          cell += `<button type="button" class="cal-more" onclick="calExpandDay('${dayStr}')">+${overflow} more</button>`;
        } else if (expanded && entries.length > CAL_CELL_LIMIT) {
          cell += `<button type="button" class="cal-more" onclick="calExpandDay('${dayStr}')">show less</button>`;
        }
        cell += `</div></div>`;
        html += cell;
      }
      html += `</div>`;
      node.innerHTML = html;
    }
    function calExpandDay(dateStr) {
      if (_calExpandedDays.has(dateStr)) _calExpandedDays.delete(dateStr);
      else _calExpandedDays.add(dateStr);
      loadCalendar();
    }

    // ── Fullscreen ─────────────────────────────────────────────────
    function toggleFullscreen() {
      if (document.fullscreenElement) {
        document.exitFullscreen?.();
        return;
      }
      const target = document.documentElement;
      if (!target.requestFullscreen) {
        showToast("Fullscreen is not available in this browser.", "error");
        return;
      }
      target.requestFullscreen().catch(() => showToast("Fullscreen was blocked by the browser.", "error"));
    }
    document.addEventListener("fullscreenchange", () => {
      const active = !!document.fullscreenElement;
      document.body.classList.toggle("is-fullscreen", active);
      const btn = document.getElementById("fullscreen-btn");
      if (btn) {
        btn.textContent = active ? "⤢" : "⛶";
        btn.title = active ? "Exit fullscreen (f)" : "Toggle fullscreen (f)";
      }
    });
    async function loadConfig() {
      appConfig = await api("/api/config");
      applyConfiguredTheme();
      applyConfiguredDashboard();
      initAccessibilityPrefs();
      applyLanguage();
      startLanguageObserver();
      setupCompletion();
    }
    async function loadNotifications() {
      if (appConfig?.notifications?.enabled === false || appConfig?.notifications?.web === false) {
        document.getElementById("notifications").innerHTML = `<div class="empty">Notifications disabled.</div>`;
        return;
      }
      const params = query();
      const notificationParams = new URLSearchParams();
      if (params.has("recipient")) notificationParams.set("recipient", params.get("recipient"));
      else if (params.has("person")) notificationParams.set("recipient", params.get("person"));
      const lookahead = firstParam(
        params,
        ["notify_lookahead"],
        appConfig?.web?.notification_lookahead || appConfig?.notifications?.lookahead || "0m"
      );
      if (lookahead) notificationParams.set("lookahead", lookahead);
      const data = await api(`/api/notifications?${notificationParams}`);
      window._lastNotifRecords = data.records || [];
      const node = document.getElementById("notifications");
      node.innerHTML = data.records.length ? "" : guidedEmptyState("🔔", "No notifications right now",
        "Notifications surface reminders and messages with a <code>notify</code> detail. Enable browser alerts to be notified while this tab is open.",
        [["Enable alerts", "enableNotifications"], ["Messages", "messages"], ["Help", "help"]]);
      const snoozeDefault = appConfig?.notifications?.snooze_default || "10m";
      let notifIdx = 0;
      for (const record of data.records) {
        notifIdx++;
        const snoozeInputId = `snooze-input-${notifIdx}`;
        const snoozeRowId = `snooze-row-${notifIdx}`;
        const actions = record.id ? `
          <div class="actions" style="flex-wrap:wrap;gap:.3rem">
            <button class="secondary" type="button" onclick="ackMessage(${escapeHtml(jsLiteral(record.id))})">Ack</button>
            <button class="secondary" type="button" onclick="snoozeMessage(${escapeHtml(jsLiteral(record.id))}, ${escapeHtml(jsLiteral(snoozeDefault))})">Snooze ${escapeHtml(snoozeDefault)}</button>
            <button class="secondary" type="button" onclick="document.getElementById(${escapeHtml(jsLiteral(snoozeRowId))}).style.display=document.getElementById(${escapeHtml(jsLiteral(snoozeRowId))}).style.display===''?'none':''" style="font-size:.73rem">Custom…</button>
            <button class="secondary" type="button" onclick="retryBrowserNotification(${escapeHtml(jsLiteral(record.id || record.notification_id || ""))})" style="font-size:.73rem" title="Re-send browser notification">Retry</button>
          </div>
          <div id="${snoozeRowId}" class="snooze-inline" style="display:none">
            <input id="${snoozeInputId}" value="${escapeHtml(snoozeDefault)}" placeholder="30m / 1h / 2h">
            <button class="secondary" type="button" onclick="snoozeMessageCustom(${escapeHtml(jsLiteral(record.id))}, ${escapeHtml(jsLiteral(snoozeInputId))})">Go</button>
          </div>
        ` : "";
        const stateBadge = notifStateBadge(record);
        const relTime = record.when ? relativeTime(record.when) : "";
        const whenDisplay = relTime ? `${escapeHtml(record.when)} <span style="color:var(--muted);font-size:.8em">(${escapeHtml(relTime)})</span>` : escapeHtml(record.when);
        node.insertAdjacentHTML(
          "beforeend",
