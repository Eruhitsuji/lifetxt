    const PRIORITY_MATRIX_GROUPS = [
      ["Q1", "Important / Urgent"],
      ["Q2", "Important / Not urgent"],
      ["Q3", "Not important / Urgent"],
      ["Q4", "Not important / Not urgent"],
      ["unclassified", "Unclassified"],
    ];
    let activePriorityMatrixGroup = "Q1";
    let priorityMatrixData = null;

    async function loadPriorityMatrix() {
      try {
        priorityMatrixData = await api("/api/priority-matrix");
        renderPriorityMatrix();
      } catch (error) {
        const detail = document.getElementById("priority-matrix-detail");
        if (detail) detail.innerHTML = `<div class="empty">${escapeHtml(t("Could not load priority matrix."))}</div>`;
      }
    }

    function selectPriorityMatrixGroup(group) {
      activePriorityMatrixGroup = group;
      renderPriorityMatrix();
    }

    function renderPriorityMatrix() {
      if (!priorityMatrixData) return;
      const grid = document.getElementById("priority-matrix-grid");
      const detail = document.getElementById("priority-matrix-detail");
      const heading = document.getElementById("priority-matrix-detail-heading");
      const evaluated = document.getElementById("priority-matrix-evaluated-at");
      if (!grid || !detail || !heading) return;
      const counts = priorityMatrixData.counts || {};
      const groups = priorityMatrixData.groups || {};
      grid.innerHTML = PRIORITY_MATRIX_GROUPS.map(([key, label]) =>
        `<button type="button" class="priority-matrix-card${key === activePriorityMatrixGroup ? " is-active" : ""}" aria-pressed="${key === activePriorityMatrixGroup}" onclick="selectPriorityMatrixGroup('${key}')"><span>${escapeHtml(t(label))}</span><strong>${Number(counts[key] || 0)}</strong></button>`
      ).join("");
      const activeLabel = PRIORITY_MATRIX_GROUPS.find(([key]) => key === activePriorityMatrixGroup)?.[1] || "Unclassified";
      heading.textContent = t(activeLabel);
      const selected = groups[activePriorityMatrixGroup] || [];
      detail.innerHTML = selected.length ? selected.map((row) => {
        const priority = row.priority ? escapeHtml(row.priority) : escapeHtml(t("Not set"));
        const due = row.due ? escapeHtml(row.due) : escapeHtml(t("No due date"));
        return `<article class="priority-matrix-row" data-no-i18n><strong class="priority-matrix-title">${escapeHtml(row.title || "")}</strong><span>${escapeHtml(t("Manual priority"))}: ${priority}</span><span>${escapeHtml(t("Due"))}: ${due}</span></article>`;
      }).join("") : `<div class="empty">${escapeHtml(t("No tasks in this group."))}</div>`;
      if (evaluated) evaluated.textContent = `${t("Evaluated at")}: ${priorityMatrixData.evaluated_at || ""} (${priorityMatrixData.timezone || "UTC"})`;
    }
