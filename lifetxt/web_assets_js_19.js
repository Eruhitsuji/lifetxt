    // ── Personal Context onboarding (#916 / #926) ────────────────
    const PERSONAL_CONTEXT_DOMAINS = ["profile", "preference", "skill", "goal", "project"];
    const PERSONAL_CONTEXT_LABELS = {
      profile: "Profile", preference: "Preferences", skill: "Skills",
      goal: "Goals", project: "Projects",
    };
    let personalContextPreviewRecords = [];
    let personalContextReadOnly = false;

    function personalContextFactRow(domain = "profile", fact = "") {
      const options = PERSONAL_CONTEXT_DOMAINS.map(value =>
        `<option value="${value}"${value === domain ? " selected" : ""}>${t(PERSONAL_CONTEXT_LABELS[value])}</option>`
      ).join("");
      return `<div class="personal-context-fact-row">
        <label><span>${t("Domain")}</span><select class="personal-context-domain">${options}</select></label>
        <label class="personal-context-fact-input"><span>${t("Fact")}</span><input class="personal-context-fact" maxlength="500" value="${escapeHtml(fact)}" placeholder="${escapeHtml(t("One fact, for example: Prefers concise answers"))}" required></label>
        <button type="button" class="secondary personal-context-remove" onclick="removePersonalContextFact(this)">${t("Remove")}</button>
      </div>`;
    }

    function invalidatePersonalContextPreview() {
      personalContextPreviewRecords = [];
      const preview = document.getElementById("personal-context-preview");
      if (preview) preview.innerHTML = "";
      const feedback = document.getElementById("personal-context-feedback");
      if (feedback) feedback.textContent = "";
    }

    function addPersonalContextFact(domain = "profile", fact = "") {
      const container = document.getElementById("personal-context-facts");
      if (!container || container.children.length >= 25) return;
      container.insertAdjacentHTML("beforeend", personalContextFactRow(domain, fact));
      container.lastElementChild?.querySelector("input")?.focus();
      invalidatePersonalContextPreview();
    }

    function removePersonalContextFact(button) {
      const container = document.getElementById("personal-context-facts");
      button?.closest(".personal-context-fact-row")?.remove();
      if (container && !container.children.length) addPersonalContextFact();
      invalidatePersonalContextPreview();
    }

    function personalContextFactsFromForm() {
      return Array.from(document.querySelectorAll(".personal-context-fact-row"))
        .map(row => ({
          domain: row.querySelector(".personal-context-domain")?.value || "",
          fact: row.querySelector(".personal-context-fact")?.value.trim() || "",
        }))
        .filter(row => row.fact);
    }

    function personalContextTags(item) {
      return Array.isArray(item?.details?.tag) ? item.details.tag : [];
    }

    function renderPersonalContextCurrent(data) {
      const target = document.getElementById("personal-context-current");
      if (!target) return;
      target.setAttribute("aria-busy", "false");
      const items = data?.items || [];
      const counts = data?.currentness_counts || {current: 0, stale: 0};
      const countTarget = document.getElementById("personal-context-counts");
      if (countTarget) countTarget.innerHTML = `<span>${t("Current")}: <strong>${Number(counts.current) || 0}</strong></span><span>${t("Stale")}: <strong>${Number(counts.stale) || 0}</strong></span>`;
      const pagination = document.getElementById("personal-context-pagination");
      const loadMore = document.getElementById("personal-context-load-more");
      if (pagination) pagination.hidden = !data?.has_more;
      if (loadMore) loadMore.disabled = false;
      if (!items.length) {
        target.innerHTML = `<div class="empty-state compact-empty"><div class="empty-title">${t("No current Personal Context yet.")}</div><p>${t("Add a few explicit facts to give tools durable context.")}</p></div>`;
        return;
      }
      const groups = PERSONAL_CONTEXT_DOMAINS.map(domain => ({
        label: PERSONAL_CONTEXT_LABELS[domain],
        rows: items.filter(item => personalContextTags(item).includes(domain)),
      }));
      groups.push({
        label: "Other context",
        rows: items.filter(item => !personalContextTags(item).some(tag => PERSONAL_CONTEXT_DOMAINS.includes(tag))),
      });
      target.innerHTML = groups.map(group => {
        const rows = group.rows;
        if (!rows.length) return "";
        return `<div class="personal-context-group"><h4>${t(group.label)} <span>${rows.length}</span></h4><ul data-no-i18n>${rows.map(row => `<li class="${row.stale ? "personal-context-stale" : ""}"><span>${escapeHtml(row.title || "")}</span>${row.stale ? `<span class="personal-context-stale-badge">${escapeHtml(t("Stale"))}</span><button type="button" class="secondary personal-context-reconfirm" data-personal-context-id="${escapeHtml(row.id || "")}" onclick="reconfirmPersonalContext(this.dataset.personalContextId)">${escapeHtml(t("Still correct"))}</button>` : ""}${personalContextReviewMenu(row.id)}</li>`).join("")}</ul></div>`;
      }).join("") || `<div class="empty">${t("No current Personal Context yet.")}</div>`;
    }

    // Progressive-disclosure review outcomes beyond plain reconfirm (#960):
    // Correct/Replace, Changed over time, No longer valid. "Review later"
    // has no control at all -- simply not opening/using this menu is that
    // outcome, and performs no mutation.
    function personalContextReviewMenu(itemId) {
      const id = escapeHtml(itemId || "");
      if (!id) return "";
      return `<details class="personal-context-review-menu"><summary>${escapeHtml(t("Something changed…"))}</summary><div class="personal-context-review-actions"><button type="button" class="secondary" data-personal-context-id="${id}" onclick="correctPersonalContext(this.dataset.personalContextId)">${escapeHtml(t("Correct the record"))}</button><button type="button" class="secondary" data-personal-context-id="${id}" onclick="changePersonalContext(this.dataset.personalContextId)">${escapeHtml(t("Changed over time"))}</button><button type="button" class="secondary" data-personal-context-id="${id}" onclick="expirePersonalContext(this.dataset.personalContextId)">${escapeHtml(t("No longer valid"))}</button></div></details>`;
    }

    function personalContextSourceRevision() {
      const target = document.getElementById("personal-context-current");
      return target?.dataset.personalContextSourceRevision || "";
    }

    // Re-fetch exactly the range of records already loaded (never resetting
    // to the first page) so a single-record review action does not discard
    // pagination the user already expanded via Load more (#961).
    async function fetchPersonalContextRange(count, includeStale) {
      const items = [];
      let offset = 0;
      let lastData = null;
      let remaining = Math.max(count, 1);
      while (remaining > 0) {
        const limit = Math.min(remaining, 100);
        const data = await api(
          `/api/personal-context?limit=${limit}&offset=${offset}${includeStale ? "&include_stale=true" : ""}`
        );
        const batch = data.items || [];
        items.push(...batch);
        lastData = data;
        offset += batch.length;
        remaining -= batch.length;
        if (!batch.length) break;
      }
      return {items, lastData};
    }

    async function refreshLoadedPersonalContext() {
      const current = document.getElementById("personal-context-current");
      const includeStale = !!document.getElementById("personal-context-include-stale")?.checked;
      const previousItems = JSON.parse(current?.dataset.personalContextItems || "[]");
      const loadedCount = previousItems.length || 100;
      const scrollY = typeof window !== "undefined" && window.scrollY;
      const {items, lastData} = await fetchPersonalContextRange(loadedCount, includeStale);
      const totalCount = lastData ? lastData.total_count : items.length;
      const data = Object.assign({}, lastData, {
        items,
        offset: 0,
        has_more: items.length < totalCount,
      });
      if (current) {
        current.dataset.personalContextOffset = "0";
        current.dataset.personalContextItems = JSON.stringify(items);
        current.dataset.personalContextSourceRevision = data.source_revision || "";
      }
      renderPersonalContextCurrent(data);
      if (typeof window !== "undefined" && window.scrollTo) window.scrollTo(0, scrollY || 0);
      return data;
    }

    async function reconfirmPersonalContext(itemId) {
      if (!itemId) return;
      const feedback = document.getElementById("personal-context-feedback");
      if (feedback) feedback.textContent = t("Reconfirming…");
      try {
        await api(`/api/personal-context/${encodeURIComponent(itemId)}/reconfirm`, {
          method: "POST",
          body: JSON.stringify({expected_source_revision: personalContextSourceRevision()}),
        });
        if (feedback) feedback.textContent = t("Reconfirmed.");
        await refreshLoadedPersonalContext();
      } catch (error) {
        if (feedback) feedback.textContent = error.message;
      }
    }

    async function expirePersonalContext(itemId) {
      if (!itemId) return;
      const feedback = document.getElementById("personal-context-feedback");
      if (feedback) feedback.textContent = t("Ending applicability…");
      try {
        await api(`/api/personal-context/${encodeURIComponent(itemId)}/expire`, {
          method: "POST",
          body: JSON.stringify({expected_source_revision: personalContextSourceRevision()}),
        });
        if (feedback) feedback.textContent = t("No longer valid.");
        await refreshLoadedPersonalContext();
      } catch (error) {
        if (feedback) feedback.textContent = error.message;
      }
    }

    async function changePersonalContext(itemId) {
      if (!itemId) return;
      const feedback = document.getElementById("personal-context-feedback");
      const replacementText = typeof window !== "undefined" && window.prompt
        ? window.prompt(t("What is true now?"))
        : "";
      if (!replacementText || !replacementText.trim()) return;
      const validFrom = typeof window !== "undefined" && window.prompt
        ? window.prompt(t("Effective from (YYYY-MM-DD, optional):")) || ""
        : "";
      if (feedback) feedback.textContent = t("Recording the change…");
      try {
        await api(`/api/personal-context/${encodeURIComponent(itemId)}/change`, {
          method: "POST",
          body: JSON.stringify({
            expected_source_revision: personalContextSourceRevision(),
            replacement_text: replacementText.trim(),
            valid_from: validFrom.trim() || undefined,
          }),
        });
        if (feedback) feedback.textContent = t("Changed over time.");
        await refreshLoadedPersonalContext();
      } catch (error) {
        if (feedback) feedback.textContent = error.message;
      }
    }

    async function correctPersonalContext(itemId) {
      if (!itemId) return;
      const feedback = document.getElementById("personal-context-feedback");
      const replacementText = typeof window !== "undefined" && window.prompt
        ? window.prompt(t("What should this record have said?"))
        : "";
      if (!replacementText || !replacementText.trim()) return;
      if (feedback) feedback.textContent = t("Correcting…");
      try {
        await api(`/api/personal-context/${encodeURIComponent(itemId)}/correct`, {
          method: "POST",
          body: JSON.stringify({
            expected_source_revision: personalContextSourceRevision(),
            replacement_text: replacementText.trim(),
          }),
        });
        if (feedback) feedback.textContent = t("Corrected.");
        await refreshLoadedPersonalContext();
      } catch (error) {
        if (feedback) feedback.textContent = error.message;
      }
    }

    async function loadMorePersonalContext() {
      const button = document.getElementById("personal-context-load-more");
      if (button) button.disabled = true;
      const includeStale = !!document.getElementById("personal-context-include-stale")?.checked;
      const current = document.getElementById("personal-context-current");
      const offset = Number(current?.dataset.personalContextOffset || 0) + 100;
      try {
        const data = await api(`/api/personal-context?limit=100&offset=${offset}${includeStale ? "&include_stale=true" : ""}`);
        const existing = JSON.parse(current.dataset.personalContextItems || "[]");
        data.items = existing.concat(data.items || []);
        data.has_more = offset + (data.items.length - existing.length) < data.total_count;
        current.dataset.personalContextOffset = String(offset);
        current.dataset.personalContextItems = JSON.stringify(data.items);
        renderPersonalContextCurrent(data);
      } catch (error) {
        if (button) button.disabled = false;
        const feedback = document.getElementById("personal-context-feedback");
        if (feedback) feedback.textContent = error.message;
      }
    }

    async function loadPersonalContext() {
      const target = document.getElementById("personal-context-current");
      if (target) target.setAttribute("aria-busy", "true");
      try {
        const includeStale = !!document.getElementById("personal-context-include-stale")?.checked;
        const [data, health] = await Promise.all([
          api(`/api/personal-context${includeStale ? "?include_stale=true" : ""}`),
          api("/api/health").catch(() => ({})),
        ]);
        personalContextReadOnly = !!health.read_only;
        renderPersonalContextCurrent(data);
        if (target) {
          target.dataset.personalContextOffset = String(data.offset || 0);
          target.dataset.personalContextItems = JSON.stringify(data.items || []);
          target.dataset.personalContextSourceRevision = data.source_revision || "";
        }
        const save = document.getElementById("personal-context-save-btn");
        if (save) save.disabled = personalContextReadOnly;
        if (personalContextReadOnly) {
          const feedback = document.getElementById("personal-context-feedback");
          if (feedback) feedback.textContent = t("Read-only mode: you can review and preview, but cannot save.");
        }
      } catch (error) {
        if (target) {
          target.setAttribute("aria-busy", "false");
          target.innerHTML = `<div class="empty error">${escapeHtml(error.message)}</div>`;
        }
      }
    }

    function renderPersonalContextPreview(records) {
      const target = document.getElementById("personal-context-preview");
      if (!target) return;
      target.innerHTML = `<h4>${t("Exact records to save")}</h4><ol data-no-i18n>${records.map(record => `<li><code>${escapeHtml(record.line)}</code></li>`).join("")}</ol>` +
        `<button id="personal-context-save-btn" type="button" onclick="savePersonalContext()"${personalContextReadOnly ? " disabled" : ""}>${t("Save records")}</button>`;
    }

    async function previewPersonalContext() {
      const feedback = document.getElementById("personal-context-feedback");
      if (feedback) feedback.textContent = "";
      const facts = personalContextFactsFromForm();
      if (!facts.length) {
        if (feedback) feedback.textContent = t("Add at least one fact before previewing.");
        document.querySelector(".personal-context-fact")?.focus();
        return;
      }
      try {
        const result = await api("/api/personal-context/preview", {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({facts}),
        });
        personalContextPreviewRecords = result.records || [];
        renderPersonalContextPreview(personalContextPreviewRecords);
      } catch (error) {
        if (feedback) feedback.textContent = `${t("Preview failed:")} ${error.message}`;
      }
    }

    async function savePersonalContextRecords(records, createRecord, onSaved) {
      let savedCount = 0;
      for (let index = 0; index < records.length; index += 1) {
        try {
          await createRecord(records[index].payload);
          savedCount += 1;
          if (onSaved) onSaved(records[index], savedCount);
        } catch (error) {
          error.savedCount = savedCount;
          error.remainingRecords = records.slice(index);
          throw error;
        }
      }
      return {savedCount, remainingRecords: []};
    }

    function replacePersonalContextFacts(records) {
      const container = document.getElementById("personal-context-facts");
      if (!container) return;
      container.innerHTML = records.length
        ? records.map(record => personalContextFactRow(record.domain, record.fact)).join("")
        : personalContextFactRow();
    }

    async function savePersonalContext() {
      if (personalContextReadOnly || !personalContextPreviewRecords.length) return;
      const feedback = document.getElementById("personal-context-feedback");
      const save = document.getElementById("personal-context-save-btn");
      if (save) save.disabled = true;
      const original = personalContextPreviewRecords.slice();
      try {
        await savePersonalContextRecords(
          original,
          payload => api("/api/items", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)}),
          (_record, count) => { if (feedback) feedback.textContent = `${count} / ${original.length} ${t("saved")}`; },
        );
        personalContextPreviewRecords = [];
        replacePersonalContextFacts([]);
        document.getElementById("personal-context-preview").innerHTML = "";
        if (feedback) feedback.textContent = t("All records saved.");
        await loadPersonalContext();
      } catch (error) {
        personalContextPreviewRecords = error.remainingRecords || original;
        replacePersonalContextFacts(personalContextPreviewRecords);
        renderPersonalContextPreview(personalContextPreviewRecords);
        if (feedback) feedback.textContent = `${t("saved; failed; remaining")}: ${error.savedCount || 0}; 1; ${personalContextPreviewRecords.length}. ${t("Remaining facts were not saved and are still editable.")} ${error.message}`;
      }
    }

    document.addEventListener("DOMContentLoaded", () => {
      const facts = document.getElementById("personal-context-facts");
      if (facts && !facts.children.length) facts.innerHTML = personalContextFactRow();
      facts?.addEventListener("input", invalidatePersonalContextPreview);
      facts?.addEventListener("change", invalidatePersonalContextPreview);
    });
