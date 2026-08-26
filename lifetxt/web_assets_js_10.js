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