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
      const advanced = new Set(["agenda", "timeline", "calendar", "focus", "review", "messages", "team", "status", "notifications", "stats", "graph", "server", "display", "kiosk"]);
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
      if (initializeCaptureMode()) return;
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

    function backupStateCopy(state) {
      return ({
        unconfigured: ["Backups not configured", "Add an opt-in backup_schedule section to server-init configuration.", "neutral"],
        disabled: ["Scheduled backups disabled", "Backup settings exist, but unattended backup execution is disabled.", "neutral"],
        never_run: ["Waiting for first backup", "Backup is enabled, but no completed run has been recorded yet.", "neutral"],
        local_failure: ["Local backup failed", "The last local backup attempt failed. Inspect server-side backup status and logs.", "danger"],
        remote_failure: ["Off-host upload failed", "The local backup succeeded, but the latest remote upload failed.", "danger"],
        healthy: ["Backup healthy", "The latest recorded local backup completed successfully.", "success"],
        unavailable: ["Backup status unavailable", "The configured backup destination could not be inspected safely.", "danger"],
      })[state] || ["Backup status unknown", "The server returned an unrecognized backup state.", "neutral"];
    }

    function backupResultCopy(value) {
      return ({
        success: "Success",
        failure: "Failed",
        never_run: "Never run",
        not_configured: "Not configured",
      })[value] || value;
    }

    function backupStatusRow(label, value, options = {}) {
      const shown = value === null || value === undefined || value === "" ? "—" : String(value);
      const protectedValue = options.data ? " data-no-i18n" : "";
      return `<div class="backup-status-row"><span>${escapeHtml(label)}</span><strong${protectedValue}>${escapeHtml(shown)}</strong></div>`;
    }

    function renderServerBackupStatus(data) {
      const state = backupStateCopy(data?.state);
      const local = data?.local || {};
      const remote = data?.remote || {};
      const remoteState = remote.configured
        ? (remote.last_upload_result || "never_run")
        : "not_configured";
      const guidance = data?.state === "unconfigured"
        ? `<p class="backup-guidance">See the <a href="https://github.com/Eruhitsuji/lifetxt/blob/main/docs/deployment/ubuntu-server.md#5-backup-and-restore" target="_blank" rel="noopener noreferrer">Ubuntu Server backup guide</a> to configure scheduled disaster-recovery backups.</p>`
        : "";
      const remoteError = remote.last_error_summary
        ? `<p class="backup-warning" role="alert">${escapeHtml(remote.last_error_summary)}</p>`
        : "";
      return `<div class="backup-summary backup-state-${escapeHtml(state[2])}" role="status">` +
        `<div><strong>${escapeHtml(state[0])}</strong><p>${escapeHtml(state[1])}</p></div>` +
        `<span class="pill">${data?.enabled ? "Backup schedule enabled" : "Backup schedule disabled"}</span></div>` +
        `<div class="backup-panel-grid">` +
          `<article class="backup-status-card"><h3>Local backup</h3>` +
            backupStatusRow("Result", backupResultCopy(local.last_attempt_result)) +
            backupStatusRow("Last attempt", local.last_attempt_at, {data: true}) +
            backupStatusRow("Last success", local.last_success_at, {data: true}) +
            backupStatusRow("Latest artifact", data?.latest_local_backup, {data: true}) +
            backupStatusRow("Complete backups", data?.backup_count ?? 0, {data: true}) +
          `</article>` +
          `<article class="backup-status-card"><h3>Off-host upload</h3>` +
            backupStatusRow("Configured", remote.configured ? "Yes" : "No") +
            backupStatusRow("Result", backupResultCopy(remoteState)) +
            backupStatusRow("Last upload", remote.last_upload_at, {data: true}) +
            backupStatusRow("Next scheduled run", data?.next_scheduled_run, {data: true}) +
            remoteError +
          `</article>` +
        `</div>${guidance}`;
    }

    async function loadServerBackupStatus() {
      const node = document.getElementById("server-backup-status");
      if (!node) return;
      node.setAttribute("aria-busy", "true");
      try {
        const data = await api("/api/backup/status");
        node.innerHTML = renderServerBackupStatus(data);
      } catch (error) {
        node.innerHTML = `<div class="diagnostic" role="alert">${escapeHtml(t("Backup status could not be loaded:"))} <span data-no-i18n>${escapeHtml(error.message || error)}</span></div>`;
      } finally {
        node.setAttribute("aria-busy", "false");
      }
    }
