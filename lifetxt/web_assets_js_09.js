          projMap[p].total++;
          if (item.status === "[x]") projMap[p].done++;
        }
      }
      const sorted = Object.entries(projMap).sort((a,b) => b[1].total - a[1].total).slice(0,6);
      if (!sorted.length) return;
      const maxT = Math.max(...sorted.map(([,v]) => v.total), 1);
      let table = `<div style="margin-top:.45rem;overflow-x:auto"><table class="proj-stats-table"><thead><tr><th>Project</th><th>✓</th><th>N</th><th></th></tr></thead><tbody>`;
      for (const [proj, v] of sorted) {
        const barW = Math.round(v.total / maxT * 56);
        const opacity = (0.4 + 0.6 * (v.done / Math.max(v.total, 1))).toFixed(2);
        table += `<tr><td>${escapeHtml(proj)}</td><td>${v.done}</td><td>${v.total}</td><td><span class="proj-stats-bar" style="width:${barW}px;opacity:${opacity}"></span></td></tr>`;
      }
      table += `</tbody></table></div>`;
      el.insertAdjacentHTML("beforeend", table);
    }
    function renderFilterChips() {
      const params = query();
      const el = document.getElementById("filter-chips");
      el.innerHTML = "";
      const filterKeys = [
        ["kind", "type"], ["status"], ["project"], ["tag"], ["user"], ["team"],
        ["person"], ["assignee"], ["owner"], ["after"], ["before"],
      ];
      const shown = new Set();
      for (const keys of filterKeys) {
        for (const k of keys) {
          if (shown.has(k)) break;
          const val = params.get(k);
          if (val) {
            shown.add(k);
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.innerHTML = `${escapeHtml(k)}:${escapeHtml(val)} <button title="Remove" onclick="removeFilter(${jsLiteral(k)})">×</button>`;
            el.appendChild(chip);
          }
        }
      }
      if (params.get("open_only") === "true") {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.innerHTML = `open only <button title="Remove" onclick="removeFilter('open_only')">×</button>`;
        el.appendChild(chip);
      }
    }
    function removeFilter(key) {
      const params = query();
      params.delete(key);
      if (key === "open_only") document.getElementById("open-only").checked = false;
      if (key === "kind" || key === "type") document.getElementById("kind").value = "";
      history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
      loadItems();
    }
    function groupKeyFor(item, groupBy) {
      if (groupBy === "project") return item?.details?.project?.[0] || "(no project)";
      if (groupBy === "type") return ITEM_TYPE_NAMES[item.type] || item.type || "(none)";
      if (groupBy === "status") return STATUS_LABEL[item.status] || item.status || "(none)";
      if (groupBy === "source") return item.source || "(unknown source)";
      return "";
    }
    function buildDueRelLabel(item) {
      const due = item?.details?.due?.[0];
      if (!due || ["[x]", "[-]"].includes(item.status)) return "";
      const d = new Date(due);
      if (isNaN(d)) return "";
      const today = new Date(); today.setHours(0,0,0,0);
      const dm = new Date(d); dm.setHours(0,0,0,0);
      const diff = Math.round((dm - today) / 86400000);
      let text, cls = "";
      if (diff < 0) { text = `${-diff}d overdue`; cls = "overdue"; }
      else if (diff === 0) { text = "due today"; cls = "due-soon"; }
      else if (diff <= dueSoonDays()) { text = `in ${diff}d`; cls = "due-soon"; }
      else if (diff <= 60) { text = `in ${diff}d`; }
      else return "";
      return `<span class="due-rel ${cls}">${escapeHtml(text)}</span>`;
    }
    function agendaCountdownLabel(record) {
      // Days-remaining countdown for an agenda record, derived from its
      // occurrence date (works for due, do, and event records alike).
      if (["[x]", "[-]"].includes(record?.status)) return "";
      const raw = record?.occurrence_start || record?.when || "";
      const d = new Date(String(raw).replace(" ", "T"));
      if (isNaN(d)) return "";
      const today = new Date(); today.setHours(0, 0, 0, 0);
      const dm = new Date(d); dm.setHours(0, 0, 0, 0);
      const diff = Math.round((dm - today) / 86400000);
      let text, cls = "";
      if (diff < 0) { text = `${-diff}d ago`; cls = "overdue"; }
      else if (diff === 0) { text = "today"; cls = "due-soon"; }
      else if (diff <= dueSoonDays()) { text = `in ${diff}d`; cls = "due-soon"; }
      else if (diff <= 365) { text = `in ${diff}d`; }
      else return "";
      return `<span class="due-rel ${cls}">${escapeHtml(text)}</span>`;
    }
    function guidedEmptyState(icon, title, hint, actions = []) {
      // Shared guided empty state (icon + title + hint + optional action
      // buttons) so Agenda, Team, Status, Notifications, Stats, and Graph give
      // the same actionable guidance as the Items view.
      const btns = actions.map(([label, action]) =>
        `<button type="button" class="secondary" onclick="runViewGuideAction(${escapeHtml(jsLiteral(action))})">${escapeHtml(label)}</button>`
      ).join("");
      return `<div class="empty-state"><div class="empty-icon" aria-hidden="true">${icon}</div>` +
        `<div class="empty-title">${escapeHtml(title)}</div>` +
        (hint ? `<div class="empty-hint">${hint}</div>` : "") +
        (btns ? `<div class="empty-actions">${btns}</div>` : "") + `</div>`;
    }
    function enhanceItemsEmptyState(hasFilters) {
      if (isKioskMode() || isDisplayMode()) return;
      const state = document.querySelector("#items .empty-state");
      if (!state) return;
      state.querySelectorAll(":scope > button, :scope > .empty-actions").forEach(el => el.remove());
      const actions = document.createElement("div");
      actions.className = "empty-actions";
      if (hasFilters) {
        actions.innerHTML =
          `<button type="button" class="secondary" onclick="clearAllFilters()">Clear filters</button>` +
          `<button type="button" onclick="newItem()">New record</button>`;
      } else {
        actions.innerHTML =
          `<button type="button" onclick="newItem()">New record</button>` +
          `<button type="button" class="secondary" onclick="toggleQuickAdd(true)">Quick add</button>` +
          `<button type="button" class="secondary" onclick="openCmdk()">Command palette</button>`;
      }
      state.appendChild(actions);
    }
    function renderItems(items) {
      const root = document.getElementById("items");
      const hasFilters = !!(document.getElementById("search").value.trim() ||
        query().get("status") || query().get("blocked") ||
        document.getElementById("kind").value || document.getElementById("open-only").checked);
      root.innerHTML = items.length ? "" : `
        <div class="empty-state">
          <div class="empty-icon" aria-hidden="true">${hasFilters ? "🔍" : "🌱"}</div>
          <div class="empty-title">${hasFilters ? "No items match the current filters" : "No items yet"}</div>
          <div class="empty-hint">${hasFilters
            ? "Try clearing the search text or status filters above."
            : "Add your first record with the quick-add bar (press q) or the New workspace."}</div>
          ${isKioskMode() || isDisplayMode() ? "" : (hasFilters
            ? `<button type="button" class="secondary" onclick="clearAllFilters()">Clear filters</button>`
            : `<button type="button" onclick="toggleQuickAdd(true)">＋ Quick add</button>`)}
        </div>`;
      if (!items.length) enhanceItemsEmptyState(hasFilters);
      renderSummary(items);
      renderFilterChips();
      updateSearchCount(items.length);
      const kioskNow = isKioskMode();
      const nextFingerprints = new Map();
      _kbIndex = -1;
      const groupBy = kioskNow ? "" : (document.getElementById("group-by")?.value || "");
      const appendItem = (item) => {
        const node = buildItemNode(item, kioskNow, nextFingerprints);
        root.appendChild(node);
      };
      if (groupBy) {
        const groups = new Map();
        for (const item of items) {
          const g = groupKeyFor(item, groupBy);
          if (!groups.has(g)) groups.set(g, []);
          groups.get(g).push(item);
        }
        for (const [name, groupItems] of groups) {
          root.insertAdjacentHTML(
            "beforeend",
            `<div class="group-header">${escapeHtml(name)} <span class="n">(${groupItems.length})</span></div>`
          );
          for (const item of groupItems) appendItem(item);
        }
      } else {
        for (const item of items) appendItem(item);
      }
      if (kioskNow) _kioskLastFingerprints = nextFingerprints;
      else _kioskLastFingerprints = null;
      const queryText = document.getElementById("search").value.trim();
      if (queryText) {
        root.querySelectorAll(".title.markdown, .meta, .body-preview").forEach(el => {
          el.innerHTML = highlightText(el.innerHTML, queryText);
        });
      }
    }
    function buildItemNode(item, kioskNow, nextFingerprints) {
        const titleHtml = safeMarkdownHtml(item?.markdown?.title, item.title);
        const previewHtml = firstMarkdownDetail(item, "body") || firstMarkdownDetail(item, "note");
        const preview = previewHtml ? `<div class="markdown body-preview">${previewHtml}</div>` : "";
        const occurrenceBadge = item.occurrence_start
          ? `<span class="occurrence-badge" title="${escapeHtml(item.occurrence_start)}">occurrence</span>`
          : "";
        const generatedBadge = item.generated && !item.occurrence_start
          ? `<span class="occurrence-badge" title="generated/read-only source file">generated</span>`
          : "";
        const statusCls = STATUS_CLASS[item.status] || "status-note";
        const statusLabel = STATUS_LABEL[item.status] || item.status;
        const typeCls = "type-" + (item.type || "N");
        const dueCls = itemDueSoonClass(item);
        const refLinks = buildRefLinksHtml(item.details);
        const parentInd = buildParentIndicator(item.details);
        const dueRel = buildDueRelLabel(item);
        const stableKey = itemStableKey(item);
        const fingerprint = itemFingerprint(item);
        nextFingerprints.set(stableKey, fingerprint);
        const node = document.createElement("button");