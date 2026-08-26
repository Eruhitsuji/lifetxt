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