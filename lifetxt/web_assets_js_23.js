    // Explicit bulk completion: every write is bound to a freshly verified source snapshot.
    let bulkDoneView = null;
    let bulkDonePending = false;
    const bulkDoneCopy = value => JSON.parse(JSON.stringify(value));
    const bulkDoneKey = item => String(item.line) + "|" + (item.source || "");
    const bulkDoneId = item => item.id || item.details?.[appConfig?.ids?.key || "id"]?.[0] || null;
    const bulkDonePayload = item => ({status:item.status, type:item.type, title:item.title, details:bulkDoneCopy(item.details || {})});
    function bulkDoneCanonical(value) {
      if (Array.isArray(value)) return value.map(bulkDoneCanonical);
      if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map(k => [k, bulkDoneCanonical(value[k])]));
      return value;
    }
    const bulkDoneSame = (a, b) => JSON.stringify(bulkDoneCanonical(bulkDonePayload(a))) === JSON.stringify(bulkDoneCanonical(bulkDonePayload(b)));
    function bulkDoneSkip(item) {
      if (!item) return "Record unavailable";
      if (!item.editable || item.generated) return "Read-only";
      if (item.type !== "T") return "Not a task";
      if (["[x]", "[-]"].includes(item.status)) return "Already completed or cancelled";
      if (Object.prototype.hasOwnProperty.call(item.details || {}, "done")) return "Existing completion date";
      if (item.details?.repeat?.length) return "Repeating task";
      return "";
    }
    function bulkDoneDate(reset = false) {
      if (bulkDonePending) return;
      if (!bulkDoneView || reset || !bulkDoneView.started) {
        const selected = [...bulkSelectedLines];
        const rows = selected.map(key => {
          const matches = currentItems.filter(item => bulkDoneKey(item) === key);
          const item = matches.length === 1 ? bulkDoneCopy(matches[0]) : null;
          return {key, original:item, reason:matches.length > 1 ? "Ambiguous identity" : bulkDoneSkip(item), state:"pending"};
        });
        bulkDoneView = {rows, started:false, value:null};
      }
      document.getElementById("bulk-done-feedback").textContent = "";
      renderBulkDone();
      bulkDoneModeChanged();
      openManagedModal(document.getElementById("bulk-done-modal"), "#bulk-done-mode");
    }
    function bulkDoneModeChanged() {
      const mode = document.getElementById("bulk-done-mode").value;
      document.getElementById("bulk-done-date").disabled = mode === "now";
      document.getElementById("bulk-done-time").disabled = mode !== "time";
    }
    function closeBulkDone() {
      if (!bulkDonePending) closeManagedModal(document.getElementById("bulk-done-modal"));
    }
    function bulkDoneValue(mode, date, time) {
      if (mode === "now") return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date < "0001-01-01" || date > "9999-12-31") throw Error(t("Invalid local date/time. Choose another time."));
      const check = new Date(date + "T00:00:00Z");
      if (!Number.isFinite(check.getTime()) || check.toISOString().slice(0,10) !== date) throw Error(t("Invalid local date/time. Choose another time."));
      if (mode === "date") return date;
      if (!/^\d{2}:\d{2}$/.test(time)) throw Error(t("Invalid local date/time. Choose another time."));
      const stamp = new Date(`${date}T${time}`), pad = n => String(n).padStart(2,"0");
      const wall = `${String(stamp.getFullYear()).padStart(4,"0")}-${pad(stamp.getMonth()+1)}-${pad(stamp.getDate())}T${pad(stamp.getHours())}:${pad(stamp.getMinutes())}`;
      if (!Number.isFinite(stamp.getTime()) || wall !== `${date}T${time}`) throw Error(t("Invalid local date/time. Choose another time."));
      return stamp.toISOString().replace(/\.\d{3}Z$/, "Z");
    }
    function renderBulkDone() {
      const view = bulkDoneView;
      if (!view) return;
      const eligible = view.rows.filter(row => !row.reason), reasons = {};
      for (const row of view.rows) if (row.reason) reasons[row.reason] = (reasons[row.reason] || 0) + 1;
      document.getElementById("bulk-done-summary").textContent = `${t("Selected")}: ${view.rows.length} / ${t("Eligible")}: ${eligible.length} / ${t("Skipped")}: ${view.rows.length - eligible.length}`;
      document.getElementById("bulk-done-skips").textContent = Object.entries(reasons).map(([reason,n]) => `${t(reason)}: ${n}`).join(" / ");
      document.getElementById("bulk-done-zone").textContent = Intl.DateTimeFormat().resolvedOptions().timeZone;
      document.getElementById("bulk-done-fields").hidden = view.started;
      document.getElementById("bulk-done-confirm").hidden = view.started;
      document.getElementById("bulk-done-confirm").disabled = bulkDonePending || !eligible.length;
      document.getElementById("bulk-done-value").textContent = view.value || "";
      document.getElementById("bulk-done-counts").textContent = view.started ? ["Completed", "Failed", "Restored", "Undo failed"].map(state => `${t(state)}: ${view.rows.filter(row => row.state === state).length}`).join(" / ") : "";
      document.getElementById("bulk-done-results").innerHTML = view.rows.filter(row => !row.reason && row.state !== "pending").map(row =>
        `<li><span data-no-i18n>${escapeHtml(row.original.title)} (${escapeHtml(bulkDoneId(row.original) || "#" + row.original.line)})</span>: ${escapeHtml(t(row.state))}${row.error ? ` — ${escapeHtml(row.error)}` : ""}</li>`).join("");
      for (const [id, available] of [["retry", eligible.some(r => r.state === "Failed")], ["undo", eligible.some(r => ["Completed", "Undo failed"].includes(r.state))], ["reset", view.started], ["close", true]]) {
        const button = document.getElementById("bulk-done-" + id);
        button.hidden = !available; button.disabled = bulkDonePending;
      }
      document.getElementById("bulk-done-modal").setAttribute("aria-busy", String(bulkDonePending));
    }
    async function bulkDoneSnapshot(original, expected) {
      const health = await api("/api/health", {cache:"no-store"});
      const before = await api("/api/revision", {cache:"no-store"});
      // Full list avoids the legacy GET-by-line ambiguity across multiple sources.
      const data = await api("/api/items", {cache:"no-store"});
      const after = await api("/api/revision", {cache:"no-store"});
      if (health.read_only || !/^[a-f0-9]{64}$/.test(before?.revision || "") || before.revision !== after?.revision || !Array.isArray(data.items)) throw Error(t("Refresh and review the record before retrying."));
      const id = bulkDoneId(original);
      const matches = data.items.filter(item => id ? bulkDoneId(item) === id : bulkDoneKey(item) === bulkDoneKey(original));
      const item = matches.length === 1 ? matches[0] : null;
      // Single-file reads intentionally omit source; accept that only for one exact writable input.
      const writableSource = item && (item.source === health.writable_path ||
        (item.source == null && health.paths?.length === 1 && health.paths[0] === health.writable_path));
      if (!item || item.source !== original.source || !writableSource || !item.editable || item.generated || !bulkDoneSame(item, expected) || bulkDoneId(item) !== id) throw Error(t("Record changed or identity is ambiguous. Refresh and review."));
      return {item, revision:before.revision, path:id ? `/api/items/id/${encodeURIComponent(id)}` : `/api/items/${item.line}`};
    }
    async function bulkDoneWrite(row, undo) {
      const expected = undo ? row.completed : row.original;
      const snapshot = await bulkDoneSnapshot(row.original, expected);
      if (!undo && bulkDoneSkip(snapshot.item)) throw Error(t("Record changed or identity is ambiguous. Refresh and review."));
      const payload = undo ? bulkDonePayload(row.original) : {...bulkDonePayload(snapshot.item), status:"[x]", details:{...snapshot.item.details, done:[bulkDoneView.value]}};
      let result;
      try {
        result = await api(snapshot.path, {method:"PUT", headers:{"Content-Type":"application/json", "If-Match":'"' + snapshot.revision + '"'}, body:JSON.stringify(payload)});
      } catch (error) {
        if (!error?.status) throw Error(t("Outcome unknown. Inspect the record before retrying."));
        throw error;
      }
      if (!result?.item || result.item.source !== snapshot.item.source || !bulkDoneSame(result.item, payload)) throw Error(t("Outcome unknown. Inspect the record before retrying."));
      if (!undo) row.completed = bulkDoneCopy(result.item);
    }
    async function runBulkDone(undo = false) {
      if (bulkDonePending || !bulkDoneView?.started) return;
      const view = bulkDoneView;
      const rows = view.rows.filter(row => !row.reason && (undo ? ["Completed", "Undo failed"].includes(row.state) : ["pending", "Failed"].includes(row.state)));
      if (!rows.length) return;
      bulkDonePending = true; renderBulkDone();
      for (const row of rows) {
        try {
          await bulkDoneWrite(row, undo);
          row.state = undo ? "Restored" : "Completed"; row.error = "";
          if (!undo) bulkSelectedLines.delete(row.key);
        } catch (error) {
          row.state = undo ? "Undo failed" : "Failed";
          row.error = t("Refresh and review the record before retrying.");
          // Avoid disclosing raw server details (which can include local paths).
          if (!error?.status) row.error = error.message || row.error;
        }
        renderBulkDone();
      }
      try { await refreshAll(); }
      catch (_) { document.getElementById("bulk-done-feedback").textContent = t("Saved results are shown below. Refresh the list before continuing."); }
      finally {
        bulkDonePending = false; renderBulkDone();
        document.getElementById("bulk-done-close").focus?.();
      }
    }
    async function confirmBulkDone() {
      if (bulkDonePending || !bulkDoneView || bulkDoneView.started || !bulkDoneView.rows.some(row => !row.reason)) return;
      try {
        bulkDoneView.value = bulkDoneValue(document.getElementById("bulk-done-mode").value, document.getElementById("bulk-done-date").value, document.getElementById("bulk-done-time").value);
      } catch (error) { document.getElementById("bulk-done-feedback").textContent = error.message; return; }
      bulkDoneView.started = true;
      document.getElementById("bulk-done-feedback").focus?.();
      document.getElementById("bulk-done-feedback").textContent = "";
      return runBulkDone();
    }
