      await refreshAll();
    }
    function _agendaMatchWhen(match, fallbackWhen) {
      if (!match) return fallbackWhen || "";
      if (match.end !== undefined && match.end !== "") return `${match.start}..${match.end}`;
      if (match.end === "") return `${match.start}..`;
      return match.start || fallbackWhen || "";
    }
    // Expand a record into one entry per in-window match, mirroring
    // _tlRecordEntries/_calRecordDayPlacements: record.matches is the
    // authoritative per-occurrence list (already clipped server-side to the
    // requested range), so a multi-day on: span or a repeat habit with
    // several occurrences inside the visible range shows one row per
    // occurrence instead of collapsing to matches[0]. A record with no
    // matches array falls back to a single entry, same as before.
    function _agendaRecordEntries(record) {
      const matches = record.matches && record.matches.length ? record.matches : [null];
      const total = matches.length;
      return matches.map((match, i) => ({
        record,
        match,
        when: _agendaMatchWhen(match, record.when),
        matchIndex: i + 1,
        matchTotal: total,
      }));
    }
    async function loadAgenda() {
      const params = query();
      const agendaParams = new URLSearchParams();
      for (const key of ["from", "to", "around", "window", "status", "kind", "type", "project", "tag", "tag_all", "exclude_tag", "user", "team", "person", "owner", "assignee", "attendee", "sender", "recipient", "text", "q", "limit"]) {
        if (params.has(key)) agendaParams.set(key, params.get(key));
      }
      if (!agendaParams.has("around") && !agendaParams.has("from")) agendaParams.set("around", "now");
      if (!agendaParams.has("window")) agendaParams.set("window", "1d");
      if (document.getElementById("open-only").checked || boolParam(params, ["open", "open_only"])) {
        agendaParams.set("open_only", "true");
      }
      const blockedMode = agendaBlockedMode();
      if (blockedMode) agendaParams.set("blocked", blockedMode);
      _syncAgendaBlockedBtn(blockedMode);
      const data = await api(`/api/agenda?${agendaParams}`);
      const node = document.getElementById("agenda");
      const entries = (data.records || [])
        .flatMap(record => _agendaRecordEntries(record))
        .sort((a, b) => String(a.when || "").localeCompare(String(b.when || "")));
      node.innerHTML = entries.length ? "" : guidedEmptyState("📅", "Nothing scheduled in this range",
        "Agenda shows records with <code>due</code>, <code>do</code>, <code>from</code>/<code>to</code>, or <code>on</code> dates. Add a dated record or widen the range.",
        [["Today", "agendaToday"], ["7 days", "agendaWeek"], ["New record", "newItem"], ["Help", "help"]]);
      const agendaLimitRaw = firstParam(query(), ["agenda_limit"], "8");
      const maxAgenda = Number(agendaLimitRaw);
      const unlimitedAgenda = agendaLimitRaw === "0" || maxAgenda === 0;
      const limit = unlimitedAgenda ? Infinity : (Number.isFinite(maxAgenda) && maxAgenda > 0 ? maxAgenda : 8);
      const shown = unlimitedAgenda ? entries : entries.slice(0, limit);
      for (const entry of shown) {
        const record = entry.record;
        const match = entry.match;
        const dueCls = agendaDueSoonClass(record);
        const borderStyle = dueCls === "overdue" ? "border-left:3px solid #c0392b;" : dueCls === "due-soon" ? "border-left:3px solid #e67e22;" : "";
        const occIndex = match && match.occurrence_index !== undefined ? match.occurrence_index : record.occurrence_index;
        const repeatRule = match && match.repeat !== undefined ? match.repeat : record.repeat_rule;
        const occ = (occIndex !== undefined || repeatRule)
          ? `<span class="occurrence-badge" title="${escapeHtml(repeatRule || entry.when || "")}">occ #${escapeHtml(String(occIndex || 1))}</span>`
          : "";
        // A record with more than one in-window match gets a small X/Y
        // badge, matching Timeline's cal-entry-span-style treatment, so the
        // separate rows read as one record rather than duplicates.
        const spanBadge = entry.matchTotal > 1
          ? `<span class="occurrence-badge" title="Occurrence ${entry.matchIndex} of ${entry.matchTotal} in this range">${entry.matchIndex}/${entry.matchTotal}</span>`
          : "";
        const blockedBadge = record.blocked
          ? `<span class="blocked-badge" title="Blocked by: ${escapeHtml((record.blocked_by || []).map(b => b.title || b.id).join(", "))}">⚡ blocked</span>`
          : "";
        const source = record.source_id ? `<div class="meta">source: ${escapeHtml(record.source_id)}</div>` : "";
        const countdown = agendaCountdownLabel({status: record.status, occurrence_start: entry.when});
        node.insertAdjacentHTML(
          "beforeend",
          `<div style="${borderStyle}padding-left:.45rem"><span class="pill">${escapeHtml(entry.when)}</span>${occ}${spanBadge}${blockedBadge}${countdown}<div class="title">${escapeHtml(record.title)}</div>${source}</div>`
        );
      }
      if (!unlimitedAgenda && entries.length > limit) {
        const remaining = entries.length - limit;
        node.insertAdjacentHTML(
          "beforeend",
          `<div style="padding:.3rem .45rem"><a href="#" class="drawer-link" onclick="event.preventDefault();setAgendaLimit(0)">View all ${entries.length} (${remaining} more)</a></div>`
        );
      }
      updateAgendaOverdueBadge(data.records);
    }
    // ── Presence rendering (Status & Team views) ───────────────────
    const PRESENCE_RULES = [
      [/^(available|free|online|in|open|active|here|present)$/, "p-available"],
      [/^(busy|meeting|call|working|occupied|class|lecture)$/, "p-busy"],
      [/^(focus|dnd|do[-_ ]?not[-_ ]?disturb|deep[-_ ]?work)$/, "p-focus"],
      [/^(away|afk|lunch|break|brb|idle|errand)$/, "p-away"],
      [/^(out|off|offline|gone|vacation|holiday|sick|absent|left)$/, "p-off"],
    ];
    function presenceClass(state, active) {
      if (active === false) return "p-off";
      const s = String(state || "").toLowerCase().trim();
      // Config-defined overrides (web.presence.states) win over built-in rules
      // so teams can recolor states without code changes.
      const overrides = appConfig?.web?.presence || {};
      if (overrides[s]) return overrides[s];
      for (const [re, cls] of PRESENCE_RULES) if (re.test(s)) return cls;
      return "p-unknown";
    }
    function presenceDot(record) {
      const cls = presenceClass(record.state, record.active);
      const label = record.active === false ? "ended" : (record.state || "unknown");
      return `<span class="presence-dot ${cls}" role="img" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}"></span>`;
    }
    function presenceCard(record, extraHtml = "") {
      const cls = presenceClass(record.state, record.active);
      const started = record.from ? relativeTime(record.from) : "";
      const stateLabel = record.active === false
        ? (record.state ? `${record.state} · ended` : "ended")
        : (record.state || "—");
      return `<div class="person-card${record.active === false ? " presence-ended" : ""}">` +
        `<div class="person-head">${presenceDot(record)}` +
        `<span class="person-name">${escapeHtml(record.person)}</span>` +
        `<span class="presence-state-badge ${cls}">${escapeHtml(stateLabel)}</span></div>` +
        (record.title ? `<div class="person-status-title">${escapeHtml(record.title)}</div>` : "") +
        `<div class="person-meta">` +
        (record.from ? `<span title="${escapeHtml(record.from)}">started ${escapeHtml(started || record.from)}</span>` : "") +
        (record.to ? `<span title="${escapeHtml(record.to)}">until ${escapeHtml(record.to.replace("T", " "))}</span>` : "") +
        (record.service ? `<span class="pill">${escapeHtml(record.service)}</span>` : "") +
        `</div>` + extraHtml + `</div>`;
    }
    function openPersonItems(person) {
      const params = query();
      params.delete("mode");
      params.delete("view");
      params.delete("workspace");
      params.delete("panel");
      params.delete("person");
      params.delete("assignee");
      params.delete("sender");
      params.delete("recipient");
      params.set("user", String(person || ""));
      params.set("open_only", "true");
      if (!params.has("sort")) params.set("sort", "time");
      if (!params.has("order")) params.set("order", "asc");
      history.pushState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadItems();
    }
    function toggleStatusActive() {
      const params = query();
      const activeOnly = firstParam(params, ["active"], "true") !== "false";
      params.set("active", activeOnly ? "false" : "true");
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadStatus();
    }
    async function loadStatus() {
      const params = query();
      const statusParams = new URLSearchParams();
      const activeOnly = firstParam(params, ["active"], "true") !== "false";
      statusParams.set("active", activeOnly ? "true" : "false");
      if (params.has("person")) statusParams.set("person", params.get("person"));
      const btn = document.getElementById("status-active-btn");
      if (btn) btn.textContent = activeOnly ? "● Active only" : "◌ All latest";
      const data = await api(`/api/status?${statusParams}`);
      const node = document.getElementById("status");
      if (!data.records.length) {
        node.innerHTML = guidedEmptyState("👥", `No ${activeOnly ? "active " : ""}status records`,
          "Presence comes from <code>S</code> records like<br><code>[/] S Working from:2026-07-07T09:00 state:busy person:alice</code>",
          (activeOnly
            ? [["Show all latest", "toggleStatusActive"], ["Team board", "team"], ["New record", "newItem"]]
            : [["Team board", "team"], ["New record", "newItem"], ["Help", "help"]]));
        return;
      }
      node.innerHTML = `<div class="status-grid">` + data.records.map(r => presenceCard(r)).join("") + `</div>`;
    }

    // ── Team board (presence + messages + workload) ────────────────
    function orderTeamRecords(records) {
      // Pinned people first (web.team.pin order), then a configured order
      // (web.team.order), then the rest alphabetically by person name.
      const pin = (appConfig?.web?.team?.pin || []).map(s => String(s).toLowerCase());
      const order = (appConfig?.web?.team?.order || []).map(s => String(s).toLowerCase());
      const rank = (person) => {
        const p = String(person || "").toLowerCase();
        const pinIdx = pin.indexOf(p);
        if (pinIdx >= 0) return [0, pinIdx, ""];
        const orderIdx = order.indexOf(p);
        if (orderIdx >= 0) return [1, orderIdx, ""];
        return [2, 0, p];
      };
      return records.slice().sort((a, b) => {
        const ra = rank(a.person), rb = rank(b.person);
        if (ra[0] !== rb[0]) return ra[0] - rb[0];
        if (ra[1] !== rb[1]) return ra[1] - rb[1];
        return ra[2].localeCompare(rb[2]);
      });
    }
    async function loadTeam() {
      const board = document.getElementById("team-board");
      if (!board) return;
      let statusData = {records: []}, msgs = [], openItems = [];
      try {
        [statusData, msgs, openItems] = await Promise.all([
          api("/api/status?active=false"),
          api("/api/messages?open_only=true&sort=time&order=desc").then(d => d.items || []).catch(() => []),
          api("/api/items?open_only=true").then(d => d.items || []).catch(() => []),
        ]);
      } catch(e) {
        board.innerHTML = `<div class="diagnostic">Team board error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      const records = orderTeamRecords(statusData.records || []);
      if (!records.length) {
        board.innerHTML = guidedEmptyState("🟢", "No presence records yet",
          "Add a status record like<br><code>[/] S Working from:2026-07-07T09:00 state:busy person:alice</code><br>to put people on the board.",
          [["Status view", "status"], ["New record", "newItem"], ["Help", "help"]]);
        return;
      }
      const msgsFor = (person) => msgs.filter(m =>
        (m?.details?.recipient || []).map(String).includes(person)).slice(0, 3);
      const workloadFor = (person) => {
        const mine = openItems.filter(i => (i?.details?.assignee || []).map(String).includes(person));
        return {open: mine.length, overdue: mine.filter(i => itemDueSoonClass(i) === "overdue").length};
      };
      board.innerHTML = records.map(record => {
        const w = workloadFor(record.person);
        const personMsgs = msgsFor(record.person);
        let extra = "";
        if (w.open || w.overdue) {
          extra += `<div class="person-workload"><span class="pill">○ ${w.open} open</span>` +
            (w.overdue ? `<span class="pill" style="color:var(--danger)">⚠ ${w.overdue} overdue</span>` : "") +
            `</div>`;
        }
        if (personMsgs.length) {
          extra += `<div class="person-msgs">` + personMsgs.map(m =>
            `<div class="person-msg" onclick="openItemByLine(${Number(m.line)})" title="${escapeHtml(m.title)}">` +
            `<span aria-hidden="true">💬</span>` +
            `<span class="person-msg-title">${escapeHtml(m.title)}</span>` +
            `<span class="review-num" style="margin-left:auto">${escapeHtml(String(m?.details?.sender?.[0] || ""))}</span>` +
            `</div>`).join("") + `</div>`;
        }
        extra += `<div class="person-card-actions"><button type="button" class="secondary person-card-action" onclick="openPersonItems(${escapeHtml(jsLiteral(record.person))})">View items</button></div>`;
        return presenceCard(record, extra);
      }).join("");
    }

    // ── Timeline view (chronological board with a now line) ────────
    let timelineRange = "today";
    let _timelineNowTimer = null;
    const TIMELINE_RANGES = new Set(["today", "24h", "week"]);
    function syncTimelineRange(range) {
      timelineRange = TIMELINE_RANGES.has(range) ? range : "today";
      document.querySelectorAll(".timeline-section .tl-controls .review-range-btn").forEach(btn =>
        btn.classList.toggle("active", btn.dataset.range === timelineRange));
    }
    function setTimelineRange(range) {
      syncTimelineRange(range);
      const params = query();
      params.set("view", "timeline");
      params.delete("mode");
      params.set("range", timelineRange);
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadTimeline();
    }
    function _tlIso(d) {
      const p = (n) => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
    }
    function _tlComparable(value, endOfDay = false) {
      const text = String(value || "");
      if (!text) return "";
      if (text.length > 10) return text;
      return text + (endOfDay ? "T23:59" : "T00:00");
    }
    function _tlDisplayInfo(match, fallbackWhen, rangeStart, rangeEnd) {
      const originalStart = match?.start || fallbackWhen || "";
      const originalEnd = match?.end || "";
      const rangeStartIso = _tlComparable(rangeStart, false);
      const rangeEndIso = _tlComparable(rangeEnd, true);
      let when = originalStart || fallbackWhen || "";
      let clipped = false;
      if (originalStart && rangeStartIso && _tlComparable(originalStart, false) < rangeStartIso) {
        when = rangeStartIso;
        clipped = true;
      }
      if (when && rangeEndIso && _tlComparable(when, false) > rangeEndIso) {
        when = rangeEndIso;
      }
      return {when, originalStart, originalEnd, clipped};
    }
    // Expand a record into one entry per in-window match, mirroring
    // _calRecordDayPlacements: record.matches is the authoritative
    // per-occurrence list (already clipped server-side to the requested
    // range by agenda.py's item_time_matches), so a multi-day on: span or a
    // repeat habit with several occurrences inside the visible range shows
    // one row per occurrence instead of collapsing to matches[0]. A record
    // with no matches array falls back to a single entry, same as before.
    function _tlRecordEntries(record, rangeStart, rangeEnd) {
      const matches = record.matches && record.matches.length ? record.matches : [null];
      const total = matches.length;
      return matches.map((match, i) => ({
        record,
        match,
        display: _tlDisplayInfo(match, record.occurrence_start || record.when, rangeStart, rangeEnd),
        matchIndex: i + 1,
        matchTotal: total,
      }));
    }
    function _tlNowLine() {
      const now = new Date();
      const p = (n) => String(n).padStart(2, "0");
      return `<div class="tl-now" aria-label="Current time"><span class="tl-now-label">${p(now.getHours())}:${p(now.getMinutes())}</span><span class="tl-now-line"></span></div>`;
    }
    function syncTimelineNowTimer() {
      if (_timelineNowTimer) {
        clearInterval(_timelineNowTimer);
        _timelineNowTimer = null;
      }
      if (currentView() !== "timeline") return;
      _timelineNowTimer = setInterval(() => {
        const node = document.getElementById("timeline");
        if (!node || !document.body.contains(node)) return;
        loadTimeline();
      }, 60000);
    }
    function _timelineEmptyState(range, label, from, to) {
      const title = range === "today"
        ? "No dated records today"
        : range === "24h"
          ? "No dated records in the next 24 hours"
          : "No dated records this week";
      const hint = "Timeline only shows records with due:, do:, from:/to:, at:, on:, or notify_at: values inside the selected range.";
      const suggestions = `<div class="tl-empty-suggestions">` +
        `<div>Try adding <code>due:${escapeHtml(from)}</code>, <code>from:${escapeHtml(from)}T09:00</code>, or <code>notify_at:${escapeHtml(from)}T09:00</code>.</div>` +
        `<div>If you expected records here, widen the range or check whether the record has a dated detail key.</div>` +
        `</div>`;
      const actions = range === "today"
        ? `<button type="button" onclick="setTimelineRange('24h')">Next 24h</button><button type="button" class="secondary" onclick="setTimelineRange('week')">This week</button>`
        : range === "24h"
          ? `<button type="button" onclick="setTimelineRange('week')">This week</button><button type="button" class="secondary" onclick="setTimelineRange('today')">Today</button>`
          : `<button type="button" onclick="setTimelineRange('today')">Today</button><button type="button" class="secondary" onclick="switchWorkspace('')">Go to Items</button>`;
      return `<div class="empty-state"><div class="empty-icon" aria-hidden="true">🕒</div>` +
        `<div class="empty-title">${escapeHtml(title)}</div>` +
        `<div class="empty-hint">${escapeHtml(hint)}</div>` +
        suggestions +
        `<div class="tl-empty-range">${escapeHtml(label)} / ${escapeHtml(from)} - ${escapeHtml(to)}</div>` +
        `<div class="tl-empty-actions">${actions}</div></div>`;
    }
    function _timelineQuietBanner(range) {
      if (range !== "today") return "";
      return `<div class="empty-state tl-now-stale" style="margin-bottom:.7rem">` +
        `<div class="empty-title">No upcoming records left today</div>` +
        `<div class="empty-hint">The rows below are earlier records from today. Switch to Next 24h or Week to see what is coming next.</div>` +
        `<div class="tl-empty-actions"><button type="button" onclick="setTimelineRange('24h')">Next 24h</button>` +
        `<button type="button" class="secondary" onclick="setTimelineRange('week')">This week</button>` +
        `<button type="button" class="secondary" onclick="newItem()">New record</button></div></div>`;
    }
    function _tlRow(record, nowIso, displayInfo, match, matchIndex, matchTotal) {
      const when = String(displayInfo?.when || record.when || "");
      const timed = when.length > 10;
      const time = timed ? when.slice(11, 16) : "all-day";
      const past = timed ? when < nowIso : when.slice(0, 10) < nowIso.slice(0, 10);
      const type = record.type || "N";
      const blockedBadge = record.blocked
        ? `<span class="blocked-badge" title="Blocked by: ${escapeHtml((record.blocked_by || []).map(b => b.title || b.id).join(", "))}">⚡ blocked</span>`
        : "";
      // Occurrence badge is sourced from this row's own match when one is
      // available (each repeat occurrence in matches carries its own
      // occurrence_index/repeat), falling back to the record-level
      // convenience fields for a record with no matches array.
      const occIndex = match && match.occurrence_index !== undefined ? match.occurrence_index : record.occurrence_index;
      const repeatRule = match && match.repeat !== undefined ? match.repeat : record.repeat_rule;
      const occ = (occIndex !== undefined || repeatRule)
        ? `<span class="occurrence-badge" title="${escapeHtml(repeatRule || displayInfo?.originalStart || "")}">occ #${escapeHtml(String(occIndex || 1))}</span>`
        : "";
      const ongoing = displayInfo?.clipped
        ? `<span class="occurrence-badge" title="Started ${escapeHtml(displayInfo.originalStart || record.when || "")}${displayInfo.originalEnd ? ` / until ${escapeHtml(displayInfo.originalEnd)}` : ""}">ongoing</span>`
        : "";
      // A record with more than one match inside the visible range (a
      // multi-day on: span, or several repeat occurrences) gets a small
      // X/Y badge so the separate rows read as one record, not several
      // unrelated same-title entries -- matches Calendar's cal-entry-span.
      const spanBadge = matchTotal > 1
        ? `<span class="occurrence-badge" title="Occurrence ${matchIndex} of ${matchTotal} in this range">${matchIndex}/${matchTotal}</span>`
        : "";
      const proj = record.details?.project?.[0]
        ? `<span class="pill">${escapeHtml(String(record.details.project[0]))}</span>` : "";
      const clickable = Number.isInteger(record.line);
      return `<div class="tl-row${past ? " tl-past" : ""}">` +
        `<div class="tl-time">${escapeHtml(time)}</div>` +
        `<div class="tl-rail"><span class="tl-node t-${escapeHtml(type)}"></span></div>` +
        `<div class="tl-card${clickable ? "" : " tl-static"}"${clickable ? ` onclick="openItemByLine(${record.line})"` : ""}>` +
        `<div class="tl-card-title">${escapeHtml(record.title)}</div>` +
        `<div class="tl-card-meta">` +
        `<span class="type-badge type-${escapeHtml(type)}" style="font-size:.66rem;padding:.05rem .35rem;min-height:auto">${escapeHtml(type)}</span>` +
        (record.status ? `<span>${escapeHtml(record.status)}</span>` : "") +
        `${proj}${blockedBadge}${occ}${ongoing}${spanBadge}</div></div></div>`;
    }
    async function loadTimeline() {
      const node = document.getElementById("timeline");
      if (!node) return;
      syncTimelineRange(firstParam(query(), ["range", "timeline_range"], timelineRange));
