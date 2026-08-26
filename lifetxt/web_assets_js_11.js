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