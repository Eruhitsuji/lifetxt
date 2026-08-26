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