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
        return `<div class="personal-context-group"><h4>${t(group.label)} <span>${rows.length}</span></h4><ul data-no-i18n>${rows.map(row => `<li class="${row.stale ? "personal-context-stale" : ""}"><span>${escapeHtml(row.title || "")}</span>${row.stale ? `<span class="personal-context-stale-badge">${escapeHtml(t("Stale"))}</span>` : ""}</li>`).join("")}</ul></div>`;
      }).join("") || `<div class="empty">${t("No current Personal Context yet.")}</div>`;
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
