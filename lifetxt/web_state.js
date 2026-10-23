(() => {
  "use strict";
  const states = ["available", "busy", "focus", "meeting", "away", "offline", "commuting", "working", "sleeping"];
  const icons = ["○", "−", "◈", "◉", "↗", "◌", "⇄", "▣", "☾"];
  const classes = ["p-available", "p-busy", "p-focus", "p-busy", "p-away", "p-off", "p-away", "p-busy", "p-off"];
  const allowedClasses = new Set(["p-available", "p-busy", "p-focus", "p-away", "p-off", "p-unknown"]);
  const copy = {
    en: {
      skip: "Skip to your status", language: "Language", theme: "Theme", system: "System", light: "Light", dark: "Dark",
      eyebrow: "A little signal to the world", heading: "Your status", self: "Just you", current: "Current status", confirmed: "Last confirmed status",
      loading: "Loading…", since: "Since", elapsed: "Elapsed", syncing: "Syncing…", refresh: "Refresh", synced: "Up to date", offlineNetwork: "Device is offline. Showing the last confirmed status.",
      choose: "Change your status", oneTap: "One tap to save", more: "More statuses", custom: "Custom…", details: "Add an activity or note", state: "Status", customState: "Custom status",
      customHelp: "The canonical value is saved without translation (leading/trailing spaces are trimmed).", activity: "Activity / title (optional)", note: "Note (optional)", force: "Restart even if this status is already current",
      noopHelp: "Repeating the current status keeps its start, title and note. Choose restart to record changes to that same status.", save: "Save status", endHeading: "Finished for now?", endHelp: "Ending closes your current status. Choosing Offline starts an offline status instead.", end: "End current status", web: "Open full Web UI",
      currentMarker: "✓ Current", unset: "No current status", never: "No status has been recorded yet.", ended: "Previous status ended", unknown: "Unavailable", readonly: "This workspace is read-only. Status changes are disabled.",
      noTarget: "No writable target is configured. Status changes are disabled.", unavailable: "Changes are disabled until the latest status is confirmed.", auth: "Authentication required. Open this page through your existing authenticated Web connection.", forbidden: "Changes are not permitted. Check read-only mode and your access.", conflict: "Data changed. Refresh to review the latest status; your inputs will be kept. Nothing is retried automatically.",
      invalid: "The status could not be accepted. Check your input and the life.txt diagnostics.", network: "Connection failed. The result may be unknown; refresh before trying again.", server: "The server could not confirm the update. Refresh before trying again.", loadFailed: "Could not refresh. The previous confirmed display and your inputs are kept.",
      saving: "Saving…", saved: "Status saved.", noChange: "This status is already current. Its start, title and note were kept.", endedSaved: "Current status ended.", savedUnconfirmed: "Save acknowledged, but the current display could not be refreshed. Refresh before making another change.", reviewed: "Latest status confirmed. Your inputs are kept; review before saving.", required: "Enter a custom status.", missingRevision: "No write revision is available. Refresh before changing status.",
      names: ["Available", "Busy", "Focus", "Meeting", "Away", "Offline", "Commuting", "Working", "Sleeping"], hours: "h", minutes: "min", lessMinute: "Less than a minute",
    },
    ja: {
      skip: "現在の状態へ移動", language: "言語", theme: "テーマ", system: "自動", light: "ライト", dark: "ダーク",
      eyebrow: "いまの自分を、ひと目で", heading: "あなたの状態", self: "自分", current: "現在の状態", confirmed: "最後に確認した状態",
      loading: "読み込み中…", since: "開始時刻", elapsed: "経過時間", syncing: "同期中…", refresh: "再読込", synced: "最新の状態です", offlineNetwork: "端末はネットワーク未接続です。最後に確認した状態を表示しています。",
      choose: "状態を切り替える", oneTap: "タップですぐ保存", more: "その他の状態", custom: "カスタム…", details: "活動名・メモを添える", state: "状態", customState: "カスタム状態",
      customHelp: "入力値は翻訳せず保存します（前後の空白は除きます）。", activity: "活動名・タイトル（任意）", note: "メモ（任意）", force: "同じ状態でも再開始する",
      noopHelp: "同じ状態を選ぶと、開始時刻・タイトル・メモを維持します。同じ状態の内容を変えるには再開始を選んでください。", save: "状態を保存", endHeading: "いったん終了しますか？", endHelp: "終了は現在の状態を閉じます。「オフライン」を選ぶと、オフラインの状態を新しく開始します。", end: "現在の状態を終了", web: "Web UI全体を開く",
      currentMarker: "✓ 現在", unset: "現在設定なし", never: "まだ状態が記録されていません。", ended: "前の状態は終了済み", unknown: "取得できません", readonly: "このworkspaceは読み取り専用です。状態は変更できません。",
      noTarget: "書き込み先が未設定のため、状態を変更できません。", unavailable: "最新の状態を確認するまで変更できません。", auth: "認証が必要です。既存の認証済みWeb接続から開いてください。", forbidden: "変更が許可されていません。読み取り専用設定とアクセス権を確認してください。", conflict: "データが更新されています。再読込で最新状態を確認してください。入力は保持し、自動再試行はしません。",
      invalid: "状態を保存できませんでした。入力とlife.txtの診断を確認してください。", network: "接続できませんでした。保存結果が未確定の場合があります。再操作の前に再読込してください。", server: "サーバーが更新を確認できませんでした。再操作の前に再読込してください。", loadFailed: "再取得できませんでした。前回確認した表示と入力を保持しています。",
      saving: "保存中…", saved: "状態を保存しました。", noChange: "すでに同じ状態です。開始時刻・タイトル・メモは維持しました。", endedSaved: "現在の状態を終了しました。", savedUnconfirmed: "保存応答は受け取りましたが、表示を再取得できませんでした。次の変更の前に再読込してください。", reviewed: "最新の状態を確認しました。入力は保持しています。内容を確認してから保存してください。", required: "カスタム状態を入力してください。", missingRevision: "更新用revisionを取得できません。再読込してから操作してください。",
      names: ["対応可能", "取り込み中", "集中", "会議中", "離席中", "オフライン", "移動中", "作業中", "睡眠中"], hours: "時間", minutes: "分", lessMinute: "1分未満",
    },
  };
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  let lang = ["en", "ja"].includes(params.get("lang")) ? params.get("lang") : ((navigator.language || "en").startsWith("ja") ? "ja" : "en");
  let languageChosen = params.has("lang"), config = {}, current = null, previous = null;
  let loaded = false, writable = false, writeReason = "readonly", stale = true, pending = false, reading = false;
  let revision = null, formRevision = null, formTouched = false, generation = 0, readController = null;
  let zone = "", serverClock = null, syncKey = "syncing", feedbackKey = "", feedbackError = false;
  const t = key => copy[lang][key];
  const label = state => {
    const index = states.indexOf(state);
    return index >= 0 ? copy[lang].names[index] : String(state || "—");
  };
  function stateClass(state) {
    const value = String(state || "").trim().toLowerCase();
    const override = config.web?.presence?.[value];
    if (allowedClasses.has(override)) return override;
    const index = states.indexOf(value);
    return index >= 0 ? classes[index] : "p-unknown";
  }
  function errorKey(error) {
    if (error.status === 401) return "auth";
    if (error.status === 403) return "forbidden";
    if ([409, 428].includes(error.status)) return "conflict";
    if ([400, 422].includes(error.status)) return "invalid";
    return error.status ? "server" : "network";
  }
  function feedback(key, error = false) {
    feedbackKey = key; feedbackError = error;
    $("feedback").textContent = key ? t(key) : "";
    $("feedback").dataset.error = String(error);
  }
  function updateControls() {
    const disabled = !loaded || !writable || stale || pending || reading || navigator.onLine === false || !revision;
    document.querySelectorAll(".tile").forEach(button => { button.disabled = disabled; });
    $("detail-fields").disabled = disabled;
    $("end").disabled = disabled || !current;
    $("refresh").disabled = pending || reading;
    $("current-card").setAttribute("aria-busy", String(pending || reading));
    const access = !writable && loaded ? writeReason : (disabled && !pending && !reading ? "unavailable" : "");
    $("write-access").hidden = !access;
    $("write-access").textContent = access ? t(access) : "";
  }
  function translate() {
    document.documentElement.lang = lang;
    document.title = (lang === "ja" ? "あなたの状態" : "Your status") + " · life.txt";
    $("language").value = lang;
    document.querySelectorAll("[data-i18n]").forEach(node => { node.textContent = t(node.dataset.i18n); });
    document.querySelectorAll(".tile").forEach(button => {
      button.querySelector(".tile-label").textContent = label(button.dataset.state);
    });
    Array.from($("form-state").options).forEach(option => { option.textContent = option.value === "__custom" ? t("custom") : label(option.value); });
    feedback(feedbackKey, feedbackError);
    renderCurrent(); updateControls();
  }
  function buildChoices() {
    states.forEach((state, index) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "tile " + classes[index]; button.dataset.state = state;
      button.setAttribute("aria-pressed", "false"); button.disabled = true;
      const symbol = document.createElement("span"); symbol.className = "symbol"; symbol.textContent = icons[index]; symbol.setAttribute("aria-hidden", "true");
      const text = document.createElement("span"); text.className = "tile-label"; text.textContent = label(state);
      const marker = document.createElement("span"); marker.className = "marker";
      button.append(symbol, text, marker); button.addEventListener("click", () => send({state}));
      $(index < 6 ? "primary-states" : "extra-states").append(button);
      const option = document.createElement("option"); option.value = state; option.textContent = label(state); $("form-state").append(option);
    });
    const custom = document.createElement("option"); custom.value = "__custom"; custom.textContent = t("custom"); $("form-state").append(custom);
  }
  function syncCustomField() {
    const custom = $("form-state").value === "__custom";
    $("custom-row").hidden = !custom; $("custom-state").required = custom;
  }
  function initializeForm() {
    if (formTouched) return;
    const value = current?.state || "available";
    $("form-state").value = states.includes(value) ? value : "__custom";
    $("custom-state").value = states.includes(value) ? "" : value;
    $("activity-input").value = current?.title || "";
    $("note-input").value = Array.isArray(current?.details?.note) ? current.details.note.join("\n") : "";
    formRevision = revision; syncCustomField();
  }
  // Naive Status timestamps belong to the server's workspace zone, not this
  // browser's zone. Ambiguous DST folds/gaps deliberately have no elapsed value.
  function timestamp(value, timeZone) {
    if (typeof value !== "string") return null;
    if (/(Z|[+-]\d\d:\d\d)$/.test(value)) {
      const parsed = Date.parse(value); return Number.isFinite(parsed) ? parsed : null;
    }
    const match = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)(?::(\d\d))?$/.exec(value);
    if (!match || !timeZone) return null;
    const parts = match.slice(1).map(Number), wall = Date.UTC(parts[0], parts[1] - 1, parts[2], parts[3], parts[4], parts[5] || 0);
    const check = new Date(wall);
    if (check.getUTCFullYear() !== parts[0] || check.getUTCMonth() + 1 !== parts[1] || check.getUTCDate() !== parts[2] || check.getUTCHours() !== parts[3] || check.getUTCMinutes() !== parts[4] || check.getUTCSeconds() !== (parts[5] || 0)) return null;
    try {
      const format = new Intl.DateTimeFormat("en-GB", {timeZone, year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit", second:"2-digit", hourCycle:"h23"});
      const zonedWall = instant => {
        const p = Object.fromEntries(format.formatToParts(new Date(instant)).map(item => [item.type, item.value]));
        return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
      };
      const candidates = new Set();
      for (const delta of [-36, 0, 36]) {
        const probe = wall + delta * 3600000, candidate = wall - (zonedWall(probe) - probe);
        if (zonedWall(candidate) === wall) candidates.add(candidate);
      }
      return candidates.size === 1 ? [...candidates][0] : null;
    } catch (_) { return null; }
  }
  function elapsed() {
    const started = timestamp(current?.from, zone);
    if (started === null || !serverClock) return t("unknown");
    const minutes = Math.floor((serverClock.instant + performance.now() - serverClock.anchor - started) / 60000);
    if (minutes < 0) return t("unknown");
    if (!minutes) return t("lessMinute");
    return (minutes >= 60 ? Math.floor(minutes / 60) + " " + t("hours") + " " : "") + (minutes % 60) + " " + t("minutes");
  }
  function renderCurrent() {
    $("current-caption").textContent = t(stale && loaded ? "confirmed" : "current");
    $("current-card").className = "current-card " + (current ? stateClass(current.state) : "p-unknown");
    $("current-state").textContent = loaded ? (current ? label(current.state) : t("unset")) : t(syncKey === "syncing" ? "loading" : "unknown");
    $("current-icon").textContent = current ? (icons[states.indexOf(current.state)] || "◇") : "◇";
    $("activity").textContent = current?.title || ""; $("activity").hidden = !current?.title;
    $("timing").hidden = !current;
    $("since").textContent = current ? (String(current.from || "").replace("T", " ") + (zone ? " · " + zone : "")) : "";
    $("since").dateTime = current?.from || "";
    $("elapsed").textContent = current ? elapsed() : "—";
    const note = Array.isArray(current?.details?.note) ? current.details.note.join("\n") : "";
    $("current-note").textContent = note; $("current-note").hidden = !note;
    $("previous").hidden = !loaded || Boolean(current);
    $("previous").textContent = previous ? t("ended") + ": " + label(previous.state) + (previous.to ? " · " + previous.to.replace("T", " ") : "") : t("never");
    $("sync").textContent = navigator.onLine === false ? t("offlineNetwork") : t(syncKey);
    document.querySelectorAll(".tile").forEach(button => {
      const selected = Boolean(current && current.state === button.dataset.state);
      button.className = "tile " + stateClass(button.dataset.state);
      button.setAttribute("aria-pressed", String(selected));
      button.querySelector(".marker").textContent = selected ? t("currentMarker") : "";
    });
  }
  function responseRevision(response) {
    return response.headers.get("ETag") || response.headers.get("X-Lifetxt-Revision") || null;
  }
  async function api(path, options = {}) {
    const response = await fetch(path, {credentials: "same-origin", cache: "no-store", ...options});
    if (!response.ok) { const error = Error("HTTP " + response.status); error.status = response.status; throw error; }
    return {data: await response.json(), revision: responseRevision(response), zone: response.headers.get("X-Lifetxt-Timezone") || ""};
  }
  async function refresh({manual = false, afterWrite = false} = {}) {
    if (pending && !afterWrite) return false;
    if (navigator.onLine === false) { syncKey = "network"; stale = true; renderCurrent(); updateControls(); return false; }
    readController?.abort();
    const controller = new AbortController(), ticket = ++generation;
    readController = controller; reading = true; syncKey = "syncing"; renderCurrent(); updateControls();
    const timer = setTimeout(() => controller.abort(), 15000);
    const clockStarted = performance.now();
    try {
      const options = {signal: controller.signal};
      const [settings, health, active, latest] = await Promise.all([
        api("/api/config", options), api("/api/health", options),
        api("/api/status?person=self&active=true", options), api("/api/status?person=self&active=false", options),
      ]);
      if (ticket !== generation) return false;
      if (!Array.isArray(active.data.records) || !Array.isArray(latest.data.records)) throw Error("Invalid status response");
      if (!active.revision || active.revision !== latest.revision) { const error = Error("Snapshot changed"); error.status = 409; throw error; }
      config = settings.data;
      if (!languageChosen && ["en", "ja"].includes(config.web?.language)) lang = config.web.language;
      zone = settings.zone || active.zone;
      const instant = Date.parse(config.current_datetime);
      serverClock = Number.isFinite(instant) ? {instant, anchor: clockStarted} : null;
      current = active.data.records.find(record => record && record.person === "self" && record.active === true && record.from && !record.to) || null;
      previous = latest.data.records.find(record => record && record.person === "self" && record.active === false) || null;
      revision = active.revision; loaded = true; stale = false;
      writable = health.data.read_only === false && Boolean(health.data.writable_path);
      writeReason = health.data.read_only ? "readonly" : "noTarget";
      syncKey = "synced"; initializeForm();
      if (manual) { formRevision = revision; feedback("reviewed"); }
      translate(); return true;
    } catch (error) {
      if (ticket !== generation) return false;
      stale = true; syncKey = error.status === 401 ? "auth" : (error.status === 403 ? "forbidden" : "loadFailed");
      if (error.status === 409) syncKey = "conflict";
      renderCurrent(); return false;
    } finally {
      clearTimeout(timer); controller.abort();
      if (ticket === generation) { reading = false; readController = null; updateControls(); }
    }
  }
  async function send(payload, expected = revision) {
    if (pending || reading || stale || !loaded || !writable || navigator.onLine === false) return;
    if (!expected) { feedback("missingRevision", true); return; }
    const focused = document.activeElement;
    pending = true; feedback("saving"); updateControls();
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 15000);
    try {
      const result = await api("/api/status", {method: "POST", signal: controller.signal, headers: {"Content-Type": "application/json", "If-Match": expected}, body: JSON.stringify(payload)});
      const confirmed = await refresh({afterWrite: true});
      feedback(confirmed ? (result.data.unchanged ? "noChange" : payload.end ? "endedSaved" : "saved") : "savedUnconfirmed", !confirmed);
      if (confirmed && formTouched && "title" in payload) formRevision = revision;
    } catch (error) {
      const key = errorKey(error);
      feedback(key, true);
      if (key !== "invalid") { stale = true; syncKey = key; renderCurrent(); }
    } finally {
      clearTimeout(timer); controller.abort(); pending = false; updateControls();
      if (focused && focused !== document.body && document.activeElement === document.body && document.visibilityState !== "hidden") {
        const blocked = focused.disabled || focused.closest?.("fieldset:disabled");
        (blocked ? $("refresh") : focused).focus();
      }
    }
  }
  function boot() {
    buildChoices();
    const theme = ["light", "dark"].includes(params.get("theme")) ? params.get("theme") : "auto";
    document.documentElement.dataset.theme = theme; $("theme").value = theme;
    $("language").addEventListener("change", () => { lang = $("language").value; languageChosen = true; translate(); const url = new URL(location.href); url.searchParams.set("lang", lang); history.replaceState(null, "", url); });
    $("theme").addEventListener("change", () => { document.documentElement.dataset.theme = $("theme").value; });
    $("refresh").addEventListener("click", () => refresh({manual: true}));
    $("end").addEventListener("click", () => send({end: true}));
    $("status-form").addEventListener("input", () => { if (!formTouched) formRevision = revision; formTouched = true; });
    $("form-state").addEventListener("change", () => { if (!formTouched) formRevision = revision; formTouched = true; syncCustomField(); });
    $("custom-open").addEventListener("click", () => { $("details").open = true; $("form-state").value = "__custom"; if (!formTouched) formRevision = revision; formTouched = true; syncCustomField(); $("custom-state").focus(); });
    $("status-form").addEventListener("submit", event => {
      event.preventDefault();
      const custom = $("form-state").value === "__custom", state = custom ? $("custom-state").value.trim() : $("form-state").value;
      if (!state) { feedback("required", true); $("custom-state").focus(); return; }
      const payload = {state, title: $("activity-input").value, note: $("note-input").value};
      if ($("force").checked) payload.force = true;
      send(payload, formRevision);
    });
    const resume = () => { if (document.visibilityState !== "hidden" && !pending) refresh(); };
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") { ++generation; readController?.abort(); readController = null; reading = false; stale = true; updateControls(); } else resume(); });
    window.addEventListener("pageshow", resume);
    window.addEventListener("focus", resume);
    window.addEventListener("online", resume);
    window.addEventListener("offline", () => { stale = true; syncKey = "network"; renderCurrent(); updateControls(); });
    setInterval(() => { if (document.visibilityState !== "hidden" && !pending && !reading) refresh(); }, 60000);
    setInterval(() => { if (current && document.visibilityState !== "hidden") $("elapsed").textContent = elapsed(); }, 15000);
    translate(); refresh();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, {once: true}); else boot();
})();
