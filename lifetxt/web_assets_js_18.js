    function statusStateChanged(container) {
      syncStatusStateMode(container);
      syncStructuredFieldsIntoDetails();
    }

    function _populateStructuredFields(prefix, details, type) {
      const container = document.getElementById(prefix === "edit" ? "structured-fields" : prefix + "-structured-fields");
      if (!container) return;
      container.innerHTML = renderStructuredFields(prefix, details, type);
      syncStatusStateMode(container);
      if (prefix === "edit" && document.getElementById("edit-type")?.disabled) {
        const fields = container.querySelector("[data-status-state-fields]");
        if (fields) fields.disabled = true;
      }
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
    if (_structuredContainer) {
      _structuredContainer.addEventListener("input", syncStructuredFieldsIntoDetails);
      _structuredContainer.addEventListener("change", event => {
        if (event.target.matches("[data-status-state-select]")) statusStateChanged(_structuredContainer);
      });
    }
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
        // Auto-open the detail drawer for a deep link (#838). Resolved
        // only after refreshAll() has loaded config/data, so the initial
        // open never races the app into showing the wrong record while
        // still loading. ?id= (canonical id:) takes precedence over the
        // older ?line= form; both replace, rather than push, this initial
        // history entry.
        const idParam = query().get("id");
        if (idParam) {
          return openItemById(idParam, "replace");
        }
        const lineParam = query().get("line");
        if (lineParam) {
          const lineNum = parseInt(lineParam, 10);
          if (!isNaN(lineNum)) return openItemByLine(lineNum, "replace");
        }
      });
    }).catch(error => {
      document.body.insertAdjacentHTML("beforeend", `<pre class="diagnostic">${escapeHtml(error.message)}</pre>`);
    });
