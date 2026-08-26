          `<div class="notification-row"><span class="pill">${whenDisplay}</span>${stateBadge}<div class="title">${escapeHtml(record.title)}</div><div class="meta">${escapeHtml(record.sender)} → ${escapeHtml((record.recipients || []).join(", "))}</div>${actions}</div>`
        );
        showBrowserNotification(record);
      }
    }
    async function ackMessage(id) {
      await api(`/api/messages/id/${encodeURIComponent(id)}/ack`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: "{}",
      });
      await refreshAll();
    }
    async function snoozeMessage(id, duration) {
      await api(`/api/messages/id/${encodeURIComponent(id)}/snooze`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({duration}),
      });
      await refreshAll();
    }
    async function enableBrowserNotifications() {
      if (!("Notification" in window)) {
        alert("This browser does not support notifications.");
        return;
      }
      const permission = await Notification.requestPermission();
      browserNotificationsEnabled = permission === "granted";
      updateNotifBtnLabel();
      updateNotifPermissionDisplay();
      if (browserNotificationsEnabled) await loadNotifications();
      else if (permission === "denied") showNotificationSettingsHelp();
    }
    function showBrowserNotification(record) {
      if (!browserNotificationsEnabled || !("Notification" in window) || Notification.permission !== "granted") return;
      const key = record.notification_id || record.id || record.text;
      if (seenNotifications.has(key)) return;
      seenNotifications.add(key);
      new Notification(record.title || "life.txt message", {
        body: `${record.sender || ""} -> ${(record.recipients || []).join(", ")}`,
        tag: key,
      });
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function jsLiteral(value) {
      return JSON.stringify(String(value ?? ""));
    }
    function focusableElements(container) {
      if (!container) return [];
      const selector = [
        "a[href]", "button:not([disabled])", "input:not([disabled])",
        "select:not([disabled])", "textarea:not([disabled])",
        "[tabindex]:not([tabindex='-1'])",
      ].join(",");
      return Array.from(container.querySelectorAll(selector))
        .filter(el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    }
    function syncBackgroundInert() {
      const hasOpenModal = !!document.querySelector(".modal-backdrop.open, .cmdk-backdrop.open");
      document.body.classList.toggle("modal-open", hasOpenModal);
      for (const el of [document.querySelector("header"), document.querySelector("main")]) {
        if (!el) continue;
        if (hasOpenModal) {
          el.setAttribute("inert", "");
          el.setAttribute("aria-hidden", "true");
        } else {
          el.removeAttribute("inert");
          el.removeAttribute("aria-hidden");
        }
      }
    }
    function openManagedModal(backdrop, focusSelector) {
      if (!backdrop) return;
      _lastFocusedBeforeModal = document.activeElement;
      backdrop.classList.add("open");
      syncBackgroundInert();
      window.setTimeout(() => {
        const target = focusSelector ? backdrop.querySelector(focusSelector) : null;
        const fallback = focusableElements(backdrop)[0];
        (target || fallback || backdrop).focus?.();
      }, 0);
    }
    function closeManagedModal(backdrop) {
      if (!backdrop) return;
      backdrop.classList.remove("open");
      syncBackgroundInert();
      const restore = _lastFocusedBeforeModal;
      _lastFocusedBeforeModal = null;
      const hiddenModal = restore?.closest?.(".modal-backdrop:not(.open), .cmdk-backdrop:not(.open)");
      if (restore && document.contains(restore) && !hiddenModal) {
        window.setTimeout(() => restore.focus?.(), 0);
      }
    }
    function activeModalBackdrop() {
      const open = Array.from(document.querySelectorAll(".modal-backdrop.open, .cmdk-backdrop.open"));
      return open.length ? open[open.length - 1] : null;
    }
    function trapModalFocus(event) {
      if (event.key !== "Tab") return false;
      const modal = activeModalBackdrop();
      if (!modal) return false;
      const focusables = focusableElements(modal);
      if (!focusables.length) {
        event.preventDefault();
        modal.focus?.();
        return true;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
        return true;
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
        return true;
      }
      return false;
    }
    async function refreshAll() {
      // Refresh only what the active view needs; notifications always poll so
      // browser alerts keep working from any view.
      const v = currentView();
      const tasks = [loadNotifications()];
      if (VIEW_PAGE[v] === "items" || v === "") tasks.push(loadItems());
      if (v === "agenda") tasks.push(loadAgenda());
      if (v === "timeline") tasks.push(loadTimeline());
      if (v === "calendar") tasks.push(loadCalendar());
      if (v === "status") tasks.push(loadStatus());
      if (v === "team") tasks.push(loadTeam());
      if (v === "dashboard") tasks.push(loadDashboard());
      if (v === "today") tasks.push(loadToday());
      if (v === "focus") tasks.push(loadFocus());
      if (v === "review") tasks.push(loadReview());
      if (v === "graph") tasks.push(loadGraphPanel());
      if (v === "stats") {
        statsLoaded = true;
        tasks.push(loadChart(currentChartType));
        tasks.push(loadStatsBreakdown());
      }
      await Promise.all(tasks);
    }

    // ── Quick-add bar ──────────────────────────────────────────────

    /**
     * Both editing bars live inside the Items page, so un-hiding one while
     * another view is active toggles a zero-size element and looks like a
     * dead button. Switch to Items first, which is where the result of the
     * edit shows up anyway.
     */
    function revealItemsPage() {
      if (VIEW_PAGE[currentView()] === "items") return;
      switchWorkspace("");
    }

    /** Bring a just-revealed bar into view; the FAB sits far below it. */
    function focusBarInput(inputId, select) {
      const input = document.getElementById(inputId);
      if (!input) return;
      input.focus();
      if (select) input.select();
      if (input.scrollIntoView) {
        input.scrollIntoView({block: "center", behavior: "smooth"});
      }
    }

    function toggleQuickAdd(show) {
      const bar = document.getElementById("quick-add-bar");
      const wanted = show === undefined ? bar.style.display === "none" : show;
      if (wanted) revealItemsPage();
      bar.style.display = wanted ? "" : "none";
      if (wanted) focusBarInput("quick-line", true);
    }
    // ── Presence status ────────────────────────────────────────────
    async function loadPresence() {
      const el = document.getElementById("presence-current");
      if (!el) return;
      try {
        const data = await api("/api/status?active=true");
        const mine = (data.records || []).filter(r => r.active);
        if (!mine.length) { el.textContent = "no open status"; el.className = "check-msg"; return; }
        const r = mine[0];
        el.textContent = "now: " + r.state + " since " + (r.from || "");
        el.className = "check-msg ok";
      } catch (err) {
        el.textContent = "";
      }
    }

    function togglePresence(show) {
      const bar = document.getElementById("presence-bar");
      if (!bar) return;
      const visible = show === undefined ? bar.style.display === "none" : show;
      if (visible) revealItemsPage();
      bar.style.display = visible ? "" : "none";
      if (visible) {
        loadPresence();
        focusBarInput("presence-input", false);
      }
    }

    async function setPresence() {
      const input = document.getElementById("presence-input");
      const raw = (input.value || "").trim();
      if (!raw) { showToast("Type a state such as busy.", "error"); return; }
      const parts = raw.split(/\s+/);
      const body = {state: parts[0]};
      if (parts.length > 1) body.title = parts.slice(1).join(" ");
      try {
        const data = await api("/api/status", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(body),
        });
        input.value = "";
        const closed = (data.closed || []).length;
        showToast("Status: " + body.state + (closed ? " (closed " + closed + " previous)" : ""), "success");
        await loadPresence();
        await refreshAll();
      } catch (err) {
        showToast("Status failed: " + (err.message || "error"), "error");
      }
    }

    async function endPresence() {
      try {
        const data = await api("/api/status", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({end: true}),
        });
        if (!(data.closed || []).length) { showToast("No open status.", "info"); }
        else { showToast("Status closed.", "success"); }
        await loadPresence();
        await refreshAll();
      } catch (err) {
        showToast("Close failed: " + (err.message || "error"), "error");
      }
    }

    // ── Capture shorthand preview ──────────────────────────────────
    let shorthandTimer = null;
    function previewShorthand() {
      const input = document.getElementById("quick-line");
      const msgEl = document.getElementById("quick-check-msg");
      if (!input || !msgEl) return;
      const text = (input.value || "").trim();
      if (shorthandTimer) clearTimeout(shorthandTimer);
      if (!text || text.startsWith("[")) { msgEl.textContent = ""; msgEl.className = "check-msg"; return; }
      shorthandTimer = setTimeout(async () => {
        try {
          const data = await api("/api/shorthand/parse", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text}),
          });
          const bits = [];
          Object.keys(data.details || {}).forEach(k => (data.details[k] || []).forEach(v => bits.push(k + ":" + v)));
          msgEl.textContent = bits.length ? ("→ " + data.title + "  " + bits.join(" ")) : "";
          msgEl.className = "check-msg ok";
        } catch (err) {
          msgEl.textContent = err.message || "";
          msgEl.className = "check-msg err";
        }
      }, 200);
    }

    async function quickAddLine() {
      const input = document.getElementById("quick-line");
      const line = input.value.trim();
      if (!line) return;
      const msgEl = document.getElementById("quick-check-msg");
      try {
        // A leading status marker means the user typed a full life.txt line.
        // Anything else is plain text with capture shorthand.
        if (line.startsWith("[")) {
          await api("/api/items/raw", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({line}),
          });
        } else {
          await api("/api/items/capture", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text: line}),
          });
        }
        input.value = "";
        input.className = "";
        if (msgEl) { msgEl.textContent = ""; msgEl.className = "check-msg"; }
        toggleQuickAdd(false);
        showToast("Item added.", "success");
        await refreshAll();
      } catch(err) {
        input.classList.add("err");
        if (msgEl) { msgEl.textContent = err.message || "Invalid line"; msgEl.className = "check-msg err"; }
        showToast("Add failed: " + (err.message || "invalid"), "error");
      }
    }

    // ── Keyboard shortcuts ─────────────────────────────────────────
    document.addEventListener("keydown", function(e) {
      if (trapModalFocus(e)) return;
      const active = document.activeElement;
      const inInput = active && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName);
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        openCmdk();
        return;
      }
      if (e.key === "Escape") {
        if (document.getElementById("cmdk-backdrop").classList.contains("open")) { closeCmdk(); return; }
        if (isKioskMode()) { toggleKioskMode(); return; }
        if (document.getElementById("help-modal").classList.contains("open")) { closeHelpModal(); return; }
        if (document.getElementById("undo-modal").classList.contains("open")) { closeUndoHistoryModal(); return; }
        if (document.getElementById("git-modal").classList.contains("open")) { closeGitModal(); return; }
        if (document.getElementById("editor-modal").classList.contains("open")) { closeEditorModal(); return; }
        if (document.getElementById("detail-drawer").classList.contains("open")) { closeDrawer(); return; }
        if (inInput) { active.blur(); return; }
        toggleQuickAdd(false);
        return;
      }
      if (inInput) return;
      if (e.key === "?") { e.preventDefault(); openHelpModal(); return; }
      if (currentView() === "calendar" && !document.getElementById("detail-drawer").classList.contains("open")) {
        if (e.key === "," || e.key === "<") { e.preventDefault(); calShift(-1); return; }
        if (e.key === "." || e.key === ">") { e.preventDefault(); calShift(1); return; }
        if (e.key === "t" || e.key === "T") { e.preventDefault(); calToday(); return; }
        if (e.key === "m" || e.key === "M") { e.preventDefault(); setCalMode(calMode === "month" ? "week" : "month"); return; }
      }
      if (e.key === "[" && document.getElementById("detail-drawer").classList.contains("open")) { e.preventDefault(); drawerPrev(); return; }
      if (e.key === "]" && document.getElementById("detail-drawer").classList.contains("open")) { e.preventDefault(); drawerNext(); return; }
      if (e.key === "<" || e.key === ",") { e.preventDefault(); cycleStatusFilter(-1); return; }
      if (e.key === ">" || e.key === ".") { e.preventDefault(); cycleStatusFilter(1); return; }
      if (e.key === "n" || e.key === "N") {
        e.preventDefault();
        newItem();
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        document.getElementById("search").focus();
        return;
      }
      if (e.key === "j") { e.preventDefault(); kbMove(1); return; }
      if (e.key === "k") { e.preventDefault(); kbMove(-1); return; }
      if (e.key === "Enter") {
        if (!document.getElementById("detail-drawer").classList.contains("open") && kbActivate()) e.preventDefault();
        return;
      }
      if (e.key === "x") { e.preventDefault(); kbToggleSelect(); return; }
      if (e.key === "q") { e.preventDefault(); toggleQuickAdd(); return; }
      if (e.key === "p" || e.key === "P") { e.preventDefault(); togglePresence(); return; }
      if (e.key === "r" || e.key === "R") { e.preventDefault(); refreshAll(); return; }
      if (e.key === "s" || e.key === "S") { e.preventDefault(); toggleStats(); return; }
      if (e.key === "d" || e.key === "D") { e.preventDefault(); toggleDarkMode(); return; }
      if (e.key === "f" || e.key === "F") { e.preventDefault(); toggleFullscreen(); return; }
      if (e.key === "g" || e.key === "G") { e.preventDefault(); jumpToLine(); return; }
      if (e.key === "K") { e.preventDefault(); toggleKioskMode(); return; }
    });

    // ── Command palette (Ctrl+K) ───────────────────────────────────
    let _cmdkIndex = 0;
    let _cmdkEntries = [];
    function fuzzyMatch(text, queryText) {
      const textLower = String(text || "").toLowerCase();
      const queryLower = String(queryText || "").toLowerCase();
      if (!queryLower) return true;
      if (textLower.includes(queryLower)) return true;
      let j = 0;
      for (let i = 0; i < textLower.length && j < queryLower.length; i++) {
        if (textLower[i] === queryLower[j]) j++;
      }
      return j === queryLower.length;
    }
    function recentItemKey(item) {
      return itemStableKey(item);
    }
    function loadRecentItems() {
      try {
        const raw = localStorage.getItem(RECENT_ITEMS_STORAGE_KEY);
        const rows = raw ? JSON.parse(raw) : [];
        return Array.isArray(rows) ? rows : [];
      } catch(_) {
        return [];
      }
    }
    function rememberRecentItem(item) {
      if (!item) return;
      try {
        const key = recentItemKey(item);
        const row = {
