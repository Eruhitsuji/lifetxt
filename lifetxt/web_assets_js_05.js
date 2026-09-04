        node.type = "button";
        node.className = "item" + (dueCls ? " " + dueCls : "");
        if (kioskNow && _kioskLastFingerprints && _kioskLastFingerprints.get(stableKey) !== fingerprint) {
          node.classList.add("kiosk-changed");
        }
        if (selectedItem && item.line === selectedItem.line && item.editable === selectedItem.editable) {
          node.classList.add("selected");
        }
        const _bulkKey = String(item.line) + "|" + (item.source || "");
        node.addEventListener("click", (e) => {
          if (e.target.closest(".ref-link")) return;
          if (e.target.closest(".item-check")) return;
          selectItem(item);
          openDrawer(item);
        });
        node.addEventListener("contextmenu", (e) => openCtxMenu(e, item));
        const isBulkSelected = bulkSelectedLines.has(_bulkKey);
        if (isBulkSelected) node.classList.add("bulk-selected");
        node.innerHTML = `
          <input type="checkbox" class="item-check" title="Select for bulk action" ${isBulkSelected ? "checked" : ""}>
          <span class="status-badge ${statusCls}" title="${escapeHtml(item.status)}">${escapeHtml(statusLabel)}</span>
          <span class="type-badge ${typeCls}">${escapeHtml(item.type)}</span>
          <div>
            <div class="title markdown">${titleHtml}${parentInd}${occurrenceBadge}${generatedBadge}</div>
            <div class="meta">${escapeHtml(detailText(item.details))}${refLinks}${dueRel}</div>
            ${preview}
          </div>
          <span class="source">${escapeHtml(item.source || `line ${item.line || ""}`)}${item.generated ? " / generated" : ""}${item.editable ? "" : " / read-only"}</span>
        `;
        node.querySelector(".item-check").addEventListener("change", (ev) => {
          ev.stopPropagation();
          if (ev.target.checked) bulkSelectedLines.add(_bulkKey);
          else bulkSelectedLines.delete(_bulkKey);
          node.classList.toggle("bulk-selected", ev.target.checked);
          _updateBulkToolbar();
        });
        node.querySelector(".item-check").addEventListener("click", (ev) => {
          ev.stopPropagation();
        });
        const statusBadge = node.querySelector(".status-badge");
        if (statusBadge && item.editable && !kioskNow) {
          statusBadge.classList.add("clickable");
          statusBadge.title = `${item.status} — click to cycle status`;
          statusBadge.addEventListener("click", (ev) => {
            ev.stopPropagation();
            cycleItemStatus(item);
          });
        }
        node._lifetxtItem = item;
        return node;
    }

    // ── Inline status cycling on item rows ─────────────────────────
    const STATUS_INLINE_CYCLE = ["[ ]", "[/]", "[x]"];
    async function cycleItemStatus(item) {
      if (!item.editable) return;
      const idx = STATUS_INLINE_CYCLE.indexOf(item.status);
      const next = STATUS_INLINE_CYCLE[(idx + 1) % STATUS_INLINE_CYCLE.length];
      const line = item.line;
      const prevPayload = {status: item.status, type: item.type, title: item.title, details: item.details || {}};
      try {
        await api(`/api/items/${line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({...prevPayload, status: next}),
        });
        registerUndo(`Status changed to ${next}.`, async () => {
          await api(`/api/items/${line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(prevPayload),
          });
        });
        await refreshAll();
      } catch(e) {
        showToast("Status change failed: " + (e.message || e), "error");
      }
    }

    // ── Keyboard focus navigation (j/k/x/Enter) ────────────────────
    let _kbIndex = -1;
    function _kbNodes() {
      return [...document.querySelectorAll("#items .item")];
    }
    function kbMove(delta) {
      const nodes = _kbNodes();
      if (!nodes.length) return;
      const next = _kbIndex === -1
        ? (delta > 0 ? 0 : nodes.length - 1)
        : Math.max(0, Math.min(nodes.length - 1, _kbIndex + delta));
      nodes.forEach(n => n.classList.remove("kb-focus"));
      _kbIndex = next;
      nodes[next].classList.add("kb-focus");
      nodes[next].scrollIntoView({block: "nearest", behavior: "smooth"});
    }
    function kbFocusedItem() {
      const nodes = _kbNodes();
      if (_kbIndex < 0 || _kbIndex >= nodes.length) return null;
      return nodes[_kbIndex]._lifetxtItem || null;
    }
    function kbActivate() {
      const item = kbFocusedItem();
      if (!item) return false;
      selectItem(item);
      openDrawer(item);
      return true;
    }
    function kbToggleSelect() {
      const nodes = _kbNodes();
      if (_kbIndex < 0 || _kbIndex >= nodes.length) return;
      const check = nodes[_kbIndex].querySelector(".item-check");
      if (check) check.click();
    }

    // ── Export filtered items (CSV / JSON / Markdown) ──────────────
    function exportItems(format) {
      const items = currentItems || [];
      if (!items.length) { showToast("No items to export.", "warning"); return; }
      let content, mime, ext;
      if (format === "json") {
        content = JSON.stringify(items.map(i => ({
          line: i.line, source: i.source, status: i.status, type: i.type,
          title: i.title, details: i.details || {},
        })), null, 2);
        mime = "application/json"; ext = "json";
      } else if (format === "markdown") {
        content = items.map(i => {
          const tick = i.status === "[x]" ? "x" : i.status === "[-]" ? "-" : " ";
          const due = i?.details?.due?.[0] ? ` (due: ${i.details.due[0]})` : "";
          const proj = i?.details?.project?.[0] ? ` [${i.details.project[0]}]` : "";
          return `- [${tick}] **${i.type}** ${i.title}${due}${proj}`;
        }).join("\n");
        mime = "text/markdown"; ext = "md";
      } else {
        const esc = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
        const header = ["line", "source", "status", "type", "title", "due", "project", "tags", "details"].join(",");
        const rows = items.map(i => [
          i.line ?? "", i.source ?? "", i.status, i.type, i.title,
          i?.details?.due?.[0] || "",
          (i?.details?.project || []).join(";"),
          (i?.details?.tag || []).join(";"),
          detailText(i.details),
        ].map(esc).join(","));
        content = [header, ...rows].join("\n");
        mime = "text/csv"; ext = "csv";
      }
      const blob = new Blob([content], {type: mime});
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `lifetxt-items-${new Date().toISOString().slice(0, 10)}.${ext}`;
      a.click();
      URL.revokeObjectURL(a.href);
      showToast(`Exported ${items.length} item(s) as ${ext.toUpperCase()}.`, "success");
    }

    // ── Undo for destructive actions ───────────────────────────────
    let _undoStack = [];
    let _undoSeq = 0;
    function registerUndo(message, undoFn) {
      const entry = {
        id: ++_undoSeq,
        message: String(message || "Undo action"),
        run: undoFn,
        createdAt: Date.now(),
      };
      _undoStack = [entry, ..._undoStack].slice(0, 5);
      renderUndoHistory();
      const container = document.getElementById("toast-container");
      const el = document.createElement("div");
      el.className = "toast success";
      const span = document.createElement("span");
      span.textContent = message;
      const btn = document.createElement("button");
      btn.className = "undo-btn";
      btn.textContent = "Undo";
      btn.addEventListener("click", async () => { el.remove(); await performUndo(entry.id); });
      el.append(span, btn);
      container.appendChild(el);
      setTimeout(() => el.remove(), 8000);
    }
    async function performUndo(entryId) {
      const idx = entryId == null ? 0 : _undoStack.findIndex(entry => entry.id === entryId);
      if (idx < 0 || !_undoStack[idx]) return;
      const [entry] = _undoStack.splice(idx, 1);
      renderUndoHistory();
      try {
        await entry.run();
        showToast("Undone.", "success");
        await refreshAll();
      } catch(e) {
        showToast("Undo failed: " + (e.message || e), "error");
      }
    }
    function openUndoHistoryModal() {
      renderUndoHistory();
      openManagedModal(document.getElementById("undo-modal"), "button");
    }
    function closeUndoHistoryModal() {
      closeManagedModal(document.getElementById("undo-modal"));
    }
    function renderUndoHistory() {
      const list = document.getElementById("undo-history-list");
      if (!list) return;
      if (!_undoStack.length) {
        list.innerHTML = `<div class="empty">No undoable actions in this session.</div>`;
        return;
      }
      list.innerHTML = _undoStack.map(entry => {
        const age = Math.max(0, Math.round((Date.now() - entry.createdAt) / 1000));
        const ageText = age < 60 ? `${age}s ago` : `${Math.floor(age / 60)}m ago`;
        return `<div class="undo-history-row">` +
          `<span class="undo-history-label">${escapeHtml(entry.message)}</span>` +
          `<span class="undo-history-time">${escapeHtml(ageText)}</span>` +
          `<button type="button" class="secondary" onclick="performUndo(${entry.id})">Undo</button>` +
          `</div>`;
      }).join("");
    }
    function _updateBulkToolbar() {
      const bar = document.getElementById("bulk-toolbar");
      const cnt = document.getElementById("bulk-count");
      if (!bar) return;
      const n = bulkSelectedLines.size;
      bar.classList.toggle("visible", n > 0);
      if (cnt) cnt.textContent = `${n} selected`;
    }
    function bulkClearSelection() {
      bulkSelectedLines.clear();
      renderItems(currentItems);
    }
    function _bulkTargets(extraFilter) {
      const keys = new Set(bulkSelectedLines);
      return currentItems.filter(i =>
        keys.has(String(i.line) + "|" + (i.source || "")) && i.editable && (!extraFilter || extraFilter(i))
      );
    }
    async function _bulkUpdateStatus(targets, statusValue, message) {
      const restores = [];
      let done = 0;
      for (const item of targets) {
        try {
          await api(`/api/items/${item.line}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ status: statusValue, type: item.type, title: item.title, details: item.details || {} }) });
          restores.push({line: item.line, payload: {status: item.status, type: item.type, title: item.title, details: item.details || {}}});
          done++;
        } catch(e) { /* skip */ }
      }
      bulkSelectedLines.clear();
      registerUndo(message.replace("{n}", String(done)), async () => {
        for (const r of restores) {
          await api(`/api/items/${r.line}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(r.payload) });
        }
      });
      await refreshAll();
    }
    async function bulkMarkDone() {
      const targets = _bulkTargets(i => !["[x]","[-]"].includes(i.status));
      if (!targets.length) { showToast("No editable open items selected.", "warning"); return; }
      await _bulkUpdateStatus(targets, "[x]", "Marked {n} item(s) done.");
    }
    async function bulkSetStatus(statusValue) {
      const targets = _bulkTargets(i => i.status !== statusValue);
      if (!targets.length) { showToast("No editable items selected (or already that status).", "warning"); return; }
      await _bulkUpdateStatus(targets, statusValue, `Set {n} item(s) to ${statusValue}.`);
    }
    async function bulkSetProject() {
      const targets = _bulkTargets();
      if (!targets.length) { showToast("No editable items selected.", "warning"); return; }
      const value = prompt(`Set project on ${targets.length} item(s) to (empty removes project):`);
      if (value === null) return;
      const proj = value.trim();
      const restores = [];
      let done = 0;
      for (const item of targets) {
        const details = JSON.parse(JSON.stringify(item.details || {}));
        if (proj) details.project = [proj];
        else delete details.project;
        try {
          await api(`/api/items/${item.line}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ status: item.status, type: item.type, title: item.title, details }) });
          restores.push({line: item.line, payload: {status: item.status, type: item.type, title: item.title, details: item.details || {}}});
          done++;
        } catch(e) { /* skip */ }
      }
      bulkSelectedLines.clear();
      registerUndo(proj ? `Set project:${proj} on ${done} item(s).` : `Removed project on ${done} item(s).`, async () => {
        for (const r of restores) {
          await api(`/api/items/${r.line}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(r.payload) });
        }
      });
      await refreshAll();
    }
    async function bulkDelete() {
      const targets = _bulkTargets();
      if (!targets.length) { showToast("No editable items selected.", "warning"); return; }
      if (!confirm(`Delete ${targets.length} item(s)?`)) return;
      targets.sort((a,b) => b.line - a.line);
      const rawLines = [];
      let done = 0;
      for (const item of targets) {
        try {
          await api(`/api/items/${item.line}`, { method: "DELETE" });
          if (item.text) rawLines.unshift(item.text);
          done++;
        }
        catch(e) { /* skip */ }
      }
      bulkSelectedLines.clear();
      registerUndo(`Deleted ${done} item(s).`, async () => {
        for (const line of rawLines) {
          await api("/api/items/raw", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({line}) });
        }
      });
      await refreshAll();
    }
    function openEditorModal() {
      openManagedModal(document.getElementById("editor-modal"), "#edit-title");
    }
    function closeEditorModal() {
      closeManagedModal(document.getElementById("editor-modal"));
    }
    function selectItem(item) {
      if (isDisplayMode()) return;
      selectedItem = item;
      document.getElementById("editor-heading").textContent = item.editable ? `Edit line ${item.line}` : "Read-only record";
      ensureBeginnerProfileVocabulary();
      refreshAuthoringModeOptions(item.status, item.type);
      document.getElementById("edit-status").value = item.status;
      document.getElementById("edit-type").value = item.type;
      document.getElementById("edit-title").value = item.title;
      document.getElementById("edit-details").value = detailsToText(item.details);
      document.getElementById("save-button").textContent = "Save";
      document.getElementById("delete-button").disabled = !item.editable;
      document.getElementById("editor-note").textContent = item.editable
        ? "Editing the writable file. Save replaces this record line."
        : "This record comes from a read-only source.";
      setEditorDisabled(!item.editable);
      renderItems(currentItems);
    }
    function newItem() {
      openEditorModal();
      selectedItem = null;
      document.getElementById("editor-heading").textContent = "New Record";
      ensureBeginnerProfileVocabulary();
      refreshAuthoringModeOptions("[ ]", "T");
      document.getElementById("edit-status").value = "[ ]";
      document.getElementById("edit-type").value = "T";
      document.getElementById("edit-title").value = "";
      document.getElementById("edit-details").value = "";
      document.getElementById("save-button").textContent = "Create";
      document.getElementById("delete-button").disabled = true;
      document.getElementById("editor-note").textContent = "Create a new record or select an editable row.";
      setEditorDisabled(false);
      renderItems(currentItems);
    }
    // ── Beginner authoring mode (#634) ──────────────────────────────
    // Progressive disclosure over the Beginner / Minimal Profile (#558):
    // beginner mode hides advanced Type/Status options by default, but
    // never drops or rewrites an advanced value already on an opened
    // record -- the current value is always kept selectable even when it
    // falls outside the beginner subset. The vocabulary itself is fetched
    // from /api/beginner-profile (lifetxt/beginner_profile.py), the single
    // Python source of truth, with a matching hardcoded fallback used
    // immediately so the editor is never blocked on that round trip.
    let beginnerProfileVocabulary = { types: ["T", "E", "N"], statuses: ["[ ]", "[x]", "[N]"] };
    let beginnerProfileFetchStarted = false;
    const AUTHORING_FULL_STATUSES = ["[ ]", "[/]", "[x]", "[-]", "[>]", "[?]", "[N]"];
    const AUTHORING_FULL_TYPES = ["T", "E", "D", "R", "H", "N", "S", "M", "J"];
    function ensureBeginnerProfileVocabulary() {
      if (beginnerProfileFetchStarted) return;
      beginnerProfileFetchStarted = true;
      api("/api/beginner-profile").then(data => {
        if (data && Array.isArray(data.types) && Array.isArray(data.statuses)) {
          beginnerProfileVocabulary = { types: data.types, statuses: data.statuses };
        }
        refreshAuthoringModeOptions();
      }).catch(() => { /* keep the hardcoded fallback */ });
    }
    function authoringModePreference() {
      try { return localStorage.getItem("lifetxt_authoring_mode") || "full"; }
      catch (e) { return "full"; }
    }
    function setAuthoringModePreference(mode) {
      try { localStorage.setItem("lifetxt_authoring_mode", mode); } catch (e) { /* ignore */ }
    }
    function _authoringVisibleValues(all, beginnerList, mode, currentValue) {
      if (mode !== "beginner") return all.slice();
      const visible = all.filter(v => beginnerList.includes(v));
      if (currentValue && !visible.includes(currentValue)) visible.push(currentValue);
      return visible;
    }
    function refreshAuthoringModeOptions(desiredStatus, desiredType) {
      const mode = authoringModePreference();
      const statusSel = document.getElementById("edit-status");
      const typeSel = document.getElementById("edit-type");
      if (!statusSel || !typeSel) return;
      const curStatus = desiredStatus !== undefined ? desiredStatus : statusSel.value;
      const curType = desiredType !== undefined ? desiredType : typeSel.value;
      const visStatus = _authoringVisibleValues(AUTHORING_FULL_STATUSES, beginnerProfileVocabulary.statuses, mode, curStatus);
      const visType = _authoringVisibleValues(AUTHORING_FULL_TYPES, beginnerProfileVocabulary.types, mode, curType);
      statusSel.innerHTML = visStatus.map(v => `<option${v === curStatus ? " selected" : ""}>${v}</option>`).join("");
      typeSel.innerHTML = visType.map(v => `<option${v === curType ? " selected" : ""}>${v}</option>`).join("");
      const toggle = document.getElementById("authoring-advanced-toggle");
      if (toggle) toggle.textContent = t(mode === "beginner" ? "Show advanced options" : "Hide advanced options");
    }
    function toggleAuthoringMode() {
      const next = authoringModePreference() === "beginner" ? "full" : "beginner";
      setAuthoringModePreference(next);
      refreshAuthoringModeOptions();
    }
    function setEditorDisabled(disabled) {
      for (const id of ["edit-status", "edit-type", "edit-title", "edit-details", "save-button"]) {
        document.getElementById(id).disabled = disabled;
      }
    }
    function editorPayload() {
      return {
        status: document.getElementById("edit-status").value,
        type: document.getElementById("edit-type").value,
        title: document.getElementById("edit-title").value,
        details: parseDetails(document.getElementById("edit-details").value),
      };
    }
    async function saveItem(event) {
      event.preventDefault();
      const payload = editorPayload();
      try {
        if (selectedItem && selectedItem.editable) {
          await api(`/api/items/${selectedItem.line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
          });
          showToast("Record saved.", "success");
        } else {
          await api("/api/items", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
          });
          showToast("Record created.", "success");
        }
      } catch(e) {
        showToast("Save failed: " + (e.message || e), "error");
        return;
      }
      closeEditorModal();
      selectedItem = null;
      await refreshAll();
    }
    async function deleteSelected() {
      if (!selectedItem || !selectedItem.editable) return;
      if (!confirm(`Delete line ${selectedItem.line}?`)) return;
      const rawLine = selectedItem.text;
      await api(`/api/items/${selectedItem.line}`, {method: "DELETE"});
      if (rawLine) {
        registerUndo("Item deleted.", async () => {
          await api("/api/items/raw", {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({line: rawLine})});
        });
      }
      closeEditorModal();
      selectedItem = null;
