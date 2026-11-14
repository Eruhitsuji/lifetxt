          `<div class="notification-row"><span class="pill">${whenDisplay}</span>${stateBadge}<div class="title">${escapeHtml(record.title)}</div><div class="meta">${escapeHtml(record.sender)} → ${escapeHtml((record.recipients || []).join(", "))}</div>${actions}</div>`
        );
      }
      for (const record of data.records) {
        if (request !== notificationRequest) break;
        try {
          await showBrowserNotification(record);
        } catch (_) {
          setNotificationDeliveryStatus("Could not send the notification. Check your device notification settings.");
        }
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
    function notificationsDisabled() {
      return appConfig?.notifications?.enabled === false || appConfig?.notifications?.web === false;
    }
    function browserAlertsPermission() {
      if (window.isSecureContext === false) return "insecure";
      return window.Notification?.permission || "unsupported";
    }
    function readNotificationStorage(key) {
      try { return window.localStorage.getItem(key); } catch (_) { return null; }
    }
    function writeNotificationStorage(key, value) {
      try { window.localStorage.setItem(key, value); } catch (_) { /* session fallback */ }
    }
    function automaticAlertsEnabled() {
      if (notificationsDisabled()) return false;
      if (window.lifetxtDesktopAlerts) return window.lifetxtDesktopAlerts.enabled;
      return browserAlertsPermission() === "granted"
        && (readNotificationStorage(notificationPrefsKey) ?? (browserAlertsPaused ? "off" : "on")) !== "off";
    }
    function syncNotificationControls() {
      updateNotifBtnLabel();
      updateNotifPermissionDisplay();
    }
    async function setAutomaticAlerts(enabled) {
      syncNotificationControls();
      if (notificationsDisabled()) return;
      try {
        if (window.lifetxtDesktopAlerts) {
          await window.lifetxtDesktopAlerts.setEnabled(enabled);
        } else {
          if (enabled && !await requestBrowserAlertsPermission()) return;
          browserAlertsPaused = !enabled;
          writeNotificationStorage(notificationPrefsKey, enabled ? "on" : "off");
        }
        syncNotificationControls();
        if (enabled) await loadNotifications();
      } catch (_) {
        showToast(t("Could not change automatic alerts."), "error");
      }
    }
    function enableBrowserNotifications() {
      return setAutomaticAlerts(true);
    }
    async function requestBrowserAlertsPermission() {
      try {
        if (browserAlertsPermission() === "default") await window.Notification.requestPermission();
      } catch (_) {
        showToast(t("Could not request notification permission."), "error");
        return false;
      }
      syncNotificationControls();
      const permission = browserAlertsPermission();
      if (permission === "granted") return true;
      if (permission === "denied") showNotificationSettingsHelp();
      else showToast(t(browserAlertsPermissionLabel(permission)), "warning");
      return false;
    }
    async function sendNotificationToDevice(test, tag, title, body, manual = false) {
      if (window.lifetxtDesktopAlerts) {
        await window.lifetxtDesktopAlerts.send(test, manual, document.documentElement.lang === "ja");
      } else {
        const notification = new window.Notification(title, {body, tag});
        notification.onclick = () => {
          window.focus();
          switchView("notifications");
          notification.close();
        };
      }
    }
    async function sendTestNotification() {
      if (notificationsDisabled()) return;
      try {
        if (!window.lifetxtDesktopAlerts && !await requestBrowserAlertsPermission()) return;
        await sendNotificationToDevice(true, "lifetxt-test", "life.txt", t("This is a test notification."));
        showToast(t("Test notification sent. Check your system notifications."), "success");
      } catch (_) {
        showToast(t("Could not send the notification. Check your device notification settings."), "error");
      }
    }
    function loadDeliveredAlerts() {
      try {
        const entries = JSON.parse(readNotificationStorage(notificationHistoryKey) || "[]");
        return new Map(Array.isArray(entries) ? entries : []);
      } catch (_) { return new Map(); }
    }
    async function showBrowserNotification(record, force = false) {
      if (notificationsDisabled() || (!force && !automaticAlertsEnabled())) return false;
      if (!window.lifetxtDesktopAlerts && browserAlertsPermission() !== "granted") return false;
      const key = notificationOccurrenceKey(record);
      const deliver = async () => {
        if (notificationsDisabled() || (!force && !automaticAlertsEnabled())) return false;
        const delivered = loadDeliveredAlerts();
        const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
        if (!force && (seenNotifications.get(key) > cutoff || delivered.get(key) > cutoff)) return false;
        await sendNotificationToDevice(false, key, record.title || "life.txt", t("Open life.txt to view the notification."), force);
        const now = Date.now();
        seenNotifications.set(key, now);
        if (seenNotifications.size > 512) seenNotifications.delete(seenNotifications.keys().next().value);
        delivered.delete(key);
        delivered.set(key, now);
        const recent = [...delivered].filter(([, time]) => time > cutoff).slice(-512);
        writeNotificationStorage(notificationHistoryKey, JSON.stringify(recent));
        return true;
      };
      // Prevent overlapping polls or tabs from sending the same occurrence.
      if (window.navigator?.locks) {
        return window.navigator.locks.request(notificationHistoryKey, deliver);
      }
      // Keep the same document serialized on browsers without Web Locks.
      const delivery = pendingNotificationDelivery.then(deliver);
      pendingNotificationDelivery = delivery.catch(() => {});
      return delivery;
    }
    let pendingNotificationDelivery = Promise.resolve();
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
      if (v === "matrix") tasks.push(loadPriorityMatrix());
      if (v === "review") tasks.push(loadReview());
      if (v === "graph") tasks.push(loadGraphPanel());
      if (v === "server") tasks.push(loadServerBackupStatus());
      if (v === "context") tasks.push(loadPersonalContext());
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
        const behavior = document.body.classList.contains("reduce-motion") ? "instant" : "smooth";
        input.scrollIntoView({block: "center", behavior});
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
        if (!mine.length) { el.textContent = t("No open status."); el.className = "check-msg"; return; }
        const r = mine[0];
        el.textContent = t("Now") + ": " + statusStateLabel(r.state) + " · " + t("Since") + ": " + (r.from || "");
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
        focusBarInput("presence-state-select", false);
      }
    }

    function standardStatusStates() {
      const states = appConfig && Array.isArray(appConfig.status_states)
        ? appConfig.status_states : [];
      return states.filter(state => typeof state === "string" && state.trim());
    }

    /** Localize only config-declared standard states; custom data is verbatim. */
    function statusStateLabel(state) {
      const value = String(state == null ? "" : state);
      if (!standardStatusStates().includes(value)) return value;
      const key = "Status state: " + value;
      const translated = t(key);
      return translated === key ? value : translated;
    }

    function refreshStatusStateLabels(root) {
      const scope = root || document;
      if (!scope || !scope.querySelectorAll) return;
      scope.querySelectorAll("#presence-state-select, select[data-status-state-select]").forEach(select => {
        for (const option of select.options || []) {
          const label = option.value === "__custom__"
            ? t("Custom…") : statusStateLabel(option.value);
          if (option.textContent !== label) option.textContent = label;
        }
      });
    }

    function setupQuickPresencePicker() {
      const select = document.getElementById("presence-state-select");
      if (!select) return;
      const states = standardStatusStates();
      select.innerHTML = states.map(state =>
        `<option value="${escapeHtml(state)}">${escapeHtml(statusStateLabel(state))}</option>`
      ).join("") + `<option value="__custom__">${escapeHtml(t("Custom…"))}</option>`;
      select.value = states.length ? states[0] : "__custom__";
      syncQuickPresenceStateMode();
    }

    function syncQuickPresenceStateMode() {
      const select = document.getElementById("presence-state-select");
      const custom = document.getElementById("presence-state-custom");
      if (!select || !custom) return;
      const customMode = select.value === "__custom__";
      custom.hidden = !customMode;
      custom.disabled = !customMode;
      custom.required = customMode;
      custom.setAttribute("aria-required", customMode ? "true" : "false");
    }

    function quickPresenceStateChanged() {
      syncQuickPresenceStateMode();
      if (document.getElementById("presence-state-select")?.value === "__custom__") {
        document.getElementById("presence-state-custom")?.focus();
      }
    }

    function quickPresencePayload() {
      const select = document.getElementById("presence-state-select");
      const custom = document.getElementById("presence-state-custom");
      const title = document.getElementById("presence-title");
      const state = select?.value === "__custom__"
        ? (custom?.value || "").trim()
        : (select?.value || "").trim();
      if (!state) return null;
      const body = {state};
      const titleValue = (title?.value || "").trim();
      if (titleValue) body.title = titleValue;
      return body;
    }

    async function setPresence() {
      const body = quickPresencePayload();
      if (!body) { showToast(t("Enter a custom status."), "error"); return; }
      try {
        const data = await api("/api/status", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(body),
        });
        const custom = document.getElementById("presence-state-custom");
        const title = document.getElementById("presence-title");
        if (custom) custom.value = "";
        if (title) title.value = "";
        const closed = (data.closed || []).length;
        if (data.unchanged) showToast(t("Already " + statusStateLabel(data.unchanged) + "."), "info");
        else showToast(t("Status") + ": " + statusStateLabel(body.state) + (closed ? " (" + t("Previous status closed") + ": " + closed + ")" : ""), "success");
        await loadPresence();
        await refreshAll();
      } catch (err) {
        showToast(t("Status update failed:") + " " + (err.message || "error"), "error");
      }
    }

    async function endPresence() {
      try {
        const data = await api("/api/status", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({end: true}),
        });
        if (!(data.closed || []).length) { showToast(t("No open status."), "info"); }
        else { showToast(t("Status closed."), "success"); }
        await loadPresence();
        await refreshAll();
      } catch (err) {
        showToast(t("Close failed:") + " " + (err.message || "error"), "error");
      }
    }

    // ── Capture shorthand preview ──────────────────────────────────
    let shorthandTimer = null;
    let shorthandGeneration = 0;
    function invalidateShorthandPreview() {
      clearTimeout(shorthandTimer);
      return ++shorthandGeneration;
    }

    function previewShorthand() {
      const input = document.getElementById("quick-line");
      const msgEl = document.getElementById("quick-check-msg");
      if (!input || !msgEl) return;
      const generation = invalidateShorthandPreview();
      const text = (input.value || "").trim();
      input.classList.remove("ok", "err");
      msgEl.textContent = "";
      msgEl.className = "check-msg";
      if (!text) return;
      const isCurrent = () => generation === shorthandGeneration && input.value.trim() === text;
      shorthandTimer = setTimeout(async () => {
        try {
          const data = await api("/api/quick/resolve", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text}),
          });
          if (!isCurrent()) return;
          const bits = [];
          Object.keys(data.details || {}).forEach(k => (data.details[k] || []).forEach(v => bits.push(k + ":" + v)));
          msgEl.textContent = bits.length ? ("→ " + data.title + "  " + bits.join(" ")) : "";
          msgEl.className = "check-msg ok";
          input.classList.add("ok");
        } catch (err) {
          if (!isCurrent()) return;
          msgEl.textContent = err.message || "";
          msgEl.className = "check-msg err";
          input.classList.add("err");
        }
      }, 200);
    }

    async function quickAddLine() {
      const input = document.getElementById("quick-line");
      const line = input.value.trim();
      if (!line) return;
      const msgEl = document.getElementById("quick-check-msg");
      const generation = invalidateShorthandPreview();
      try {
        await api("/api/items/capture", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({text: line}),
        });
        input.value = "";
        previewShorthand();
        toggleQuickAdd(false);
        showToast("Item added.", "success");
        await refreshAll();
      } catch(err) {
        if (generation === shorthandGeneration && input.value.trim() === line) {
          input.classList.remove("ok");
          input.classList.add("err");
          if (msgEl) { msgEl.textContent = err.message || "Invalid line"; msgEl.className = "check-msg err"; }
        }
        showToast("Add failed: " + (err.message || "invalid"), "error");
      }
    }

    let captureSubmitPending = false;
    let capturePreviewBinding = null;

    function captureSuccessSummary(data) {
      const item = data?.item || {};
      const title = String(item.title || "").trim();
      const idKey = appConfig?.ids?.key || "id";
      const idValue = Array.isArray(item.details?.[idKey]) ? item.details[idKey][0] : "";
      const summary = title && idValue ? `${title} (${idValue})` : (title || idValue || t("item"));
      return summary.length > 80 ? summary.slice(0, 77) + "…" : summary;
    }

    function captureSyntax() {
      return document.getElementById("capture-input-syntax")?.value || "quick";
    }

    function invalidateCapturePreview() {
      capturePreviewBinding = null;
      const preview = document.getElementById("capture-preview");
      const confirm = document.getElementById("capture-confirm");
      if (preview) preview.hidden = true;
      if (confirm) confirm.hidden = true;
    }

    function captureInputChanged() {
      invalidateCapturePreview();
    }

    function captureSyntaxChanged() {
      invalidateCapturePreview();
      const syntax = captureSyntax();
      const input = document.getElementById("capture-text");
      const submit = document.getElementById("capture-submit");
      const help = document.getElementById("capture-syntax");
      if (input) input.placeholder = syntax === "todo" ? "(A) Prepare proposal +Work @office due:2026-10-30" : "Buy milk @home ^tomorrow";
      if (submit) submit.textContent = t(syntax === "todo" ? "Preview" : "Capture");
      if (help) help.textContent = t(syntax === "todo" ? "One todo.txt task; project, context, priority, dates, and key:value metadata are decoded on the server." : "shorthand and full life.txt lines use the same Quick add semantics.");
    }

    function appendCapturePreviewField(root, key, value) {
      const name = document.createElement("dt");
      const content = document.createElement("dd");
      name.textContent = key;
      content.textContent = Array.isArray(value) ? value.join(", ") : String(value ?? "");
      root.append(name, content);
    }

    function renderTodoCapturePreview(data) {
      const preview = document.getElementById("capture-preview");
      const fields = document.getElementById("capture-preview-fields");
      const diagnostics = document.getElementById("capture-preview-diagnostics");
      const confirm = document.getElementById("capture-confirm");
      if (!preview || !fields || !diagnostics || !confirm) return;
      fields.replaceChildren();
      appendCapturePreviewField(fields, "title", data.title);
      appendCapturePreviewField(fields, "status", data.status);
      appendCapturePreviewField(fields, "type", data.type);
      for (const [key, values] of Object.entries(data.details || {})) {
        appendCapturePreviewField(fields, key, values);
      }
      const warnings = (data.diagnostics || []).filter(row => row.severity !== "error");
      diagnostics.textContent = warnings.length ?
        t("Warnings:") + " " + warnings.map(row => `${row.code}: ${row.message}`).join("; ") :
        t("Warnings: none.");
      preview.hidden = false;
      confirm.hidden = Boolean(data.read_only);
    }

    async function previewTodoCapture(text) {
      const data = await api("/api/quick/resolve", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text, syntax: "todo"}),
      });
      if (!data.context_token || !data.source_revision) {
        throw new Error(t("Review or revision is unavailable. Nothing was saved. Refresh the page and preview again."));
      }
      capturePreviewBinding = {
        text,
        token: data.context_token,
        sourceRevision: data.source_revision,
      };
      renderTodoCapturePreview(data);
      return data;
    }

    async function submitCapture() {
      if (captureSubmitPending) return;
      const input = document.getElementById("capture-text");
      const button = document.getElementById("capture-submit");
      const feedback = document.getElementById("capture-feedback");
      const text = String(input?.value || "").trim();
      if (!text || !input || !button || !feedback) return;
      captureSubmitPending = true;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      feedback.textContent = "";
      feedback.className = "capture-feedback";
      try {
        if (captureSyntax() === "todo") {
          await previewTodoCapture(text);
          feedback.textContent = t("Review every mapped field, then confirm capture.");
          feedback.className = "capture-feedback ok";
          return;
        }
        const data = await api("/api/items/capture", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({text}),
        });
        feedback.textContent = `${t("Captured:")} ${captureSuccessSummary(data)}`;
        feedback.className = "capture-feedback ok";
        input.value = "";
      } catch (error) {
        feedback.textContent = `${t("Capture failed:")} ${t(actionableErrorText(error))}`;
        feedback.className = "capture-feedback err";
      } finally {
        captureSubmitPending = false;
        button.disabled = false;
        button.removeAttribute("aria-busy");
        input.focus({preventScroll: true});
      }
    }

    async function confirmTodoCapture() {
      if (captureSubmitPending) return;
      const input = document.getElementById("capture-text");
      const confirm = document.getElementById("capture-confirm");
      const feedback = document.getElementById("capture-feedback");
      const binding = capturePreviewBinding;
      if (!input || !confirm || !feedback || !binding || captureSyntax() !== "todo" || input.value.trim() !== binding.text) {
        invalidateCapturePreview();
        if (feedback) {
          feedback.textContent = t("Input changed. Preview again before saving.");
          feedback.className = "capture-feedback err";
        }
        return;
      }
      captureSubmitPending = true;
      confirm.disabled = true;
      confirm.setAttribute("aria-busy", "true");
      try {
        const data = await api("/api/items/capture", {
          method: "POST",
          headers: {"Content-Type": "application/json", "If-Match": binding.sourceRevision},
          body: JSON.stringify({
            text: binding.text,
            syntax: "todo",
            context_token: binding.token,
            expected_source_revision: binding.sourceRevision,
          }),
        });
        feedback.textContent = `${t("Captured:")} ${captureSuccessSummary(data)}`;
        feedback.className = "capture-feedback ok";
        input.value = "";
        invalidateCapturePreview();
      } catch (error) {
        invalidateCapturePreview();
        feedback.textContent = `${t("Capture failed:")} ${t(actionableErrorText(error))} ${t("Nothing was saved. Preview again before retrying.")}`;
        feedback.className = "capture-feedback err";
      } finally {
        captureSubmitPending = false;
        confirm.disabled = false;
        confirm.removeAttribute("aria-busy");
        input.focus({preventScroll: true});
      }
    }

    function initializeCaptureMode() {
      if (location.pathname.replace(/\/+$/, "") !== "/capture") return false;
      document.body.classList.add("capture-mode");
      document.title = `${t("Quick Capture")} — life.txt`;
      const input = document.getElementById("capture-text");
      captureSyntaxChanged();
      requestAnimationFrame(() => input?.focus({preventScroll: true}));
      return true;
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
        if (document.getElementById("bulk-done-modal").classList.contains("open")) { closeBulkDone(); return; }
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
