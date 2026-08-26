      dashboard: {
        label: "Dashboard",
        description: "A compact overview of open work, agenda pressure, messages, and presence.",
        actions: [["Open agenda", "agenda"], ["Open focus", "focus"], ["Refresh", "refresh"]],
      },
      today: {
        label: "Today",
        description: "The Daily Command Center: what to do now, what needs attention, the Unified Inbox, and what is coming up.",
        actions: [["Dashboard", "dashboard"], ["Open agenda", "agenda"], ["Refresh", "refresh"]],
      },
      agenda: {
        label: "Agenda",
        description: "Review dated work in the selected range, including blocked and upcoming records.",
        actions: [["Today", "agendaToday"], ["7 days", "agendaWeek"], ["Refresh", "refresh"]],
      },
      timeline: {
        label: "Timeline",
        description: "See dated records on a chronological board with empty-range guidance.",
        actions: [["Today", "timelineToday"], ["Next 24h", "timeline24h"], ["Week", "timelineWeek"]],
      },
      calendar: {
        label: "Calendar",
        description: "Place due, do, and event records on a month or week grid; click any entry to open it.",
        actions: [["Today", "calToday"], ["Month", "calMonth"], ["Week", "calWeek"]],
      },
      focus: {
        label: "Focus",
        description: "Prioritize open, actionable work and reduce noisy context while planning.",
        actions: [["Open tasks", "openTasks"], ["New record", "newItem"], ["Refresh", "refresh"]],
      },
      review: {
        label: "Review",
        description: "Summarize completed, carried, blocked, and planned work for a chosen period.",
        actions: [["This week", "reviewWeek"], ["Copy Markdown", "copyReview"], ["Refresh", "refresh"]],
      },
      messages: {
        label: "Messages",
        description: "Filter message records and manage notification-oriented conversations.",
        actions: [["New message", "newMessage"], ["Notifications", "notifications"], ["Clear filters", "clearFilters"]],
      },
      team: {
        label: "Team",
        description: "Combine presence, open workload, and recent messages per person.",
        actions: [["Status view", "status"], ["Messages", "messages"], ["Refresh", "refresh"]],
      },
      status: {
        label: "Status",
        description: "Show the latest presence state for each person or active status records only.",
        actions: [["Active only", "toggleStatusActive"], ["Team board", "team"], ["Refresh", "refresh"]],
      },
      notifications: {
        label: "Notifications",
        description: "Review pending notification records, acknowledge them, or request browser alerts.",
        actions: [["Enable alerts", "enableNotifications"], ["Messages", "messages"], ["Refresh", "refresh"]],
      },
      stats: {
        label: "Statistics",
        description: "Inspect charted trends for tasks, projects, messages, and journal fields.",
        actions: [["Refresh charts", "refreshCharts"], ["Dashboard", "dashboard"]],
      },
      graph: {
        label: "Graph",
        description: "Explore dependencies, references, parent-child links, and related records.",
        actions: [["Refresh graph", "refreshGraph"], ["Items", "items"]],
      },
      display: {
        label: "Display",
        description: "Read-focused wall display mode with editing controls hidden.",
        actions: [["Exit display", "items"]],
      },
      kiosk: {
        label: "Kiosk",
        description: "Always-on display mode with automatic refresh and compact controls.",
        actions: [["Exit kiosk", "items"]],
      },
    };
    const VIEW_ACTIONS = {
      newItem: () => newItem(),
      quickAdd: () => toggleQuickAdd(true),
      setStatus: () => togglePresence(true),
      endStatus: () => endPresence(),
      clearFilters: () => clearAllFilters(),
      refresh: () => triggerRefresh(),
      items: () => switchWorkspace(""),
      dashboard: () => switchWorkspace("dashboard"),
      today: () => switchWorkspace("today"),
      agenda: () => switchWorkspace("agenda"),
      focus: () => switchWorkspace("focus"),
      review: () => switchWorkspace("review"),
      messages: () => switchWorkspace("messages"),
      team: () => switchWorkspace("team"),
      status: () => switchWorkspace("status"),
      notifications: () => switchWorkspace("notifications"),
      agendaToday: () => setAgendaQuickRange("today"),
      agendaWeek: () => setAgendaQuickRange("7d"),
      timelineToday: () => setTimelineRange("today"),
      timeline24h: () => setTimelineRange("24h"),
      timelineWeek: () => setTimelineRange("week"),
      calendar: () => switchWorkspace("calendar"),
      calToday: () => calToday(),
      calMonth: () => setCalMode("month"),
      calWeek: () => setCalMode("week"),
      openTasks: () => openTaskItems(),
      reviewWeek: () => setReviewRange("week"),
      copyReview: () => copyReviewMarkdown(),
      newMessage: () => {
        newItem();
        setTimeout(() => {
          const type = document.getElementById("edit-type");
          if (type) type.value = "M";
          updateTypeHints("M");
        }, 0);
      },
      toggleStatusActive: () => toggleStatusActive(),
      enableNotifications: () => enableBrowserNotifications(),
      refreshCharts: () => refreshStatsView(),
      refreshGraph: () => loadGraphPanel(),
      help: () => openHelpModal(),
      stats: () => switchWorkspace("stats"),
      graph: () => switchWorkspace("graph"),
    };
    const VIEW_HELP = {
      dashboard: "Dashboard: overview KPI tiles, attention list, completions, and project progress.",
      "": "Items: searchable record list with filters, grouping, edit modal, bulk actions, and exports.",
      agenda: "Agenda: date-range list for due, do, at, from/to, on, and notify_at records.",
      timeline: "Timeline: chronological board for today, next 24 hours, or week with an updated now line.",
      calendar: "Calendar: month/week grid of dated records; click a day for Agenda or an entry for details.",
      focus: "Focus: reduced-noise list of overdue, due-today, and in-progress work.",
      review: "Review: weekly/monthly/custom period summary with Markdown copy.",
      messages: "Messages: type M records, sender/recipient filters, and notification-oriented conversations.",
      team: "Team: presence, workload, and recent messages grouped by person.",
      status: "Status: latest or active presence records for each person.",
      notifications: "Notifications: due messages/reminders, acknowledge, snooze, and browser alert controls.",
      stats: "Stats: charts, heatmaps, and type/status breakdowns.",
      graph: "Graph: id, parent, ref, depends_on, blocks, and related links.",
      display: "Display: read-focused wall mode that hides editing controls. Use Back or Exit Display to leave.",
      kiosk: "Kiosk: always-on board with clock, auto-refresh, optional kiosk_filter, and auto-scroll.",
    };
    const CONTROL_HELP = {
      "dark-btn": "Toggle light and dark theme. Add ?theme=light or ?theme=dark to force a wall-display theme.",
      "contrast-btn": "High-contrast mode increases borders and text contrast for low-visibility displays.",
      "motion-btn": "Reduced motion disables most transitions and animation-heavy feedback.",
      "density-btn": "Compact density hides long body previews and fits more records on small screens.",
      "fullscreen-btn": "Use browser fullscreen for kiosk or display boards. Press f to toggle.",
      "notif-btn": "Open notification records and optionally request browser notification permission.",
      "refresh-btn": "Reload the active view from disk/API without changing filters. Press r as a shortcut.",
      "status-active-btn": "Switch Status between active records only and latest status per person.",
      "agenda-blocked-btn": "Cycle Agenda blocker filtering: all, only blocked, or hide blocked records.",
      "export-select": "Download the current Items result as CSV, JSON, or Markdown.",
      "group-by": "Group the Items list without changing the source file.",
      "sort": "Sort visible Items by line, time, title, type, status, or source.",
      "order": "Choose ascending or descending sort order.",
      "limit": "Limit the number of visible Items. Leave empty for all matching records.",
      "search": "Search title, raw line, and detail values. Shortcut: /.",
    };
    const SHORTCUT_HELP_ROWS = [
      ["/", "Focus search"],
      ["Ctrl+K", "Command palette (actions + jump to item)"],
      ["j / k", "Move keyboard focus down / up in item list"],
      ["Enter", "Open focused item in detail modal"],
      ["x", "Toggle bulk selection on focused item"],
      ["n", "New item (opens the record editor)"],
      ["q", "Toggle quick-add bar"],
      ["r", "Refresh current view"],
      ["s", "Go to Stats view"],
      ["d", "Toggle dark mode"],
      ["f", "Toggle fullscreen"],
      ["Ctrl+K display", "Open or toggle Display mode"],
      ["g", "Jump to line number (opens detail modal)"],
      ["Shift+K", "Toggle kiosk mode"],
      ["Esc", "Close modal / palette / blur input / exit kiosk"],
      ["[ / ]", "Prev / next item in detail modal"],
      ["< / >", "Prev / next status filter"],
      [", / . (Calendar)", "Previous / next calendar period"],
      ["t / m (Calendar)", "Jump to today / toggle month/week"],
      ["?", "Show / hide this help"],
    ];
    function runViewGuideAction(action) {
      const fn = VIEW_ACTIONS[action];
      if (fn) fn();
    }
    function syncViewGuide() {
      const node = document.getElementById("view-guide");
      if (!node) return;
      const v = currentView();
      const meta = VIEW_META[v] || VIEW_META[""];
      const actions = (meta.actions || []).map(([label, action]) =>
        `<button type="button" class="secondary" onclick="runViewGuideAction(${escapeHtml(jsLiteral(action))})">${escapeHtml(label)}</button>`
      ).join("");
      node.innerHTML = `
        <div class="view-guide-card">
          <span class="view-guide-chip">${escapeHtml(v || "items")}</span>
          <div class="view-guide-copy">
            <div class="view-guide-title">${escapeHtml(meta.label)}</div>
            <div class="view-guide-desc">${escapeHtml(meta.description)}</div>
          </div>
          <div class="view-guide-actions">${actions}</div>
        </div>`;
    }
    function setupWorkspaceTabs() {
      const nav = document.getElementById("workspace-tabs");
      if (!nav) return;
      nav.setAttribute("role", "tablist");
      nav.addEventListener("keydown", (event) => {
        if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
        const tabs = Array.from(nav.querySelectorAll(".workspace-tab[data-view]"));
        const current = tabs.indexOf(document.activeElement);
        if (current < 0 || !tabs.length) return;
        event.preventDefault();
        let next = current;
        if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else next = (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        tabs[next].focus();
      });
    }
    function openTaskItems() {
      const params = query();
      params.delete("mode");
      params.delete("view");
      params.delete("workspace");
      params.delete("panel");
      params.set("kind", "T");
      params.set("open_only", "true");
      history.pushState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadItems();
    }
    function setAgendaQuickRange(range) {
      const params = query();
      params.delete("mode");
      params.set("view", "agenda");
      params.delete("from");
      params.delete("to");
      params.delete("around");
      params.delete("window");
      const today = new Date();
      if (range === "today") {
        params.set("from", _fmtDate(today));
        params.set("to", _fmtDate(today));
      } else {
        const end = new Date(today);
        end.setDate(end.getDate() + (range === "7d" ? 7 : 1));
        params.set("from", _fmtDate(today));
        params.set("to", _fmtDate(end));
      }
      history.pushState(null, "", `${location.pathname}?${params.toString()}`);
      applyUrlToControls();
      loadAgenda();
    }
    function refreshStatsView() {
      statsLoaded = true;
      loadChart(currentChartType);
      loadStatsBreakdown();
    }
    function switchWorkspace(view, historyMode = "push") {
      const params = query();
      params.delete("mode");
      params.delete("view");
      params.delete("workspace");
      params.delete("panel");
      if (view === "kiosk" || view === "display") params.set("mode", view);
      else if (view) params.set("view", view);
      const method = historyMode === "replace" ? "replaceState" : "pushState";
      history[method](null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      applyUrlToControls();
      refreshAll();
    }
    function switchView(view) { switchWorkspace(view); }
    function switchViewWorkspace(view, workspace) { switchWorkspace(view || workspace || ""); }
    function toggleDisplayMode() {
      switchWorkspace(isDisplayMode() ? "" : "display");
    }
    let _displayDefaultSubtitle = null;
    function _displayApply() {
      const active = isDisplayMode();
      const exitBtn = document.getElementById("display-exit-btn");
      const subtitle = document.getElementById("app-subtitle");
      if (exitBtn) exitBtn.style.display = active ? "inline-flex" : "none";
      if (subtitle && _displayDefaultSubtitle === null) _displayDefaultSubtitle = subtitle.textContent;
      if (subtitle && active) {
        subtitle.textContent = firstParam(query(), ["display_title"], "Read-focused wall display.");
      } else if (subtitle && _displayDefaultSubtitle !== null && !isKioskMode()) {
        subtitle.textContent = _displayDefaultSubtitle;
      }
      document.body.dataset.activeView = currentView() || "items";
    }
    function syncViewTabs() {
      const v = currentView();
      document.querySelectorAll(".workspace-tab[data-view]").forEach(btn => {
        const active = (btn.dataset.view || "") === v;
        btn.classList.toggle("active", active);
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-selected", active ? "true" : "false");
        btn.tabIndex = active ? 0 : -1;
      });
      const notifBtn = document.getElementById("notif-btn");
      if (notifBtn) notifBtn.classList.toggle("btn-active", v === "notifications");
    }
    function syncPages() {
      const page = VIEW_PAGE[currentView()] || "items";
      document.querySelectorAll("main .page").forEach(sec => {
        sec.classList.toggle("page-active", sec.dataset.page === page);
      });
      const label = document.getElementById("items-heading-label");
      if (label) label.textContent = currentView() === "messages" ? "Messages" : "Items";
    }
    function isDisplayMode() {
      const params = query();
      return firstParam(params, ["mode", "view"], "").toLowerCase() === "display";
    }
    function isKioskMode() {
      const params = query();
      return firstParam(params, ["mode", "view"], "").toLowerCase() === "kiosk";
    }
    function currentView() {
      const params = query();
      const value = firstParam(params, ["view", "mode"], "").toLowerCase();
      if (["display", "kiosk"].includes(value)) return value;
      if (PAGE_VIEWS.includes(value)) return value;
      // Back-compat: old ?workspace= / ?panel= parameters map onto page views.
      const ws = firstParam(params, ["workspace", "panel"], "").toLowerCase();
      if (PAGE_VIEWS.includes(ws)) {
        warnDeprecatedWorkspaceParam();
        return ws;
      }
      return "";
    }
    let _workspaceDeprecationWarned = false;
    function warnDeprecatedWorkspaceParam() {
      // The legacy ?workspace= / ?panel= aliases are deprecated in favor of
      // ?view=. Warn once per session before the mapping is removed in a
      // future release.
      if (_workspaceDeprecationWarned) return;
      _workspaceDeprecationWarned = true;
      console.warn(
        "[life.txt] The ?workspace= / ?panel= URL parameters are deprecated and " +
        "will be removed in a future release. Use ?view=NAME instead."
      );
    }
    window.addEventListener("popstate", () => {
      applyPresetToUrl();
      applyUrlToControls();
      refreshAll();
    });
    function applyPresetToUrl() {
      const params = query();
      // Support ?view=NAME as alias for ?preset=NAME (config-defined presets)
      const viewAlias = (params.get("view") || "").toLowerCase();
      if (viewAlias && !PAGE_VIEWS.includes(viewAlias) && !["display", "kiosk"].includes(viewAlias) && !params.get("preset")) {
        params.set("preset", params.get("view"));
        history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      }
      const presetName = params.get("preset");
      if (!presetName || params.get("_preset_applied") === presetName) return;
      const preset = getViewPreset(presetName);
      if (!preset) return;
      const next = new URLSearchParams(params);
      for (const [key, value] of Object.entries(preset)) {
        if (!next.has(key)) next.set(key, value);
      }
      next.set("_preset_applied", presetName);
      history.replaceState(null, "", `${location.pathname}?${next.toString()}`);
    }
    function applyUrlToControls() {
      const params = query();
      document.body.classList.toggle("display-mode", isDisplayMode());
      document.body.classList.toggle("kiosk-mode", isKioskMode());
      syncViewTabs();
      syncPages();
      syncViewGuide();
      _displayApply();
      _kioskApply();
      document.getElementById("search").value = firstParam(params, ["text", "q"], "");
      const fallbackKind = currentView() === "messages" ? "M" : "";
      const fallbackSort = currentView() === "messages" ? "time" : (appConfig?.web?.default_sort || "line");
      document.getElementById("kind").value = firstParam(params, ["kind", "type"], fallbackKind);
      document.getElementById("sort").value = firstParam(params, ["sort"], fallbackSort);
      document.getElementById("order").value = firstParam(params, ["order"], appConfig?.web?.default_order || "asc");
      document.getElementById("open-only").checked = boolParam(params, ["open", "open_only"]) || params.get("blocked") === "true";
      document.getElementById("limit").value = firstParam(params, ["limit"], appConfig?.web?.default_limit || "");
      const groupSel = document.getElementById("group-by");
      if (groupSel) groupSel.value = firstParam(params, ["group_by"], "");
      syncTimelineRange(firstParam(params, ["range", "timeline_range"], timelineRange));
      syncCalStateFromUrl();
      syncStatusFilterBarsFromUrl();
      configureAutoRefresh();
      configureNotificationPolling();
      syncTimelineNowTimer();
    }
    function configureAutoRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      const displayFallback = String(appConfig?.web?.display_refresh || 60);
      const seconds = Number(firstParam(query(), ["refresh"], (isDisplayMode() || isKioskMode()) ? displayFallback : ""));
      if (Number.isFinite(seconds) && seconds > 0) {
        refreshTimer = setInterval(refreshAll, seconds * 1000);
      }
    }
    function configureNotificationPolling() {
      if (notificationTimer) clearInterval(notificationTimer);
