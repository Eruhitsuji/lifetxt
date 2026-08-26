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