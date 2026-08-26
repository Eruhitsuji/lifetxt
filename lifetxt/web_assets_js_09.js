          key,
          line: item.line,
          source: item.source || "",
          title: item.title || "",
          type: item.type || "",
          opened_at: Date.now(),
        };
        const next = [row, ...loadRecentItems().filter(r => r.key !== key)].slice(0, 8);
        localStorage.setItem(RECENT_ITEMS_STORAGE_KEY, JSON.stringify(next));
      } catch(_) {}
    }
    const CMDK_ACTIONS = [
      {label: "New item", run: newItem},
      {label: "Go to Dashboard", run: () => switchWorkspace("dashboard")},
      {label: "Go to Items", run: () => switchWorkspace("")},
      {label: "Go to Agenda", run: () => switchWorkspace("agenda")},
      {label: "Go to Timeline", run: () => switchWorkspace("timeline")},
      {label: "Go to Calendar", run: () => switchWorkspace("calendar")},
      {label: "Go to Focus", run: () => switchWorkspace("focus")},
      {label: "Go to Review", run: () => switchWorkspace("review")},
      {label: "Go to Messages", run: () => switchWorkspace("messages")},
      {label: "Go to Team", run: () => switchWorkspace("team")},
      {label: "Go to Status", run: () => switchWorkspace("status")},
      {label: "Toggle fullscreen", run: () => toggleFullscreen()},
      {label: "Go to Notifications", run: () => switchWorkspace("notifications")},
      {label: "Go to Stats", run: () => switchWorkspace("stats")},
      {label: "Go to Graph", run: () => switchWorkspace("graph")},
      {label: "Go to Display mode", run: () => switchWorkspace("display")},
      {label: "Go to Kiosk mode", run: () => switchWorkspace("kiosk")},
      {label: "Toggle quick-add bar", run: () => toggleQuickAdd(true)},
      {label: "Refresh all", run: refreshAll},
      {label: "Toggle dark mode", run: toggleDarkMode},
      {label: "Toggle display mode", run: toggleDisplayMode},
      {label: "Toggle kiosk mode", run: toggleKioskMode},
      {label: "Toggle agenda blocked filter", run: toggleAgendaBlocked},
      {label: "Show undo history", run: openUndoHistoryModal},
      {label: "Export items as CSV", run: () => exportItems("csv")},
      {label: "Export items as JSON", run: () => exportItems("json")},
      {label: "Export items as Markdown", run: () => exportItems("markdown")},
      {label: "Jump to line number", run: jumpToLine},
      {label: "Keyboard shortcuts help", run: openHelpModal},
    ];
    // ── Slash commands (shared vocabulary with the TUI) ────────────
    // The catalog comes from /api/commands, which derives it from the TUI
    // command registry, so a command means the same thing in both places.
    // Execution happens here because selection and filters are browser state.
    let COMMAND_CATALOG = [];

    async function loadCommandCatalog() {
      try {
        const data = await api("/api/commands");
        COMMAND_CATALOG = data.commands || [];
      } catch (err) {
        COMMAND_CATALOG = [];
      }
    }

    function commandByName(name) {
      const key = String(name || "").toLowerCase();
      return COMMAND_CATALOG.find(c => c.name === key || (c.alias && c.alias === key)) || null;
    }

    function matchingCommands(typed) {
      const raw = String(typed || "").replace(/^\//, "");
      const name = raw.split(/\s+/)[0].toLowerCase();
      if (!name) return COMMAND_CATALOG.slice();
      const exact = COMMAND_CATALOG.find(c => c.alias && c.alias === name);
      const rest = COMMAND_CATALOG.filter(c => c !== exact && fuzzyMatch(c.name, name));
      return exact ? [exact, ...rest] : rest;
    }

    function _selectedTargets() {
      const targets = _bulkTargets();
      if (targets.length) return targets;
      if (selectedItem && selectedItem.editable) return [selectedItem];
      return [];
    }

    async function _applyToTargets(label, mutate) {
      const targets = _selectedTargets();
      if (!targets.length) {
        showToast("Select one or more records first (click a row, or press x).", "error");
        return;
      }
      let done = 0;
      for (const item of targets) {
        try {
          await mutate(item);
          done += 1;
        } catch (err) {
          showToast(`${label} failed: ${err.message || "error"}`, "error");
          break;
        }
      }
      if (done) {
        bulkSelectedLines.clear();
        showToast(`${label}: ${done} record(s).`, "success");
        await refreshAll();
      }
    }

    async function _setDetailOnTargets(key, value, label) {
      await _applyToTargets(label, async (item) => {
        const details = JSON.parse(JSON.stringify(item.details || {}));
        if (value === "") delete details[key];
        else details[key] = [value];
        await api(`/api/items/${item.line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({status: item.status, type: item.type, title: item.title, details}),
        });
      });
    }

    async function _resolveDateToken(value) {
      const data = await api("/api/shorthand/parse", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({date: value}),
      });
      return data.date;
    }

    function _setSearchBox(value) {
      const box = document.getElementById("search");
      if (box) { box.value = value; }
    }

    const WEB_COMMAND_HANDLERS = {
      help: async (arg) => {
        if (arg) { renderCmdk("/" + arg); openCmdk(); return; }
        openHelpModal();
      },
      view: async (arg) => {
        const name = (arg || "").trim().toLowerCase();
        const known = ["", "dashboard", "agenda", "timeline", "calendar", "focus", "review", "team", "stats", "graph"];
        const target = name === "all" || name === "items" ? "" : name;
        if (!known.includes(target)) throw new Error(`Unknown view: ${name}`);
        switchWorkspace(target);
      },
      next: async () => {
        _setSearchBox("");
        setStatusFilter("[ ]");
        showToast("Showing open work. Sort by priority for next actions.", "info");
        await loadItems();
      },
      search: async (arg) => { _setSearchBox(arg || ""); await loadItems(); },
      project: async (arg) => { _setSearchBox(arg ? `project:${arg}` : ""); await loadItems(); },
      context: async (arg) => { _setSearchBox(arg ? `context:${arg}` : ""); await loadItems(); },
      tag: async (arg) => { _setSearchBox(arg ? `tag:${String(arg).replace(/^#/, "")}` : ""); await loadItems(); },
      sort: async (arg) => {
        const select = document.getElementById("sort");
        const wanted = (arg || "").trim().toLowerCase();
        if (!select) throw new Error("Sorting is not available in this view.");
        const option = Array.from(select.options).find(o => o.value.toLowerCase() === wanted);
        if (!option) throw new Error(`Unknown sort: ${wanted}. Options: ${Array.from(select.options).map(o => o.value).join(", ")}`);
        select.value = option.value;
        await loadItems();
      },
      clear: async () => { clearAllFilters(); },
      goto: async (arg) => {
        const wanted = String(arg || "").trim();
        if (!wanted) throw new Error("Usage: /goto ID");
        const idKey = appConfig?.ids?.key || "id";
        const match = (currentItems || []).find(i => (i?.details?.[idKey] || []).includes(wanted));
        if (!match) throw new Error(`No visible record with id ${wanted}. Clear filters first.`);
        selectItem(match);
        openDrawer(match);
      },
      mark: async (arg) => {
        const mode = (arg || "toggle").trim().toLowerCase();
        if (mode === "none") { bulkClearSelection(); return; }
        if (mode === "all") {
          (currentItems || []).filter(i => i.editable)
            .forEach(i => bulkSelectedLines.add(String(i.line) + "|" + (i.source || "")));
          renderItems(currentItems);
          return;
        }
        throw new Error("Usage: /mark all|none");
      },
      done: async () => { await bulkOrSelectedStatus("[x]", "Marked done"); },
      status: async (arg) => {
        const aliases = {open: "[ ]", todo: "[ ]", active: "[/]", progress: "[/]", doing: "[/]",
                         done: "[x]", complete: "[x]", dropped: "[-]", cancelled: "[-]", canceled: "[-]",
                         deferred: "[>]", moved: "[>]", pending: "[?]"};
        const raw = (arg || "").trim().toLowerCase();
        const status = aliases[raw] || (raw.startsWith("[") ? raw : "");
        if (!status) throw new Error(`Unknown status: ${arg}. Try open, active, done, dropped, deferred.`);
        await bulkOrSelectedStatus(status, `Set ${status}`);
      },
      set: async (arg) => {
        const parts = String(arg || "").trim().split(/\s+/);
        const key = parts.shift();
        if (!key) throw new Error("Usage: /set KEY VALUE");
        await _setDetailOnTargets(key, parts.join(" "), `Set ${key}`);
      },
      due: async (arg) => {
        const raw = String(arg || "").trim();
        if (!raw) { await _setDetailOnTargets("due", "", "Cleared due"); return; }
        const resolved = await _resolveDateToken(raw);
        await _setDetailOnTargets("due", resolved, `Set due ${resolved}`);
      },
      assign: async (arg) => {
        await _setDetailOnTargets("assignee", String(arg || "").trim(), "Assigned");
      },
      add: async (arg) => {
        const text = String(arg || "").trim();
        if (!text) { toggleQuickAdd(true); return; }
        await api("/api/items/capture", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({text}),
        });
        showToast("Item added.", "success");
        await refreshAll();
      },
      delete: async (arg) => {
        if (String(arg || "").trim().toLowerCase() !== "yes") {
          throw new Error(`Deleting ${_selectedTargets().length} record(s). Re-run as /delete yes to confirm.`);
        }
        await _applyToTargets("Deleted", async (item) => {
          await api(`/api/items/${item.line}`, {method: "DELETE"});
        });
      },
      state: async (arg) => {
        const raw = String(arg || "").trim();
        if (!raw || raw.toLowerCase() === "end") { await endPresence(); return; }
        const parts = raw.split(/\s+/);
        const body = {state: parts[0]};
        if (parts.length > 1) body.title = parts.slice(1).join(" ");
        const data = await api("/api/status", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(body),
        });
        if (data.unchanged) showToast(`Already ${data.unchanged}.`, "info");
        else showToast(`Status: ${body.state}`, "success");
        await loadPresence();
        await refreshAll();
      },
      now: async () => {
        const data = await api("/api/status?active=true");
        const open = (data.records || []).filter(r => r.active);
        if (!open.length) { showToast("No open status.", "info"); return; }
        showToast(open.map(r => `${r.person}: ${r.state} since ${r.from}`).join("  |  "), "info");
      },
      timer: async (arg) => {
        const action = (arg || "status").trim().toLowerCase();
        if (action === "status") {
          const data = await api("/api/timer");
          showToast(data.running ? `Timer ${data.id}: ${data.elapsed}` : "No running timer.", "info");
          return;
        }
        if (!["start", "stop", "cancel"].includes(action)) throw new Error("Usage: /timer start|stop|status|cancel");
        const body = {action};
        if (action === "start") {
          const target = _selectedTargets()[0];
          const idKey = appConfig?.ids?.key || "id";
          const id = target?.details?.[idKey]?.[0];
          if (!id) throw new Error("Select a record with an id: to start a timer.");
          body.id = id;
        }
        const data = await api("/api/timer", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(body),
        });
        showToast(action === "start" ? `Timer started for ${data.id}.` : `Timer ${action}ed.`, "success");
        await refreshAll();
      },
      export: async (arg) => {
        const format = (arg || "markdown").trim().toLowerCase();
        const allowed = ["csv", "json", "markdown", "life"];
        if (!allowed.includes(format)) throw new Error(`Unknown format: ${format}. Options: ${allowed.join(", ")}`);
        exportItems(format);
      },
      stats: async () => { switchWorkspace("stats"); },
      detail: async () => {
        const target = _selectedTargets()[0];
        if (!target) throw new Error("Select a record first.");
        selectItem(target);
        openDrawer(target);
      },
      reload: async () => { await refreshAll(); showToast("Reloaded.", "success"); },
      theme: async (arg) => {
        const wanted = (arg || "").trim().toLowerCase();
        const dark = document.body.classList.contains("dark");
        if ((wanted === "dark" && !dark) || (wanted === "light" && dark) || !wanted) toggleDarkMode();
      },
    };

    async function bulkOrSelectedStatus(statusValue, label) {
      await _applyToTargets(label, async (item) => {
        await api(`/api/items/${item.line}`, {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({status: statusValue, type: item.type, title: item.title, details: item.details}),
        });
      });
    }

    async function runWebCommand(text) {
      const raw = String(text || "").trim().replace(/^\//, "");
      if (!raw) return;
      const [name, ...rest] = raw.split(/\s+/);
      const arg = rest.join(" ");
      const command = commandByName(name);
      if (!command) {
        const near = matchingCommands(name)[0];
        showToast(`Unknown command /${name}.` + (near ? ` Did you mean /${near.name}?` : ""), "error");
        return;
      }
      if (!command.web) {
        showToast(`/${command.name} is terminal-only. ${command.note || ""}`.trim(), "error");
        return;
      }
      const handler = WEB_COMMAND_HANDLERS[command.name];
      if (!handler) {
        showToast(`/${command.name} is not wired up in the browser yet.`, "error");
        return;
      }
      try {
        await handler(arg);
      } catch (err) {
        showToast(err.message || `/${command.name} failed.`, "error");
      }
    }

    // ── Mobile action button ───────────────────────────────────────
    // A phone has no Ctrl+K, no n, and no x, so every keyboard-only entry
    // point needs one reachable equivalent.
    function toggleMobileMenu(show) {
      const menu = document.getElementById("mobile-fab-menu");
      const fab = document.getElementById("mobile-fab");
      if (!menu) return;
      const open = show === undefined ? !menu.classList.contains("open") : show;
      menu.classList.toggle("open", open);
      if (fab) fab.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function mobileAction(what) {
      toggleMobileMenu(false);
      if (what === "command") { openCmdk(); const i = document.getElementById("cmdk-input"); if (i) i.value = "/"; renderCmdk("/"); }
      else if (what === "add") toggleQuickAdd(true);
      else if (what === "new") newItem();
      else if (what === "presence") togglePresence(true);
      else if (what === "refresh") refreshAll();
    }

    document.addEventListener("click", (e) => {
      const menu = document.getElementById("mobile-fab-menu");
      if (!menu || !menu.classList.contains("open")) return;
      if (e.target.closest("#mobile-fab-menu") || e.target.closest("#mobile-fab")) return;
      toggleMobileMenu(false);
    });

    function renderCmdkCommands(typed, list) {
      const matches = matchingCommands(typed);
      _cmdkEntries = matches.map(command => ({
        kind: command.web ? "cmd" : "cli",
        label: "/" + command.name + (command.usage ? " " + command.usage : ""),
        hint: command.alias ? "/" + command.alias : "",
        section: command.web ? "Commands" : "Terminal only",
        run: () => runWebCommand(typed.split(/\s+/)[0] === "/" + command.name || typed.slice(1).split(/\s+/)[0] === command.alias
          ? typed
          : "/" + command.name + " " + typed.split(/\s+/).slice(1).join(" ")),
        summary: command.summary,
      }));
      _cmdkIndex = 0;
      if (!_cmdkEntries.length) {
        list.innerHTML = `<div class="cmdk-empty">No command matches. Type / to list them all.</div>`;
        return;
      }
      list.innerHTML = "";
      let lastSection = "";
      _cmdkEntries.forEach((entry, i) => {
        if (entry.section !== lastSection) {
          const section = document.createElement("div");
          section.className = "cmdk-section";
          section.textContent = entry.section;
          list.appendChild(section);
          lastSection = entry.section;
        }
        const row = document.createElement("div");
        row.className = "cmdk-row" + (i === _cmdkIndex ? " focus" : "");
        // The label and hint are literal command syntax ("/stats", "/s"), not
        // prose; data-no-i18n keeps the generic translator from peeling the
        // "/" and rewriting the bare command name as if it were a UI label.
        row.innerHTML = `<span class="cmdk-kind">${escapeHtml(entry.kind)}</span>` +
          `<span data-no-i18n>${escapeHtml(entry.label)}</span>` +
          (entry.summary
            ? `<span style="margin-left:auto;color:var(--muted);font-size:.78rem">${escapeHtml(entry.summary)}</span>`
            : `<span style="margin-left:auto;color:var(--muted);font-size:.78rem" data-no-i18n>${escapeHtml(entry.hint)}</span>`);
        row.addEventListener("click", () => { closeCmdk(); entry.run(); });
        list.appendChild(row);
      });
    }

    function openCmdk() {
      const backdrop = document.getElementById("cmdk-backdrop");
