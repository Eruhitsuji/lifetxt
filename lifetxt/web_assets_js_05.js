        if (replacement !== trimmed) {
          // Keep the original surrounding whitespace so layout does not shift.
          textNode.nodeValue = raw.replace(trimmed, replacement);
        }
      }

      const scope = root.querySelectorAll ? root : document;
      for (const name of I18N_ATTRIBUTES) {
        scope.querySelectorAll("[" + name + "]").forEach(el => {
          if (el.closest("[data-no-i18n]")) return;
          const value = el.getAttribute(name);
          const trimmed = String(value || "").trim();
          const replacement = translateString(trimmed, dict);
          if (replacement !== trimmed) {
            if (!el.hasAttribute("data-i18n-" + name)) {
              el.setAttribute("data-i18n-" + name, trimmed);
            }
            el.setAttribute(name, replacement);
          }
        });
      }
    }

    function applyLanguage() {
      const lang = currentLanguage();
      document.documentElement.setAttribute("lang", lang || "en");
      if (!i18nDictionary()) return;
      _i18nApplying = true;
      try {
        translateTree(document.body);
      } finally {
        _i18nApplying = false;
      }
    }

    // Views re-render constantly. Observing the document keeps every rendered
    // view translated without having to remember a call at each render site.
    function startLanguageObserver() {
      if (!i18nDictionary() || typeof MutationObserver === "undefined") return;
      let scheduled = false;
      const observer = new MutationObserver(() => {
        if (_i18nApplying || scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => {
          scheduled = false;
          applyLanguage();
        });
      });
      // Views render asynchronously and set title/placeholder text as they go,
      // so attribute changes need watching too, not just inserted nodes.
      observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
        attributeFilter: I18N_ATTRIBUTES,
      });
    }

    function configuredDashboardCards() {
      const raw = appConfig?.web?.dashboard?.cards;
      const list = Array.isArray(raw)
        ? raw.map(String)
        : String(raw || "").split(",").map(part => part.trim());
      const cards = list.filter(card => DASHBOARD_CARDS.includes(card));
      return cards.length ? cards : DASHBOARD_CARDS.slice();
    }
    function applyConfiguredDashboard() {
      const grid = document.getElementById("dash-grid");
      if (!grid) return;
      const configured = configuredDashboardCards();
      const enabled = new Set(configured);
      const byName = {};
      grid.querySelectorAll("[data-dashboard-card]").forEach(card => {
        byName[card.dataset.dashboardCard] = card;
        card.classList.toggle("card-hidden", !enabled.has(card.dataset.dashboardCard));
      });
      for (const name of configured) {
        if (byName[name]) grid.appendChild(byName[name]);
      }
    }
    function dashboardLimit(cardName, fallback) {
      const raw = appConfig?.web?.dashboard?.limits?.[cardName];
      const n = Number(raw);
      return Number.isFinite(n) && n > 0 ? n : fallback;
    }
    function detailText(details) {
      return Object.entries(details || {}).flatMap(([key, values]) =>
        values.map(value => `${key}:${value}`)
      ).join(" ");
    }
    function itemStableKey(item) {
      const idKey = appConfig?.ids?.key || "id";
      return String(item?.id || item?.details?.[idKey]?.[0] || `${item?.source || ""}:${item?.line || ""}:${item?.title || ""}`);
    }
    function itemFingerprint(item) {
      return JSON.stringify({
        status: item?.status || "",
        type: item?.type || "",
        title: item?.title || "",
        details: item?.details || {},
        raw: item?.raw || "",
      });
    }
    function detailsToText(details) {
      const lines = [];
      for (const [key, values] of Object.entries(details || {})) {
        for (const value of values) {
          const text = String(value);
          if (key === "body" && text.includes("\n")) {
            const parts = text.split(/\n/);
            lines.push(`${key}:${parts.shift() || ""}`);
            for (const part of parts) lines.push(part ? `| ${part}` : "|");
          } else {
            lines.push(`${key}:${text}`);
          }
        }
      }
      return lines.join("\n");
    }
    function parseDetails(text) {
      const details = {};
      for (const line of text.split(/\n/)) {
        if (line.startsWith("|")) {
          if (!details.body || !details.body.length) details.body = [""];
          const value = line.startsWith("| ") ? line.slice(2) : line.slice(1);
          details.body[0] += `${details.body[0] ? "\n" : ""}${value}`;
          continue;
        }
        const trimmed = line.trim();
        if (!trimmed) continue;
        const colon = trimmed.indexOf(":");
        const equal = trimmed.indexOf("=");
        let index = -1;
        if (colon >= 0 && equal >= 0) index = Math.min(colon, equal);
        else index = Math.max(colon, equal);
        if (index <= 0) continue;
        const key = trimmed.slice(0, index).trim();
        const value = trimmed.slice(index + 1).trim();
        (details[key] ||= []).push(value);
      }
      return details;
    }
    function query() {
      return new URLSearchParams(window.location.search);
    }
    function firstParam(params, names, fallback = "") {
      for (const name of names) {
        const value = params.get(name);
        if (value !== null && value !== "") return value;
      }
      return fallback;
    }
    function boolParam(params, names) {
      const value = firstParam(params, names, "");
      return ["1", "true", "yes", "on", "open"].includes(value.toLowerCase());
    }
    function parseKioskFilter(value) {
      const result = {};
      if (!value) return result;
      const aliases = {type: "kind", q: "text", open: "open_only"};
      for (const part of String(value).split(/[;,]/)) {
        const trimmed = part.trim();
        if (!trimmed) continue;
        const idx = Math.max(trimmed.indexOf(":"), trimmed.indexOf("="));
        if (idx <= 0) continue;
        const rawKey = trimmed.slice(0, idx).trim();
        const key = aliases[rawKey] || rawKey;
        const val = trimmed.slice(idx + 1).trim();
        if (key && val) result[key] = val;
      }
      return result;
    }
    function applyKioskFilterParams(result, params) {
      if (!isKioskMode()) return;
      const filter = parseKioskFilter(firstParam(params, ["kiosk_filter"], ""));
      for (const [key, value] of Object.entries(filter)) {
        if (key === "open_only") {
          if (["1", "true", "yes", "on", "open"].includes(value.toLowerCase())) result.set("open_only", "true");
          continue;
        }
        if (!result.has(key)) result.set(key, value);
      }
    }
    // ── Single-content page router ─────────────────────────────────
    // Each view owns the whole screen: exactly one page section is shown.
    const PAGE_VIEWS = ["dashboard", "today", "agenda", "timeline", "calendar", "focus", "review", "messages", "team", "status", "notifications", "stats", "graph"];
    const VIEW_PAGE = {
      "": "items", "messages": "items", "kiosk": "items", "display": "items",
      "dashboard": "dashboard", "today": "today", "agenda": "agenda", "timeline": "timeline",
      "calendar": "calendar", "focus": "focus", "review": "review", "team": "team",
      "status": "status", "notifications": "notifications",
      "stats": "stats", "graph": "graph",
    };
    const VIEW_META = {
      "": {
        label: "Items",
        description: "Search, filter, edit, and bulk-manage life.txt records.",
        actions: [["New record", "newItem"], ["Quick add", "quickAdd"], ["Set status", "setStatus"], ["End status", "endStatus"], ["Clear filters", "clearFilters"]],
      },