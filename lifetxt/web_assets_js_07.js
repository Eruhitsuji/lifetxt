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