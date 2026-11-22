(() => {
  "use strict";
  const copy = {
    en: {skip: "Skip to tasks", title: "Desk", calendar: "Calendar", planner: "Planner", tasks: "Tasks", captureLabel: "Quick add", capturePlaceholder: "Quick add: title @project !high ^tomorrow", add: "Add",
      overdue: "Overdue", dueToday: "Due today", next: "Next actions", allDay: "All day", noEvents: "No events today.", noTasks: "Nothing to do right now.", start: "Start", stop: "Stop",
      markDone: "Mark as done", etaMin: "in {n} min", etaHour: "in {h} h {m} min", noNext: "No more events today", week: "Week {n}", dayOfYear: "Day {n}", loading: "Loading…",
      captured: "Added.", saved: "Updated.", readonly: "Read-only: changes are disabled.", error: "Could not load: ", conflict: "Data changed. Reload and try again.", noRevision: "Could not obtain a write revision. Reload and try again.", requestFailed: "Request failed", due: "due {d}",
      modeDay: "Today", modeWeek: "7 days", modeMonth: "Month", changeDue: "Change due", openInPlanner: "Open in Planner", details: "Details", close: "Close", type: "Type", statusLabel: "Status", when: "When", openDetails: "Show details: "},
    ja: {skip: "タスクへ移動", title: "Desk", calendar: "カレンダー", planner: "Planner", tasks: "タスク", captureLabel: "クイック追加", capturePlaceholder: "クイック追加: タイトル @project !高 ^明日", add: "追加",
      overdue: "期限超過", dueToday: "今日", next: "次の一手", allDay: "終日", noEvents: "今日の予定はありません。", noTasks: "今やることはありません。", start: "開始", stop: "停止",
      markDone: "完了にする", etaMin: "あと {n}分", etaHour: "あと {h}時間{m}分", noNext: "今日の予定はもうありません", week: "第{n}週", dayOfYear: "年内 {n}日目", loading: "読み込み中…",
      captured: "追加しました。", saved: "更新しました。", readonly: "読み取り専用のため変更できません。", error: "読み込めませんでした: ", conflict: "データが更新されています。再読み込みしてやり直してください。", noRevision: "更新用リビジョンを取得できません。再読み込みしてください。", requestFailed: "リクエストに失敗しました", due: "期限 {d}",
      modeDay: "今日", modeWeek: "7日間", modeMonth: "月", changeDue: "期限を変更", openInPlanner: "Plannerで開く", details: "詳細", close: "閉じる", type: "種類", statusLabel: "状態", when: "日時", openDetails: "詳細を表示: "}
  };
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const requested = params.get("lang");
  const lang = ["en", "ja"].includes(requested) ? requested : ((navigator.language || "en").slice(0, 2) === "ja" ? "ja" : "en");
  const t = copy[lang];
  const fmt = (s, v) => s.replace(/\{(\w+)\}/g, (_, k) => v[k]);
  let mode = "day", pickedDay = "",  weekEvents = [], today = "", clock = null, writable = false, pending = false, generation = 0, revision = null, items = [], nowIso = "", events = [];
  const recordRevisions = new WeakMap();
  const REFRESH_MS = 60000;
  let tickTimer = null, refreshTimer = null;

  function translate() {
    document.documentElement.lang = lang;
    document.title = "life.txt " + t.title;
    document.querySelectorAll("[data-i18n]").forEach(n => { if (t[n.dataset.i18n]) n.textContent = t[n.dataset.i18n]; });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(n => { n.placeholder = t[n.dataset.i18nPlaceholder] || n.placeholder; });
  }
  function say(text) { $("feedback").textContent = text || ""; }

  function responseRevision(response) {
    const token = response.headers.get("X-Lifetxt-Revision");
    return response.headers.get("ETag") || (token ? '"' + token + '"' : null);
  }
  async function api(path, options = {}) {
    const {expectedRevision, ...init} = options;
    if (["POST", "PUT", "PATCH", "DELETE"].includes((init.method || "GET").toUpperCase())) {
      // An explicit snapshot is never upgraded by discovery or background reads.
      if (expectedRevision === undefined && !revision) await api("/api/revision");
      const expected = expectedRevision === undefined ? revision : expectedRevision;
      if (!expected) throw Error(t.noRevision);
      const headers = new Headers(init.headers || {});
      headers.set("If-Match", expected);
      init.headers = headers;
    }
    const response = await fetch(path, init);
    const raw = await response.text();
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; } catch (_) {}
    if (!response.ok) {
      const error = Error(response.status === 409 ? t.conflict : response.status === 428 ? t.noRevision : data.message || data.detail || t.requestFailed);
      error.status = response.status;
      throw error;
    }
    const token = responseRevision(response);
    if (token) revision = token;
    recordRevisions.set(data, token);
    for (const item of [...(data.items || []), ...(data.item ? [data.item] : [])]) recordRevisions.set(item, token);
    return data;
  }
  const pathFor = i => i.id ? "/api/items/id/" + encodeURIComponent(i.id) : i.line && i.editable ? "/api/items/" + encodeURIComponent(i.line) : null;

  // ---- Details dialog (read-only) ----
  function showDetail(record, when, item, day) {
    const box = $("detail-content");
    box.replaceChildren();
    $("detail-heading").textContent = record.title || t.details;
    const rows = [[t.type, record.type || record.kind], [t.statusLabel, record.status], [t.when, when]];
    for (const [k, v] of Object.entries(record.details || {})) rows.push([k, Array.isArray(v) ? v.join(", ") : String(v)]);
    for (const k of ["due", "project", "progress", "reason"]) if (record[k] && !(record.details || {})[k]) rows.push([k, String(record[k])]);
    for (const [k, v] of rows) {
      if (!v) continue;
      const p = document.createElement("p"), b = document.createElement("b");
      b.textContent = k + ": "; p.append(b, document.createTextNode(String(v))); box.append(p);
    }
    const acts = $("detail-actions");
    acts.replaceChildren();
    if (item && writable && item.editable && pathFor(item) && (item.type === "T")) {
      const input = document.createElement("input"), btn = document.createElement("button");
      input.type = "date"; input.id = "detail-due"; input.setAttribute("aria-label", t.changeDue);
      const old = String((item.details || {}).due || "");
      input.value = old.slice(0, 10);
      btn.type = "button"; btn.className = "go"; btn.textContent = t.changeDue;
      btn.onclick = () => {
        if (!input.value) return;
        const next = input.value + (old.includes("T") ? old.slice(10) : "");
        $("detail-dialog").close();
        mutate(() => api(pathFor(item), {expectedRevision: recordRevisions.get(item) || null, method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({status: item.status, type: item.type, title: item.title, details: Object.assign({}, item.details || {}, {due: next})})}));
      };
      acts.append(input, btn);
    }
    if (day) {
      const a = document.createElement("a");
      a.className = "go"; a.textContent = t.openInPlanner;
      a.href = "/planner?date=" + encodeURIComponent(day) + (lang === "ja" ? "&lang=ja" : "");
      acts.append(a);
    }
    $("detail-dialog").showModal();
    $("detail-close").focus();
  }
  function detailButton(node, label, record, when, item, day) {
    node.setAttribute("role", "button");
    node.tabIndex = 0;
    node.setAttribute("aria-label", t.openDetails + label);
    node.classList.add("clickable");
    const open = () => showDetail(record, when, item, day);
    node.addEventListener("click", open);
    node.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  }

  // ---- Clock: workspace time from /api/config, advanced locally ----
  function acceptClock(config, started) {
    clock = null;
    const raw = config.current_datetime;
    if (typeof raw !== "string" || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$/.test(raw) || performance.now() - started > 10000) return;
    const offset = (Number(raw.slice(-5, -3)) * 60 + Number(raw.slice(-2))) * (raw.at(-6) === "-" ? -1 : 1);
    const epoch = Date.parse(raw);
    if (Number.isFinite(epoch) && Math.abs(offset) <= 840) clock = {epoch, offset, received: performance.now()};
  }
  // A Date whose UTC fields read as the workspace wall clock.
  function wallNow() {
    if (clock) return new Date(clock.epoch + (performance.now() - clock.received) + clock.offset * 60000);
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  }
  const pad = n => String(n).padStart(2, "0");
  const hhmm = d => pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes());
  const isoDay = d => d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1) + "-" + pad(d.getUTCDate());
  function isoWeek(d) {
    const x = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    x.setUTCDate(x.getUTCDate() + 4 - (x.getUTCDay() || 7));
    return Math.ceil(((x - Date.UTC(x.getUTCFullYear(), 0, 1)) / 86400000 + 1) / 7);
  }
  const dayOfYear = d => Math.floor((Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - Date.UTC(d.getUTCFullYear(), 0, 0)) / 86400000);
  function tick() {
    const d = wallNow();
    const sec = document.createElement("small");
    sec.textContent = pad(d.getUTCSeconds());
    $("clock").replaceChildren(hhmm(d), sec);
    const loc = lang === "ja" ? "ja-JP" : "en-US";
    $("clock-date").textContent = new Intl.DateTimeFormat(loc, {month: "long", day: "numeric", weekday: "short", timeZone: "UTC"}).format(d);
    $("clock-week").textContent = d.getUTCFullYear() + " · " + fmt(t.week, {n: isoWeek(d)}) + " · " + fmt(t.dayOfYear, {n: dayOfYear(d)});
    nowIso = isoDay(d) + "T" + hhmm(d);
    if (today && isoDay(d) !== today) syncConfig().then(load);
    updateNext(d);
    const n = $("now-line");
    if (n) n.firstChild.textContent = hhmm(d);
  }

  // ---- Calendar ----
  const clockPart = s => String(s || "").includes("T") ? String(s).slice(11, 16) : "";
  function buildEvents(records) {
    const out = [];
    for (const r of records) {
      if (!["E", "R", "D"].includes(r.type)) continue;
      for (const m of (Array.isArray(r.matches) ? r.matches : [])) {
        if (String(m.start || "").slice(0, 10) !== today) continue;
        out.push({record: r, title: r.title, time: clockPart(m.start), end: clockPart(m.end), kind: r.type});
      }
    }
    return out.sort((a, b) => (a.time || "").localeCompare(b.time || "") || a.title.localeCompare(b.title, lang));
  }
  function nowLine() {
    const n = document.createElement("div"), s = document.createElement("span"), i = document.createElement("i");
    n.className = "now"; n.id = "now-line"; s.textContent = nowIso.slice(11, 16); n.append(s, i);
    return n;
  }
  function buildWeek(records) {
    const out = [];
    for (const r of records) {
      if (!["E", "R", "D"].includes(r.type)) continue;
      for (const m of (Array.isArray(r.matches) ? r.matches : [])) {
        out.push({record: r, title: r.title, day: String(m.start || "").slice(0, 10), time: clockPart(m.start), end: clockPart(m.end)});
      }
    }
    return out.sort((a, b) => (a.day + (a.time || "")).localeCompare(b.day + (b.time || "")));
  }
  function renderWeek() {
    const box = $("timeline");
    box.replaceChildren();
    if (!weekEvents.length) { const p = document.createElement("p"); p.className = "empty"; p.textContent = t.noEvents; box.append(p); return; }
    let last = "";
    for (const e of weekEvents) {
      if (e.day !== last) { last = e.day; const h = document.createElement("div"); h.className = "sec info"; h.textContent = e.day; box.append(h); }
      const row = document.createElement("div"), tm = document.createElement("div"), ev = document.createElement("div");
      row.className = "row"; tm.className = "tm"; tm.textContent = e.time || t.allDay;
      ev.className = "ev"; ev.append(document.createTextNode(e.title));
      detailButton(ev, e.title, e.record, e.day + " " + (e.time || t.allDay), null, e.day);
      row.append(tm, ev); box.append(row);
    }
  }
  function monthRange() {
    const [y, m] = today.split("-").map(Number);
    const first = new Date(Date.UTC(y, m - 1, 1)), last = new Date(Date.UTC(y, m, 0));
    return {first, last, from: isoDay(first), to: isoDay(last)};
  }
  function renderMonth() {
    const box = $("timeline"), keep = box.scrollTop;
    box.replaceChildren();
    const {first, last} = monthRange();
    const counts = {};
    for (const e of weekEvents) counts[e.day] = (counts[e.day] || 0) + 1;
    if (!pickedDay || pickedDay.slice(0, 7) !== today.slice(0, 7)) pickedDay = today;
    const grid = document.createElement("div");
    grid.className = "mgrid";
    const lead = (first.getUTCDay() + 6) % 7;
    for (let i = 0; i < lead; i++) grid.append(document.createElement("span"));
    for (let d = 1; d <= last.getUTCDate(); d++) {
      const iso = today.slice(0, 8) + pad(d), b = document.createElement("button");
      b.type = "button"; b.className = "mday" + (iso === today ? " today" : "") + (iso === pickedDay ? " picked" : "");
      b.setAttribute("aria-pressed", String(iso === pickedDay));
      b.textContent = String(d);
      if (counts[iso]) { const u = document.createElement("u"); u.textContent = counts[iso]; b.append(u); }
      b.onclick = () => { pickedDay = iso; renderMonth(); };
      grid.append(b);
    }
    box.append(grid);
    const h = document.createElement("div"); h.className = "sec info"; h.textContent = pickedDay; box.append(h);
    const day = weekEvents.filter(e => e.day === pickedDay);
    if (!day.length) { const p = document.createElement("p"); p.className = "empty"; p.textContent = t.noEvents; box.append(p); }
    for (const e of day) {
      const row = document.createElement("div"), tm = document.createElement("div"), ev = document.createElement("div");
      row.className = "row"; tm.className = "tm"; tm.textContent = e.time || t.allDay;
      ev.className = "ev"; ev.append(document.createTextNode(e.title));
      detailButton(ev, e.title, e.record, e.day + " " + (e.time || t.allDay), null, e.day);
      row.append(tm, ev); box.append(row);
    }
    box.scrollTop = keep;
  }
  function setMode(m) {
    mode = m;
    $("mode-month").setAttribute("aria-pressed", String(m === "month"));
    $("mode-day").setAttribute("aria-pressed", String(m === "day"));
    $("mode-week").setAttribute("aria-pressed", String(m === "week"));
    load();
  }
  function renderTimeline() {
    if (mode === "week") { renderWeek(); return; }
    if (mode === "month") { renderMonth(); return; }
    const box = $("timeline");
    box.replaceChildren();
    if (!events.length) { const p = document.createElement("p"); p.className = "empty"; p.textContent = t.noEvents; box.append(p); return; }
    const nowTime = nowIso.slice(11, 16);
    let placed = false;
    for (const e of events) {
      if (!placed && e.time && e.time > nowTime) { box.append(nowLine()); placed = true; }
      const row = document.createElement("div"), tm = document.createElement("div"), ev = document.createElement("div");
      row.className = "row"; tm.className = "tm"; tm.textContent = e.time || t.allDay;
      ev.className = "ev" + (e.kind === "R" ? " g" : "") + (e.time && (e.end || e.time) <= nowTime ? " past" : "");
      ev.append(document.createTextNode(e.title));
      const range = e.time && e.end ? e.time + " – " + e.end : "";
      if (range) { const s = document.createElement("small"); s.textContent = range; ev.append(s); }
      detailButton(ev, e.title, e.record, range || e.time || t.allDay, null, today);
      row.append(tm, ev); box.append(row);
    }
    if (!placed) box.append(nowLine());
    const n = $("now-line");
    box.scrollTop = Math.max(0, n.offsetTop - box.offsetTop - box.clientHeight / 3);
  }
  function updateNext(d) {
    const nowTime = hhmm(d);
    const nxt = events.find(e => e.time && e.time > nowTime);
    if (!nxt) { $("next-eta").textContent = ""; $("next-title").textContent = t.noNext; return; }
    const [h, m] = nxt.time.split(":").map(Number);
    const diff = h * 60 + m - (d.getUTCHours() * 60 + d.getUTCMinutes());
    $("next-eta").textContent = diff < 60 ? fmt(t.etaMin, {n: diff}) : fmt(t.etaHour, {h: Math.floor(diff / 60), m: diff % 60});
    $("next-title").textContent = nxt.time + " " + nxt.title;
  }

  // ---- Tasks ----
  const findItem = ref => items.find(i => (ref.id && ref.id === i.id) || (ref.source === i.source && ref.line === i.line)) || items.find(i => i.title === ref.title);
  async function mutate(action) {
    if (pending) return;
    pending = true;
    try { await action(); say(t.saved); pending = false; await load(); } catch (e) { say(e.message); } finally { pending = false; }
  }
  const putBody = (i, status) => JSON.stringify({status, type: i.type, title: i.title, details: i.details || {}});
  const complete = i => mutate(() => api(i.id ? pathFor(i) + "/complete" : pathFor(i), {
    expectedRevision: recordRevisions.get(i) || null, method: i.id ? "POST" : "PUT",
    headers: {"Content-Type": "application/json"}, body: i.id ? JSON.stringify({date: today}) : putBody(i, "[x]")}));
  const toggleStart = i => mutate(() => api(pathFor(i), {expectedRevision: recordRevisions.get(i) || null, method: "PUT",
    headers: {"Content-Type": "application/json"}, body: putBody(i, i.status === "[/]" ? "[ ]" : "[/]")}));
  function taskRow(ref, bad) {
    const i = findItem(ref);
    const row = document.createElement("div"), cb = document.createElement("button"), tt = document.createElement("div"), go = document.createElement("button");
    row.className = "task"; cb.type = "button"; cb.className = "cb" + (bad ? " bad" : "");
    cb.setAttribute("aria-label", t.markDone + ": " + ref.title);
    tt.className = "tt" + (i && i.status === "[/]" ? " active" : "");
    tt.append(document.createTextNode(ref.title));
    const detail = [ref.reason || (ref.due ? fmt(t.due, {d: String(ref.due).slice(0, 10)}) : ""), ref.project].filter(Boolean).join(" · ");
    if (detail) { const s = document.createElement("small"); s.textContent = detail; tt.append(s); }
    const pct = /^(\d+(?:\.\d+)?)%$/.exec(String(ref.progress || ""));
    if (pct) { const pg = document.createElement("div"), b = document.createElement("b"); pg.className = "pg"; b.style.width = Math.min(100, Number(pct[1])) + "%"; pg.append(b); tt.append(pg); }
    detailButton(tt, ref.title, i ? Object.assign({}, ref, i) : ref, ref.due ? String(ref.due) : "", i, "");
    const can = Boolean(writable && i && i.editable && pathFor(i));
    cb.disabled = !can; go.disabled = !can;
    go.type = "button"; go.className = "go"; go.textContent = i && i.status === "[/]" ? t.stop : t.start;
    if (can) { cb.onclick = () => complete(i); go.onclick = () => toggleStart(i); }
    row.append(cb, tt, go);
    return row;
  }
  function section(box, cls, label, refs, bad) {
    if (!refs.length) return;
    const h = document.createElement("div");
    h.className = "sec " + cls; h.textContent = label; box.append(h);
    refs.forEach(r => box.append(taskRow(r, bad)));
  }
  function renderTasks(day) {
    const box = $("tasks"), keep = box.scrollTop;
    box.replaceChildren();
    const open = r => r.kind === "T" || r.kind === undefined;
    const key = r => r.id || r.source + ":" + r.line;
    const overdue = (day.overdue || []).filter(open), due = (day.due_today || []).filter(open);
    const seen = new Set([...overdue, ...due].map(key));
    const nxt = (day.next_actions || []).filter(r => open(r) && !r.blocked && !seen.has(key(r)));
    $("count-overdue").textContent = overdue.length ? t.overdue + " " + overdue.length : "";
    $("count-today").textContent = due.length ? t.dueToday + " " + due.length : "";
    $("count-next").textContent = nxt.length ? t.next + " " + nxt.length : "";
    if (!overdue.length && !due.length && !nxt.length) { const p = document.createElement("p"); p.className = "empty"; p.textContent = t.noTasks; box.append(p); return; }
    section(box, "bad", t.overdue, overdue, true);
    section(box, "warn", t.dueToday, due, false);
    section(box, "info", t.next, nxt, false);
    box.scrollTop = keep;
  }
  function renderStatus(day) {
    const s = Array.isArray(day.now) && day.now[0], pill = $("status-pill");
    pill.hidden = !s;
    pill.textContent = s ? "● " + (s.state || s.status || "") : "";
    $("status-title").textContent = s ? (s.title || s.activity || "") : "";
  }

  function addDays(iso, n) {
    const d = new Date(iso + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }
  async function load() {
    const mine = ++generation;
    try {
      const [day, agenda, list] = await Promise.all([
        api("/api/command-center?date=" + today), api("/api/agenda?from=" + (mode === "month" ? monthRange().from : today) + "&to=" + (mode === "week" ? addDays(today, 6) : mode === "month" ? monthRange().to : today)),
        api("/api/items?type=T&open_only=true")]);
      if (mine !== generation) return;
      items = list.items || [];
      events = buildEvents(agenda.records || []);
      weekEvents = mode !== "day" ? buildWeek(agenda.records || []) : [];
      renderStatus(day); renderTimeline(); renderTasks(day); updateNext(wallNow());
      $("open-planner").href = "/planner?date=" + today + (lang === "ja" ? "&lang=ja" : "");
    } catch (e) { if (mine === generation) say(t.error + e.message); }
  }
  async function syncConfig() {
    const started = performance.now();
    try { const c = await api("/api/config"); today = c.today; acceptClock(c, started); } catch (_) {}
  }
  async function capture(event) {
    event.preventDefault();
    const input = $("capture-text"), text = input.value.trim();
    if (!text || pending || !writable) return;
    pending = true;
    try {
      const snap = revision;
      await api("/api/items/capture", {expectedRevision: snap, method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text, expected_source_revision: (snap || "").replace(/^"|"$/g, "")})});
      input.value = ""; say(t.captured);
      pending = false; await load();
    } catch (e) { say(e.message); } finally { pending = false; }
  }
  function stopTimers() { clearInterval(tickTimer); clearInterval(refreshTimer); tickTimer = refreshTimer = null; }
  function startTimers() {
    stopTimers();
    tick(); tickTimer = setInterval(tick, 1000);
    refreshTimer = setInterval(() => { syncConfig().then(load); }, REFRESH_MS);
  }
  async function boot() {
    translate(); say(t.loading);
    const started = performance.now();
    const [config, health] = await Promise.all([api("/api/config"), api("/api/health")]);
    today = config.today; acceptClock(config, started);
    writable = !health.read_only && (health.can_write ?? Boolean(health.writable_path));
    $("capture-text").disabled = !writable; $("capture-form").querySelector("button").disabled = !writable;
    $("detail-close").onclick = () => $("detail-dialog").close();
    $("capture-form").onsubmit = capture;
    $("mode-day").onclick = () => setMode("day");
    $("mode-week").onclick = () => setMode("week");
    $("mode-month").onclick = () => setMode("month");
    tick(); await load(); say(writable ? "" : t.readonly);
    startTimers();
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") { syncConfig().then(load); startTimers(); } else stopTimers();
    });
  }
  boot().catch(e => say(t.error + e.message));
})();
