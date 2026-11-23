    // ── Calendar time grid (Day / Week) ────────────────────────────
    // Google-Calendar-style schedule: an hour axis, blocks sized by
    // duration, side-by-side columns for overlapping events, an all-day
    // row and a current-time line. Rendering only; data comes from the
    // same /api/agenda records as the Month grid.
    const CAL_HOUR_PX = 48;
    const CAL_DEFAULT_MINUTES = 30;
    const CAL_MIN_BLOCK_MINUTES = 20;
    function _calMinutes(when) {
      const m = /T(\d{2}):(\d{2})/.exec(String(when || ""));
      return m ? Number(m[1]) * 60 + Number(m[2]) : null;
    }
    // Split one day's entries into all-day chips and positioned blocks.
    function _calSplitDay(entries, dayStr) {
      const allDay = [];
      const timed = [];
      for (const entry of entries) {
        const startMin = _calMinutes(entry.when);
        const match = (entry.record.matches || []).find(m => m.start === entry.when) || {};
        // on: dates (and date-only values) are all-day, even if the
        // server normalizes them to a midnight timestamp.
        if (startMin === null || match.key === "on" || (startMin === 0 && !match.end)) { allDay.push(entry); continue; }
        let endMin = null;
        if (match.end && String(match.end).slice(0, 10) === dayStr) endMin = _calMinutes(match.end);
        else if (match.end && String(match.end).slice(0, 10) > dayStr) endMin = 24 * 60;
        if (endMin === null || endMin <= startMin) endMin = Math.min(24 * 60, startMin + CAL_DEFAULT_MINUTES);
        endMin = Math.max(endMin, startMin + CAL_MIN_BLOCK_MINUTES);
        timed.push({entry, start: startMin, end: Math.min(endMin, 24 * 60)});
      }
      return {allDay, timed};
    }
    // Greedy column packing: overlapping blocks share the width.
    function _calPackBlocks(blocks) {
      const sorted = blocks.slice().sort((a, b) => a.start - b.start || b.end - a.end);
      let cluster = [];
      let clusterEnd = -1;
      const flush = () => {
        const cols = [];
        for (const b of cluster) {
          let i = cols.findIndex(end => end <= b.start);
          if (i < 0) { i = cols.length; cols.push(0); }
          cols[i] = b.end;
          b.col = i;
        }
        for (const b of cluster) b.cols = cols.length;
        cluster = [];
      };
      for (const b of sorted) {
        if (cluster.length && b.start >= clusterEnd) { flush(); clusterEnd = -1; }
        cluster.push(b);
        clusterEnd = Math.max(clusterEnd, b.end);
      }
      if (cluster.length) flush();
      return sorted;
    }
    function _calBlockHtml(block) {
      const {record, when} = block.entry;
      const type = record.type || "N";
      const top = block.start / 60 * CAL_HOUR_PX;
      const height = Math.max(14, (block.end - block.start) / 60 * CAL_HOUR_PX - 1);
      const left = block.col / block.cols * 100;
      const width = 100 / block.cols;
      const dueCls = agendaDueSoonClass(record);
      const clickable = Number.isInteger(record.line);
      const done = /x/i.test(String(record.status || ""));
      const label = _temporalDisplayLabel(when, {allDayMidnight: true, dayContext: true});
      const tag = clickable ? "button" : "div";
      const pc = _calProjectAttrs(record);
      const drag = _calDragInfo(block.entry);
      return `<${tag} class="cal-tg-block t-${escapeHtml(type)}${pc.cls}${drag ? " cal-tg-drag" : ""}${dueCls ? " cal-" + dueCls : ""}${done ? " cal-done" : ""}"` +
        (clickable ? ` type="button" onclick="openItemByLine(${record.line})"` : "") +
        (clickable ? ` data-line="${record.line}" data-when="${escapeHtml(String(when))}"` : "") +
        ` style="${pc.style}top:${top}px;height:${height}px;left:${left}%;width:calc(${width}% - 2px)"` +
        ` title="${escapeHtml((label ? label + " · " : "") + record.title)}">` +
        `<span class="cal-tg-title">${escapeHtml(record.title)}${record.repeat_rule ? " ↻" : ""}</span>` +
        (height >= 30 ? `<span class="cal-tg-time">${escapeHtml(label)}</span>` : "") +
        (drag && drag.resize ? `<span class="cal-tg-resize" aria-hidden="true"></span>` : "") + `</${tag}>`;
    }
    function _calTimeGridHtml(days, byDay) {
      const todayStr = _fmtDate(new Date());
      const cols = days.length;
      const split = days.map(d => _calSplitDay(byDay.get(_fmtDate(d)) || [], _fmtDate(d)));
      let html = `<div class="cal-tg cal-tg-${cols === 1 ? "day" : "week"}" style="--cal-cols:${cols}">`;
      html += `<div class="cal-tg-head"><div class="cal-tg-gutter"></div>`;
      days.forEach(day => {
        const dayStr = _fmtDate(day);
        html += `<div class="cal-tg-dayhead${dayStr === todayStr ? " cal-today" : ""}">` +
          `<span class="cal-tg-dow">${escapeHtml(day.toLocaleDateString(uiLocale(), {weekday: "short"}))}</span>` +
          `<button type="button" class="cal-tg-date" onclick="calGotoDay('${dayStr}')" aria-label="${escapeHtml(dayStr)}">${day.getDate()}</button></div>`;
      });
      html += `</div>`;
      if (split.some(s => s.allDay.length)) {
        html += `<div class="cal-tg-allday"><div class="cal-tg-gutter cal-tg-gutter-label">${escapeHtml(t("All-day"))}</div>`;
        split.forEach((s, di) => {
          html += `<div class="cal-tg-allday-cell" data-calendar-day="${escapeHtml(_fmtDate(days[di]))}">${s.allDay.map(e => _calEntryHtml(e.record, e.when, e.dayIndex, e.dayTotal)).join("")}</div>`;
        });
        html += `</div>`;
      }
      html += `<div class="cal-tg-scroll"><div class="cal-tg-body" style="height:${24 * CAL_HOUR_PX}px"><div class="cal-tg-hours">`;
      for (let h = 1; h < 24; h++) {
        html += `<div class="cal-tg-hour" style="top:${h * CAL_HOUR_PX}px">${String(h).padStart(2, "0")}:00</div>`;
      }
      html += `</div><div class="cal-tg-cols">`;
      days.forEach((day, i) => {
        const dayStr = _fmtDate(day);
        html += `<div class="cal-tg-col${dayStr === todayStr ? " cal-today" : ""}" data-calendar-day="${escapeHtml(dayStr)}">`;
        for (const b of _calPackBlocks(split[i].timed)) html += _calBlockHtml(b);
        if (dayStr === todayStr) {
          const now = new Date();
          html += `<div class="cal-tg-now" style="top:${(now.getHours() * 60 + now.getMinutes()) / 60 * CAL_HOUR_PX}px"><span></span></div>`;
        }
        html += `</div>`;
      });
      html += `</div></div></div></div>`;
      return html;
    }
    function _calTimeGridAfterRender(node) {
      const scroll = node.querySelector(".cal-tg-scroll");
      if (!scroll) return;
      const first = node.querySelector(".cal-tg-block");
      const focus = node.querySelector(".cal-tg-now") ? new Date().getHours() - 1
        : first ? Math.floor(parseFloat(first.style.top) / CAL_HOUR_PX) - 1 : 7;
      scroll.scrollTop = Math.max(0, focus) * CAL_HOUR_PX;
      // Keep header / all-day columns aligned with the scrolling body:
      // reserve the same width the body's scrollbar takes.
      const grid = node.querySelector(".cal-tg");
      if (grid) grid.style.setProperty("--cal-sb", `${scroll.offsetWidth - scroll.clientWidth}px`);
      const cols = node.querySelector(".cal-tg-cols");
      if (cols) _calBindDrag(cols);
    }
    function calGotoDay(dateStr) {
      const d = _calParseAnchor(dateStr);
      if (!d) return;
      calAnchor = d;
      calMode = "day";
      _calWriteUrl(true);
      syncCalStateFromUrl();
      loadCalendar();
    }

    // ── Calendar month grid (spanning bars, overflow popover) ──────
    function _calAddDays(dateStr, n) {
      const d = _calParseAnchor(dateStr);
      d.setDate(d.getDate() + n);
      return _fmtDate(d);
    }
    // Multi-day records become one continuous bar per week row instead of
    // one repeated entry per day. Repeating records are never bars.
    function _calSpanSegments(records) {
      const segments = [];
      const covered = new Map();
      for (const record of records) {
        if (record.repeat_rule) continue;
        const matches = record.matches || [];
        const found = [];
        for (const m of matches) {
          const s = String(m.start || "").slice(0, 10);
          let e = String(m.end || "").slice(0, 10);
          if (!s || !e || e <= s) continue;
          // A timed end exactly at midnight does not occupy the new day.
          if (String(m.end).length > 10 && /T00:00/.test(String(m.end))) e = _calAddDays(e, -1);
          if (e > s) found.push({start: s, end: e});
        }
        if (!found.length) {
          const onDays = [...new Set(matches.filter(m => m.key === "on")
            .map(m => String(m.start || "").slice(0, 10)).filter(Boolean))].sort();
          let run = null;
          for (const d of onDays) {
            if (run && _calAddDays(run.end, 1) === d) run.end = d;
            else { if (run && run.end > run.start) found.push(run); run = {start: d, end: d}; }
          }
          if (run && run.end > run.start) found.push(run);
        }
        for (const f of found) {
          segments.push({record, start: f.start, end: f.end});
          if (!covered.has(record)) covered.set(record, new Set());
          for (let d = f.start; d <= f.end; d = _calAddDays(d, 1)) covered.get(record).add(d);
        }
      }
      return {segments, covered};
    }
    function _calWeekBars(weekDays, segments) {
      const wStart = _fmtDate(weekDays[0]);
      const wEnd = _fmtDate(weekDays[6]);
      const idx = day => weekDays.findIndex(d => _fmtDate(d) === day);
      const clipped = segments.filter(s => s.end >= wStart && s.start <= wEnd).map(s => ({
        seg: s,
        col0: idx(s.start < wStart ? wStart : s.start),
        col1: idx(s.end > wEnd ? wEnd : s.end),
        left: s.start < wStart,
        right: s.end > wEnd,
      })).sort((a, b) => a.col0 - b.col0 || (b.col1 - b.col0) - (a.col1 - a.col0));
      const laneEnds = [];
      for (const bar of clipped) {
        let lane = laneEnds.findIndex(end => end < bar.col0);
        if (lane < 0) { lane = laneEnds.length; laneEnds.push(-1); }
        laneEnds[lane] = bar.col1;
        bar.lane = lane;
      }
      return {bars: clipped, lanes: laneEnds.length};
    }
    function _calBarHtml(bar) {
      const {record} = bar.seg;
      const type = record.type || "N";
      const clickable = Number.isInteger(record.line);
      const tag = clickable ? "button" : "div";
      const dueCls = agendaDueSoonClass(record);
      const pc = _calProjectAttrs(record);
      return `<${tag} class="cal-span-bar t-${escapeHtml(type)}${pc.cls}${dueCls ? " cal-" + dueCls : ""}${bar.left ? " cal-span-cl" : ""}${bar.right ? " cal-span-cr" : ""}"` +
        (clickable ? ` type="button" onclick="openItemByLine(${record.line})" data-line="${record.line}" data-when="${escapeHtml(String(bar.seg.start))}"` : "") +
        (_calDragInfo({record, when: bar.seg.start}) ? ` data-cal-drag="1"` : "") +
        ` style="${pc.style}grid-column:${bar.col0 + 1} / ${bar.col1 + 2};grid-row:${bar.lane + 1}"` +
        ` title="${escapeHtml(record.title + " · " + bar.seg.start + " → " + bar.seg.end)}">` +
        `${bar.left ? "‹ " : ""}${escapeHtml(record.title)}${bar.right ? " ›" : ""}</${tag}>`;
    }
    let _calDayEntries = new Map();
    function _calMonthHtml(days, byDay, segments) {
      const ws = _calWeekStartIndex();
      const todayStr = _fmtDate(new Date());
      _calDayEntries = new Map();
      let html = `<div class="cal-grid cal-mode-month"><div class="cal-weekdays">`;
      for (let i = 0; i < 7; i++) {
        const d = new Date(2024, 0, 7 + ((ws + i) % 7)); // 2024-01-07 is a Sunday
        html += `<div class="cal-weekday">${escapeHtml(d.toLocaleDateString(uiLocale(), {weekday: "short"}))}</div>`;
      }
      html += `</div>`;
      for (let w = 0; w < days.length / 7; w++) {
        const weekDays = days.slice(w * 7, w * 7 + 7);
        const {bars, lanes} = _calWeekBars(weekDays, segments);
        html += `<div class="cal-week" style="--lanes:${lanes}"><div class="cal-week-cells">`;
        for (const day of weekDays) {
          const dayStr = _fmtDate(day);
          const inMonth = day.getMonth() === calAnchor.getMonth();
          const entries = byDay.get(dayStr) || [];
          const spans = segments.filter(s => s.start <= dayStr && dayStr <= s.end);
          const total = entries.length + spans.length;
          _calDayEntries.set(dayStr, {entries, spans});
          const limit = Math.max(1, CAL_CELL_LIMIT - lanes);
          const shown = entries.slice(0, limit);
          const overflow = entries.length - shown.length;
          html += `<div data-calendar-day="${escapeHtml(dayStr)}" class="cal-cell${inMonth ? "" : " cal-out"}${dayStr === todayStr ? " cal-today" : ""}${total ? " cal-has" : ""}">`;
          html += `<div class="cal-daynum"><button type="button" class="cal-daylink" aria-label="${escapeHtml(t("Open day") + ": " + dayStr)}">${day.getDate()}</button>`;
          html += total ? `<span class="cal-count">${total}</span>` : "";
          html += `</div><div class="cal-entries">`;
          html += shown.map(e => _calEntryHtml(e.record, e.when, e.dayIndex, e.dayTotal)).join("");
          if (overflow > 0) {
            html += `<button type="button" class="cal-more" onclick="calMoreOpen('${dayStr}', this)">+${overflow} more</button>`;
          }
          html += `</div></div>`;
        }
        html += `</div>`;
        if (bars.length) html += `<div class="cal-week-bars">${bars.map(_calBarHtml).join("")}</div>`;
        html += `</div>`;
      }
      return html + `</div>`;
    }
    let _calPopover = null;
    function calClosePopover() {
      if (!_calPopover) return;
      _calPopover.remove();
      _calPopover = null;
      document.removeEventListener("mousedown", _calPopoverOutside, true);
      document.removeEventListener("keydown", _calPopoverKey, true);
    }
    function _calPopoverOutside(event) {
      if (_calPopover && !_calPopover.contains(event.target)) calClosePopover();
    }
    function _calPopoverKey(event) {
      if (event.key === "Escape") { event.stopPropagation(); calClosePopover(); }
    }
    function calMoreOpen(dayStr, anchor) {
      calClosePopover();
      const info = _calDayEntries.get(dayStr);
      if (!info) return;
      const d = _calParseAnchor(dayStr);
      const dayMs = 86400000;
      const spanRows = info.spans.map(s => {
        const n = Math.round((d - _calParseAnchor(s.start)) / dayMs) + 1;
        const tot = Math.round((_calParseAnchor(s.end) - _calParseAnchor(s.start)) / dayMs) + 1;
        return _calEntryHtml(s.record, dayStr, n, tot);
      });
      const rows = spanRows.concat(info.entries.map(e => _calEntryHtml(e.record, e.when, e.dayIndex, e.dayTotal)));
      const pop = document.createElement("div");
      pop.className = "cal-popover";
      pop.setAttribute("role", "dialog");
      pop.setAttribute("aria-label", dayStr);
      pop.innerHTML = `<div class="cal-popover-head"><button type="button" class="cal-popover-day" onclick="calClosePopover();calGotoDay('${dayStr}')">` +
        `${escapeHtml(d.toLocaleDateString(uiLocale(), {weekday: "short", month: "short", day: "numeric"}))}</button>` +
        `<button type="button" class="cal-popover-close" aria-label="${escapeHtml(t("Close"))}" onclick="calClosePopover()">✕</button></div>` +
        `<div class="cal-popover-list">${rows.join("")}</div>`;
      document.body.appendChild(pop);
      const rect = anchor.getBoundingClientRect();
      pop.style.left = `${Math.max(8, Math.min(window.innerWidth - pop.offsetWidth - 8, rect.left - 8))}px`;
      pop.style.top = `${Math.max(8, Math.min(window.innerHeight - pop.offsetHeight - 8, rect.top - 8))}px`;
      pop.addEventListener("click", event => { if (event.target.closest(".cal-entry")) calClosePopover(); });
      _calPopover = pop;
      document.addEventListener("mousedown", _calPopoverOutside, true);
      document.addEventListener("keydown", _calPopoverKey, true);
      (pop.querySelector(".cal-entry") || pop.querySelector(".cal-popover-close")).focus();
    }

    // ── Direct manipulation: create / move / resize ────────────────
    // Dragging on an empty slot creates an event, dragging a block moves
    // it (also across days) and the bottom edge resizes it; chips in the
    // Month grid / all-day row move to another day. Every change is the
    // same revision-guarded PUT the editor uses. Touch needs a long press
    // so scrolling is never hijacked. Repeating records move as a whole
    // series after a confirmation.
    let _calGridRecords = new Map();
    let _calSuppressClickUntil = 0;
    const CAL_SNAP_MINUTES = 15;
    const CAL_SHIFT_KEYS = ["from", "to", "at", "on", "due", "do"];
    const CAL_VALUE_RE = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?$/;
    function _calEntryKey(entry) {
      const record = entry.record || {};
      const when = String(entry.when || "");
      const matches = record.matches || [];
      const hit = matches.find(m => m.start === when)
        || matches.find(m => String(m.start || "").slice(0, 10) === when.slice(0, 10))
        || matches.find(m => m.start <= when && (!m.end || when <= m.end))
        || matches[0];
      return hit ? String(hit.key).replace(/^repeat:/, "") : null;
    }
    // Why a record cannot be dragged (null when it can).
    function _calNoDragReason(record) {
      if (record.editable === false) return "readonly";
      if (!Number.isInteger(record.line)) return "other";
      if (record.repeat_rule && /BY(DAY|MONTHDAY|SETPOS|MONTH|YEARDAY|WEEKNO)/i.test(String(record.repeat_rule))) return "repeat";
      return null;
    }
    // {keys, timed, resize} or null. keys = the details that move together.
    function _calDragInfo(entry) {
      const record = entry.record || {};
      if (_calNoDragReason(record)) return null;
      const key = _calEntryKey(entry);
      if (key !== "from/to" && !CAL_SHIFT_KEYS.includes(key)) return null;
      const details = record.details || {};
      const keys = (key === "from" || key === "to" || key === "from/to") ? ["from", "to"].filter(k => details[k]) : [key];
      let timed = true;
      for (const k of keys) {
        const values = details[k];
        if (!Array.isArray(values) || !values.length) return null;
        for (const v of values) {
          const m = CAL_VALUE_RE.exec(String(v));
          if (!m) return null;
          if (m[4] === undefined) timed = false;
        }
      }
      const dayStr = String(entry.when || "").slice(0, 10);
      const toVals = details.to || [];
      const resize = keys.includes("to") && timed && toVals.length === 1 && (details.from || []).length === 1
        && String(toVals[0]).slice(0, 10) === dayStr;
      return {keys, timed, resize};
    }
    function _calShiftValue(str, days, minutes) {
      const m = CAL_VALUE_RE.exec(String(str));
      if (!m) return String(str);
      const timed = m[4] !== undefined;
      const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3] + days, timed ? +m[4] : 0, timed ? +m[5] + minutes : 0));
      const iso = d.toISOString();
      return timed ? iso.slice(0, 10) + "T" + iso.slice(11, 16) : iso.slice(0, 10);
    }
    function _calShiftDetails(record, info, days, minutes, mode) {
      const details = JSON.parse(JSON.stringify(record.details || {}));
      if (mode === "resize") {
        details.to = details.to.map(v => _calShiftValue(v, 0, minutes));
        const floor = _calShiftValue(details.from[0], 0, CAL_SNAP_MINUTES);
        if (details.to[0] < floor) details.to = [floor];
      } else {
        for (const k of info.keys) details[k] = details[k].map(v => _calShiftValue(v, days, minutes));
      }
      return details;
    }
    function _calSnap(minutes) { return Math.round(minutes / CAL_SNAP_MINUTES) * CAL_SNAP_MINUTES; }
    function _calFmtMin(min) {
      const m = Math.max(0, Math.min(24 * 60 - 1, min));
      return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
    }
    function _calMinOf(str) { return Number(String(str).slice(11, 13)) * 60 + Number(String(str).slice(14, 16)); }
    // Mouse/pen start at once; touch starts after a long press that did
    // not move, so scrolling keeps working.
    function _calArm(event, start) {
      if (event.pointerType !== "touch") { start(event); return; }
      const id = event.pointerId;
      const sx = event.clientX;
      const sy = event.clientY;
      let x = sx;
      let y = sy;
      let timer = 0;
      const stop = () => {
        clearTimeout(timer);
        document.removeEventListener("pointermove", mv, true);
        document.removeEventListener("pointerup", stop, true);
        document.removeEventListener("pointercancel", stop, true);
      };
      const mv = e => {
        if (e.pointerId !== id) return;
        x = e.clientX;
        y = e.clientY;
        if (Math.hypot(x - sx, y - sy) > 8) stop();
      };
      timer = setTimeout(() => {
        stop();
        if (navigator.vibrate) navigator.vibrate(15);
        start({clientX: x, clientY: y, touch: true, preventDefault() {}});
      }, 400);
      document.addEventListener("pointermove", mv, true);
      document.addEventListener("pointerup", stop, true);
      document.addEventListener("pointercancel", stop, true);
    }
    function _calNoDragHint(event, line) {
      if (event.pointerType === "touch") return;
      const record = _calGridRecords.get(line);
      if (!record) return;
      const reason = _calNoDragReason(record) || "other";
      const sx = event.clientX;
      const sy = event.clientY;
      const mv = e => {
        if (Math.hypot(e.clientX - sx, e.clientY - sy) < 6) return;
        end();
        _calSuppressClickUntil = performance.now() + 400;
        showToast(reason === "readonly" ? t("This record is read-only.")
          : reason === "repeat" ? t("This repeating record can't be moved by dragging — open it to edit its rule.")
          : t("This record can't be moved by dragging — open it to edit its dates."), "info");
      };
      const end = () => {
        document.removeEventListener("pointermove", mv, true);
        document.removeEventListener("pointerup", end, true);
      };
      document.addEventListener("pointermove", mv, true);
      document.addEventListener("pointerup", end, true);
    }
    function _calBindChipDrag(node) {
      if (node._calChipBound) return;
      node._calChipBound = true;
      node.addEventListener("click", event => {
        if (performance.now() < _calSuppressClickUntil) { event.preventDefault(); event.stopImmediatePropagation(); }
      }, true);
      node.addEventListener("pointerdown", event => {
        if (event.button !== 0 || event.target.closest(".cal-tg-block")) return;
        const chip = event.target.closest(".cal-entry, .cal-span-bar");
        if (!chip) {
          const cell = event.target.closest(".cal-cell, .cal-tg-allday-cell");
          if (cell && cell.dataset.calendarDay && !event.target.closest("button, a, .cal-more")) {
            _calArm(event, ev => _calStartAllDayCreate(ev, cell, cell.classList.contains("cal-tg-allday-cell")));
          }
          return;
        }
        if (!chip.dataset.line) return;
        if (!chip.dataset.calDrag) { _calNoDragHint(event, Number(chip.dataset.line)); return; }
        _calArm(event, ev => _calStartChipDrag(ev, chip));
      });
    }
    function _calBindDrag(cols) {
      cols.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        const block = event.target.closest(".cal-tg-block");
        if (block) {
          if (!block.classList.contains("cal-tg-drag")) { _calNoDragHint(event, Number(block.dataset.line)); return; }
          const mode = event.target.closest(".cal-tg-resize") ? "resize" : "move";
          _calArm(event, ev => _calStartBlockDrag(ev, cols, block, mode));
        } else if (event.target.classList.contains("cal-tg-col")) {
          const col = event.target;
          _calArm(event, ev => _calStartCreateDrag(ev, cols, col));
        }
      });
    }
    function _calColAt(cols, clientX) {
      const list = [...cols.querySelectorAll(".cal-tg-col")];
      const rect = cols.getBoundingClientRect();
      const idx = Math.max(0, Math.min(list.length - 1, Math.floor((clientX - rect.left) / rect.width * list.length)));
      return {list, idx, width: rect.width / list.length};
    }
    function _calDayAtPoint(x, y) {
      for (const el of document.elementsFromPoint(x, y)) {
        const cell = el.closest && el.closest("[data-calendar-day]");
        if (cell) return cell.dataset.calendarDay;
      }
      return null;
    }
    function _calRun(event, onMove, onEnd) {
      const move = e => onMove(e);
      const block = e => e.preventDefault();
      let finished = false;
      const finish = (e, commit) => {
        if (finished) return;
        finished = true;
        document.removeEventListener("pointermove", move, true);
        document.removeEventListener("pointerup", up, true);
        document.removeEventListener("pointercancel", cancel, true);
        document.removeEventListener("keydown", key, true);
        document.removeEventListener("touchmove", block, true);
        document.removeEventListener("contextmenu", block, true);
        onEnd(e, commit);
      };
      const up = e => finish(e, true);
      const cancel = e => finish(e, false);
      const key = e => { if (e.key === "Escape") { e.stopPropagation(); finish(e, false); } };
      document.addEventListener("pointermove", move, true);
      document.addEventListener("pointerup", up, true);
      document.addEventListener("pointercancel", cancel, true);
      document.addEventListener("keydown", key, true);
      if (event.touch) {
        document.addEventListener("touchmove", block, {capture: true, passive: false});
        document.addEventListener("contextmenu", block, true);
      }
      event.preventDefault();
    }
    function _calStartCreateDrag(event, cols, col) {
      const list = [...cols.querySelectorAll(".cal-tg-col")];
      const rect = col.getBoundingClientRect();
      const toMin = y => Math.max(0, Math.min(24 * 60, (y - rect.top) / CAL_HOUR_PX * 60));
      const startIdx = list.indexOf(col);
      const startMin = Math.floor(toMin(event.clientY) / CAL_SNAP_MINUTES) * CAL_SNAP_MINUTES;
      const startX = event.clientX;
      const startY = event.clientY;
      let endIdx = startIdx;
      let endMin = Math.min(24 * 60, startMin + 60);
      let moved = false;
      let ghosts = [];
      const range = () => {
        let a = [startIdx, startMin];
        let b = [endIdx, endMin];
        if (b[0] < a[0] || (b[0] === a[0] && b[1] < a[1])) [a, b] = [b, a];
        if (a[0] === b[0] && b[1] - a[1] < CAL_SNAP_MINUTES) b = [b[0], Math.min(24 * 60, a[1] + CAL_SNAP_MINUTES)];
        return [a, b];
      };
      const paint = () => {
        ghosts.forEach(g => g.remove());
        ghosts = [];
        const [a, b] = range();
        for (let i = a[0]; i <= b[0]; i++) {
          const g = document.createElement("div");
          g.className = "cal-tg-ghost";
          const from = i === a[0] ? a[1] : 0;
          const to = i === b[0] ? b[1] : 24 * 60;
          g.style.top = `${from / 60 * CAL_HOUR_PX}px`;
          g.style.height = `${Math.max(CAL_SNAP_MINUTES, to - from) / 60 * CAL_HOUR_PX}px`;
          if (i === a[0]) g.textContent = `${_calFmtMin(a[1])} – ${_calFmtMin(b[1])}`;
          list[i].appendChild(g);
          ghosts.push(g);
        }
      };
      if (event.touch) paint();
      _calRun(event, e => {
        if (Math.abs(e.clientY - startY) > 4 || Math.abs(e.clientX - startX) > 4) moved = true;
        if (!moved) return;
        endIdx = _calColAt(cols, e.clientX).idx;
        endMin = _calSnap(toMin(e.clientY));
        paint();
      }, (_e, commit) => {
        ghosts.forEach(g => g.remove());
        if (!commit) return;
        if (!moved) { endIdx = startIdx; endMin = Math.min(24 * 60, startMin + 60); }
        const [a, b] = range();
        calCreateAt(list[a[0]].dataset.calendarDay, a[1], b[1], list[b[0]].dataset.calendarDay);
      });
    }
    function _calStartAllDayCreate(event, cell, createOnClick) {
      const startDay = cell.dataset.calendarDay;
      let endDay = startDay;
      let moved = false;
      const sx = event.clientX;
      const sy = event.clientY;
      const ordered = () => (startDay <= endDay ? [startDay, endDay] : [endDay, startDay]);
      const clear = () => document.querySelectorAll(".cal-drop").forEach(n => n.classList.remove("cal-drop"));
      const mark = () => {
        clear();
        const [a, b] = ordered();
        document.querySelectorAll(".cal-cell[data-calendar-day], .cal-tg-allday-cell[data-calendar-day]").forEach(n => {
          const d = n.dataset.calendarDay;
          if (d >= a && d <= b) n.classList.add("cal-drop");
        });
      };
      if (event.touch) mark();
      _calRun(event, e => {
        if (Math.hypot(e.clientX - sx, e.clientY - sy) > 4) moved = true;
        if (!moved) return;
        const d = _calDayAtPoint(e.clientX, e.clientY);
        if (d) endDay = d;
        mark();
      }, (_e, commit) => {
        clear();
        if (!commit) return;
        if (moved) _calSuppressClickUntil = performance.now() + 400;
        else if (!createOnClick && !event.touch) return;
        const [a, b] = ordered();
        calCreateAllDay(a, b);
      });
    }
    function calCreateAllDay(first, last) {
      const days = [];
      const cur = new Date(first + "T00:00:00");
      const stop = new Date(last + "T00:00:00");
      while (cur <= stop && days.length < 366) {
        days.push(_fmtDate(cur));
        cur.setDate(cur.getDate() + 1);
      }
      _calOpenCreate(days.map(d => `on:${d}`).join("\n"));
    }
    function calCreateAt(day, startMin, endMin, endDay) {
      _calOpenCreate(`from:${day}T${_calFmtMin(startMin)}\nto:${endDay || day}T${_calFmtMin(endMin)}`);
    }
    function _calOpenCreate(details) {
      newItem();
      document.getElementById("edit-type").value = "E";
      document.getElementById("edit-details").value = details;
      const note = document.getElementById("editor-note");
      if (note) note.textContent = t("Create a new record. The field(s) below were prefilled from your current context — review, edit, or remove them before creating.");
      const title = document.getElementById("edit-title");
      if (title) title.focus();
    }
    function _calStartBlockDrag(event, cols, block, mode) {
      const record = _calGridRecords.get(Number(block.dataset.line));
      if (!record) return;
      const info = _calDragInfo({record, when: block.dataset.when});
      if (!info || (mode === "resize" && !info.resize)) return;
      const details = record.details || {};
      const mins = [].concat(...info.keys.map(k => details[k].map(_calMinOf)));
      const lo = Math.min(...mins);
      const hi = Math.max(...mins);
      const toMin = info.resize ? _calMinOf(details.to[0]) : 0;
      const startY = event.clientY;
      const origCol = _calColAt(cols, event.clientX).idx;
      const origHeight = block.offsetHeight;
      const colWidth = _calColAt(cols, event.clientX).width;
      let dMin = 0;
      let colIdx = origCol;
      let moved = false;
      block.classList.add("cal-tg-dragging");
      _calRun(event, e => {
        const idx = _calColAt(cols, e.clientX).idx;
        if (Math.abs(e.clientY - startY) > 4 || (mode === "move" && idx !== origCol)) moved = true;
        if (!moved) return;
        dMin = _calSnap((e.clientY - startY) / CAL_HOUR_PX * 60);
        if (mode === "move") {
          colIdx = idx;
          dMin = Math.max(-lo, Math.min(24 * 60 - 1 - hi, dMin));
          block.style.transform = `translate(${(colIdx - origCol) * colWidth}px, ${dMin / 60 * CAL_HOUR_PX}px)`;
        } else {
          dMin = Math.max(-toMin, Math.min(24 * 60 - 1 - toMin, dMin));
          block.style.height = `${Math.max(14, origHeight + dMin / 60 * CAL_HOUR_PX)}px`;
        }
      }, (_e, commit) => {
        block.classList.remove("cal-tg-dragging");
        block.style.transform = "";
        if (!moved) return;
        _calSuppressClickUntil = performance.now() + 400;
        const days = mode === "move" ? colIdx - origCol : 0;
        if (!commit || (dMin === 0 && days === 0)) { block.style.height = `${origHeight}px`; return; }
        _calSaveDrag(record, _calShiftDetails(record, info, days, dMin, mode));
      });
    }
    function _calStartChipDrag(event, chip) {
      const record = _calGridRecords.get(Number(chip.dataset.line));
      if (!record) return;
      const info = _calDragInfo({record, when: chip.dataset.when});
      if (!info) return;
      const downDay = _calDayAtPoint(event.clientX, event.clientY);
      if (!downDay) return;
      const sx = event.clientX;
      const sy = event.clientY;
      let moved = false;
      let target = null;
      let ghost = null;
      const clearTarget = () => document.querySelectorAll(".cal-drop").forEach(n => n.classList.remove("cal-drop"));
      _calRun(event, e => {
        if (!moved && Math.hypot(e.clientX - sx, e.clientY - sy) < 5) return;
        if (!moved) {
          moved = true;
          chip.classList.add("cal-chip-dragging");
          ghost = document.createElement("div");
          ghost.className = "cal-chip-ghost";
          ghost.textContent = record.title;
          document.body.appendChild(ghost);
        }
        ghost.style.left = `${e.clientX + 10}px`;
        ghost.style.top = `${e.clientY + 10}px`;
        clearTarget();
        target = _calDayAtPoint(e.clientX, e.clientY);
        if (target) {
          const cell = document.querySelector(`[data-calendar-day="${target}"]`);
          if (cell) cell.classList.add("cal-drop");
        }
      }, (_e, commit) => {
        chip.classList.remove("cal-chip-dragging");
        clearTarget();
        if (ghost) ghost.remove();
        if (!moved) return;
        _calSuppressClickUntil = performance.now() + 400;
        if (!commit || !target || target === downDay) return;
        const days = Math.round((Date.parse(target + "T00:00:00Z") - Date.parse(downDay + "T00:00:00Z")) / 86400000);
        _calSaveDrag(record, _calShiftDetails(record, info, days, 0, "move"));
      });
    }
    async function _calSaveDrag(record, details) {
      if (record.repeat_rule && !window.confirm(t("This is a repeating record. The change applies to all occurrences. Continue?"))) {
        loadCalendar();
        return;
      }
      try {
        await api(`/api/items/${record.line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({status: record.status, type: record.type, title: record.title, details}),
        });
        showToast(t("Event updated."), "success");
      } catch (error) {
        showToast(error.status === 409
          ? t("This record changed elsewhere. The calendar was reloaded; try again.")
          : (error.message || t("Update failed.")), "error");
      }
      loadCalendar();
    }
