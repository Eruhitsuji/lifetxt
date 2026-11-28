(() => {
  "use strict";
  const copy = {
    en: {layout: "Layout", layoutTitle: "Screen layout", layoutPreset: "Preset", layoutCustom: "Custom", presetNames: {standard: "Standard", clock: "Clock", tasks: "Tasks", calendar: "Calendar"}, blockNames: {clock: "Clock", status: "Status", next: "Next event", calendar: "Calendar", tasks: "Tasks", capture: "Quick add", habits: "Habits", messages: "Messages and notes", deadlines: "Upcoming deadlines", summary: "Summary"}, habitsTitle: "Habits", messagesTitle: "Messages and notes", deadlinesTitle: "Upcoming deadlines", summaryTitle: "Summary", habitDone: "Done today", habitOpen: "Not yet", habitCount: "{done} / {total} done", noHabits: "No habits.", messagesHeading: "Messages", notesHeading: "Recent notes", noMessages: "No messages or notes.", noDeadlines: "No deadlines in the next 14 days.", daysToday: "Today", daysLeft: "{n} d left", doneToday: "Done today", openTasks: "Open tasks", noProject: "No project", projectsHeading: "Projects", projectCounts: "{open} open · {overdue} overdue · {done} done today", layoutColumns: ["Left column", "Right column"], layoutUp: "Move up", layoutDown: "Move down", layoutRight: "Move to right column", layoutLeft: "Move to left column", layoutSwap: "Swap columns", layoutReset: "Reset to standard", layoutRatio: "Column width", ratioNames: {balanced: "Balanced", left: "Wider left", right: "Wider right"}, layoutFont: "Text size", fontNames: {s: "Small", m: "Medium", l: "Large"}, layoutShow: "Checked items are shown. Settings are saved in this browser.", layoutBlockFont: "Text size", fontXl: "Extra large", fontDefault: "Default", layoutAuto: "Reset sizes", splitColumns: "Column width (drag or arrow keys, double-click to reset)", splitBlock: "Height of {name} (drag or arrow keys, double-click for automatic)",
      fullscreenOn: "Full screen", fullscreenOff: "Exit full screen", fullscreenFailed: "Could not change full screen mode.", statusNow: "Status", statusNone: "No status", statusChange: "Change status", statusEnd: "End current status", statusActivity: "Activity (optional)", statusCustom: "Custom status", statusSet: "Set custom status", statusForce: "Restart even if this status is already current", statusSame: "This status is already current; its start and title were kept.", statusRequired: "Enter a custom status.", since: "since {at} · {span}", spanMin: "{m} min", spanHour: "{h} h {m} min",
      stateNames: ["Available", "Busy", "Focus", "Meeting", "Away", "Offline", "Commuting", "Working", "Sleeping"],
      skip: "Skip to tasks", title: "Desk", reasonToday: "due today", reasonOverdue: "{n} overdue (days)", top: "Top", calendar: "Calendar", planner: "Planner", tasks: "Tasks", captureLabel: "Quick add", capturePlaceholder: "Quick add: title @project !high ^tomorrow", add: "Add", preview: "Preview", confirmCapture: "Confirm capture", editBtn: "Edit", detailsLabel: "Details (key:value per line)", themeAuto: "Theme: auto", themeDark: "Theme: dark", themeLight: "Theme: light", reviewFirst: "Review the mapped fields, then confirm.",
      overdue: "Overdue", dueToday: "Due today", next: "Next actions", allDay: "All day", noEvents: "No events today.", noTasks: "Nothing to do right now.", start: "Start", stop: "Stop",
      markDone: "Mark as done", doneAt: "Completion date and time", completeNow: "Complete now", completeAt: "Complete at selected time", etaMin: "in {n} min", etaHour: "in {h} h {m} min", noNext: "No more events today", loading: "Loading…",
      captured: "Added.", saved: "Updated.", readonly: "Read-only: changes are disabled.", error: "Could not load: ", conflict: "Data changed. Reload and try again.", noRevision: "Could not obtain a write revision. Reload and try again.", requestFailed: "Request failed", due: "due {d}",
      modeDay: "Today", modeWeek: "7 days", modeMonth: "Month", save: "Save", evTitle: "Title", evDate: "Date", evStart: "Start", evEnd: "End", badRange: "End must be after start.", requiredFields: "Enter a title, date, and time.", requiredTitle: "Enter a title.", requiredDate: "Choose a date.", dueDate: "Due date", changeDue: "Change due", openInPlanner: "Open in Planner", details: "Details", close: "Close", type: "Type", statusLabel: "Status", when: "When", openDetails: "Show details: "},
    ja: {layout: "画面構成", layoutTitle: "画面構成", layoutPreset: "プリセット", layoutCustom: "カスタム", presetNames: {standard: "標準", clock: "時計中心", tasks: "タスク中心", calendar: "カレンダー中心"}, blockNames: {clock: "時計", status: "状態", next: "次の予定", calendar: "カレンダー", tasks: "タスク", capture: "クイック追加", habits: "習慣", messages: "メッセージ・メモ", deadlines: "今後の締切", summary: "集計"}, habitsTitle: "習慣", messagesTitle: "メッセージ・メモ", deadlinesTitle: "今後の締切", summaryTitle: "集計", habitDone: "今日は完了", habitOpen: "未完了", habitCount: "{done} / {total} 完了", noHabits: "習慣はありません。", messagesHeading: "メッセージ", notesHeading: "最近のメモ", noMessages: "メッセージやメモはありません。", noDeadlines: "14日以内の締切はありません。", daysToday: "今日", daysLeft: "あと{n}日", doneToday: "今日の完了", openTasks: "未完了タスク", noProject: "プロジェクトなし", projectsHeading: "プロジェクト", projectCounts: "未完了 {open} · 期限超過 {overdue} · 今日完了 {done}", layoutColumns: ["左の列", "右の列"], layoutUp: "上へ", layoutDown: "下へ", layoutRight: "右の列へ", layoutLeft: "左の列へ", layoutSwap: "左右を入れ替える", layoutReset: "標準に戻す", layoutRatio: "列の幅", ratioNames: {balanced: "均等", left: "左を広く", right: "右を広く"}, layoutFont: "文字サイズ", fontNames: {s: "小", m: "中", l: "大"}, layoutShow: "チェックした項目を表示します。設定はこのブラウザに保存されます。", layoutBlockFont: "文字サイズ", fontXl: "特大", fontDefault: "全体と同じ", layoutAuto: "大きさを戻す", splitColumns: "列の幅（ドラッグまたは矢印キー、ダブルクリックで戻す）", splitBlock: "{name}の高さ（ドラッグまたは矢印キー、ダブルクリックで自動）",
      fullscreenOn: "全画面", fullscreenOff: "全画面を終了", fullscreenFailed: "全画面表示を切り替えられませんでした。", statusNow: "状態", statusNone: "現在設定なし", statusChange: "状態を切り替える", statusEnd: "現在の状態を終了", statusActivity: "活動名（任意）", statusCustom: "カスタム状態", statusSet: "カスタム状態を設定", statusForce: "同じ状態でも再開始する", statusSame: "すでに同じ状態です。開始時刻とタイトルは維持しました。", statusRequired: "カスタム状態を入力してください。", since: "{at} から · {span}", spanMin: "{m}分", spanHour: "{h}時間{m}分",
      stateNames: ["対応可能", "取り込み中", "集中", "会議中", "離席中", "オフライン", "移動中", "作業中", "睡眠中"],
      skip: "タスクへ移動", title: "Desk", reasonToday: "今日が期限", reasonOverdue: "{n}日超過", top: "トップ", calendar: "カレンダー", planner: "Planner", tasks: "タスク", captureLabel: "クイック追加", capturePlaceholder: "クイック追加: タイトル @project !高 ^明日", add: "追加", preview: "プレビュー", confirmCapture: "追加を確定", editBtn: "編集", detailsLabel: "詳細 (1行に key:value)", themeAuto: "テーマ: 自動", themeDark: "テーマ: ダーク", themeLight: "テーマ: ライト", reviewFirst: "変換結果を確認して確定してください。",
      overdue: "期限超過", dueToday: "今日", next: "次の一手", allDay: "終日", noEvents: "今日の予定はありません。", noTasks: "今やることはありません。", start: "開始", stop: "停止",
      markDone: "完了にする", doneAt: "完了日時", completeNow: "今すぐ完了", completeAt: "指定した日時で完了", etaMin: "あと {n}分", etaHour: "あと {h}時間{m}分", noNext: "今日の予定はもうありません", loading: "読み込み中…",
      captured: "追加しました。", saved: "更新しました。", readonly: "読み取り専用のため変更できません。", error: "読み込めませんでした: ", conflict: "データが更新されています。再読み込みしてやり直してください。", noRevision: "更新用リビジョンを取得できません。再読み込みしてください。", requestFailed: "リクエストに失敗しました", due: "期限 {d}",
      modeDay: "今日", modeWeek: "7日間", modeMonth: "月", save: "保存", evTitle: "タイトル", evDate: "日付", evStart: "開始", evEnd: "終了", badRange: "終了は開始より後にしてください。", requiredFields: "タイトル、日付、時刻を入力してください。", requiredTitle: "タイトルを入力してください。", requiredDate: "日付を選択してください。", dueDate: "期限日", changeDue: "期限を変更", openInPlanner: "Plannerで開く", details: "詳細", close: "閉じる", type: "種類", statusLabel: "状態", when: "日時", openDetails: "詳細を表示: "}
  };
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const requested = params.get("lang");
  const lang = ["en", "ja"].includes(requested) ? requested : ((navigator.language || "en").slice(0, 2) === "ja" ? "ja" : "en");
  const t = copy[lang];
  const layoutCopy = lang === "ja"
    ? {share: "画面構成をURLに反映", linked: "画面構成をアドレスバーのURLに反映しました。", scoped: "このリンクの画面構成を編集中です。"}
    : {share: "Put layout in URL", linked: "The address bar now includes this layout.", scoped: "You are editing the layout for this link."};
  const fmt = (s, v) => s.replace(/\{(\w+)\}/g, (_, k) => v[k]);
  let eventItems = [], mode = "day", pickedDay = "",  weekEvents = [], today = "", clock = null, writable = false, pending = false, generation = 0, revision = null, items = [], nowIso = "", events = [];
  const recordRevisions = new WeakMap();
  const REFRESH_MS = 60000;
  let tickTimer = null, refreshTimer = null;

  function translate() {
    document.documentElement.lang = lang;
    document.title = "life.txt " + t.title;
    document.querySelectorAll("[data-i18n]").forEach(n => { if (t[n.dataset.i18n]) n.textContent = t[n.dataset.i18n]; });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(n => { n.placeholder = t[n.dataset.i18nPlaceholder] || n.placeholder; });
  }
  function localReason(r) {
    if (!r || lang !== "ja") return r;
    if (r === "due today") return t.reasonToday;
    const m = /^(\d+) days? overdue$/.exec(r);
    return m ? fmt(t.reasonOverdue, {n: m[1]}) : r;
  }
  let sayTimer = null;
  function say(text) { $("feedback").textContent = text || ""; clearTimeout(sayTimer); if (text) sayTimer = setTimeout(() => { $("feedback").textContent = ""; }, 3000); }

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

  // ---- Details dialog ----
  function showDetailError(message) {
    const error = $("detail-error");
    error.textContent = message;
    error.scrollIntoView({block: "nearest"});
  }

  function detailField(label, control) {
    const field = document.createElement("label");
    field.className = "fld";
    field.textContent = label;
    field.append(control);
    return field;
  }

  function detailInput(id, type, value) {
    const input = document.createElement("input");
    input.id = id;
    input.type = type;
    input.value = value;
    return input;
  }

  function detailFields(...fields) {
    const group = document.createElement("div");
    group.className = "detail-fields";
    group.append(...fields);
    return group;
  }

  function detailList(rows, className) {
    const list = document.createElement("dl");
    list.className = className;
    for (const [key, value] of rows) {
      if (!value) continue;
      const row = document.createElement("div");
      const term = document.createElement("dt");
      const definition = document.createElement("dd");
      term.textContent = key;
      definition.textContent = value;
      row.append(term, definition);
      list.append(row);
    }
    return list;
  }

  const detailsText = d => Object.entries(d || {}).flatMap(([k, vs]) => (Array.isArray(vs) ? vs : [vs]).map(v => k + ":" + v)).join("\n");
  const parseDetailsText = text => { const out = {}; for (const line of text.split("\n")) { const x = line.trim(); if (!x) continue; const c = x.indexOf(":"); if (c < 1) continue; const k = x.slice(0, c).trim(); (out[k] = out[k] || []).push(x.slice(c + 1).trim()); } return out; };
  function fullEdit(item) {
    const box = $("detail-content"), acts = $("detail-actions");
    box.replaceChildren(); acts.replaceChildren();
    $("detail-error").textContent = "";
    const ti = detailInput("detail-title", "text", item.title);
    const st = document.createElement("select");
    for (const v of new Set(["[ ]", "[/]", "[x]", "[-]", "[>]", "[?]", "[N]", item.status])) { const o = document.createElement("option"); o.value = o.textContent = v; st.append(o); }
    st.value = item.status;
    const ty = detailInput("detail-type", "text", item.type);
    const de = document.createElement("textarea");
    de.value = detailsText(item.details);
    de.rows = 6;
    box.append(detailField(t.evTitle, ti),
      detailFields(detailField(t.statusLabel, st), detailField(t.type, ty)),
      detailField(t.detailsLabel, de));
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "go go-primary"; btn.textContent = t.save;
    btn.onclick = () => {
      if (!ti.value.trim()) { showDetailError(t.requiredTitle); return; }
      const det = parseDetailsText(de.value);
      $("detail-dialog").close();
      mutate(() => api(pathFor(item), {expectedRevision: recordRevisions.get(item) || null, method: "PUT",
        headers: {"Content-Type": "application/json"}, body: JSON.stringify({status: st.value, type: ty.value.trim() || item.type, title: ti.value.trim(), details: det})}));
    };
    acts.append(btn); ti.focus();
  }
  function showDetail(record, when, item, day) {
    const box = $("detail-content");
    box.replaceChildren();
    $("detail-heading").textContent = record.title || t.details;
    $("detail-error").textContent = "";
    const summary = detailList([[t.type, record.type || record.kind], [t.statusLabel, record.status], [t.when, when]], "detail-summary");
    if (summary.childElementCount) box.append(summary);
    const rows = [];
    for (const [k, v] of Object.entries(record.details || {})) rows.push([k, Array.isArray(v) ? v.join(", ") : String(v)]);
    for (const k of ["due", "project", "progress", "reason"]) if (record[k] && !(record.details || {})[k]) rows.push([k, k === "reason" ? localReason(String(record[k])) : String(record[k])]);
    const details = detailList(rows, "detail-properties");
    if (details.childElementCount) box.append(details);
    const acts = $("detail-actions");
    acts.replaceChildren();
    if (item && writable && item.editable && pathFor(item) && (item.type === "T")) {
      const old = String((item.details || {}).due || "");
      const input = detailInput("detail-due", "date", old.slice(0, 10));
      const btn = document.createElement("button");
      btn.type = "button"; btn.className = "go"; btn.textContent = t.changeDue;
      btn.onclick = () => {
        if (!input.value) { showDetailError(t.requiredDate); return; }
        const next = input.value + (old.includes("T") ? old.slice(10) : "");
        $("detail-dialog").close();
        mutate(() => api(pathFor(item), {expectedRevision: recordRevisions.get(item) || null, method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({status: item.status, type: item.type, title: item.title, details: Object.assign({}, item.details || {}, {due: next})})}));
      };
      acts.append(detailFields(detailField(t.dueDate, input)), btn);
    }
    if (item && item.type === "E" && writable && item.editable && pathFor(item)) {
      const one = k => { const v = (item.details || {})[k]; const x = Array.isArray(v) ? (v.length === 1 ? v[0] : "") : v; return typeof x === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(x) ? x : ""; };
      const f = one("from"), tt = one("to");
      const at = one("at");
      if (!f && !tt && at) {
        const ti = detailInput("detail-title", "text", item.title);
        const di = detailInput("detail-date", "date", at.slice(0, 10));
        const si = detailInput("detail-start", "time", at.slice(11, 16));
        const btn = document.createElement("button");
        btn.type = "button"; btn.className = "go go-primary"; btn.textContent = t.save;
        btn.onclick = () => {
          if (!ti.value.trim() || !di.value || !si.value) { showDetailError(t.requiredFields); return; }
          $("detail-dialog").close();
          const det = Object.assign({}, item.details || {}, {at: di.value + "T" + si.value + at.slice(16)});
          mutate(() => api(pathFor(item), {expectedRevision: recordRevisions.get(item) || null, method: "PUT",
            headers: {"Content-Type": "application/json"}, body: JSON.stringify({status: item.status, type: item.type, title: ti.value.trim(), details: det})}));
        };
        acts.append(detailFields(detailField(t.evTitle, ti), detailField(t.evDate, di), detailField(t.evStart, si)), btn);
      }
      if (f && tt) {
        const ti = detailInput("detail-title", "text", item.title);
        const di = detailInput("detail-date", "date", f.slice(0, 10));
        const si = detailInput("detail-start", "time", f.slice(11, 16));
        const ei = detailInput("detail-end", "time", tt.slice(11, 16));
        const btn = document.createElement("button");
        btn.type = "button"; btn.className = "go go-primary"; btn.textContent = t.save;
        btn.onclick = () => {
          const sameDay = tt.slice(0, 10) === f.slice(0, 10);
          if (!ti.value.trim() || !di.value || !si.value || !ei.value) { showDetailError(t.requiredFields); return; }
          if (sameDay && ei.value <= si.value) { showDetailError(t.badRange); return; }
          $("detail-dialog").close();
          const span = Math.round((Date.parse(tt.slice(0, 10)) - Date.parse(f.slice(0, 10))) / 86400000);
          const det = Object.assign({}, item.details || {}, {from: di.value + "T" + si.value + f.slice(16), to: addDays(di.value, span) + "T" + ei.value + tt.slice(16)});
          mutate(() => api(pathFor(item), {expectedRevision: recordRevisions.get(item) || null, method: "PUT",
            headers: {"Content-Type": "application/json"}, body: JSON.stringify({status: item.status, type: item.type, title: ti.value.trim(), details: det})}));
        };
        acts.append(detailFields(detailField(t.evTitle, ti), detailField(t.evDate, di), detailField(t.evStart, si), detailField(t.evEnd, ei)), btn);
      }
    }
    if (item && writable && item.editable && pathFor(item)) {
      const eb = document.createElement("button");
      eb.type = "button"; eb.className = "go"; eb.textContent = t.editBtn;
      eb.onclick = () => fullEdit(item);
      acts.append(eb);
    }
    if (day) {
      const a = document.createElement("a");
      a.className = "go"; a.textContent = t.openInPlanner;
      a.href = "/planner?date=" + encodeURIComponent(day) + (lang === "ja" ? "&lang=ja" : "");
      acts.append(a);
    }
    $("detail-dialog").showModal();
    box.parentElement.scrollTop = 0;
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
  let clockView = null;
  function tick() {
    const d = wallNow();
    // The true instant (for other time zones) and the workspace UTC offset.
    const instant = clock ? clock.epoch + performance.now() - clock.received : Date.now();
    clockView?.render(d, instant, clock ? clock.offset : -new Date().getTimezoneOffset());
    nowIso = isoDay(d) + "T" + hhmm(d);
    if (today && isoDay(d) !== today) syncConfig().then(load);
    updateNext(d);
    renderElapsed(d);
    const n = $("now-line");
    if (n) n.firstChild.textContent = hhmm(d);
  }

  // ---- Calendar ----
  const clockPart = s => String(s || "").includes("T") ? String(s).slice(11, 16) : "";
  const eventItem = r => eventItems.find(i => (i.id && r.details && (r.details.id || []).includes(i.id)) || (i.line === r.line && (i.source || null) === (r.source || null))) || null;
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
      detailButton(ev, e.title, e.record, e.day + " " + (e.time || t.allDay), eventItem(e.record), e.day);
      row.append(tm, ev); box.append(row);
    }
  }
  function monthRange() {
    const [y, m] = today.split("-").map(Number);
    const first = new Date(Date.UTC(y, m - 1, 1)), last = new Date(Date.UTC(y, m, 0));
    return {first, last, from: isoDay(first), to: isoDay(last)};
  }
  function renderMonth(restoreDayFocus = false) {
    const box = $("timeline"), keep = box.scrollTop;
    box.replaceChildren();
    const {first, last} = monthRange();
    const counts = {};
    for (const e of weekEvents) counts[e.day] = (counts[e.day] || 0) + 1;
    if (!pickedDay || pickedDay.slice(0, 7) !== today.slice(0, 7)) pickedDay = today;
    const grid = document.createElement("div");
    let selectedButton;
    grid.className = "mgrid";
    const lead = (first.getUTCDay() + 6) % 7;
    for (let i = 0; i < lead; i++) grid.append(document.createElement("span"));
    for (let d = 1; d <= last.getUTCDate(); d++) {
      const iso = today.slice(0, 8) + pad(d), b = document.createElement("button");
      b.type = "button"; b.className = "mday" + (iso === today ? " today" : "") + (iso === pickedDay ? " picked" : "");
      b.setAttribute("aria-pressed", String(iso === pickedDay));
      b.textContent = String(d);
      if (counts[iso]) { const u = document.createElement("u"); u.textContent = counts[iso]; b.append(u); }
      if (iso === pickedDay) selectedButton = b;
      b.onclick = () => { pickedDay = iso; renderMonth(document.activeElement === b); };
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
      detailButton(ev, e.title, e.record, e.day + " " + (e.time || t.allDay), eventItem(e.record), e.day);
      row.append(tm, ev); box.append(row);
    }
    box.scrollTop = keep;
    if (restoreDayFocus && selectedButton) selectedButton.focus({preventScroll: true});
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
      detailButton(ev, e.title, e.record, range || e.time || t.allDay, eventItem(e.record), today);
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
    try { const message = await action(); say(typeof message === "string" ? message : t.saved); pending = false; await load(); } catch (e) { say(e.message); } finally { pending = false; }
  }
  const putBody = (i, status) => JSON.stringify({status, type: i.type, title: i.title, details: i.details || {}});
  const nowStamp = () => {
    const d = wallNow();
    return isoDay(d) + "T" + hhmm(d) + ":" + pad(d.getUTCSeconds());
  };
  function complete(item, stamp) {
    const viaEndpoint = item.id && item.details?.repeat?.length;
    const details = {...item.details, done: [stamp]};
    return mutate(() => api(viaEndpoint ? pathFor(item) + "/complete" : pathFor(item), {
      expectedRevision: recordRevisions.get(item) || null,
      method: viaEndpoint ? "POST" : "PUT",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(viaEndpoint ? {done_at: stamp} :
        {status: "[x]", type: item.type, title: item.title, details})
    }));
  }

  function showCompletion(item) {
    if (pending) return;
    const dialog = $("detail-dialog");
    const form = document.createElement("form");
    form.id = "desk-completion";
    const input = detailInput("detail-done-at", "datetime-local", nowStamp());
    input.required = true;
    input.step = "1";
    form.append(detailField(t.doneAt, input));
    const finish = stamp => {
      if (pending) return;
      dialog.close();
      complete(item, stamp);
    };
    form.onsubmit = event => { event.preventDefault(); finish(input.value); };
    const now = document.createElement("button");
    now.type = "button";
    now.className = "go go-primary";
    now.textContent = t.completeNow;
    now.onclick = () => finish(nowStamp());
    const selected = document.createElement("button");
    selected.type = "submit";
    selected.setAttribute("form", form.id);
    selected.className = "go";
    selected.textContent = t.completeAt;
    $("detail-heading").textContent = item.title;
    $("detail-content").replaceChildren(form);
    $("detail-actions").replaceChildren(now, selected);
    $("detail-error").textContent = "";
    dialog.showModal();
    form.closest(".detail-body").scrollTop = 0;
    now.focus();
  }
  const toggleStart = i => mutate(() => api(pathFor(i), {expectedRevision: recordRevisions.get(i) || null, method: "PUT",
    headers: {"Content-Type": "application/json"}, body: putBody(i, i.status === "[/]" ? "[ ]" : "[/]")}));
  function taskRow(ref, bad) {
    const i = findItem(ref);
    const row = document.createElement("div"), cb = document.createElement("button"), tt = document.createElement("div"), go = document.createElement("button");
    row.className = "task"; cb.type = "button"; cb.className = "cb" + (bad ? " bad" : "");
    cb.setAttribute("aria-label", t.markDone + ": " + ref.title);
    tt.className = "tt" + (i && i.status === "[/]" ? " active" : "");
    tt.append(document.createTextNode(ref.title));
    const detail = [localReason(ref.reason) || (ref.due ? fmt(t.due, {d: String(ref.due).slice(0, 10)}) : ""), ref.project].filter(Boolean).join(" · ");
    if (detail) { const s = document.createElement("small"); s.textContent = detail; tt.append(s); }
    const pct = /^(\d+(?:\.\d+)?)%$/.exec(String(ref.progress || ""));
    if (pct) { const pg = document.createElement("div"), b = document.createElement("b"); pg.className = "pg"; b.style.width = Math.min(100, Number(pct[1])) + "%"; pg.append(b); tt.append(pg); }
    detailButton(tt, ref.title, i ? Object.assign({}, ref, i) : ref, ref.due ? String(ref.due) : "", i, "");
    const can = Boolean(writable && i && i.editable && pathFor(i));
    cb.disabled = !can; go.disabled = !can;
    go.type = "button"; go.className = "go"; go.textContent = i && i.status === "[/]" ? t.stop : t.start;
    if (can) {
      cb.setAttribute("aria-haspopup", "dialog");
      cb.onclick = () => showCompletion(i);
      go.onclick = () => toggleStart(i);
    }
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
  // ---- Status: the current person's presence ----
  const STATES = ["available", "busy", "focus", "meeting", "away", "offline", "commuting", "working", "sleeping"];
  const stateLabel = s => t.stateNames[STATES.indexOf(s)] || String(s || "");
  let currentStatus = null, statusRevision = null;
  function renderStatus(data) {
    statusRevision = recordRevisions.get(data) || null;
    currentStatus = (data.records || []).find(r => r.active && !r.to) || null;
    $("status-state").textContent = currentStatus ? stateLabel(currentStatus.state) : t.statusNone;
    $("status-state").className = "pill " + (currentStatus ? "pill-ok" : "pill-info");
    $("status-title").textContent = currentStatus?.title || "";
    $("status-card").disabled = !writable;
    renderElapsed(wallNow());
  }
  function renderElapsed(d) {
    const from = String(currentStatus?.from || "");
    // Timestamps without an offset are workspace wall-clock time, like wallNow().
    const zoned = /(Z|[+-]\d\d:\d\d)$/.test(from);
    const started = Date.parse(zoned || !from.includes("T") ? from : from + "Z");
    const now = zoned ? (clock ? clock.epoch + performance.now() - clock.received : Date.now()) : d.getTime();
    const minutes = Math.floor((now - started) / 60000);
    if (!from.includes("T") || !(minutes >= 0)) { $("status-since").textContent = ""; return; }
    const at = from.slice(0, 10) === isoDay(d) ? from.slice(11, 16) : from.slice(5, 16).replace("T", " ");
    const span = minutes < 60 ? fmt(t.spanMin, {m: minutes}) : fmt(t.spanHour, {h: Math.floor(minutes / 60), m: minutes % 60});
    $("status-since").textContent = fmt(t.since, {at, span});
  }
  function showStatusDialog() {
    if (pending || !writable) return;
    // The revision of the status shown when the dialog opened; never upgraded.
    const expected = statusRevision, current = currentStatus;
    const activity = detailInput("detail-activity", "text", current?.title || "");
    const custom = detailInput("detail-custom-state", "text", current && !STATES.includes(current.state) ? current.state : "");
    const force = detailInput("detail-force", "checkbox", "on");
    const forceRow = detailField(t.statusForce, force);
    forceRow.classList.add("check");
    const send = body => {
      if (pending) return;
      $("detail-dialog").close();
      mutate(async () => {
        try {
          const result = await api("/api/status", {expectedRevision: expected, method: "POST",
            headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
          return result.unchanged ? t.statusSame : t.saved;
        } catch (e) { load(); throw e; }
      });
    };
    const choose = state => send(Object.assign({state, title: activity.value.trim()}, force.checked ? {force: true} : {}));
    const button = (label, action) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "go"; b.textContent = label; b.onclick = action;
      return b;
    };
    const tiles = document.createElement("div");
    tiles.className = "state-tiles";
    for (const state of STATES) {
      const b = button(stateLabel(state), () => choose(state));
      b.setAttribute("aria-pressed", String(current?.state === state));
      tiles.append(b);
    }
    $("detail-heading").textContent = t.statusChange;
    $("detail-content").replaceChildren(detailField(t.statusActivity, activity), tiles, detailField(t.statusCustom, custom), forceRow);
    const actions = [button(t.statusSet, () => {
      if (!custom.value.trim()) { showDetailError(t.statusRequired); return; }
      choose(custom.value.trim());
    })];
    if (current) actions.push(button(t.statusEnd, () => send({end: true})));
    $("detail-actions").replaceChildren(...actions);
    $("detail-error").textContent = "";
    $("detail-dialog").showModal();
    $("detail-content").parentElement.scrollTop = 0;
    $("detail-close").focus();
  }

  // ---- Optional information blocks: fetched only while shown ----
  const first = (record, key) => { const v = (record.details || {})[key]; return String((Array.isArray(v) ? v[0] : v) || ""); };
  function infoRow(title, note, mark, record, when, item) {
    const row = document.createElement("div"), text = document.createElement("div");
    row.className = "task"; text.className = "tt";
    text.append(document.createTextNode(title));
    if (note) { const s = document.createElement("small"); s.textContent = note; text.append(s); }
    detailButton(text, title, record, when, item, "");
    row.append(text);
    if (mark) { const pill = document.createElement("span"); pill.className = "pill " + mark[0]; pill.textContent = mark[1]; row.append(pill); }
    return row;
  }
  function heading(label) {
    const h = document.createElement("div");
    h.className = "sec info"; h.textContent = label;
    return h;
  }
  function fill(name, nodes, empty) {
    const box = $(name), keep = box.scrollTop;
    if (!nodes.length) { const p = document.createElement("p"); p.className = "empty"; p.textContent = empty; nodes = [p]; }
    box.replaceChildren(...nodes);
    box.scrollTop = keep;
  }
  function renderHabits(list) {
    const habits = (list.items || []).filter(i => ["[ ]", "[/]"].includes(i.status));
    const doneToday = i => [].concat((i.details || {}).done || []).some(v => String(v).slice(0, 10) === today);
    const done = habits.filter(doneToday).length;
    $("count-habits").textContent = habits.length ? fmt(t.habitCount, {done, total: habits.length}) : "";
    fill("habits", habits.map(i => infoRow(i.title, first(i, "project"),
      doneToday(i) ? ["pill-ok", t.habitDone] : ["pill-warn", t.habitOpen], i, "", i)), t.noHabits);
  }
  function renderMessages(day, notes) {
    const messages = day.messages || [], recent = notes.items || [];
    $("count-messages").textContent = messages.length ? t.messagesHeading + " " + messages.length : "";
    const nodes = [];
    if (messages.length) nodes.push(heading(t.messagesHeading), ...messages.map(r => infoRow(r.title, r.project || "", null, r, "", null)));
    if (recent.length) nodes.push(heading(t.notesHeading), ...recent.map(i => infoRow(i.title, first(i, "project"), null, i, "", i)));
    fill("messages", nodes, t.noMessages);
  }
  function renderDeadlines(day) {
    const refs = [...(day.due_today || []), ...(day.upcoming || [])]
      .sort((a, b) => String(a.due || "").localeCompare(String(b.due || "")));
    $("count-deadlines").textContent = refs.length ? String(refs.length) : "";
    fill("deadlines", refs.map(r => {
      const date = String(r.due || "").slice(0, 10);
      const left = Math.round((Date.parse(date) - Date.parse(today)) / 86400000);
      const item = r.kind === "T" ? findItem(r) : null;
      return infoRow(r.title, [date, r.project].filter(Boolean).join(" · "),
        Number.isFinite(left) ? [left <= 0 ? "pill-warn" : "pill-info", left <= 0 ? t.daysToday : fmt(t.daysLeft, {n: left})] : null,
        item ? Object.assign({}, r, item) : r, date, item);
    }), t.noDeadlines);
  }
  function renderSummary(day, all) {
    const done = (all.items || []).filter(i => i.status === "[x]" && first(i, "done").slice(0, 10) === today);
    const overdue = (day.overdue || []).filter(r => r.kind === "T");
    const projects = new Map();
    const count = (name, key) => {
      const row = projects.get(name || "") || {open: 0, overdue: 0, done: 0};
      row[key]++; projects.set(name || "", row);
    };
    items.forEach(i => count(first(i, "project"), "open"));
    overdue.forEach(r => count(r.project, "overdue"));
    done.forEach(i => count(first(i, "project"), "done"));
    const totals = document.createElement("div");
    totals.className = "totals";
    for (const [label, value] of [[t.doneToday, done.length], [t.overdue, overdue.length], [t.openTasks, items.length]]) {
      const cell = document.createElement("div"), number = document.createElement("strong"), name = document.createElement("span");
      number.textContent = String(value); name.textContent = label; cell.append(number, name); totals.append(cell);
    }
    const nodes = [totals];
    if (projects.size) nodes.push(heading(t.projectsHeading));
    for (const [name, row] of [...projects].sort((a, b) => b[1].overdue - a[1].overdue || b[1].open - a[1].open || a[0].localeCompare(b[0], lang))) {
      const line = document.createElement("div"), text = document.createElement("div"), s = document.createElement("small");
      line.className = "task"; text.className = "tt";
      text.append(document.createTextNode(name || t.noProject)); s.textContent = fmt(t.projectCounts, row); text.append(s);
      line.append(text); nodes.push(line);
    }
    fill("summary", nodes, "");
  }
  // Each block loads on its own, so one failing request leaves the others usable.
  function loadExtras(mine) {
    const date = "/api/command-center?date=" + today;
    const sources = {
      habits: [["/api/items?type=H"], renderHabits],
      messages: [[date + "&person=self", "/api/notes?limit=5"], renderMessages],
      deadlines: [[date + "&horizon=14"], renderDeadlines],
      summary: [[date, "/api/items?type=T"], renderSummary]
    };
    for (const [name, [paths, render]] of Object.entries(sources)) {
      if (layout.hidden.includes(name)) continue;
      Promise.all(paths.map(p => api(p)))
        .then(data => { if (mine === generation) render(...data); })
        .catch(e => {
          if (mine !== generation) return;
          $("count-" + name)?.replaceChildren();
          fill(name, [], t.error + e.message);
        });
    }
  }

  function addDays(iso, n) {
    const d = new Date(iso + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }
  async function load() {
    const mine = ++generation;
    try {
      const [day, agenda, list, elist, status] = await Promise.all([
        api("/api/command-center?date=" + today), api("/api/agenda?from=" + (mode === "month" ? monthRange().from : today) + "&to=" + (mode === "week" ? addDays(today, 6) : mode === "month" ? monthRange().to : today)),
        api("/api/items?type=T&open_only=true"), api("/api/items?type=E"),
        api("/api/status?person=self&active=true")]);
      if (mine !== generation) return;
      items = list.items || [];
      eventItems = elist.items || [];
      events = buildEvents(agenda.records || []);
      weekEvents = mode !== "day" ? buildWeek(agenda.records || []) : [];
      loaded = true; renderStatus(status); renderTimeline(); renderTasks(day); updateNext(wallNow());
      $("open-top").href = "/" + (lang === "ja" ? "?lang=ja" : "");
      $("open-planner").href = "/planner?date=" + today + (lang === "ja" ? "&lang=ja" : "");
      loadExtras(mine);
    } catch (e) { if (mine === generation) say(t.error + e.message); }
  }
  async function syncConfig() {
    const started = performance.now();
    try { const c = await api("/api/config"); today = c.today; acceptClock(c, started); } catch (_) {}
  }
  let binding = null, previewTimer = null, previewGeneration = 0;
  const syntax = () => $("capture-syntax").value;
  function resetPreview() {
    previewGeneration++;
    clearTimeout(previewTimer);
    binding = null;
    $("capture-preview").textContent = "";
    $("capture-form").querySelector("button").textContent = syntax() === "todo" ? t.preview : t.add;
  }
  const bitsOf = d => { const bits = []; Object.keys(d.details || {}).forEach(k => (d.details[k] || []).forEach(v => bits.push(k + ":" + v))); return bits.join(" "); };
  function livePreview() {
    resetPreview();
    const requestGeneration = previewGeneration;
    const text = $("capture-text").value.trim();
    if (!text || syntax() !== "quick") return;
    previewTimer = setTimeout(async () => {
      try {
        const d = await api("/api/quick/resolve", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({text})});
        if (requestGeneration !== previewGeneration) return;
        const bits = bitsOf(d);
        $("capture-preview").textContent = bits ? "→ " + d.title + "  " + bits : "";
      } catch (e) {
        if (requestGeneration === previewGeneration) $("capture-preview").textContent = e.message || "";
      }
    }, 200);
  }
  async function capture(event) {
    event.preventDefault();
    const input = $("capture-text"), text = input.value.trim();
    if (!text || pending || !writable) return;
    pending = true;
    const requestGeneration = previewGeneration;
    const needsPreview = syntax() === "todo" && binding?.text !== text;
    try {
      if (needsPreview) {
        const d = await api("/api/quick/resolve", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({text, syntax: "todo"})});
        if (requestGeneration !== previewGeneration) return;
        if (!d.context_token || !d.source_revision) throw new Error(t.noRevision);
        binding = {text, token: d.context_token, rev: d.source_revision};
        $("capture-preview").textContent = "→ " + d.title + "  " + bitsOf(d) + "  " + t.reviewFirst;
        $("capture-form").querySelector("button").textContent = t.confirmCapture;
        return;
      }
      if (syntax() === "todo") {
        await api("/api/items/capture", {method: "POST", headers: {"Content-Type": "application/json", "If-Match": binding.rev},
          body: JSON.stringify({text, syntax: "todo", context_token: binding.token, expected_source_revision: binding.rev})});
      } else {
        const snap = revision;
        await api("/api/items/capture", {expectedRevision: snap, method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({text, expected_source_revision: (snap || "").replace(/^"|"$/g, "")})});
      }
      if (requestGeneration === previewGeneration) { input.value = ""; resetPreview(); }
      say(t.captured);
      pending = false; await load();
    } catch (e) {
      const isCurrent = requestGeneration === previewGeneration;
      if (isCurrent) resetPreview();
      if (!needsPreview || isCurrent) say(e.message);
    } finally { pending = false; }
  }
  function stopTimers() { clearInterval(tickTimer); clearInterval(refreshTimer); tickTimer = refreshTimer = null; }
  function startTimers() {
    stopTimers();
    tick(); tickTimer = setInterval(tick, 1000);
    refreshTimer = setInterval(() => { syncConfig().then(load); }, REFRESH_MS);
  }
  // ---- Layout: per-browser arrangement of the screen blocks ----
  const EXTRAS = ["habits", "messages", "deadlines", "summary"];
  const BLOCKS = ["clock", "status", "next", "calendar", "tasks", "capture", ...EXTRAS];
  const FLEXIBLE = ["calendar", "tasks", ...EXTRAS];
  const RATIOS = ["balanced", "left", "right"], FONTS = ["s", "m", "l"];
  const BLOCK_FONTS = ["s", "m", "l", "xl"], ZOOM = {s: .9, m: 1, l: 1.2, xl: 1.45};
  const MIN_HEIGHT = 48, MAX_HEIGHT = 2000, MIN_SPLIT = 25, MAX_SPLIT = 75;
  const clamp = (v, low, high) => Math.min(high, Math.max(low, Math.round(v)));
  // Information blocks start hidden at the end of the right column.
  const preset = (left, right, hidden = [], ratio = "balanced", font = "m") => ({cols: [left, [...right, ...EXTRAS]], hidden: [...hidden, ...EXTRAS], ratio, font, split: null, heights: {}, fonts: {}});
  const PRESETS = {
    standard: preset(["clock", "status", "next", "calendar"], ["tasks", "capture"]),
    clock: preset(["clock", "status", "next"], ["calendar", "tasks", "capture"], ["capture"], "left", "l"),
    tasks: preset(["tasks", "capture"], ["clock", "status", "next", "calendar"], [], "left"),
    calendar: preset(["calendar"], ["clock", "status", "next", "tasks", "capture"], [], "left")
  };
  const copyLayout = v => ({cols: v.cols.map(c => [...c]), hidden: [...v.hidden], ratio: v.ratio, font: v.font, split: v.split, heights: {...v.heights}, fonts: {...v.fonts}});
  const validLayout = v => Boolean(v) && Array.isArray(v.cols) && v.cols.length === 2 && v.cols.every(Array.isArray) &&
    v.cols.flat().length === BLOCKS.length && BLOCKS.every(b => v.cols.flat().includes(b)) &&
    Array.isArray(v.hidden) && v.hidden.every(b => BLOCKS.includes(b)) && RATIOS.includes(v.ratio) && FONTS.includes(v.font);
  // Sizes are optional so an arrangement saved before they existed still loads;
  // an unusable size is dropped without discarding the arrangement.
  // Blocks added after an arrangement was saved join it hidden.
  function addMissing(v) {
    if (!Array.isArray(v?.cols) || v.cols.length !== 2 || !v.cols.every(Array.isArray) || !Array.isArray(v.hidden)) return v;
    const missing = EXTRAS.filter(b => !v.cols.flat().includes(b));
    return {...v, cols: [v.cols[0], [...v.cols[1], ...missing]], hidden: [...v.hidden, ...missing]};
  }
  function readLayout(saved) {
    const v = addMissing(saved);
    if (!validLayout(v)) return null;
    const number = (n, low, high) => Number.isFinite(n) ? clamp(n, low, high) : null;
    const entries = (o, read) => Object.fromEntries(BLOCKS.map(b => [b, read(o?.[b])]).filter(e => e[1] !== null));
    return copyLayout({...v, split: number(v.split, MIN_SPLIT, MAX_SPLIT),
      heights: entries(v.heights, n => number(n, MIN_HEIGHT, MAX_HEIGHT)),
      fonts: entries(v.fonts, f => BLOCK_FONTS.includes(f) ? f : null)});
  }
  let layout = copyLayout(PRESETS.standard), loaded = false, layoutInUrl = false;
  const zoomOf = name => ZOOM[layout.fonts[name] || layout.font];
  function saveLayout() {
    if (layoutInUrl) layoutUrl.write(layout);
    else {
      try { localStorage.setItem("desk-layout", JSON.stringify(layout)); } catch (_) {}
    }
  }
  function sizeZone(name) {
    const zone = $(name + "-zone"), height = layout.heights[name], zoom = zoomOf(name);
    zone.style.zoom = zoom === 1 ? "" : zoom;
    zone.classList.toggle("sized", Boolean(height));
    // The stored height is in screen pixels; CSS lengths inside a zoomed block are scaled.
    if (height) zone.style.setProperty("--block-height", height / zoom + "px");
    else zone.style.removeProperty("--block-height");
  }
  function currentSplit() {
    const left = $("col-0").offsetWidth, right = $("col-1").offsetWidth;
    return left + right ? clamp(left * 100 / (left + right), MIN_SPLIT, MAX_SPLIT) : 50;
  }
  function placeColumnSplitter() {
    const bar = $("col-splitter"), left = $("col-0");
    bar.hidden = $("cols").classList.contains("single");
    if (bar.hidden) return;
    bar.style.left = (left.offsetLeft + left.offsetWidth + $("col-1").offsetLeft) / 2 + "px";
    bar.setAttribute("aria-valuenow", String(currentSplit()));
  }
  function sizeColumns() {
    const cols = $("cols");
    cols.toggleAttribute("data-split", layout.split !== null);
    if (layout.split !== null) {
      cols.style.setProperty("--left", layout.split + "fr");
      cols.style.setProperty("--right", 100 - layout.split + "fr");
    }
    placeColumnSplitter();
  }
  // Pointer and keyboard resizing share one path: change, show, then save once.
  function resizer(bar, vertical, begin, apply, reset) {
    const finish = () => { saveLayout(); if (loaded) renderTimeline(); };
    bar.onpointerdown = e => {
      if (e.button) return;
      e.preventDefault();
      const origin = vertical ? e.clientX : e.clientY, from = begin();
      let moved = false;
      bar.setPointerCapture(e.pointerId);
      bar.onpointermove = ev => {
        const by = (vertical ? ev.clientX : ev.clientY) - origin;
        if (by || moved) { moved = true; apply(from, by); }
      };
      bar.onpointerup = bar.onpointercancel = () => {
        bar.onpointermove = bar.onpointerup = bar.onpointercancel = null;
        if (moved) finish();
      };
    };
    bar.onkeydown = e => {
      const keys = vertical ? {ArrowLeft: -1, ArrowRight: 1} : {ArrowUp: -1, ArrowDown: 1};
      if (keys[e.key]) { e.preventDefault(); apply(begin(), keys[e.key] * 16); finish(); }
      else if (e.key === "Enter" || e.key === "Home") { e.preventDefault(); reset(); finish(); }
    };
    bar.ondblclick = () => { reset(); finish(); };
  }
  function blockSplitter(name) {
    const bar = document.createElement("div");
    bar.className = "splitter row-splitter"; bar.tabIndex = 0; bar.dataset.block = name;
    bar.setAttribute("role", "separator"); bar.setAttribute("aria-orientation", "horizontal");
    bar.setAttribute("aria-label", fmt(t.splitBlock, {name: t.blockNames[name]}));
    resizer(bar, false, () => $(name + "-zone").getBoundingClientRect().height,
      (from, by) => { layout.heights[name] = clamp(from + by, MIN_HEIGHT, MAX_HEIGHT); sizeZone(name); },
      () => { delete layout.heights[name]; sizeZone(name); });
    return bar;
  }
  function initColumnSplitter() {
    resizer($("col-splitter"), true,
      () => ({split: layout.split ?? currentSplit(), width: $("col-0").offsetWidth + $("col-1").offsetWidth}),
      (from, by) => { layout.split = clamp(from.split + by * 100 / (from.width || 1), MIN_SPLIT, MAX_SPLIT); sizeColumns(); },
      () => { layout.split = null; sizeColumns(); });
    $("col-splitter").setAttribute("aria-label", t.splitColumns);
    new ResizeObserver(placeColumnSplitter).observe($("cols"));
  }
  function applyLayout() {
    document.querySelectorAll(".row-splitter").forEach(n => n.remove());
    layout.cols.forEach((names, index) => {
      const column = $("col-" + index);
      const shown = names.filter(n => !layout.hidden.includes(n));
      const flexible = shown.some(n => FLEXIBLE.includes(n) && !layout.heights[n]);
      for (const name of names) {
        const zone = $(name + "-zone");
        zone.hidden = !shown.includes(name);
        column.append(zone);
        if (!zone.hidden && name !== shown.at(-1)) column.append(blockSplitter(name));
        sizeZone(name);
      }
      if (names.includes("clock")) $("clock-zone").classList.toggle("grow", !flexible);
      column.hidden = !shown.length;
    });
    $("cols").classList.toggle("single", $("col-0").hidden || $("col-1").hidden);
    $("cols").dataset.ratio = layout.ratio;
    $("desk").dataset.font = layout.font;
    document.querySelector(".skip").hidden = layout.hidden.includes("tasks");
    sizeColumns();
    if (loaded) renderTimeline();
  }
  function changeLayout(next, focus) {
    const added = EXTRAS.some(n => layout.hidden.includes(n) && !next.hidden.includes(n));
    layout = next;
    saveLayout();
    applyLayout();
    if (added && loaded) load();
    renderLayoutDialog(focus);
  }
  function renderLayoutDialog(focus) {
    const box = $("layout-content"), keep = box.scrollTop;
    const button = (key, text, label, action, disabled) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "go"; b.textContent = text; b.dataset.key = key; b.disabled = Boolean(disabled);
      b.setAttribute("aria-label", label); b.onclick = action;
      return b;
    };
    const select = (key, label, options, value, action) => {
      const s = document.createElement("select");
      s.dataset.key = key;
      for (const [v, text] of options) { const o = document.createElement("option"); o.value = v; o.textContent = text; s.append(o); }
      s.value = value; s.onchange = () => action(s.value);
      return detailField(label, s);
    };
    const edit = (key, change) => { const next = copyLayout(layout); change(next); changeLayout(next, key); };
    const same = JSON.stringify(layout);
    const current = Object.keys(PRESETS).find(n => JSON.stringify(PRESETS[n]) === same) || "";
    const presets = Object.keys(PRESETS).map(n => [n, t.presetNames[n]]);
    if (!current) presets.unshift(["", t.layoutCustom]);
    const note = document.createElement("p");
    note.className = "muted";
    note.setAttribute("role", "status");
    note.textContent = layoutInUrl ? layoutCopy.scoped : t.layoutShow;
    const nodes = [detailFields(
      select("preset", t.layoutPreset, presets, current, v => { if (PRESETS[v]) changeLayout(copyLayout(PRESETS[v]), "preset"); }),
      select("ratio", t.layoutRatio, RATIOS.map(v => [v, t.ratioNames[v]]), layout.ratio, v => edit("ratio", n => { n.ratio = v; n.split = null; })),
      select("font", t.layoutFont, FONTS.map(v => [v, t.fontNames[v]]), layout.font, v => edit("font", n => { n.font = v; }))), note];
    layout.cols.forEach((names, c) => {
      const group = document.createElement("fieldset"), legend = document.createElement("legend");
      group.className = "layout-col"; legend.textContent = t.layoutColumns[c]; group.append(legend);
      names.forEach((name, i) => {
        const row = document.createElement("div"), label = document.createElement("label"), check = document.createElement("input");
        row.className = "layout-row"; check.type = "checkbox"; check.checked = !layout.hidden.includes(name); check.dataset.key = name;
        check.onchange = () => edit(name, n => { n.hidden = check.checked ? n.hidden.filter(x => x !== name) : [...n.hidden, name]; });
        label.append(check, t.blockNames[name]);
        const shift = by => edit(name + (by < 0 ? "-up" : "-down"), n => { const list = n.cols[c]; [list[i], list[i + by]] = [list[i + by], list[i]]; });
        const other = c ? t.layoutLeft : t.layoutRight;
        const size = document.createElement("select");
        size.dataset.key = name + "-font"; size.setAttribute("aria-label", t.blockNames[name] + ": " + t.layoutBlockFont);
        for (const v of ["", ...BLOCK_FONTS]) {
          const o = document.createElement("option");
          o.value = v; o.textContent = !v ? t.fontDefault : v === "xl" ? t.fontXl : t.fontNames[v]; size.append(o);
        }
        size.value = layout.fonts[name] || "";
        size.onchange = () => edit(name + "-font", n => { if (size.value) n.fonts[name] = size.value; else delete n.fonts[name]; });
        row.append(label, size,
          button(name + "-up", "↑", t.blockNames[name] + ": " + t.layoutUp, () => shift(-1), i === 0),
          button(name + "-down", "↓", t.blockNames[name] + ": " + t.layoutDown, () => shift(1), i === names.length - 1),
          button(name + "-move", c ? "←" : "→", t.blockNames[name] + ": " + other,
            () => edit(name + "-move", n => { n.cols[c].splice(i, 1); n.cols[1 - c].push(name); })));
        group.append(row);
      });
      nodes.push(group);
    });
    const actions = document.createElement("div");
    actions.className = "layout-actions";
    actions.append(button("swap", t.layoutSwap, t.layoutSwap, () => edit("swap", n => { n.cols.reverse(); if (n.split !== null) n.split = 100 - n.split; })),
      button("auto", t.layoutAuto, t.layoutAuto, () => edit("auto", n => { n.heights = {}; n.split = null; })),
      button("share", layoutCopy.share, layoutCopy.share, () => {
        layoutInUrl = true;
        saveLayout();
        note.textContent = layoutCopy.linked;
      }),
      button("reset", t.layoutReset, t.layoutReset, () => changeLayout(copyLayout(PRESETS.standard), "reset")));
    nodes.push(actions);
    box.replaceChildren(...nodes);
    box.scrollTop = keep;
    if (!focus) return;
    // A button that became disabled hands focus to its block's checkbox.
    const find = key => box.querySelector('[data-key="' + key + '"]');
    const target = find(focus);
    (target && !target.disabled ? target : find(focus.split("-")[0]))?.focus();
  }
  function initLayout() {
    const wanted = params.get("preset");
    const linked = readLayout(layoutUrl.read(params));
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem("desk-layout")); } catch (_) {}
    const presetLayout = Object.hasOwn(PRESETS, wanted || "") ? copyLayout(PRESETS[wanted]) : null;
    layoutInUrl = Boolean(linked || presetLayout);
    layout = linked || presetLayout || readLayout(saved) || layout;
    initColumnSplitter();
    applyLayout();
    $("layout-open").onclick = () => { renderLayoutDialog(); $("layout-dialog").showModal(); $("layout-content").scrollTop = 0; $("layout-close").focus(); };
    $("layout-close").onclick = () => $("layout-dialog").close();
  }
  const THEMES = ["auto", "dark", "light"];
  function applyTheme(m) {
    if (m === "auto") document.documentElement.removeAttribute("data-theme"); else document.documentElement.setAttribute("data-theme", m);
    const b = $("theme-toggle"); if (b) { b.textContent = t["theme" + m[0].toUpperCase() + m.slice(1)]; b.dataset.mode = m; }
  }
  function initTheme() {
    let m = "auto"; try { m = localStorage.getItem("desk-theme") || "auto"; } catch (_) {}
    if (!THEMES.includes(m)) m = "auto";
    applyTheme(m);
    $("theme-toggle").onclick = () => { const n = THEMES[(THEMES.indexOf($("theme-toggle").dataset.mode) + 1) % 3]; try { localStorage.setItem("desk-theme", n); } catch (_) {} applyTheme(n); };
  }
  function initFullscreen() {
    const b = $("fullscreen-toggle"), root = document.documentElement;
    if (!document.fullscreenEnabled || !root.requestFullscreen) return;
    const sync = () => {
      const on = Boolean(document.fullscreenElement);
      b.textContent = on ? t.fullscreenOff : t.fullscreenOn;
      b.setAttribute("aria-pressed", String(on));
    };
    b.onclick = () => (document.fullscreenElement ? document.exitFullscreen() : root.requestFullscreen()).catch(() => say(t.fullscreenFailed));
    document.addEventListener("fullscreenchange", sync);
    sync();
    b.hidden = false;
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
    $("capture-text").oninput = livePreview; $("capture-syntax").onchange = livePreview;
    initTheme();
    initFullscreen();
    initLayout();
    clockView = DeskClock.create({lang, field: detailField, nextEvent: now => events.find(e => e.time && e.time > now)});
    $("status-card").onclick = showStatusDialog;
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
