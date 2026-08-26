            : "";
          html += `<div class="message-thread-row${current}"><div><strong>${escapeHtml(row.title || "")}</strong></div>` +
            `<div class="message-thread-meta">${escapeHtml(sender)} -> ${escapeHtml(recipients)}${when ? " / " + escapeHtml(when) : ""}</div>${actions}</div>`;
        }
        html += `</div>`;
        container.innerHTML = html;
      } catch(e) {
        container.innerHTML = `<div class="drawer-section-title">Message Thread</div><div class="empty">Error: ${escapeHtml(e.message)}</div>`;
      }
    }

    async function replyToMessage(messageId) {
      const titleEl = document.getElementById("message-reply-title");
      const bodyEl = document.getElementById("message-reply-body");
      const title = (titleEl?.value || "").trim();
      const body = (bodyEl?.value || "").trim();
      if (!title && !body) {
        showToast("Reply title or body is required.", "warning");
        return;
      }
      try {
        await api(`/api/messages/id/${encodeURIComponent(messageId)}/reply`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({title: title || body.slice(0, 60) || "Reply", body}),
        });
        if (titleEl) titleEl.value = "";
        if (bodyEl) bodyEl.value = "";
        showToast("Reply added.", "success");
        await refreshAll();
        if (drawerItem) {
          const idKey = appConfig?.ids?.key || "id";
          const currentId = drawerItem?.id || drawerItem?.details?.[idKey]?.[0] || messageId;
          await drawerNavigate(currentId);
        }
      } catch(e) {
        showToast("Reply failed: " + (e.message || e), "error");
      }
    }

    function closeDrawer() {
      closeManagedModal(document.getElementById("detail-drawer"));
      drawerItem = null;
    }

    function drawerEdit() {
      if (!drawerItem) return;
      if (!drawerItem.editable) { showToast("This record is read-only.", "warning"); return; }
      drawerEditing = true;
      document.getElementById("drawer-head-btns").innerHTML =
        `<button class="primary" onclick="drawerSaveEdit()">Save</button>` +
        `<button class="secondary" onclick="drawerCancelEdit()">Cancel</button>`;
      const item = drawerItem;
      const statusOpts = ["[ ]","[/]","[x]","[-]","[>]","[?]","[N]"]
        .map(s => `<option${s === item.status ? " selected" : ""}>${s}</option>`).join("");
      const typeOpts = ["T","E","D","R","H","N","S","M","J"]
        .map(t => `<option${t === item.type ? " selected" : ""}>${t}</option>`).join("");
      document.getElementById("drawer-body").innerHTML =
        `<form class="drawer-edit-form" onsubmit="event.preventDefault();drawerSaveEdit()">` +
        `<label>Status<select id="drawer-edit-status">${statusOpts}</select></label>` +
        `<label>Type<select id="drawer-edit-type">${typeOpts}</select></label>` +
        `<label>Title<input id="drawer-edit-title" value="${escapeHtml(item.title)}" required autocomplete="off"></label>` +
        `<label>Details<textarea id="drawer-edit-details" rows="7" placeholder="due:2026-01-01&#10;project:work">${escapeHtml(detailsToText(item.details))}</textarea></label>` +
        `</form>`;
      // Freshly built markup, so its completion has to be wired up again.
      setupCompletion();
      document.getElementById("drawer-edit-title").focus();
    }

    function drawerCancelEdit() {
      drawerEditing = false;
      openDrawer(drawerItem);
    }

    async function drawerSaveEdit() {
      if (!drawerItem || !drawerItem.editable) return;
      const saveLine = drawerItem.line;
      const titleEl = document.getElementById("drawer-edit-title");
      if (!titleEl || !titleEl.value.trim()) { showToast("Title is required.", "warning"); return; }
      const payload = {
        status: document.getElementById("drawer-edit-status").value,
        type: document.getElementById("drawer-edit-type").value,
        title: titleEl.value.trim(),
        details: parseDetails(document.getElementById("drawer-edit-details").value),
      };
      try {
        await api(`/api/items/${saveLine}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        drawerEditing = false;
        showToast("Record saved.", "success");
        await refreshAll();
        const updated = (currentItems || []).find(i => i.line === saveLine && i.editable);
        if (updated) openDrawer(updated);
      } catch(e) {
        showToast("Save failed: " + (e.message || e), "error");
      }
    }

    async function drawerMarkDone() {
      if (!drawerItem || !drawerItem.editable) return;
      const line = drawerItem.line;
      const prevPayload = {status: drawerItem.status, type: drawerItem.type, title: drawerItem.title, details: drawerItem.details || {}};
      await api(`/api/items/${line}`, {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({...prevPayload, status: "[x]"}),
      });
      registerUndo("Marked done.", async () => {
        await api(`/api/items/${line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(prevPayload),
        });
      });
      closeDrawer();
      await refreshAll();
    }

    async function drawerComplete() {
      // Complete a repeat-enabled instance and materialize the next occurrence
      // via the shared /complete route (mirrors CLI `complete` + MCP tool).
      if (!drawerItem || !drawerItem.editable) return;
      const idKey = appConfig?.ids?.key || "id";
      const itemId = drawerItem?.id || drawerItem?.details?.[idKey]?.[0];
      if (!itemId) { showToast("This record needs an id: to complete.", "warning"); return; }
      try {
        const result = await api(`/api/items/id/${encodeURIComponent(itemId)}/complete`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({}),
        });
        const nextId = result?.next?.id || result?.next?.details?.[idKey]?.[0];
        showToast(nextId ? `Completed. Next occurrence created (${nextId}).` : "Completed.", "success");
      } catch(e) {
        showToast("Complete failed: " + e.message, "error");
        return;
      }
      closeDrawer();
      await refreshAll();
    }

    async function drawerDelete() {
      if (!drawerItem || !drawerItem.editable) return;
      if (!confirm(`Delete "${drawerItem.title}"?`)) return;
      const rawLine = drawerItem.text;
      await api(`/api/items/${drawerItem.line}`, {method: "DELETE"});
      if (rawLine) {
        registerUndo("Item deleted.", async () => {
          await api("/api/items/raw", {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({line: rawLine})});
        });
      } else {
        showToast("Item deleted.", "info");
      }
      closeDrawer();
      newItem();
      await refreshAll();
    }

    // ── Drawer: due-date quick actions (postpone) ──────────────────
    async function drawerPostpone(action) {
      if (!drawerItem || !drawerItem.editable) return;
      const line = drawerItem.line;
      const prevPayload = {status: drawerItem.status, type: drawerItem.type, title: drawerItem.title, details: drawerItem.details || {}};
      const details = JSON.parse(JSON.stringify(drawerItem.details || {}));
      const current = details.due?.[0] || "";
      const timePart = current.includes("T") ? current.split("T")[1] : "";
      const today = new Date(); today.setHours(0, 0, 0, 0);
      let label;
      if (action === "clear") {
        delete details.due;
        label = "Due date cleared.";
      } else {
        let base = current ? new Date(current.split("T")[0] + "T00:00:00") : new Date(today);
        if (isNaN(base)) base = new Date(today);
        base.setHours(0, 0, 0, 0);
        let next;
        if (action === "today") next = new Date(today);
        else if (action === "+1d") { next = new Date(Math.max(+base, +today)); next.setDate(next.getDate() + 1); }
        else if (action === "+1w") { next = new Date(Math.max(+base, +today)); next.setDate(next.getDate() + 7); }
        else return;
        const pad = n => String(n).padStart(2, "0");
        const dateStr = `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
        details.due = [timePart ? `${dateStr}T${timePart}` : dateStr];
        label = `Due set to ${details.due[0]}.`;
      }
      try {
        await api(`/api/items/${line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({...prevPayload, details}),
        });
        registerUndo(label, async () => {
          await api(`/api/items/${line}`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(prevPayload),
          });
        });
        await refreshAll();
        const updated = (currentItems || []).find(i => i.line === line && i.editable);
        if (updated) openDrawer(updated);
      } catch(e) {
        showToast("Due update failed: " + (e.message || e), "error");
      }
    }

    // ── est/elapsed progress bar ────────────────────────────────────
    function parseDurationMinutes(value) {
      const text = String(value || "").trim().toLowerCase();
      if (!text) return null;
      let total = 0;
      let matched = false;
      const re = /(\d+(?:\.\d+)?)\s*([dhm])/g;
      let m;
      while ((m = re.exec(text)) !== null) {
        matched = true;
        const n = parseFloat(m[1]);
        total += m[2] === "d" ? n * 24 * 60 : m[2] === "h" ? n * 60 : n;
      }
      if (!matched) {
        const n = parseFloat(text);
        return isNaN(n) ? null : n;
      }
      return total;
    }
    function buildEstProgressHtml(item) {
      const estRaw = item?.details?.est?.[0];
      const est = parseDurationMinutes(estRaw);
      if (!est || est <= 0) return "";
      const elapsedRaw = item?.details?.elapsed?.[0];
      const elapsed = parseDurationMinutes(elapsedRaw) || 0;
      const pct = Math.round(elapsed / est * 100);
      const width = Math.min(100, pct);
      const over = pct > 100;
      return `<div class="progress-wrap"><div class="drawer-section-title">Progress (elapsed vs est)</div>` +
        `<div class="progress-track"><div class="progress-fill${over ? " over" : ""}" style="width:${width}%"></div></div>` +
        `<div class="progress-label">${escapeHtml(elapsedRaw || "0m")} of ${escapeHtml(estRaw)} (${pct}%)${over ? " — over estimate" : ""}</div></div>`;
    }

    async function drawerNavigate(itemId) {
      if (!itemId) return;
      try {
        const data = await api(`/api/items/id/${encodeURIComponent(itemId)}`);
        if (data?.item) openDrawer(data.item);
      } catch(e) {
        showToast("Item not found: " + itemId, "error");
      }
    }

    // ── Live syntax check for quick-add bar ───────────────────────
    let _checkTimer = null;
    document.addEventListener("DOMContentLoaded", async () => {
      // Show read-only banner if server is in read-only mode
      try {
        const health = await api("/api/health");
        if (health.read_only) {
          const banner = document.getElementById("read-only-banner");
          if (banner) banner.style.display = "";
        }
      } catch(_) {}
      populateSavedViewsAndAreas();

      const qInput = document.getElementById("quick-line");
      if (qInput) {
        qInput.addEventListener("input", () => {
          clearTimeout(_checkTimer);
          _checkTimer = setTimeout(() => liveCheckLine(qInput.value), 280);
        });
      }
      const rawInput = document.getElementById("import-raw-input");
      if (rawInput) {
        rawInput.addEventListener("input", () => {
          clearTimeout(_checkTimer);
          _checkTimer = setTimeout(() => liveParseRawImport(rawInput.value), 280);
        });
      }
      // Sync agenda limit spinner from URL and wire change handler
      const spinner = document.getElementById("agenda-limit-spinner");
      if (spinner) {
        const raw = new URLSearchParams(location.search).get("agenda_limit");
        if (raw !== null) spinner.value = raw === "0" ? "0" : String(Number(raw) || 8);
        spinner.addEventListener("change", () => {
          const n = parseInt(spinner.value, 10);
          const params = new URLSearchParams(location.search);
          if (!n || n === 8) params.delete("agenda_limit");
          else params.set("agenda_limit", String(n < 0 ? 0 : n));
          const qs = params.toString();
          history.replaceState(null, "", qs ? "?" + qs : location.pathname);
          refresh();
        });
      }
    });
    async function liveCheckLine(line) {
      const qInput = document.getElementById("quick-line");
      if (!qInput) return;
      if (!line.trim()) { qInput.className = ""; document.getElementById("quick-check-msg") && (document.getElementById("quick-check-msg").textContent = ""); return; }
      try {
        const data = await api("/api/check-line", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line}),
        });
        qInput.classList.toggle("ok", data.ok);
        qInput.classList.toggle("err", !data.ok);
        const msg = document.getElementById("quick-check-msg");
        if (msg) {
          const errs = (data.diagnostics || []).filter(d => d.severity === "error");
          msg.textContent = errs.length ? errs[0].message : (data.ok && data.item_count > 0 ? "✓" : "");
          msg.className = "check-msg " + (data.ok ? "ok" : "err");
        }
      } catch(_) {}
    }
    async function liveParseRawImport(line) {
      const preview = document.getElementById("import-raw-preview");
      if (!preview) return;
      const text = String(line || "").trim();
      if (!text) {
        preview.style.display = "none";
        preview.className = "parse-preview";
        preview.textContent = "";
        return;
      }
      try {
        const data = await api("/api/items/parse", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({line: text}),
        });
        renderRawParsePreview(data);
      } catch(e) {
        preview.style.display = "";
        preview.className = "parse-preview err";
        preview.textContent = "Parse preview failed: " + (e.message || e);
      }
    }
    function renderRawParsePreview(data) {
      const preview = document.getElementById("import-raw-preview");
      if (!preview) return;
      const diagnostics = data?.diagnostics || [];
      const errors = diagnostics.filter(d => d.severity === "error");
      const warnings = diagnostics.filter(d => d.severity === "warning");
      const item = (data?.items || [])[0];
      preview.style.display = "";
      preview.className = "parse-preview " + (errors.length ? "err" : warnings.length ? "warn" : "ok");
      const diagLines = diagnostics.map(d => `${String(d.severity || "").toUpperCase()} ${d.code || ""}: ${d.message || ""}`);
      const itemLine = item ? `Parsed: ${item.status} ${item.type} ${item.title}` : `Parsed item count: ${data?.item_count || 0}`;
      preview.innerHTML = `<div>${escapeHtml(itemLine)}</div>` +
        (diagLines.length ? `<ul>${diagLines.map(line => `<li>${escapeHtml(line)}</li>`).join("")}</ul>` : `<div>No diagnostics.</div>`);
    }

    // ── Type-aware field hints in editor ────────────────────────────
    const TYPE_HINTS = {
      T: "due: est: project: tag: assignee: depends_on: parent:",
      E: "from: to: attendee: project: location: url:",
      D: "due: project: tag: assignee:",
      R: "repeat: interval: due: project:",
      H: "repeat: interval: done: project:",
      N: "body: tag: project: url:",
      S: "person: state: from: project:",
      M: "sender: recipient: notify_at: channel: body: ref:",
      J: "mood: body: project: on:",
    };
    document.addEventListener("change", function(e) {
      if (e.target.id === "edit-type") updateTypeHints(e.target.value);
    });
    function updateTypeHints(type) {
      const el = document.getElementById("type-hints");
      if (!el) return;
      const hint = TYPE_HINTS[type];
      if (hint) { el.textContent = "Suggested keys: " + hint; el.style.display = ""; }
      else el.style.display = "none";
    }

    // ── Search highlighting in item list ────────────────────────────
    function highlightText(html, query) {
      if (!query || !query.trim()) return html;
      const safe = query.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      try {
        return html.replace(new RegExp("(" + safe + ")", "gi"), "<mark>$1</mark>");
      } catch(_) { return html; }
    }
    // ── Agenda overdue/due-soon highlighting ───────────────────────
    function agendaDueSoonClass(record) {
      const due = record?.details?.due?.[0] || record?.due;
      if (!due) return "";
      const d = new Date(due); if (isNaN(d)) return "";
      const today = new Date(); today.setHours(0,0,0,0);
      d.setHours(0,0,0,0);
      const diffDays = Math.floor((d - today) / 86400000);
      if (diffDays < 0) return "overdue";
      if (diffDays <= dueSoonDays()) return "due-soon";
      return "";
    }

    // ── Notification permission state display ──────────────────────
    function updateNotifPermissionDisplay() {
      const bar = document.getElementById("notif-permission-bar");
