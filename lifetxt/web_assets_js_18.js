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
      return structuredFieldsForType(type).map(field => {
        const value = Array.isArray(values[field.key]) ? values[field.key].join(", ") : (values[field.key] || "");
        const inputId = prefix + "-" + field.key;
        const wide = field.key === "tag" || field.key === "project";
        return `<label class="structured-field${wide ? " wide-field" : ""}" for="${inputId}">` +
          `<span>${escapeHtml(field.label)} <small>(${escapeHtml(field.key)}:)</small></span>` +
          `<input id="${inputId}" data-structured-key="${escapeHtml(field.key)}" value="${escapeHtml(String(value))}" autocomplete="off">` +
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

    // Keep advanced destinations discoverable without giving them equal first-
    // run prominence. Direct URLs still open the More group automatically.
    const _beginnerNavSyncViewTabs = syncViewTabs;
    syncViewTabs = function() {
      _beginnerNavSyncViewTabs();
      const more = document.getElementById("nav-more");
      const advanced = new Set(["agenda", "timeline", "calendar", "focus", "review", "messages", "team", "status", "notifications", "stats", "graph", "display", "kiosk"]);
      if (more && advanced.has(currentView())) more.open = true;
    };
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
