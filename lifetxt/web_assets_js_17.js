      </div>`;
    }

    function _todaySubsection(title, rows, emptyText) {
      rows = rows || [];
      const body = rows.length
        ? rows.slice(0, TODAY_ROW_LIMIT).map(_todayRefRow).join("") +
          (rows.length > TODAY_ROW_LIMIT ? `<div class="dash-row empty">+${rows.length - TODAY_ROW_LIMIT} more</div>` : "")
        : `<div class="empty">${escapeHtml(emptyText)}</div>`;
      return `<div class="today-subsection"><div class="today-subsection-title">${escapeHtml(title)} (${rows.length})</div>${body}</div>`;
    }

    // Omitted entirely (no title, no wrapper) when empty, so the Status/
    // Presence and Events subsections cost zero space on a simple file --
    // only the shared command-center data decides whether they render.
    function _todayStatusSubsection(rows) {
      rows = rows || [];
      if (!rows.length) return "";
      const body = rows.slice(0, TODAY_ROW_LIMIT).map(row => {
        const since = row.since ? `<span class="pill">since ${escapeHtml(row.since)}</span>` : "";
        return `<div class="dash-row"><span class="dash-row-title">${escapeHtml(row.person || "self")}: ${escapeHtml(row.state || "")}</span>${since}</div>`;
      }).join("");
      return `<div class="today-subsection"><div class="today-subsection-title">Status (${rows.length})</div>${body}</div>`;
    }

    async function loadToday() {
      const dateEl = document.getElementById("today-date");
      let data;
      try {
        data = await api("/api/command-center");
      } catch (e) {
        const nowEl = document.getElementById("today-now");
        if (nowEl) nowEl.innerHTML = `<div class="diagnostic">Today error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      if (dateEl) {
        dateEl.textContent = data.reference_date
          ? new Date(data.reference_date + "T00:00:00").toLocaleDateString(undefined, {weekday: "long", month: "long", day: "numeric"})
          : "";
      }

      const nowEl = document.getElementById("today-now");
      if (nowEl) {
        nowEl.innerHTML =
          _todayStatusSubsection(data.now) +
          _todaySubsection("Today", data.today_events, "Nothing scheduled today.") +
          _todaySubsection("Due today", data.due_today, "Nothing due today.") +
          _todaySubsection("Next actions", data.next_actions, "Nothing actionable.") +
          _todaySubsection("Overdue", data.overdue, "Nothing overdue.");
      }

      const attentionEl = document.getElementById("today-attention");
      if (attentionEl) {
        const projects = data.project_attention || [];
        const projectRows = projects.slice(0, TODAY_ROW_LIMIT).map(p =>
          `<div class="dash-row"><span class="dash-row-title">${escapeHtml(p.display_name || p.name)}</span>` +
          `<span class="pill">${escapeHtml(p.health)}</span></div>`
        ).join("");
        const safety = data.safety || {};
        const safetyRow = safety.ok
          ? ""
          : `<div class="today-subsection"><div class="dash-row">` +
            `<span class="blocked-badge">${Number(safety.config_errors) || 0}</span>` +
            `<span class="dash-row-title">Configuration errors</span></div></div>`;
        attentionEl.innerHTML =
          _todaySubsection("Blocked", data.blocked, "Nothing blocked.") +
          _todaySubsection("Waiting", data.waiting, "Nothing waiting.") +
          _todaySubsection("Tickets", data.ticket_attention, "No tickets need attention.") +
          `<div class="today-subsection"><div class="today-subsection-title">Projects (${projects.length})</div>` +
          (projectRows || `<div class="empty">All projects green.</div>`) + `</div>` +
          safetyRow;
      }

      const inboxEl = document.getElementById("today-inbox");
      if (inboxEl) {
        const inbox = data.inbox || {};
        const pending = inbox.pending || [];
        const pendingRows = pending.slice(0, TODAY_ROW_LIMIT).map(p =>
          `<div class="dash-row"><span class="dash-row-title">${escapeHtml(p.summary || p.id || "")}</span>` +
          (p.source ? `<span class="pill">${escapeHtml(p.source)}</span>` : "") + `</div>`
        ).join("");
        const deferredLine = inbox.deferred_count
          ? `<div class="today-subsection"><div class="empty">deferred (${Number(inbox.deferred_count) || 0})</div></div>`
          : "";
        inboxEl.innerHTML =
          `<div class="today-subsection"><div class="today-subsection-title">Unified Inbox (${Number(inbox.pending_count) || 0})</div>` +
          (pendingRows || `<div class="empty">Inbox is empty.</div>`) + `</div>` +
          deferredLine +
          _todaySubsection("Messages", data.messages, "No unread messages.");
      }

      const upcomingEl = document.getElementById("today-upcoming");
      if (upcomingEl) {
        upcomingEl.innerHTML =
          _todaySubsection("Upcoming", data.upcoming, "Nothing upcoming.") +
          _todaySubsection("Habits", data.habits, "No open habits.");
      }
    }

    // ── Focus view (today's work, distraction-free) ────────────────
    async function loadFocus() {
      const listEl = document.getElementById("focus-list");
      if (!listEl) return;
      const dateEl = document.getElementById("focus-date");
      if (dateEl) dateEl.textContent = new Date().toLocaleDateString(undefined, {weekday: "long", month: "long", day: "numeric"});
      let items = [];
      try {
        items = (await api("/api/items?open_only=true")).items || [];
      } catch(e) {
        listEl.innerHTML = `<div class="diagnostic">Focus error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      const today = new Date(); today.setHours(0, 0, 0, 0);
      const detailDate = (item, keys) => {
        for (const key of keys) {
          const value = item?.details?.[key]?.[0];
          if (!value) continue;
          const d = new Date(value); if (isNaN(d)) continue;
          d.setHours(0, 0, 0, 0);
          return d;
        }
        return null;
      };
      // Reminders count at:/on: as their due date; tasks and deadlines use due: only.
      const dueKeysByType = {T: ["due"], D: ["due"], R: ["due", "at", "on"], H: ["due"]};
      const dueDiff = (item) => {
        const d = detailDate(item, dueKeysByType[item.type] || ["due"]);
        return d === null ? null : Math.round((d - today) / 86400000);
      };
      const workTypes = new Set(["T", "D", "R", "H"]);
      const overdue = [], dueToday = [], todayEvents = [], inProgress = [], anytimeReminders = [];
      for (const item of items) {
        if (item.type === "E") {
          const d = detailDate(item, ["from", "on", "at", "due"]);
          if (d && +d === +today) todayEvents.push(item);
          continue;
        }
        if (!workTypes.has(item.type)) continue;
        const diff = dueDiff(item);
        if (diff !== null && diff < 0) overdue.push(item);
        else if (diff === 0) dueToday.push(item);
        else if (item.status === "[/]") inProgress.push(item);
        else if (item.type === "R" && diff === null) anytimeReminders.push(item);
      }
      todayEvents.sort((a, b) =>
        String(a?.details?.from?.[0] || a?.details?.at?.[0] || "").localeCompare(
          String(b?.details?.from?.[0] || b?.details?.at?.[0] || "")));
      const groups = [
        {label: "⚠️ Overdue", items: overdue, cls: "focus-overdue"},
        {label: "📅 Due today", items: dueToday, cls: ""},
        {label: "🕑 Today's schedule", items: todayEvents, cls: ""},
        {label: "◑ In progress", items: inProgress, cls: ""},
        {label: "📌 Anytime reminders", items: anytimeReminders, cls: ""},
      ].filter(g => g.items.length);
      if (!groups.length) {
        listEl.innerHTML = `<div class="empty-state"><div class="empty-icon" aria-hidden="true">🎉</div>` +
          `<div class="empty-title">All clear</div>` +
          `<div class="empty-hint">Nothing overdue, due today, or in progress. Enjoy the calm — or pull something forward from Items.</div>` +
          `<button type="button" class="secondary" onclick="switchWorkspace('')">Open Items</button></div>`;
        return;
      }
      window._focusItems = groups.flatMap(g => g.items);
      const eventTime = (item) => {
        const value = String(item?.details?.from?.[0] || item?.details?.at?.[0] || "");
        const match = value.match(/T(\d{2}:\d{2})/);
        return match ? match[1] : "🕑";
      };
      let idx = 0;
      let html = "";
      for (const group of groups) {
        html += `<div class="focus-group-label ${group.cls}">${group.label} (${group.items.length})</div>`;
        for (const item of group.items) {
          const dueRel = buildDueRelLabel(item);
          const proj = item?.details?.project?.[0] ? `<span class="pill">${escapeHtml(item.details.project[0])}</span>` : "";
          const lead = item.type === "E"
            ? `<span class="focus-event-time pill">${escapeHtml(eventTime(item))}</span>`
            : `<button type="button" class="focus-check" title="${item.editable ? "Mark done" : "Read-only"}" ${item.editable ? `onclick="focusMarkDone(${idx})"` : "disabled"}></button>`;
          html += `<div class="focus-row${item.editable ? "" : " focus-readonly"}">` + lead +
            `<div class="focus-row-main" onclick="focusOpen(${idx})">` +
            `<div class="focus-row-title">${escapeHtml(item.title)}</div>` +
            `<div class="focus-row-meta">${proj}${dueRel}</div>` +
            `</div></div>`;
          idx++;
        }
      }
      listEl.innerHTML = html;
    }
    async function focusQuickAdd() {
      const input = document.getElementById("focus-quick-title");
      const title = (input?.value || "").trim();
      if (!title) return;
      const safe = /^[A-Za-z0-9_.\-]+$/.test(title)
        ? title
        : `"${title.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
      const line = `[ ] T ${safe} due:${_fmtDate(new Date())}`;
      try {
        await api("/api/items/raw", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line}),
        });
        input.value = "";
        showToast("Task added for today.", "success");
        await loadFocus();
      } catch(e) {
        showToast("Quick add failed: " + (e.message || e), "error");
      }
    }
    async function focusMarkDone(index) {
      const item = (window._focusItems || [])[index];
      if (!item || !item.editable) return;
      const line = item.line;
      const prevPayload = {status: item.status, type: item.type, title: item.title, details: item.details || {}};
      try {
        await api(`/api/items/${line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({...prevPayload, status: "[x]"}),
        });
        registerUndo(`Done: ${item.title}`, async () => {
          await api(`/api/items/${line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(prevPayload),
          });
        });
        await loadFocus();
      } catch(e) {
        showToast("Mark done failed: " + (e.message || e), "error");
      }
    }
    function focusOpen(index) {
      const item = (window._focusItems || [])[index];
      if (item) openDrawer(item);
    }

    // ── Review view (weekly/monthly retrospective) ────────────────
    let reviewRange = "week";
    function setReviewRange(range) {
      reviewRange = range;
      document.querySelectorAll("#review-range-bar .review-range-btn").forEach(btn =>
        btn.classList.toggle("active", btn.dataset.range === range));
      loadReview();
    }
    function setReviewCustom() {
      reviewRange = "custom";
      document.querySelectorAll("#review-range-bar .review-range-btn").forEach(btn =>
        btn.classList.remove("active"));
      loadReview();
    }
    function _reviewProjectParam() {
      const value = (document.getElementById("review-project")?.value || "").trim();
      return value ? `&project=${encodeURIComponent(value)}` : "";
    }
    function _reviewQuery() {
      const today = new Date();
      if (reviewRange === "week") return "week=true" + _reviewProjectParam();
      if (reviewRange === "last-week") {
        const dow = (today.getDay() + 6) % 7; // Monday-based weekday
        const monday = new Date(today); monday.setDate(today.getDate() - dow);
        const start = new Date(monday); start.setDate(monday.getDate() - 7);
        const end = new Date(monday); end.setDate(monday.getDate() - 1);
        return `from=${_fmtDate(start)}&to=${_fmtDate(end)}` + _reviewProjectParam();
      }
      const y = today.getFullYear(), m = today.getMonth();
      if (reviewRange === "month") return `month=${y}-${String(m + 1).padStart(2, "0")}` + _reviewProjectParam();
      if (reviewRange === "custom") {
        const start = (document.getElementById("review-from")?.value || "").trim();
        const end = (document.getElementById("review-to")?.value || "").trim();
        const parts = [];
        if (start) parts.push(`from=${encodeURIComponent(start)}`);
        if (end) parts.push(`to=${encodeURIComponent(end)}`);
        const project = _reviewProjectParam().replace(/^&/, "");
        if (project) parts.push(project);
        return parts.join("&") || "week=true";
      }
      const prev = new Date(y, m - 1, 1);
      return `month=${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, "0")}` + _reviewProjectParam();
    }
    async function loadReview() {
      const kpiEl = document.getElementById("review-kpis");
      if (!kpiEl) return;
      let data;
      try {
        data = await api(`/api/review?${_reviewQuery()}`);
      } catch(e) {
        kpiEl.innerHTML = `<div class="diagnostic">Review error: ${escapeHtml(e.message)}</div>`;
        return;
      }
      window._lastReviewData = data;
      const rangeEl = document.getElementById("review-range-label");
      if (rangeEl) rangeEl.textContent = data.range || "";
      const habitTitles = Object.keys(data.habits || {});
      const kpis = [
        {n: data.completed_tasks || 0, label: "Completed", icon: "✓", cls: "kpi-ok"},
        {n: data.open_tasks || 0, label: "Still open", icon: "○"},
        {n: data.journals || 0, label: "Journal entries", icon: "📓"},
        {n: habitTitles.length, label: "Habits tracked", icon: "🔁"},
      ];
      kpiEl.innerHTML = kpis.map(k =>
        `<div class="kpi-tile ${k.cls || ""}"><span class="kpi-icon" aria-hidden="true">${k.icon}</span>` +
        `<span class="kpi-n">${k.n}</span><span class="kpi-label">${escapeHtml(k.label)}</span></div>`
      ).join("");
      const doneEl = document.getElementById("review-completed");
      if (doneEl) {
        const completed = data.completed || [];
        doneEl.innerHTML = completed.length
          ? completed.map(t =>
              `<div class="dash-row">` +
              (t.done ? `<span class="pill">${escapeHtml(String(t.done).slice(0, 10))}</span>` : "") +
              (t.id
                ? `<button type="button" class="dash-row-title review-click" onclick="drawerNavigate(${escapeHtml(jsLiteral(t.id))})">${escapeHtml(t.title)}</button>`
                : `<span class="dash-row-title">${escapeHtml(t.title)}</span>`) +
              (t.project ? `<span class="pill">${escapeHtml(t.project)}</span>` : "") +
              `</div>`).join("")
          : `<div class="empty">No tasks completed in this range.</div>`;
      }
      const habitsEl = document.getElementById("review-habits");
      if (habitsEl) {
        habitsEl.innerHTML = habitTitles.length
          ? habitTitles.map(title => {
              const h = data.habits[title];
              const total = h.done + h.open;
              const cur = Number(h.current_streak || 0);
              const longest = Number(h.longest_streak || 0);
              const streak = (cur || longest)
                ? `<span class="review-streak" title="Current / longest consecutive-day streak">` +
                  `🔥 ${cur}d${longest > cur ? ` · best ${longest}d` : ""}</span>`
                : "";
              return `<div class="dash-row"><span class="dash-row-title">${escapeHtml(title)}</span>` +
                streak +
                `<span class="review-num">${h.done}/${total} (${h.completion_rate}%)</span>` +
                `<span class="review-habit-bar"><span style="width:${h.completion_rate}%"></span></span></div>`;
            }).join("")
          : `<div class="empty">No habit records in this range.</div>`;
      }
      const journalEl = document.getElementById("review-journal");
      if (journalEl) {
        const entries = data.journal_entries || [];
        const moods = data.mood_trend || [];
        const moodLine = moods.length
          ? `<div class="dash-row review-mood-row"><span class="review-num">Mood:</span>${moods.map(m =>
              `<span class="pill" title="${escapeHtml(m.date)}">${escapeHtml(m.mood)}</span>`).join("")}</div>`
          : "";
        journalEl.innerHTML = (entries.length || moods.length)
          ? moodLine + entries.map(e =>
              `<div class="dash-row"><span class="pill">${escapeHtml(e.date)}</span>` +
              `<div style="flex:1;min-width:0"><div class="dash-row-title">${escapeHtml(e.title)}</div>` +
              (e.excerpt ? `<div class="review-excerpt">${escapeHtml(e.excerpt)}</div>` : "") +
              `</div></div>`).join("")
          : `<div class="empty">No journal entries in this range.</div>`;
      }
      const elapsedEl = document.getElementById("review-elapsed");
      if (elapsedEl) {
        const rows = Object.entries(data.elapsed_by_project || {});
        elapsedEl.innerHTML = rows.length
          ? rows.map(([proj, elapsed]) =>
              `<div class="dash-row"><span class="dash-row-title">${escapeHtml(proj)}</span>` +
              `<span class="pill">${escapeHtml(elapsed)}</span></div>`).join("")
          : `<div class="empty">No elapsed time recorded.</div>`;
      }
    }
    function reviewMarkdown(data) {
      const lines = [
        "# life.txt Review",
        "",
        `Range: ${data?.range || ""}`,
        "",
        "## Summary",
        `- Completed tasks: ${data?.completed_tasks || 0}`,
        `- Open tasks: ${data?.open_tasks || 0}`,
        `- Journal entries: ${data?.journals || 0}`,
      ];
      const completed = data?.completed || [];
      if (completed.length) {
        lines.push("", "## Completed");
        for (const item of completed) {
          const bits = [];
          if (item.done) bits.push(`done:${item.done}`);
          if (item.project) bits.push(`project:${item.project}`);
          if (item.id) bits.push(`id:${item.id}`);
          lines.push(`- [x] ${item.title}${bits.length ? " (" + bits.join(", ") + ")" : ""}`);
        }
      }
      const habits = Object.entries(data?.habits || {});
      if (habits.length) {
        lines.push("", "## Habits");
        for (const [title, h] of habits) {
          const total = (Number(h.done) || 0) + (Number(h.open) || 0);
          lines.push(`- ${title}: ${h.done}/${total} (${h.completion_rate}%)`);
        }
      }
      const journals = data?.journal_entries || [];
      if (journals.length) {
        lines.push("", "## Journal");
        for (const entry of journals) {
          lines.push(`- ${entry.date} ${entry.title}${entry.excerpt ? " — " + entry.excerpt : ""}`);
        }
      }
      const elapsed = Object.entries(data?.elapsed_by_project || {});
      if (elapsed.length) {
        lines.push("", "## Elapsed");
        for (const [project, value] of elapsed) lines.push(`- ${project}: ${value}`);
      }
      return lines.join("\n");
    }
    function copyReviewMarkdown() {
      const data = window._lastReviewData;
      if (!data) { showToast("Load a review first.", "warning"); return; }
      navigator.clipboard.writeText(reviewMarkdown(data)).then(
        () => showToast("Review copied as Markdown.", "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    loadConfig().then(() => {
