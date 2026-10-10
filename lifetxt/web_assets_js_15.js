      } catch(e) {
        showToast("Import error: " + e.message, "error");
      }
    }

    // All bulk handlers live at page scope; CSS displays modals only with .open.
    let bulkPreviewRevision = 0;
    let bulkPreviewText = "";
    let bulkSavePending = false;
    let bulkLastFocused = null;

    function invalidateBulkPreview() {
      ++bulkPreviewRevision;
      bulkPreviewText = "";
      const add = document.getElementById("bulk-input-add");
      if (add) add.disabled = true;
      const preview = document.getElementById("bulk-input-preview");
      if (preview) preview.textContent = "Input changed. Preview again before Add all.";
    }

    function openBulkInput() {
      const modal = document.getElementById("bulk-input-modal");
      if (!modal) return;
      bulkLastFocused = document.activeElement;
      invalidateBulkPreview();
      modal.hidden = false;
      modal.classList.add("open");
      document.body.classList.add("modal-open");
      document.getElementById("bulk-input-text")?.focus();
    }

    function closeBulkInput() {
      if (bulkSavePending) return;
      const modal = document.getElementById("bulk-input-modal");
      if (!modal) return;
      invalidateBulkPreview();
      modal.classList.remove("open");
      modal.hidden = true;
      if (!document.querySelector(".modal-backdrop.open")) {
        document.body.classList.remove("modal-open");
      }
      bulkLastFocused?.focus?.();
      bulkLastFocused = null;
    }

    async function previewBulkInput() {
      if (bulkSavePending) return;
      const input = document.getElementById("bulk-input-text");
      const root = document.getElementById("bulk-input-preview");
      if (!input || !root) return;
      const text = input.value;
      invalidateBulkPreview();
      const revision = bulkPreviewRevision;
      if (!text.trim()) { root.textContent = "Paste at least one life.txt record."; return; }
      if (new TextEncoder().encode(text).length > 512 * 1024) {
        root.textContent = "Batch input is limited to 512 KiB.";
        return;
      }
      root.textContent = "Checking…";
      try {
        const data = await api("/api/items/parse", {
          method: "POST", headers: {"Content-Type":"application/json"},
          body: JSON.stringify({line: text}),
        });
        if (revision !== bulkPreviewRevision || input.value !== text) return;
        const diagnostics = data.diagnostics || [];
        const errors = diagnostics.filter(d => d.severity === "error");
        const warnings = diagnostics.filter(d => d.severity === "warning");
        const count = Number(data.item_count || 0);
        const summary = count + " logical record(s), " + errors.length +
          " error(s), " + warnings.length + " warning(s).";
        if (!data.ok || errors.length || !count || count > 500) {
          root.textContent = summary + (count > 500 ? " Maximum 500 records." :
            errors.length ? " " + errors.map(d => d.code + ": " + d.message).join(" ") :
            " Nothing to save.");
          return;
        }
        // A preview can be used in read-only mode, but saving never can.
        const health = await api("/api/health", {cache:"no-store"});
        if (revision !== bulkPreviewRevision || input.value !== text) return;
        if (health.read_only || !health.writable_path) {
          root.textContent = summary + " Read-only workspace: preview only.";
          return;
        }
        if (!health.source_revision) {
          root.textContent = summary + " Source revision unavailable; saving disabled.";
          return;
        }
        bulkPreviewText = text;
        root.textContent = summary + " Review the meaning, then choose Add all.";
        document.getElementById("bulk-input-add").disabled = false;
      } catch (error) {
        if (revision === bulkPreviewRevision) {
          root.textContent = "Preview failed: " + (error.message || String(error));
        }
      }
    }

    async function addAllBulkInput() {
      const input = document.getElementById("bulk-input-text");
      const add = document.getElementById("bulk-input-add");
      if (bulkSavePending || !input || !add || add.disabled) return;
      if (!bulkPreviewText || input.value !== bulkPreviewText) {
        invalidateBulkPreview();
        showToast("Input changed. Preview again before saving.", "warning");
        return;
      }
      if (!window.confirm("Add all previewed records? This writes to life.txt.")) return;
      if (input.value !== bulkPreviewText) {
        invalidateBulkPreview();
        return;
      }
      bulkSavePending = true;
      input.disabled = true;
      add.disabled = true;
      try {
        const health = await api("/api/health", {cache:"no-store"});
        if (health.read_only || !health.writable_path) {
          throw Object.assign(new Error("This workspace is read-only."), {status:403});
        }
        if (!health.source_revision) {
          throw Object.assign(new Error("Source revision unavailable."), {status:428});
        }
        const result = await api("/api/items/batch", {
          method: "POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            text: bulkPreviewText, expected_source_revision: health.source_revision,
          }),
        });
        if (!result.ok || !result.saved) throw new Error("Save result is uncertain.");
        showToast("Added " + result.saved + " record(s).", "success");
        input.value = "";
        bulkSavePending = false;
        input.disabled = false;
        closeBulkInput();
        await loadItems();
      } catch (error) {
        bulkSavePending = false;
        input.disabled = false;
        // On any failure require fresh review, never silently resend.
        invalidateBulkPreview();
        const message = error.status === 409 ?
          "File changed. Review and preview again before retrying." :
          error.status === 403 ? "Read-only workspace: nothing was saved." :
          error.status === 422 ? "Validation failed; no records were saved." :
          error.status === 413 ? "Batch exceeds the 512 KiB limit." :
          error.status === 428 ? "Source revision is unavailable; nothing was sent." :
          "Save outcome uncertain. Check Items before retrying to avoid duplicates.";
        const root = document.getElementById("bulk-input-preview");
        if (root) root.textContent = message;
        showToast(message, "error");
      }
    }

    document.addEventListener("keydown", event => {
      const modal = document.getElementById("bulk-input-modal");
      if (event.key === "Escape" && modal && !modal.hidden && !bulkSavePending) {
        event.preventDefault();
        closeBulkInput();
      }
    });

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
    function writeClipboardText(text, onSuccess, onFailure) {
      const succeed = () => { if (onSuccess) onSuccess(); };
      const fail = () => { if (onFailure) onFailure(); };
      if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(String(text)).then(succeed, () => {
          if (!_legacyCopyText(text)) fail(); else succeed();
        });
        return;
      }
      if (!_legacyCopyText(text)) fail(); else succeed();
    }
    function _legacyCopyText(text) {
      if (typeof document === "undefined" || !document.createElement || !document.body || !document.body.appendChild) return false;
      const textarea = document.createElement("textarea");
      textarea.value = String(text);
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      let copied = false;
      try { copied = document.execCommand("copy"); } catch (_) { copied = false; }
      if (textarea.remove) textarea.remove();
      else textarea.parentNode?.removeChild(textarea);
      return copied;
    }
    function drawerCopyId() {
      if (!drawerItem) return;
      const idKey = (appConfig?.ids?.key) || "id";
      const idVal = drawerItem?.details?.[idKey]?.[0] || drawerItem?.id || "";
      if (!idVal) { showToast("No ID on this item.", "error"); return; }
      writeClipboardText(String(idVal), () => showToast("Copied: " + idVal, "success"), () => showToast("Copy failed.", "error"));
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
      writeClipboardText(md, () => showToast("Copied as Markdown.", "success"), () => showToast("Copy failed.", "error"));
    }

    // ── Share: canonical record deep link (#839) ───────────────────
    // Builds the same URL #838's ?id=/?line= deep-link loading resolves
    // back to, using URL/URLSearchParams rather than manual string
    // concatenation so the current origin/base path and any unrelated
    // existing query parameters are preserved. Prefers the stable
    // canonical id: over the line number, since a line shifts whenever
    // the file changes above it.
    function buildItemDeepLink(item) {
      const itemId = _drawerIdFor(item);
      const url = new URL(location.href);
      url.searchParams.delete("id");
      url.searchParams.delete("line");
      if (itemId) url.searchParams.set("id", itemId);
      else if (item?.line != null) url.searchParams.set("line", String(item.line));
      else return null;
      return {url: url.toString(), label: itemId ? ("id=" + itemId) : ("line=" + item.line)};
    }
    function copyItemDeepLink(item) {
      const built = item ? buildItemDeepLink(item) : null;
      if (!built) { showToast("No record selected.", "error"); return; }
      const announce = (ok) => {
        if (ok) showToast(t("Link copied:") + " " + built.label, "success");
        else showToast(t("Copy failed. Select and copy manually:") + " " + built.url, "error", 8000);
      };
      writeClipboardText(built.url, () => announce(true), () => announce(false));
    }
    function drawerShareLink() { copyItemDeepLink(drawerItem); }

    // Browser-side representation of #840's authoritative formatter. Using
    // encodeURIComponent for the single path segment matches Python's
    // quote(..., safe="") contract for supported canonical ids.
    function buildStableItemLink(item) {
      const itemId = _drawerIdFor(item);
      if (!itemId) return null;
      const encoded = encodeURIComponent(itemId).replace(/[!'()*]/g, ch =>
        "%" + ch.charCodeAt(0).toString(16).toUpperCase()
      );
      return "lifetxt://item/" + encoded;
    }
    function drawerCopyStableLink() {
      const link = buildStableItemLink(drawerItem);
      if (!link) { showToast(t("This record has no canonical ID."), "error"); return; }
      const announce = (ok) => {
        if (ok) showToast(t("Stable link copied:") + " " + link, "success");
        else showToast(t("Copy failed. Select and copy manually:") + " " + link, "error", 8000);
      };
      writeClipboardText(link, () => announce(true), () => announce(false));
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
      copyItemDeepLink(t);
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
    async function openItemByLine(lineNum, urlMode = "push") {
      try {
        const data = await api(`/api/items/${lineNum}`);
        if (data?.item) { openDrawer(data.item, urlMode); selectItem(data.item); }
        else showToast("No item at line " + lineNum, "error");
      } catch(e) { showToast("Line " + lineNum + ": " + e.message, "error"); }
    }

    // Open a record directly by its canonical id: (#838), sharing the
    // #837 exact-ID Web API route. An unknown id shows a clear
    // not-found state rather than silently opening another record.
    async function openItemById(itemId, urlMode = "push") {
      try {
        const data = await api(`/api/items/${encodeURIComponent(itemId)}`);
        if (data?.item) { openDrawer(data.item, urlMode); selectItem(data.item); }
        else showToast(`No record found for id "${itemId}".`, "error");
      } catch(e) {
        const status = Number(e?.status);
        if (status === 404) showToast(`No record found for id "${itemId}".`, "error");
        else showToast(`Could not load id "${itemId}": ` + (e.message || e), "error");
      }
    }

    // Restore (or close) the drawer to match the current ?id=/?line=
    // state after Back/Forward navigation (#838). The URL is already
    // correct at this point (the browser just restored it), so drawer
    // updates here must never themselves push/replace history.
    function syncDrawerFromUrl() {
      const params = query();
      const idParam = params.get("id");
      const lineParam = params.get("line");
      if (idParam) {
        if (_drawerIdFor(drawerItem || {}) !== idParam) openItemById(idParam, "none");
        return;
      }
      if (lineParam) {
        const lineNum = parseInt(lineParam, 10);
        if (!isNaN(lineNum) && (!drawerItem || drawerItem.line !== lineNum)) {
          openItemByLine(lineNum, "none");
        }
        return;
      }
      if (drawerItem) closeDrawer("none");
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
