    // Structured common-key authoring (#776 / #775).  These controls are a
    // presentation adapter only: values are merged into the existing Details
    // object and continue through the established POST/PUT validation path.
    const STRUCTURED_COMMON_FIELDS = [
      {key: "due", label: "Deadline", types: ["T", "D", "R", "H"]},
      {key: "do", label: "Scheduled", types: ["T", "D", "R", "H"]},
      {key: "on", label: "Date", types: ["E", "J"]},
      {key: "from", label: "Start", types: ["E", "S"]},
      {key: "to", label: "End", types: ["E", "S"]},
      {key: "at", label: "At", types: ["E", "J"]},
      {key: "project", label: "Project", types: null},
      {key: "priority", label: "Priority", types: ["T", "D", "R", "H"]},
      {key: "tag", label: "Tag", types: null},
      {key: "progress", label: "Progress", types: ["T", "D", "R", "H"]},
    ];

    function structuredFieldsForType(type) {
      return STRUCTURED_COMMON_FIELDS.filter(field => !field.types || field.types.includes(type));
    }

    function renderStructuredFields(prefix, details, type) {
      const values = details || {};
      const help = {
        due: "When this task should be finished.",
        project: "Group this record with related work.",
        priority: "How important this item is compared with other work.",
        progress: "Completion percentage, from 0 to 100.",
      };
      return structuredFieldsForType(type).map(field => {
        const value = Array.isArray(values[field.key]) ? values[field.key].join(", ") : (values[field.key] || "");
        const inputId = prefix + "-" + field.key;
        const wide = field.key === "tag" || field.key === "project";
        const helpId = inputId + "-help";
        const helpText = help[field.key] || "Optional details for this record.";
        return `<label class="structured-field${wide ? " wide-field" : ""}" for="${inputId}">` +
          `<span>${escapeHtml(field.label)} <small>(${escapeHtml(field.key)}:)</small></span>` +
          `<input id="${inputId}" aria-describedby="${helpId}" data-structured-key="${escapeHtml(field.key)}" value="${escapeHtml(String(value))}" autocomplete="off">` +
          `<small id="${helpId}" class="field-help-text">${escapeHtml(helpText)}</small>` +
          `</label>`;
      }).join("");
    }

    function _structuredDetails(textareaId, prefix) {
      const textarea = document.getElementById(textareaId);
      const details = parseDetails(textarea ? textarea.value : "");
      for (const field of STRUCTURED_COMMON_FIELDS) {
        const input = document.getElementById(prefix + "-" + field.key);
        if (!input) continue;
        const value = input.value.trim();
        if (value) details[field.key] = value.split(",").map(v => v.trim()).filter(Boolean);
        else delete details[field.key];
      }
      return details;
    }

    function _populateStructuredFields(prefix, details, type) {
      const container = document.getElementById(prefix === "edit" ? "structured-fields" : prefix + "-structured-fields");
      if (!container) return;
      container.innerHTML = renderStructuredFields(prefix, details, type);
    }

    function refreshStructuredFields() {
      const type = document.getElementById("edit-type")?.value || "T";
      const details = parseDetails(document.getElementById("edit-details")?.value || "");
      _populateStructuredFields("edit", details, type);
    }

    function syncStructuredFieldsIntoDetails() {
      const textarea = document.getElementById("edit-details");
      if (textarea) textarea.value = detailsToText(_structuredDetails("edit-details", "edit"));
    }

    const _structuredOriginalEditorPayload = editorPayload;
    editorPayload = function() {
      const payload = _structuredOriginalEditorPayload();
      payload.details = _structuredDetails("edit-details", "edit");
      return payload;
    };

    const _structuredOriginalNewItem = newItem;
    newItem = function() {
      _structuredOriginalNewItem();
      refreshStructuredFields();
    };
    const _structuredOriginalSelectItem = selectItem;
    selectItem = function(item) {
      _structuredOriginalSelectItem(item);
      refreshStructuredFields();
    };

    const _structuredOriginalImportRawLine = importRawLine;
    importRawLine = async function() {
      await _structuredOriginalImportRawLine();
      refreshStructuredFields();
    };

    function _structuredTypeChanged() {
      syncStructuredFieldsIntoDetails();
      refreshStructuredFields();
    }

    const _structuredTypeSelect = document.getElementById("edit-type");
    if (_structuredTypeSelect) _structuredTypeSelect.addEventListener("change", _structuredTypeChanged);
    const _structuredDetailsTextarea = document.getElementById("edit-details");
    if (_structuredDetailsTextarea) _structuredDetailsTextarea.addEventListener("input", () => {
      syncStructuredFieldsIntoDetails();
      refreshStructuredFields();
    });
    const _structuredContainer = document.getElementById("structured-fields");
    if (_structuredContainer) _structuredContainer.addEventListener("input", syncStructuredFieldsIntoDetails);
    refreshStructuredFields();

    const _beginnerTodaySubsection = _todaySubsection;
    _todaySubsection = function(title, rows, emptyText) {
      rows = rows || [];
      if (rows.length || !/^(Today|Due today|Next actions)$/i.test(title)) {
        return _beginnerTodaySubsection(title, rows, emptyText);
      }
      const cta = title === "Today" || title === "Due today"
        ? `<button type="button" class="secondary empty-cta" onclick="newItem()">＋ Add a task</button>`
        : `<button type="button" class="secondary empty-cta" onclick="switchWorkspace('')">View all items</button>`;
      return `<div class="today-subsection"><div class="today-subsection-title">${escapeHtml(title)} (0)</div>` +
        `<div class="empty-state compact-empty"><div class="empty-title">${escapeHtml(emptyText)}</div>${cta}</div></div>`;
    };

    // Keep advanced destinations discoverable without giving them equal first-
    // run prominence. Direct URLs still open the More group automatically.
    const _beginnerNavSyncViewTabs = syncViewTabs;
    syncViewTabs = function() {
      _beginnerNavSyncViewTabs();
      const more = document.getElementById("nav-more");
      const advanced = new Set(["agenda", "timeline", "calendar", "focus", "review", "messages", "team", "status", "notifications", "stats", "graph", "display", "kiosk"]);
      if (more && advanced.has(currentView())) more.open = true;
      const summary = document.getElementById("nav-more-summary");
      if (summary && more) summary.setAttribute("aria-expanded", more.open ? "true" : "false");
    };
    const _moreNav = document.getElementById("nav-more");
    if (_moreNav) _moreNav.addEventListener("toggle", () => {
      document.getElementById("nav-more-summary")?.setAttribute("aria-expanded", _moreNav.open ? "true" : "false");
    });

    function actionableErrorText(error) {
      const status = Number(error?.status);
      if (status === 409 || /conflict|revision|changed/i.test(error?.message || "")) {
        return "This item changed after you opened it. Your changes were not silently overwritten.";
      }
      if (status === 401 || status === 403) return "This workspace is read-only or you do not have permission to change it.";
      if (status >= 500 || !status) return "Check the connection and try again.";
      return error?.message || "Check the highlighted fields and try again.";
    }
    function showActionableError(title, error, options = {}) {
      const detail = escapeHtml(error?.message || error || "Unknown error");
      if (options.retry) renderActionableError(document.getElementById("toast-container"), title, error, options.retry);
      else showToast(`${title} ${actionableErrorText(error)} Technical details: ${detail}`, "error", 7000);
    }
    function renderActionableError(container, title, error, retry) {
      if (!container) return;
      const id = "error-details-" + Date.now();
      container.innerHTML = `<div class="actionable-error" role="alert" tabindex="-1"><strong>${escapeHtml(title)}</strong>` +
        `<span>${escapeHtml(actionableErrorText(error))}</span>` +
        `<button type="button" class="secondary" data-retry>Try again</button>` +
        `<details><summary>Technical details</summary><code id="${id}">${escapeHtml(error?.message || error || "")}</code></details></div>`;
      container.querySelector("[data-retry]")?.addEventListener("click", retry);
      container.querySelector(".actionable-error")?.focus();
    }
      applyPresetToUrl();
      applyUrlToControls();
      updateNotifPermissionDisplay();
      updateNotifBtnLabel();
      updateTypeHints(document.getElementById("edit-type").value);
      setupContextualHelp();
      setupWorkspaceTabs();
      syncStatusFilterBarsFromUrl();
      _syncGraphLayoutBtns();
      startGitPolling();
      // Back-compat: ?workspace=new used to open the editor panel
      if (firstParam(query(), ["workspace", "panel"], "").toLowerCase() === "new") newItem();
      return refreshAll().then(() => {
        // Auto-open detail modal for ?line=N deep links
        const lineParam = query().get("line");
        if (lineParam) {
          const lineNum = parseInt(lineParam, 10);
          if (!isNaN(lineNum)) openItemByLine(lineNum);
        }
      });
    }).catch(error => {
      document.body.insertAdjacentHTML("beforeend", `<pre class="diagnostic">${escapeHtml(error.message)}</pre>`);
    });
