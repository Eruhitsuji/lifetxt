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
      if (drawerItem) loadDependencyLinks(drawerItem);
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

    async function loadDependencyLinks(item) {
      const idKey = appConfig?.ids?.key || "id";
      const itemId = item?.id || (item?.details?.[idKey]?.[0]);
      const container = document.getElementById("drawer-deps");
      if (!container) return;
      if (!itemId) {
        container.innerHTML = `<div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty">No ID — cannot look up links.</div>`;
        return;
      }
      try {
        const data = await api(`/api/links?id=${encodeURIComponent(itemId)}&direction=both`);
        const records = data.records || [];
        let graphData = null;
        try {
          graphData = await api(`/api/graph?root=${encodeURIComponent(itemId)}&depth=2`);
        } catch(_) {}
        if (!records.length) {
          container.innerHTML = `<div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty">No links.</div>`;
          return;
        }
        const outgoing = records.filter(r => r.source_id === itemId);
        const incoming = records.filter(r => r.target_id === itemId && r.source_id !== itemId);
        let html = `<div class="drawer-section-title">Dependencies &amp; Links (${records.length})</div>` +
          renderDependencyMiniGraph(records, itemId, graphData) +
          `<div class="dep-graph">`;

        function depRow(arrow, arrowCls, relLabel, otherId, otherTitle, otherStatus, otherType) {
          const statusIcon = STATUS_ICON[otherStatus] || "·";
          const statusCls = STATUS_CLASS[otherStatus] || "status-note";
          const typeCls = "type-" + (otherType || "N");
          const nav = escapeHtml(jsLiteral(otherId || ""));
          return `<div class="dep-row">
            <span class="dep-arrow ${arrowCls}">${arrow}</span>
            <span class="status-badge ${statusCls}" style="font-size:.7rem;padding:.1rem .35rem">${escapeHtml(statusIcon)}</span>
            <span class="type-badge ${typeCls}" style="font-size:.7rem;padding:.1rem .35rem">${escapeHtml(otherType || "?")}</span>
            <span class="dep-rel">${escapeHtml(relLabel)}</span>
            ${otherId
              ? `<a class="drawer-link" onclick="drawerNavigate(${nav})">${escapeHtml(otherTitle || otherId)}</a>`
              : `<span class="dep-missing">${escapeHtml(otherTitle || otherId || "?")}</span>`}
          </div>`;
        }

        if (outgoing.length) {
          html += `<div class="dep-group-label">This item →</div>`;
          for (const r of outgoing) {
            const lbl = DEP_RELATION_LABEL[r.relation] || r.relation;
            html += depRow("→", "dep-out", lbl, r.target_id, r.target_title, r.target_status, r.target_type);
          }
        }
        if (incoming.length) {
          html += `<div class="dep-group-label" style="margin-top:.5rem">← This item</div>`;
          for (const r of incoming) {
            const lbl = DEP_RELATION_LABEL[r.relation] || r.relation;
            html += depRow("←", "dep-in", lbl, r.source_id, r.source_title, r.source_status, r.source_type);
          }
        }
        html += `</div>`;
        container.innerHTML = html;
      } catch(e) {
        if (container) container.innerHTML = `<div class="drawer-section-title">Dependencies &amp; Links</div><div class="empty">Error: ${escapeHtml(e.message)}</div>`;
      }
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
