    }

    function computeLayeredPositions(shownNodes, shownEdges, layout, w, h) {
      const ids = shownNodes.map(n => String(n.id));
      const idSet = new Set(ids);
      const indeg = new Map(ids.map(id => [id, 0]));
      const out = new Map(ids.map(id => [id, []]));
      for (const e of shownEdges) {
        const s = String(e.source), t = String(e.target);
        if (!idSet.has(s) || !idSet.has(t) || s === t) continue;
        out.get(s).push(t);
        indeg.set(t, indeg.get(t) + 1);
      }
      // Kahn-style layering; cycles fall into the trailing layer.
      const layer = new Map();
      const seen = new Set();
      let frontier = ids.filter(id => indeg.get(id) === 0);
      if (!frontier.length && ids.length) frontier = [ids[0]];
      let depth = 0;
      const remaining = new Map(indeg);
      while (frontier.length) {
        const next = [];
        for (const id of frontier) {
          if (seen.has(id)) continue;
          seen.add(id);
          layer.set(id, depth);
          for (const t of out.get(id) || []) {
            remaining.set(t, remaining.get(t) - 1);
            if (remaining.get(t) <= 0 && !seen.has(t)) next.push(t);
          }
        }
        frontier = next;
        depth++;
      }
      for (const id of ids) if (!layer.has(id)) layer.set(id, depth);
      const byLayer = new Map();
      for (const id of ids) {
        const l = layer.get(id);
        if (!byLayer.has(l)) byLayer.set(l, []);
        byLayer.get(l).push(id);
      }
      const layers = [...byLayer.keys()].sort((a, b) => a - b);
      const main = layout === "lr" ? w : h;
      const cross = layout === "lr" ? h : w;
      const mainPad = 52, crossPad = 36;
      const positions = {};
      layers.forEach((l, li) => {
        const layerIds = byLayer.get(l);
        const mainPos = layers.length > 1 ? mainPad + (main - 2 * mainPad) * li / (layers.length - 1) : main / 2;
        layerIds.forEach((id, i) => {
          const crossPos = layerIds.length > 1 ? crossPad + (cross - 2 * crossPad) * i / (layerIds.length - 1) : cross / 2;
          positions[id] = layout === "lr" ? {x: mainPos, y: crossPos} : {x: crossPos, y: mainPos};
        });
      });
      return positions;
    }

    function computeForcePositions(nodes, edges, w, h, focusId) {
      // Lightweight deterministic force-directed layout (Fruchterman-Reingold
      // style): repulsion between all nodes, attraction along edges, cooling.
      const ids = nodes.map(n => String(n.id));
      const n = ids.length;
      const pad = 40;
      const pos = {};
      // Seed positions on a circle for a stable, reproducible start.
      ids.forEach((id, i) => {
        const a = (Math.PI * 2 * i) / Math.max(1, n);
        pos[id] = {
          x: w / 2 + Math.cos(a) * (Math.min(w, h) / 3),
          y: h / 2 + Math.sin(a) * (Math.min(w, h) / 3),
        };
      });
      if (n <= 1) { if (n === 1) pos[ids[0]] = {x: w / 2, y: h / 2}; return pos; }
      const area = (w - 2 * pad) * (h - 2 * pad);
      const k = Math.sqrt(area / n) * 0.85;
      const adj = edges.map(e => [String(e.source), String(e.target)])
        .filter(([s, t]) => pos[s] && pos[t] && s !== t);
      let temp = Math.min(w, h) / 6;
      const iterations = 220;
      for (let step = 0; step < iterations; step++) {
        const disp = {};
        for (const id of ids) disp[id] = {x: 0, y: 0};
        // Repulsive forces between every pair.
        for (let i = 0; i < n; i++) {
          for (let j = i + 1; j < n; j++) {
            const a = pos[ids[i]], b = pos[ids[j]];
            let dx = a.x - b.x, dy = a.y - b.y;
            let dist = Math.hypot(dx, dy) || 0.01;
            const rep = (k * k) / dist;
            const ux = dx / dist, uy = dy / dist;
            disp[ids[i]].x += ux * rep; disp[ids[i]].y += uy * rep;
            disp[ids[j]].x -= ux * rep; disp[ids[j]].y -= uy * rep;
          }
        }
        // Attractive forces along edges.
        for (const [s, t] of adj) {
          const a = pos[s], b = pos[t];
          let dx = a.x - b.x, dy = a.y - b.y;
          let dist = Math.hypot(dx, dy) || 0.01;
          const att = (dist * dist) / k;
          const ux = dx / dist, uy = dy / dist;
          disp[s].x -= ux * att; disp[s].y -= uy * att;
          disp[t].x += ux * att; disp[t].y += uy * att;
        }
        // Apply displacement capped by temperature, keep in bounds.
        for (const id of ids) {
          if (String(id) === String(focusId)) continue; // pin focus loosely
          const d = disp[id];
          const len = Math.hypot(d.x, d.y) || 0.01;
          pos[id].x += (d.x / len) * Math.min(len, temp);
          pos[id].y += (d.y / len) * Math.min(len, temp);
          pos[id].x = Math.max(pad, Math.min(w - pad, pos[id].x));
          pos[id].y = Math.max(pad, Math.min(h - pad, pos[id].y));
        }
        temp *= 0.97;
      }
      if (focusId && pos[String(focusId)]) pos[String(focusId)] = {x: w / 2, y: h / 2};
      return pos;
    }

    function renderGraphSvg(nodes, edges, options = {}) {
      const compact = !!options.compact;
      const focusId = options.focusId || "";
      const layout = options.layout || "ring";
      const maxNodes = compact ? 10 : 40;
      const shownNodes = (nodes || []).slice(0, maxNodes);
      const shown = new Set(shownNodes.map(n => String(n.id)));
      const shownEdges = (edges || []).filter(e => shown.has(String(e.source)) && shown.has(String(e.target)));
      const w = compact ? 360 : 640;
      const h = compact ? 180 : 300;
      let positions = {};
      if (layout === "force") {
        positions = computeForcePositions(shownNodes, shownEdges, w, h, focusId);
      } else if (layout === "lr" || layout === "tb") {
        positions = computeLayeredPositions(shownNodes, shownEdges, layout, w, h);
      } else {
        const cx = w / 2;
        const cy = h / 2;
        const r = compact ? 56 : 110;
        const focusIndex = shownNodes.findIndex(n => String(n.id) === String(focusId));
        const ringNodes = focusIndex >= 0 ? shownNodes.filter((_, i) => i !== focusIndex) : shownNodes;
        if (focusIndex >= 0) positions[String(focusId)] = {x: cx, y: cy};
        ringNodes.forEach((node, i) => {
          const angle = (Math.PI * 2 * i / Math.max(1, ringNodes.length)) - Math.PI / 2;
          positions[String(node.id)] = {x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r};
        });
      }
      const defs = `<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#94a3b8"/></marker></defs>`;
      const edgeHtml = shownEdges.map(e => {
        const a = positions[String(e.source)];
        const b = positions[String(e.target)];
        if (!a || !b) return "";
        const mx = (a.x + b.x) / 2;
        const my = (a.y + b.y) / 2;
        return `<line class="graph-edge" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"></line>` +
          `<text class="graph-edge-label" x="${mx}" y="${my - 4}" text-anchor="middle">${escapeHtml(truncateLabel(e.relation, compact ? 8 : 12))}</text>`;
      }).join("");
      const nodeHtml = shownNodes.map(node => {
        const p = positions[String(node.id)];
        if (!p) return "";
        const id = String(node.id || "");
        const missing = !!node.missing;
        const label = truncateLabel(node.title || id, compact ? 12 : 18) + (missing ? " (?)" : "");
        const nav = escapeHtml(jsLiteral(id));
        const radius = id === String(focusId) ? (compact ? 18 : 24) : (compact ? 14 : 20);
        const tooltip = id + " " + (node.title || "") + (missing ? " — referenced but not found in loaded files" : "");
        return `<g class="graph-node${missing ? " missing" : ""}" onclick="drawerNavigate(${nav})" transform="translate(${p.x},${p.y})">` +
          `<title>${escapeHtml(tooltip)}</title>` +
          `<circle r="${radius}"${missing ? "" : ` fill="${graphColor(node.type)}"`}></circle>` +
          `<text text-anchor="middle" y="${radius + 13}">${escapeHtml(label)}</text>` +
          `</g>`;
      }).join("");
      const more = (nodes || []).length > shownNodes.length
        ? `<text x="${w - 10}" y="${h - 10}" text-anchor="end" fill="#64748b" font-size="10">+${(nodes || []).length - shownNodes.length} more</text>`
        : "";
      return `<svg class="graph-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="life.txt dependency graph">${defs}${edgeHtml}${nodeHtml}${more}</svg>`;
    }

    // ── Graph layout presets + SVG/PNG export ─────────────────────
    let _graphLayout = (function() {
      try { return localStorage.getItem("lifetxt_graph_layout") || "ring"; } catch(_) { return "ring"; }
    })();
    function setGraphLayout(layout) {
      _graphLayout = layout;
      try { localStorage.setItem("lifetxt_graph_layout", layout); } catch(_) {}
      _syncGraphLayoutBtns();
      if (graphLoaded) loadGraphPanel();
      const binding = document.getElementById("drawer-deps")?._relationGraph;
      const panel = document.querySelector("#drawer-deps .drawer-relation-graph");
      if (panel && binding?.graph) panel.innerHTML = renderDependencyMiniGraph(binding.records, binding.id, binding.graph);
    }
    function _syncGraphLayoutBtns() {
      document.querySelectorAll(".graph-layout-btn[data-layout]").forEach(b => {
        b.classList.toggle("active", b.dataset.layout === _graphLayout);
      });
    }
    const GRAPH_EXPORT_CSS = "svg{background:#ffffff;font-family:sans-serif}" +
      ".graph-edge{stroke:#94a3b8;stroke-width:1.4;marker-end:url(#arrow);opacity:.8}" +
      ".graph-edge-label{fill:#68706a;font-size:9px}" +
      ".graph-node circle{stroke:#fff;stroke-width:2}" +
      ".graph-node text{fill:#202421;font-size:10px;font-weight:700}" +
      ".graph-node.missing circle{fill:#ffffff;stroke:#9ca3af;stroke-dasharray:4 3}" +
      ".graph-node.missing text{font-style:italic;fill:#9ca3af}";
    function _graphSvgForExport() {
      const svg = document.querySelector("#graph-panel .graph-svg");
      if (!svg) { showToast("Open and load the Graph panel first.", "warning"); return null; }
      const clone = svg.cloneNode(true);
      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
      style.textContent = GRAPH_EXPORT_CSS;
      clone.insertBefore(style, clone.firstChild);
      clone.querySelectorAll("[onclick]").forEach(el => el.removeAttribute("onclick"));
      return clone;
    }
    function _downloadBlob(blob, filename) {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    }
    function exportGraphSvg() {
      const clone = _graphSvgForExport();
      if (!clone) return;
      const text = new XMLSerializer().serializeToString(clone);
      _downloadBlob(new Blob([text], {type: "image/svg+xml"}), "lifetxt-graph.svg");
      showToast("Graph exported as SVG.", "success");
    }
    function exportGraphPng() {
      const clone = _graphSvgForExport();
      if (!clone) return;
      const vb = (clone.getAttribute("viewBox") || "0 0 640 300").split(/\s+/).map(Number);
      clone.setAttribute("width", String(vb[2]));
      clone.setAttribute("height", String(vb[3]));
      const text = new XMLSerializer().serializeToString(clone);
      const img = new Image();
      const scale = 2;
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = vb[2] * scale;
        canvas.height = vb[3] * scale;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(blob => {
          if (!blob) { showToast("PNG export failed.", "error"); return; }
          _downloadBlob(blob, "lifetxt-graph.png");
          showToast("Graph exported as PNG.", "success");
        }, "image/png");
      };
      img.onerror = () => showToast("PNG export failed.", "error");
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(text);
    }

    function graphFromLinkRecords(records, focusId) {
      const map = new Map();
      const edges = [];
      const put = (id, title, status, type, missing) => {
        if (!id) return;
        const key = String(id);
        if (!map.has(key)) map.set(key, {id: key, title: title || key, status: status || "", type: type || "", missing: !!missing});
        else if (!missing) map.get(key).missing = false;
      };
      put(focusId, focusId, "", "", false);
      for (const r of records || []) {
        put(r.source_id, r.source_title, r.source_status, r.source_type, false);
        put(r.target_id, r.target_title, r.target_status, r.target_type, r.status === "missing");
        if (r.source_id && r.target_id) edges.push({source: r.source_id, target: r.target_id, relation: r.relation});
      }
      return {nodes: [...map.values()], edges};
    }

    function renderDependencyMiniGraph(records, focusId, graphData) {
      const graph = graphData && (graphData.nodes || graphData.edges)
        ? {nodes: graphData.nodes || [], edges: graphData.edges || []}
        : graphFromLinkRecords(records, focusId);
      if (graph.nodes.length <= 1) return "";
      const layoutBar = `<div class="graph-layout-bar" style="margin:.1rem 0 .3rem">` +
        ["ring", "lr", "tb"].map(l =>
          `<button class="graph-layout-btn${l === _graphLayout ? " active" : ""}" type="button" onclick="setGraphLayout(${escapeHtml(jsLiteral(l))})" title="Switch mini-graph layout">${l.toUpperCase()}</button>`
        ).join("") + `</div>`;
      return `<div class="drawer-graph-mini">${layoutBar}${renderGraphSvg(graph.nodes, graph.edges, {compact: true, focusId, layout: _graphLayout})}</div>`;
    }

    async function loadGraphPanel() {
      const panel = document.getElementById("graph-panel");
      if (!panel) return;
      graphLoaded = true;
      const rootInput = document.getElementById("graph-root");
      const depthInput = document.getElementById("graph-depth");
      const root = (rootInput && rootInput.value) || firstParam(query(), ["graph_root", "root"], "");
      const depth = (depthInput && depthInput.value) || firstParam(query(), ["graph_depth", "depth"], "");
      const params = new URLSearchParams();
      if (root) params.set("root", root);
      if (depth) params.set("depth", depth);
      panel.innerHTML = `<div class="empty">Loading graph…</div>`;
      try {
        const data = await api(`/api/graph?${params.toString()}`);
        const nodes = data.nodes || [];
        const edges = data.edges || [];
        if (!nodes.length) {
          panel.innerHTML = guidedEmptyState("🕸️", "No ID links to graph yet",
            "Give records an <code>id</code> and connect them with <code>parent</code>, <code>ref</code>, <code>depends_on</code>, <code>blocks</code>, or <code>related</code> details.",
            [["New record", "newItem"], ["Items", "items"], ["Help", "help"]]);
          return;
        }
        const missingCount = nodes.filter(n => n.missing).length;
        const missingNote = missingCount ? ` ${missingCount} dashed node(s) are referenced but missing.` : "";
        panel.innerHTML = renderGraphSvg(nodes, edges, {focusId: root, layout: _graphLayout}) +
          `<div class="note" style="margin-top:.45rem">${nodes.length} nodes / ${edges.length} edges. Click a node to open it.${escapeHtml(missingNote)}</div>`;
      } catch(e) {
        panel.innerHTML = `<div class="diagnostic">Graph error: ${escapeHtml(e.message)}</div>`;
      }
    }

    // ── Native Timeline visual explorer (#769) ──────────────────────────
    // Pure presentation over the existing temporal-timeline-v1 read model
    // returned by GET /api/native-timeline/{id} (#762 / lifetxt.native_timeline).
    // No history parsing, ordering, or completeness computation happens
    // here: every fact rendered below is read directly from the shared
    // result, and filters delegate to the same since/until/event/limit
    // query parameters the API and TUI /timeline command already accept.
    let _ntCurrentItemId = null;
    let _ntRequestToken = 0;
    let _ntAdvancedOpen = false;
    function nativeTimelineText(en, ja) {
      return typeof currentLanguage === "function" && currentLanguage() === "ja" ? ja : en;
    }
    function nativeTimelineUi(value) {
      const labels = {
        __proto__: null,
        Created: "作成", "Status changed": "状態を変更", Completed: "完了", Reopened: "再開", Canceled: "取消",
        "Relation added": "関連を追加", "Relation removed": "関連を削除", "Schedule changed": "予定を変更",
        "Time entry": "時間を記録", "Progress increment": "進捗を加算", "All events": "すべてのイベント",
        At: "日時", "Record ID": "記録ID", Event: "イベント", Item: "レコード", Progress: "進捗", Ticket: "チケット", Time: "時間", Record: "記録種別",
        Transaction: "トランザクション", "Source revision": "出典リビジョン", Sequence: "連番",
      };
      return nativeTimelineText(value, labels[value] || value);
    }
    function nativeTimelineStatus(value) {
      const names = {__proto__: null, "[ ]": ["Open", "未完了"], "[/]": ["In progress", "進行中"], "[x]": ["Done", "完了"], "[-]": ["Canceled", "取消"], "[>]": ["Deferred", "延期"], "[?]": ["Uncertain", "未確定"], "[N]": ["Note", "メモ"]};
      return names[value] ? nativeTimelineText(...names[value]) + " " + value : String(value ?? "—");
    }

    let _ntFilters = { since: "", until: "", event: "", limit: "" };

    const NATIVE_TIMELINE_EVENT_LABELS = {
      __proto__: null,
      created: "Created", status_changed: "Status changed", completed: "Completed",
      reopened: "Reopened", canceled: "Canceled",
      relation_added: "Relation added", relation_removed: "Relation removed",
      schedule_changed: "Schedule changed", time_entry: "Time entry",
    };
    const NATIVE_TIMELINE_KIND_ICON = {
      __proto__: null,
      item_event: "●", progress_event: "◐", ticket_event: "▣", time_entry: "⏱",
    };
    const NATIVE_TIMELINE_KIND_LABEL = {
      __proto__: null,
      item_event: "Item", progress_event: "Progress", ticket_event: "Ticket", time_entry: "Time",
    };
    const NATIVE_TIMELINE_EVENT_VALUES = [
      ["", "All events"], ["created", "Created"], ["status_changed", "Status changed"],
      ["completed", "Completed"], ["reopened", "Reopened"], ["canceled", "Canceled"],
      ["relation_added", "Relation added"], ["relation_removed", "Relation removed"],
      ["schedule_changed", "Schedule changed"], ["progress_increment", "Progress increment"],
    ];

    function nativeTimelineEventLabel(row) {
      const event = row?.event || "";
      const kind = row?.record_kind || "";
      if (NATIVE_TIMELINE_EVENT_LABELS[event]) return nativeTimelineUi(NATIVE_TIMELINE_EVENT_LABELS[event]);
      if (kind === "progress_event") return nativeTimelineUi("Progress " + event.replace(/^progress_/, ""));
      if (kind === "ticket_event") return nativeTimelineText("Ticket", "チケット") + ": " + (event || nativeTimelineText("event", "イベント"));
      return event || kind || "event";
    }

    function nativeTimelineTransitionHtml(payload) {
      if (!payload || typeof payload !== "object") return "";
      if ("before_status" in payload || "after_status" in payload) {
        return `<span class="nt-transition">${escapeHtml(nativeTimelineStatus(payload.before_status))} → ${escapeHtml(nativeTimelineStatus(payload.after_status))}</span>`;
      }
      if ("before_progress" in payload || "after_progress" in payload) {
        const before = payload.before_missing ? "—" : escapeHtml(String(payload.before_progress ?? ""));
        return `<span class="nt-transition">${before} → ${escapeHtml(String(payload.after_progress ?? ""))}</span>`;
      }
      if ("field" in payload && ("before" in payload || "after" in payload)) {
        const before = payload.before_missing ? "—" : escapeHtml(String(payload.before ?? ""));
        const after = payload.after_missing ? "—" : escapeHtml(String(payload.after ?? ""));
        return `<span class="nt-transition">${escapeHtml(String(payload.field || ""))}: ${before} → ${after}</span>`;
      }
      if ("relation" in payload && "target" in payload) {
        return `<span class="nt-transition">${escapeHtml(String(payload.relation))} → ${escapeHtml(String(payload.target))}</span>`;
      }
      return "";
    }

    function nativeTimelineProgressTrendHtml(eventsNewestFirst) {
      const points = [];
      for (const row of eventsNewestFirst) {
        if (row.record_kind !== "progress_event") continue;
        const raw = row?.payload?.after_progress;
        if (!raw) continue;
        const match = /^(\d+(?:\.\d+)?)%$/.exec(String(raw).trim());
        if (!match) continue;
        points.push(parseFloat(match[1]));
      }
      if (points.length < 2) return "";
      const ordered = points.slice().reverse(); // oldest -> newest for the trend
      const bars = ordered.map(v => {
        const height = Math.max(2, Math.round((Math.max(0, Math.min(100, v)) / 100) * 14));
        return `<span style="height:${height}px" title="${escapeHtml(String(v))}%"></span>`;
      }).join("");
      return `<span class="nt-progress-trend" title="${nativeTimelineText(`Progress trend across ${ordered.length} valid percentage event(s)`, `${ordered.length}件の有効な百分率イベントの推移`)}">${bars}</span>`;
    }

    function nativeTimelineDetailsHtml(row) {
      const rows = [
        ["At", row.at],
        ["Record ID", row.record_id],
        ["Event", row.event],
        ["Record", row.record_kind],
        ["Transaction", row.transaction],
        ["Source revision", row.source_revision],
        ["Sequence", row.sequence != null ? String(row.sequence) : ""],
      ];
      let html = `<div class="nt-details-body">`;
      for (const [label, value] of rows) {
        if (!value) continue;
        html += `<div class="row"><span class="k">${escapeHtml(nativeTimelineUi(label))}</span><span>${escapeHtml(String(value))}</span></div>`;
      }
      const payload = row.payload || {};
      for (const [key, value] of Object.entries(payload)) {
        const text = Array.isArray(value) ? value.join(", ") : String(value);
        html += `<div class="row"><span class="k">${escapeHtml(key)}</span><span>${escapeHtml(text)}</span></div>`;
      }
      html += `</div>`;
      return html;
    }

    function nativeTimelineEventRowHtml(row) {
      const icon = NATIVE_TIMELINE_KIND_ICON[row.record_kind] || "○";
      const kindLabel = NATIVE_TIMELINE_KIND_LABEL[row.record_kind] || row.record_kind || "event";
      const transition = nativeTimelineTransitionHtml(row.payload);
      const invalid = row.valid === false;
      return `<div class="nt-event${invalid ? " nt-invalid" : ""}">
        <span class="nt-marker nt-marker-${escapeHtml(row.record_kind || "")}" aria-hidden="true">${icon}</span>
        <div class="nt-body">
          <div class="nt-head">
            <span class="nt-time">${typeof drawerDateValue === "function" ? drawerDateValue(row.at || "") : escapeHtml(String(row.at || ""))}</span>
            <span class="nt-kind-badge">${escapeHtml(nativeTimelineUi(kindLabel))}</span>
            <span class="nt-event-label">${escapeHtml(nativeTimelineEventLabel(row))}${invalid ? nativeTimelineText(" (invalid)", "（無効）") : ""}</span>
            ${transition}
          </div>
          <details class="nt-details">
            <summary>${nativeTimelineText("Technical details", "技術情報")}</summary>
            ${nativeTimelineDetailsHtml(row)}
          </details>
        </div>
      </div>`;
    }

    function nativeTimelineDateKey(at) {
      const value = String(at || "");
      const formatted = typeof drawerDateValue === "function" ? drawerDateValue(value) : "";
      const match = />(\d{4}-\d{2}-\d{2}) /.exec(formatted) || /^(\d{4}-\d{2}-\d{2})/.exec(value);
      return match ? match[1] : (value || nativeTimelineText("Unknown date", "日時不明"));
    }

    function renderNativeTimelineFiltersHtml() {
      const eventOptions = NATIVE_TIMELINE_EVENT_VALUES.map(([value, label]) =>
        `<option value="${escapeHtml(value)}"${value === _ntFilters.event ? " selected" : ""}>${escapeHtml(nativeTimelineUi(label))}</option>`
      ).join("");
      const text = nativeTimelineText;
      return `<div class="nt-filters" role="group" aria-label="${text("Timeline filters", "履歴フィルタ")}">
        <div class="nt-filter-presets" role="group" aria-label="${text("Time range", "期間")}">
          <button type="button" class="secondary" onclick="setNativeTimelineRange('all')">${text("All", "全件")}</button>
          <button type="button" class="secondary" onclick="setNativeTimelineRange('7d')">${text("7d", "過去7日")}</button>
          <button type="button" class="secondary" onclick="setNativeTimelineRange('30d')">${text("30d", "過去30日")}</button>
          <button type="button" class="secondary" onclick="setNativeTimelineRange('custom')">${text("Custom", "期間を指定")}</button>
        </div>
        <details id="nt-advanced" class="drawer-disclosure"${_ntAdvancedOpen ? " open" : ""}>
          <summary>${text("Detailed filters", "詳細フィルタ")}</summary>
          <p>${text("Use ISO datetimes with an explicit offset or Z. Filters are applied by the history API.", "日時はオフセットまたはZ付きのISO形式で入力します。絞り込みは履歴APIが行います。")}</p>
          <div class="nt-advanced-fields">
            <label for="nt-filter-since">${text("Since", "開始日時")}</label><input id="nt-filter-since" type="text" placeholder="2026-10-30T00:00:00+09:00" value="${escapeHtml(_ntFilters.since)}">
            <label for="nt-filter-until">${text("Until", "終了日時")}</label><input id="nt-filter-until" type="text" placeholder="2026-10-31T00:00:00+09:00" value="${escapeHtml(_ntFilters.until)}">
            <label for="nt-filter-event">${text("Event type", "イベント種別")}</label><select id="nt-filter-event">${eventOptions}</select>
            <label for="nt-filter-limit">${text("Limit", "表示上限")}</label><input id="nt-filter-limit" type="text" inputmode="numeric" value="${escapeHtml(_ntFilters.limit)}">
          </div>
        </details>
        <div class="actions"><button class="secondary" type="button" onclick="applyNativeTimelineFilters()">${text("Apply", "適用")}</button><button class="secondary" type="button" onclick="clearNativeTimelineFilters()">${text("Clear", "解除")}</button></div>
      </div>`;
    }

    function setNativeTimelineRange(range) {
      if (range === "custom") {
        _ntAdvancedOpen = true;
        const details = document.getElementById("nt-advanced");
        if (details) details.open = true;
        document.getElementById("nt-filter-since")?.focus();
        return;
      }
      const now = new Date();
      _ntFilters.since = range === "all" ? "" : new Date(now.getTime() - (range === "7d" ? 7 : 30) * 86400000).toISOString();
      _ntFilters.until = range === "all" ? "" : now.toISOString();
      for (const key of ["since", "until"]) {
        const field = document.getElementById("nt-filter-" + key);
        if (field) field.value = _ntFilters[key];
      }
      reloadNativeTimelinePanel();
    }

    function nativeTimelineLimitation(code) {
      const labels = {
        __proto__: null,
        no_native_history: ["No native history has been recorded.", "履歴記録がありません。"],
        event_limit_truncated: ["The event limit truncated the results.", "表示上限により履歴の一部を省略しています。"],
        malformed_events_excluded: ["Invalid events were excluded.", "無効なイベントを除外しています。"],
        history_diagnostics_present: ["History diagnostics require attention.", "確認が必要な履歴診断があります。"],
      };
      if (labels[code]) return nativeTimelineText(...labels[code]);
      if (/^(item|progress|ticket|time_entry)_history_incomplete$/.test(code))
        return nativeTimelineText("History is incomplete; earlier changes may be missing.", "履歴は不完全です。過去の変更が含まれない場合があります。");
      return String(code);
    }

    function renderNativeTimelinePanel(nativeTimeline) {
      let html = `<div class="drawer-section-title">${nativeTimelineText("Change history", "変更履歴")}</div>`;
      html += renderNativeTimelineFiltersHtml();
      if (!nativeTimeline) {
        html += `<div class="empty">${nativeTimelineText("Native Timeline unavailable for this item.", "このレコードの履歴は利用できません。IDの有無や接続を確認してください。")}</div>`;
        return html;
      }
      const complete = !!nativeTimeline.complete;
      const bounds = nativeTimeline.bounds || {};
      const limitations = nativeTimeline.limitations || [];
      const invalidEvents = nativeTimeline.invalid_events || [];
      const diagnostics = nativeTimeline.diagnostics || [];
      html += `<div><span class="nt-coverage ${complete ? "nt-coverage-complete" : "nt-coverage-partial"}">` +
        `${complete ? nativeTimelineText("Complete history", "完全な履歴") : nativeTimelineText("Partial / limited history", "確認可能な履歴は一部です")}</span></div>`;
      if (limitations.length || invalidEvents.length || diagnostics.length) {
        const parts = [];
        if (limitations.length) parts.push(limitations.map(nativeTimelineLimitation).join(" "));
        if (invalidEvents.length) parts.push(`${invalidEvents.length} ${nativeTimelineText("invalid event(s) excluded", "件の無効なイベントを除外")}`);
        if (diagnostics.length) parts.push(`${diagnostics.length} ${nativeTimelineText("diagnostic(s)", "件の診断")}`);
        html += `<div class="nt-limitations">⚠ ${escapeHtml(parts.join("; "))}.</div>`;
      }
      const events = (nativeTimeline.events || []).slice().reverse(); // newest first for scanning
      if (!events.length) {
        html += `<div class="empty">${nativeTimelineText("No native history events match these filters yet.", "表示条件に一致する履歴はありません。")}</div>`;
      } else {
        const trend = nativeTimelineProgressTrendHtml(events);
        if (trend) html += `<div class="note">${nativeTimelineText("Progress trend", "進捗の推移")} ${trend}</div>`;
        let currentDay = null;
        html += `<div class="nt-axis">`;
        for (const row of events) {
          const day = nativeTimelineDateKey(row.at);
          if (day !== currentDay) {
            if (currentDay !== null) html += `</div>`;
            currentDay = day;
            html += `<div class="nt-day-group"><div class="nt-day-heading">${escapeHtml(day)}</div>`;
          }
          html += nativeTimelineEventRowHtml(row);
        }
        html += `</div></div>`;
      }
      html += `<div class="note">${bounds.returned_events ?? 0}/${bounds.total_valid_events ?? 0} ${nativeTimelineText("event(s) returned", "件を表示")}` +
        `${bounds.truncated ? nativeTimelineText("; truncated", "（上限により省略）") : ""}.</div>`;
      html += `<details class="drawer-disclosure nt-evidence"><summary>${nativeTimelineText("History evidence and diagnostics", "履歴の範囲・診断・技術情報")}</summary>` +
        `<pre class="drawer-raw-pre">${escapeHtml(JSON.stringify({schema: nativeTimeline.schema, target_id: nativeTimeline.target_id, source: nativeTimeline.source, git_composed: nativeTimeline.git_composed, completeness: nativeTimeline.completeness, bounds, limitations, invalid_events: invalidEvents, diagnostics}, null, 2))}</pre></details>`;
      return html;
    }

    async function reloadNativeTimelinePanel() {
      const container = document.getElementById("drawer-native-timeline");
      const itemId = _ntCurrentItemId;
      if (!container || !itemId) return;
      _ntAdvancedOpen = document.getElementById("nt-advanced")?.open ?? _ntAdvancedOpen;
      for (const key of ["since", "until", "event", "limit"]) {
        const field = document.getElementById("nt-filter-" + key);
        if (field) _ntFilters[key] = field.value.trim();
      }
      const token = ++_ntRequestToken;
      const current = () => token === _ntRequestToken && _ntCurrentItemId === itemId &&
        document.getElementById("drawer-native-timeline") === container && _drawerIdFor(drawerItem) === itemId && !drawerEditing;
      const params = new URLSearchParams();
      for (const key of ["since", "until", "event", "limit"]) if (_ntFilters[key]) params.set(key, _ntFilters[key]);
      const filters = renderNativeTimelineFiltersHtml();
      container.innerHTML = filters + `<div class="empty" role="status">${nativeTimelineText("Loading…", "読込中…")}</div>`;
      try {
        const query = params.toString();
        const data = await api(`/api/native-timeline/${encodeURIComponent(itemId)}${query ? "?" + query : ""}`);
        if (current()) container.innerHTML = renderNativeTimelinePanel(data);
      } catch(e) {
        if (current()) container.innerHTML = filters + `<div class="diagnostic" role="alert">${nativeTimelineText("Timeline error", "履歴を取得できませんでした")}: ${escapeHtml(e.message)}</div>`;
      }
    }

    function applyNativeTimelineFilters() { reloadNativeTimelinePanel(); }

    function clearNativeTimelineFilters() {
      _ntFilters = { since: "", until: "", event: "", limit: "" };
      ["nt-filter-since", "nt-filter-until", "nt-filter-event", "nt-filter-limit"].forEach(id => {
        const field = document.getElementById(id);
        if (field) field.value = "";
      });
      reloadNativeTimelinePanel();
    }

    function switchDrawerTab(name) {
      const allowed = new Set(["overview", "timeline", "relations"]);
      const selected = allowed.has(name) ? name : "overview";
      document.querySelectorAll("#drawer-body .drawer-tab").forEach(button => {
        const active = button.getAttribute("aria-controls") === "drawer-tab-" + selected;
        button.classList.toggle("active", active);
        button.setAttribute("aria-selected", active ? "true" : "false");
      });
      document.querySelectorAll("#drawer-body .drawer-tab-panel").forEach(panel => {
        panel.hidden = panel.id !== "drawer-tab-" + selected;
      });
      if (selected === "timeline" && _ntCurrentItemId) reloadNativeTimelinePanel();
    }

    function drawerRelationLabel(relation, incoming = false) {
      const labels = {
        parent: incoming ? ["Child", "子"] : ["Parent", "親"],
        depends_on: incoming ? ["Waiting on this item", "この項目を待っている"] : ["Waiting on", "待っている項目"],
        blocks: incoming ? ["Blocked by", "妨げている項目"] : ["Blocks", "この項目が妨げている"],
        ref: incoming ? ["Referenced by", "参照元"] : ["References", "参照先"],
        related: ["Related", "関連"],
        follows: incoming ? ["Next", "後続"] : ["Previous", "先行"],
        realizes: incoming ? ["Realized by", "実現した記録"] : ["Realizes", "実現元の計画"],
        replaced_by: incoming ? ["Replaces", "置き換え元"] : ["Replaced by", "置き換え先"],
        duplicate_of: incoming ? ["Duplicates", "重複している記録"] : ["Duplicate of", "重複元"],
      };
      return Object.hasOwn(labels, relation) ? drawerText(...labels[relation]) : relation;
    }

    function drawerRelationRow(label, id, row = {}, resolution = "ok", raw = "") {
      const status = row.status || "";
      const kind = row.kind || "";
      const title = row.title || id || drawerText("Unknown record", "不明な記録");
      const state = resolution === "ok" ? "" :
        `<span class="dep-missing">${escapeHtml(drawerText("Unresolved reference", "参照先を特定できません"))} (${escapeHtml(resolution)})</span>`;
      return `<li class="drawer-relation-row"><span class="dep-rel">${escapeHtml(label)}</span>` +
        `<div class="drawer-relation-target">` +
        (status ? `<span class="status-badge">${escapeHtml(t(STATUS_LABEL[status] || status))}</span>` : "") +
        (kind ? `<span class="type-badge">${escapeHtml(kind)}</span>` : "") +
        (id && resolution === "ok"
          ? `<button type="button" class="drawer-link secondary" data-relation-id="${escapeHtml(id)}" onclick="drawerNavigate(${escapeHtml(jsLiteral(id))})">${escapeHtml(title)}</button>`
          : `<span>${escapeHtml(title)}</span>`) + state +
        (raw ? `<small class="note">${escapeHtml(raw)}</small>` : "") + `</div></li>`;
    }

    function renderDrawerRelations(itemId, links, thread, linksError = "", threadError = "") {
      const error = text => `<p role="alert">${escapeHtml(text)}</p>`;
      let html = `<div class="drawer-section-title">${drawerText("Explicit links", "明示された関係")}</div>` +
        `<p class="note">${drawerText("Direction and labels are relative to this record. Opening a link shows a different record.", "種類と方向は現在のレコードを基準に表示します。リンクを開くと別のレコードに移動します。")}</p>`;
      if (linksError) html += error(drawerText("Could not load links: ", "関係を取得できません: ") + linksError);
      else {
        const records = links?.records || [];
        html += `<ul class="drawer-relations-list">`;
        for (const r of records) {
          const incoming = r.source_id !== itemId;
          const prefix = incoming ? "source" : "target";
          const label = (incoming ? "← " : "→ ") + drawerRelationLabel(r.relation, incoming);
          html += drawerRelationRow(label, r[prefix + "_id"], {
            title:r[prefix + "_title"], status:r[prefix + "_status"], kind:r[prefix + "_type"],
          }, r.status || "ok", r.relation);
        }
        html += `</ul>`;
        if (!records.length) html += `<p class="empty">${drawerText("No explicit links.", "明示された関係はありません。")}</p>`;
        if (records.length) html += `<details class="drawer-disclosure" ontoggle="loadDrawerRelationGraph(this)"><summary>${drawerText("Show graph", "グラフを表示")}</summary><div class="drawer-relation-graph"></div></details>`;
      }
      html += `<div class="drawer-section-title">${drawerText("Lifecycle thread", "前後・実現・置き換えのつながり")}</div>`;
      if (threadError) return html + error(drawerText("Could not load temporal context: ", "前後のつながり・日付候補を取得できません: ") + threadError);
      let count = 0;
      html += `<ul class="drawer-relations-list">`;
      for (const [key, en, ja] of [
        ["predecessors", "Previous", "先行"], ["successors", "Next", "後続"],
        ["realized_plans", "Realizes", "実現元の計画"], ["realized_by", "Realized by", "実現した記録"],
        ["replacement_predecessors", "Replaces", "置き換え元"], ["replacement_successors", "Replaced by", "置き換え先"],
      ]) for (const row of thread?.relations?.[key] || []) {
        html += drawerRelationRow(drawerText(en, ja), row.id, row); count++;
      }
      html += `</ul>`;
      if (!count) html += `<p class="empty">${drawerText("No explicit lifecycle relations.", "前後・実現・置き換えの明示関係はありません。")}</p>`;
      if (thread?.explicit?.truncated) html += `<p class="note">${drawerText("Only part of the explicit thread is shown (API bounds).", "取得上限により、明示されたつながりは一部のみ表示しています。")}</p>`;
      const consistencyWarnings = thread?.consistency?.warnings || [];
      if (consistencyWarnings.length || thread?.consistency?.truncated) html += `<details class="drawer-disclosure"><summary>${drawerText("Date consistency warnings", "日付の整合性に関する警告")} (${consistencyWarnings.length})</summary>` +
        `<p>${drawerText("Explicit order and recorded dates may disagree. No relation has been changed.", "明示された順序と記録の日付が矛盾している可能性があります。関係は変更していません。")}</p>` +
        `<pre class="drawer-raw-pre">${escapeHtml(JSON.stringify(thread.consistency, null, 2))}</pre></details>`;
      const nearby = thread?.derived?.related || [];
      html += `<div class="drawer-section-title">${drawerText("Nearby dates (derived)", "日付が近い候補（導出）")} (${nearby.length})</div>` +
        `<p class="note">${drawerText("Read-only suggestions within the API window and limit, not stored links or a complete list of related records.", "APIの期間・取得上限内で日付から導いた閲覧用候補です。保存された関係や、関連記録の全件一覧ではありません。")}</p><ul class="drawer-relations-list">`;
      for (const row of nearby) {
        const labels = {same_day:["Same day", "同日"], before:["Before", "前の日付"], after:["After", "後の日付"]};
        const label = Object.hasOwn(labels, row.relation) ? drawerText(...labels[row.relation]) : row.relation;
        html += drawerRelationRow(label, row.target_id, row.target, "ok", `${row.source_field || ""} → ${row.target_field || ""} · ${row.days ?? ""}`);
      }
      html += `</ul>`;
      if (!nearby.length) html += `<p class="empty">${drawerText("No nearby date candidates in this range.", "この範囲に日付が近い候補はありません。")}</p>`;
      return html;
    }

    async function loadDrawerRelationGraph(disclosure) {
      if (!disclosure.open || disclosure.dataset.loaded) return;
      disclosure.dataset.loaded = "true";
      const container = document.getElementById("drawer-deps");
      const binding = container?._relationGraph;
      const panel = disclosure.querySelector(".drawer-relation-graph");
      if (!binding || !panel) return;
      panel.textContent = drawerText("Loading…", "読み込み中…");
      try {
        const graph = await api(`/api/graph?root=${encodeURIComponent(binding.id)}&depth=2`);
        if (document.getElementById("drawer-deps") !== container || !panel.isConnected) return;
        binding.graph = graph;
        panel.innerHTML = renderDependencyMiniGraph(binding.records, binding.id, graph);
      } catch(e) {
        if (!panel.isConnected) return;
        panel.textContent = drawerText("Graph unavailable: ", "グラフを取得できません: ") + e.message;
        delete disclosure.dataset.loaded;
      }
    }

    async function loadDependencyLinks(item) {
      const itemId = _drawerIdFor(item);
      const container = document.getElementById("drawer-deps");
      if (!container) return;
      container.dataset.noI18n = "";
      if (!itemId) {
        container.textContent = drawerText("No ID — links cannot be looked up.", "IDがないため関係を取得できません。");
        return;
      }
      const results = await Promise.allSettled([
        api(`/api/links?id=${encodeURIComponent(itemId)}&direction=both`),
        api(`/api/temporal-thread/${encodeURIComponent(itemId)}`),
      ]);
      if (document.getElementById("drawer-deps") !== container || drawerItem !== item || drawerEditing) return;
      const [links, thread] = results.map(r => r.status === "fulfilled" ? r.value : null);
      const errors = results.map(r => r.status === "rejected" ? String(r.reason?.message || r.reason) : "");
      container._relationGraph = {id:itemId, records:links?.records || []};
      container.innerHTML = renderDrawerRelations(itemId, links, thread, ...errors);
    }

    async function loadDrawerMessageThread(item) {
      const container = document.getElementById("drawer-thread");
      if (!container) return;
      const idKey = appConfig?.ids?.key || "id";
      const itemId = item?.id || item?.details?.[idKey]?.[0];
      if (!itemId) return;
      try {
        const data = await api(`/api/messages/thread/${encodeURIComponent(itemId)}`);
        const rows = data.items || [];
        if (!rows.length) {
          container.innerHTML = `<div class="drawer-section-title">Message Thread</div><div class="empty">No related messages.</div>`;
          return;
        }
        let html = `<div class="drawer-section-title">Message Thread (${rows.length})</div><div class="message-thread">`;
        for (const row of rows) {
          const rowId = row?.id || row?.details?.[idKey]?.[0] || "";
          const current = rowId === itemId ? " current" : "";
          const sender = row?.details?.sender?.[0] || "";
          const recipients = (row?.details?.recipient || []).join(", ");
          const when = row?.details?.notify_at?.[0] || row?.details?.created?.[0] || "";
          const nav = escapeHtml(jsLiteral(rowId));
          const actions = rowId
            ? `<div class="actions" style="margin-top:.3rem;gap:.25rem"><button class="secondary" type="button" onclick="drawerNavigate(${nav})">Open</button><button class="secondary" type="button" onclick="ackMessage(${nav})">Ack</button></div>`
