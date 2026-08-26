      } catch(e) {
        showToast("Import error: " + e.message, "error");
      }
    }

    // ── Dark mode ─────────────────────────────────────────────────
    (function initDarkMode() {
      const stored = localStorage.getItem("lifetxt_dark");
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const urlTheme = new URLSearchParams(location.search).get("theme");
      const dark = urlTheme
        ? urlTheme === "dark"
        : (stored !== null ? stored === "1" : prefersDark);
      if (dark) document.documentElement.setAttribute("data-theme", "dark");
      const btn = document.getElementById("dark-btn");
      if (btn) btn.textContent = dark ? "☀️" : "🌙";
      // Auto-follow OS theme when user has not explicitly set a preference
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function(ev) {
        if (localStorage.getItem("lifetxt_dark") !== null) return;
        const wantsDark = ev.matches;
        if (wantsDark) document.documentElement.setAttribute("data-theme", "dark");
        else document.documentElement.removeAttribute("data-theme");
        const b = document.getElementById("dark-btn");
        if (b) b.textContent = wantsDark ? "☀️" : "🌙";
      });
    })();
    function toggleDarkMode() {
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      if (isDark) {
        document.documentElement.removeAttribute("data-theme");
        localStorage.setItem("lifetxt_dark", "0");
      } else {
        document.documentElement.setAttribute("data-theme", "dark");
        localStorage.setItem("lifetxt_dark", "1");
      }
      const btn = document.getElementById("dark-btn");
      if (btn) btn.textContent = !isDark ? "☀️" : "🌙";
    }

    // ── High contrast + reduced motion (accessibility) ────────────
    function _syncA11yButtons() {
      const hc = document.documentElement.getAttribute("data-contrast") === "high";
      const rm = document.body.classList.contains("reduce-motion");
      const hcBtn = document.getElementById("contrast-btn");
      if (hcBtn) { hcBtn.classList.toggle("btn-active", hc); hcBtn.setAttribute("aria-pressed", hc ? "true" : "false"); }
      const rmBtn = document.getElementById("motion-btn");
      if (rmBtn) { rmBtn.classList.toggle("btn-active", rm); rmBtn.setAttribute("aria-pressed", rm ? "true" : "false"); }
    }
    function applyHighContrast(on) {
      if (on) document.documentElement.setAttribute("data-contrast", "high");
      else document.documentElement.removeAttribute("data-contrast");
      _syncA11yButtons();
    }
    function applyReducedMotion(on) {
      document.body.classList.toggle("reduce-motion", !!on);
      _syncA11yButtons();
    }
    function initAccessibilityPrefs() {
      const params = new URLSearchParams(location.search);
      // Precedence: explicit URL param > stored user choice > config default.
      const urlContrast = (params.get("contrast") || "").toLowerCase();
      let hc;
      if (urlContrast) hc = urlContrast === "high" || urlContrast === "1";
      else {
        const stored = localStorage.getItem("lifetxt_contrast");
        hc = stored !== null ? stored === "1" : !!(appConfig?.web?.high_contrast);
      }
      applyHighContrast(hc);
      const urlMotion = (params.get("motion") || "").toLowerCase();
      let rm;
      if (urlMotion) rm = urlMotion === "reduce" || urlMotion === "1";
      else {
        const stored = localStorage.getItem("lifetxt_motion");
        rm = stored !== null ? stored === "1" : !!(appConfig?.web?.reduced_motion);
      }
      applyReducedMotion(rm);
    }
    function toggleHighContrast() {
      const on = document.documentElement.getAttribute("data-contrast") !== "high";
      try { localStorage.setItem("lifetxt_contrast", on ? "1" : "0"); } catch(_) {}
      applyHighContrast(on);
      showToast(on ? "High contrast on." : "High contrast off.", "info", 1600);
    }
    function toggleReducedMotion() {
      const on = !document.body.classList.contains("reduce-motion");
      try { localStorage.setItem("lifetxt_motion", on ? "1" : "0"); } catch(_) {}
      applyReducedMotion(on);
      showToast(on ? "Reduced motion on." : "Reduced motion off.", "info", 1600);
    }

    // ── Density toggle (comfortable / compact) ────────────────────
    function _applyDensity(compact) {
      document.body.classList.toggle("density-compact", compact);
      const btn = document.getElementById("density-btn");
      if (btn) btn.classList.toggle("btn-active", compact);
    }
    function toggleDensity() {
      const compact = !document.body.classList.contains("density-compact");
      try { localStorage.setItem("lifetxt_density", compact ? "compact" : "comfortable"); } catch(_) {}
      _applyDensity(compact);
      showToast(compact ? "Compact density." : "Comfortable density.", "info", 1800);
    }
    document.addEventListener("DOMContentLoaded", () => {
      let stored = "";
      try { stored = localStorage.getItem("lifetxt_density") || ""; } catch(_) {}
      if (stored === "compact") _applyDensity(true);
    });

    // ── Back-to-top button ────────────────────────────────────────
    window.addEventListener("scroll", () => {
      const btn = document.getElementById("back-to-top");
      if (btn) btn.classList.toggle("visible", window.scrollY > 400);
    }, {passive: true});

    // ── Clear view preset ─────────────────────────────────────────

    // ── Drawer: copy ID to clipboard ──────────────────────────────
    function drawerCopyId() {
      if (!drawerItem) return;
      const idKey = (appConfig?.ids?.key) || "id";
      const idVal = drawerItem?.details?.[idKey]?.[0] || drawerItem?.id || "";
      if (!idVal) { showToast("No ID on this item.", "error"); return; }
      navigator.clipboard.writeText(String(idVal)).then(
        () => showToast("Copied: " + idVal, "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    // ── Drawer: copy as Markdown ───────────────────────────────────
    function drawerCopyMarkdown() {
      if (!drawerItem) return;
      const item = drawerItem;
      const tick = item.status === "[x]" ? "x" : item.status === "[-]" ? "-" : " ";
      const due = item?.details?.due?.[0] ? ` — due: ${item.details.due[0]}` : "";
      const proj = item?.details?.project?.[0] ? ` — project: ${item.details.project[0]}` : "";
      const tags = (item?.details?.tag || []).map(t => `#${t}`).join(" ");
      const md = `- [${tick}] ${item.title}${due}${proj}${tags ? " " + tags : ""}`;
      navigator.clipboard.writeText(md).then(
        () => showToast("Copied as Markdown.", "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    // ── Drawer: share deep-link ────────────────────────────────────
    function drawerShareLink() {
      if (!drawerItem) return;
      const url = location.origin + location.pathname + "?line=" + encodeURIComponent(drawerItem.line);
      navigator.clipboard.writeText(url).then(
        () => showToast("Link copied: ?line=" + drawerItem.line, "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    // ── Context menu: copy line number + share link ───────────────
    function ctxCopyLineNumber() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      navigator.clipboard.writeText(String(t.line)).then(
        () => showToast("Line " + t.line + " copied.", "success"),
        () => showToast("Copy failed.", "error")
      );
    }
    function ctxShareLink() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      const url = location.origin + location.pathname + "?line=" + encodeURIComponent(t.line);
      navigator.clipboard.writeText(url).then(
        () => showToast("Link copied: ?line=" + t.line, "success"),
        () => showToast("Copy failed.", "error")
      );
    }

    // ── Agenda: blocked-item filter (all / only / hide) ───────────
    function agendaBlockedMode() {
      return firstParam(query(), ["agenda_blocked"], "");
    }
    function _syncAgendaBlockedBtn(mode) {
      const btn = document.getElementById("agenda-blocked-btn");
      if (!btn) return;
      btn.textContent = mode === "only" ? "⚡ Only" : mode === "hide" ? "⚡ Hidden" : "⚡ All";
      btn.classList.toggle("active", !!mode);
    }
    function toggleAgendaBlocked() {
      const modes = ["", "only", "hide"];
      const next = modes[(modes.indexOf(agendaBlockedMode()) + 1) % modes.length];
      const params = query();
      if (next) params.set("agenda_blocked", next);
      else params.delete("agenda_blocked");
      history.replaceState(null, "", `${location.pathname}${params.toString() ? "?" + params.toString() : ""}`);
      loadAgenda();
    }

    // ── Agenda: "view all" — set agenda_limit to 0 ───────────────
    function setAgendaLimit(n) {
      const params = query();
      if (n === 0) params.delete("agenda_limit");
      else params.set("agenda_limit", String(n));
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadAgenda();
    }

    // ── Context menu ──────────────────────────────────────────────
    let ctxTarget = null;
    function openCtxMenu(e, item) {
      e.preventDefault();
      ctxTarget = item;
      const menu = document.getElementById("ctx-menu");
      if (!menu) return;
      menu.style.display = "";
      menu.style.left = Math.min(e.clientX, window.innerWidth - 170) + "px";
      menu.style.top = Math.min(e.clientY, window.innerHeight - 160) + "px";
      const doneEl = document.getElementById("ctx-done");
      if (doneEl) doneEl.style.display = (item?.editable && !["[x]","[-]"].includes(item?.status)) ? "" : "none";
    }
    function closeCtxMenu() {
      const menu = document.getElementById("ctx-menu");
      if (menu) menu.style.display = "none";
      ctxTarget = null;
    }
    document.addEventListener("click", function(e) {
      const menu = document.getElementById("ctx-menu");
      if (menu && !menu.contains(e.target)) closeCtxMenu();
    });
    document.addEventListener("contextmenu", function(e) {
      // Close menu if right-clicking outside of an item row
      if (!e.target.closest(".item")) closeCtxMenu();
    });
    document.addEventListener("keydown", function(e) { if (e.key === "Escape") closeCtxMenu(); }, true);
    async function ctxMarkDone() {
      const t = ctxTarget; closeCtxMenu();
      if (!t || !t.editable) return;
      const prevPayload = {status: t.status, type: t.type, title: t.title, details: t.details || {}};
      try {
        await api(`/api/items/${t.line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({...prevPayload, status: "[x]"}),
        });
        registerUndo("Marked done.", async () => {
          await api(`/api/items/${t.line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(prevPayload),
          });
        });
        await refreshAll();
      } catch(e) {
        showToast("Failed: " + e.message, "error");
      }
    }
    function ctxCopyTitle() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      navigator.clipboard.writeText(t.title || "").then(
        () => showToast("Copied: " + (t.title || ""), "success"),
        () => showToast("Copy failed.", "error")
      );
    }
    function ctxCopyId() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      const idKey = appConfig?.ids?.key || "id";
      const idVal = t?.details?.[idKey]?.[0] || t?.id || "";
      if (!idVal) { showToast("No ID on this item.", "error"); return; }
      navigator.clipboard.writeText(String(idVal)).then(
        () => showToast("Copied: " + idVal, "success"),
        () => showToast("Copy failed.", "error")
      );
    }
    function ctxOpenDrawer() {
      const t = ctxTarget; closeCtxMenu();
      if (t) openDrawer(t);
    }
    function ctxEdit() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      selectItem(t);
      openEditorModal();
    }
    function ctxDuplicate() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      openEditorModal();
      document.getElementById("edit-status").value = "[ ]";
      document.getElementById("edit-type").value = t.type || "T";
      document.getElementById("edit-title").value = t.title || "";
      document.getElementById("edit-details").value = detailsToText(t.details || {});
      selectedItem = null;
      document.getElementById("editor-heading").textContent = "New Record (duplicate)";
      document.getElementById("save-button").textContent = "Create";
      document.getElementById("delete-button").disabled = true;
      updateTypeHints(t.type || "T");
      setEditorDisabled(false);
      document.getElementById("edit-title").focus();
      showToast("Duplicated — edit and save to create.", "info");
    }
    function ctxShowRawPath() {
      const t = ctxTarget; closeCtxMenu();
      if (!t) return;
      const path = t.source || "(unknown source)";
      showToast("File: " + path, "info", 5000);
    }

    // ── Jump to line number ───────────────────────────────────────
    function jumpToLine() {
      const n = prompt("Go to line number:");
      if (!n || !n.trim()) return;
      const lineNum = parseInt(n.trim(), 10);
      if (!isNaN(lineNum)) openItemByLine(lineNum);
    }
    async function openItemByLine(lineNum) {
      try {
        const data = await api(`/api/items/${lineNum}`);
        if (data?.item) { openDrawer(data.item); selectItem(data.item); }
        else showToast("No item at line " + lineNum, "error");
      } catch(e) { showToast("Line " + lineNum + ": " + e.message, "error"); }
    }

    // ── Inline completion ─────────────────────────────────────────
    //
    // One widget serves every input that completes. A field supplies a
    // *resolver* that looks at the text and the caret and answers "what is
    // being typed right now" as {kind, prefix, start, end}; the widget owns
    // fetching, ranking display, keyboard handling, and replacement.
    //
    // Candidates come from /api/complete, which reads the same life.txt the
    // shell completion and the TUI read, so all three agree.

    const CPL_STATIC = {
      // Date words the shorthand accepts. These are grammar, not file
      // content, so they never need a round trip.
      date: ["today", "tomorrow", "yesterday", "monday", "tuesday", "wednesday",
             "thursday", "friday", "saturday", "sunday", "next_monday",
             "next_tuesday", "next_wednesday", "next_thursday", "next_friday",
             "next_saturday", "next_sunday", "next_week",
             "+1d", "+3d", "+1w", "-1w", "+1m", "+1y"],
    };

    let _cplPop = null;
    let _cplState = null;
    let _cplSeq = 0;

    function cplPopup() {
      if (_cplPop) return _cplPop;
      _cplPop = document.createElement("div");
      _cplPop.className = "cpl-pop";
      _cplPop.setAttribute("role", "listbox");
      _cplPop.setAttribute("data-no-i18n", "");
      document.body.appendChild(_cplPop);
      return _cplPop;
    }

    function cplClose() {
      const pop = cplPopup();
      pop.classList.remove("open");
      pop.innerHTML = "";
      if (_cplState) _cplState.items = [];
    }

    function cplIsOpen() {
      return cplPopup().classList.contains("open");
    }

    async function cplFetch(kind, prefix) {
      if (CPL_STATIC[kind]) {
        const needle = String(prefix || "").toLowerCase();
        return CPL_STATIC[kind].filter(v => v.toLowerCase().startsWith(needle));
      }
      try {
        const data = await api(`/api/complete?kind=${encodeURIComponent(kind)}` +
                               `&prefix=${encodeURIComponent(prefix || "")}&limit=20`);
        return data.candidates || [];
      } catch (e) {
        // Completion is an assist, never a blocker: a failed lookup just
        // means no suggestions, not an error banner over the user's typing.
        return [];
      }
    }

    function cplRender(input, token, values) {
      const pop = cplPopup();
      if (!values.length) { cplClose(); return; }

      _cplState = {input: input, token: token, items: values, index: 0};
      pop.innerHTML = values.map((value, i) =>
        `<div class="cpl-row${i === 0 ? " focus" : ""}" role="option" data-index="${i}">` +
        `<span class="cpl-kind">${escapeHtml(token.kind)}</span>${escapeHtml(value)}</div>`
      ).join("");

      const rect = input.getBoundingClientRect();
      pop.style.left = `${Math.round(rect.left + window.scrollX)}px`;
      pop.style.top = `${Math.round(rect.bottom + window.scrollY + 4)}px`;
      pop.style.minWidth = `${Math.round(Math.min(rect.width, 340))}px`;
      pop.classList.add("open");

      // Flip above the field when the popup would fall off the viewport,
      // which is the normal case for a bar near the bottom on a phone.
      const popRect = pop.getBoundingClientRect();
      if (popRect.bottom > window.innerHeight && rect.top > popRect.height) {
        pop.style.top = `${Math.round(rect.top + window.scrollY - popRect.height - 4)}px`;
