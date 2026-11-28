// ---- Clock block: per-browser display settings (localStorage "desk-clock") ----
// Times are the workspace wall clock: a Date whose UTC fields read as that clock.
const DeskClock = (() => {
  "use strict";
  const copy = {
    en: {button: "Clock", title: "Clock display", close: "Close", note: "Settings are saved in this browser. Times use the workspace clock.",
      style: "Style", styles: {digital: "Digital", large: "Large digital", analog: "Analog"}, size: "Size", sizes: {s: "Small", m: "Medium", l: "Large", xl: "Extra large"},
      hour: "Hour format", hours: {"24": "24-hour", "12": "12-hour"}, seconds: "Show seconds", date: "Date format",
      dates: {standard: "Standard", long: "With year", iso: "YYYY-MM-DD", none: "Hidden", custom: "Custom"}, format: "Custom format",
      formatHelp: "Tokens: YYYY MM M DD D dddd ddd HH H hh h mm ss A GGGG WW z Z; put plain text in [brackets].", badFormat: "That format is not valid.",
      weekday: "Show weekday", week: "Show week number", dayOfYear: "Show day of year", weekText: "Week {n}", dayText: "Day {n}",
      zones: "Other time zones", zone: "Time zone (e.g. Europe/London)", addZone: "Add time zone", removeZone: "Remove {zone}", badZone: "Unknown time zone.", dupZone: "That time zone is already shown.", manyZones: "Up to {n} time zones.",
      progress: "Progress bars", progressNames: {day: "Today", week: "This week", year: "This year"},
      countdown: "Countdown to", countdownLabel: "Countdown name", dateGroup: "Date", countdownGroup: "Countdown", nextEvent: "Show time until today's next event", untilNext: "Until {name}", noNext: "No more events today",
      target: "Target", left: "{span} left", passed: "{span} ago", spanDays: "{d} d {h} h {m} min", spanHours: "{h} h {m} min", spanMin: "{m} min", reset: "Reset clock"},
    ja: {button: "時計", title: "時計の表示", close: "閉じる", note: "設定はこのブラウザに保存されます。時刻はワークスペースの時計が基準です。",
      style: "見た目", styles: {digital: "デジタル", large: "デジタル（特大）", analog: "アナログ"}, size: "大きさ", sizes: {s: "小", m: "中", l: "大", xl: "特大"},
      hour: "時刻の形式", hours: {"24": "24時間", "12": "12時間"}, seconds: "秒を表示する", date: "日付の形式",
      dates: {standard: "標準", long: "年も表示", iso: "YYYY-MM-DD", none: "非表示", custom: "自由書式"}, format: "自由書式",
      formatHelp: "使える記号: YYYY MM M DD D dddd ddd HH H hh h mm ss A GGGG WW z Z。そのまま表示する文字は [ ] で囲みます。", badFormat: "書式が正しくありません。",
      weekday: "曜日を表示する", week: "週番号を表示する", dayOfYear: "通日を表示する", weekText: "第{n}週", dayText: "年内 {n}日目",
      zones: "他のタイムゾーン", zone: "タイムゾーン（例: Europe/London）", addZone: "タイムゾーンを追加", removeZone: "{zone} を削除", badZone: "不明なタイムゾーンです。", dupZone: "すでに表示しています。", manyZones: "タイムゾーンは{n}件までです。",
      progress: "経過バー", progressNames: {day: "今日", week: "今週", year: "今年"},
      countdown: "カウントダウン先", countdownLabel: "カウントダウンの名前", dateGroup: "日付", countdownGroup: "カウントダウン", nextEvent: "今日の次の予定までの時間を表示する", untilNext: "{name} まで", noNext: "今日の予定はもうありません",
      target: "目標", left: "あと {span}", passed: "{span} 経過", spanDays: "{d}日 {h}時間 {m}分", spanHours: "{h}時間 {m}分", spanMin: "{m}分", reset: "時計を標準に戻す"}
  };
  const TOKENS = ["YYYY", "YY", "MMMM", "MMM", "MM", "M", "DD", "D", "dddd", "ddd", "dd", "d", "E", "HH", "H", "hh", "h", "mm", "m", "ss", "s", "A", "a", "GGGG", "WW", "W", "ZZ", "Z", "z"].sort((a, b) => b.length - a.length);
  const STYLES = ["digital", "large", "analog"], SIZES = ["s", "m", "l", "xl"], SCALE = {s: .75, m: 1, l: 1.3, xl: 1.65};
  const DATES = ["standard", "long", "iso", "none", "custom"], BARS = ["day", "week", "year"], MAX_ZONES = 6;
  const DEFAULTS = () => ({style: "digital", size: "m", hour: "24", seconds: true, date: "standard", format: "YYYY-MM-DD ddd",
    weekday: true, week: true, dayOfYear: true, zones: [], progress: [], target: "", label: "", nextEvent: false});
  const fmt = (s, v) => s.replace(/\{(\w+)\}/g, (_, k) => v[k]);
  const pad = n => String(n).padStart(2, "0");

  function parseFormat(format) {
    if (typeof format !== "string" || !format || format.length > 128 || /[\x00-\x1f\x7f]/.test(format)) return null;
    const parts = [];
    for (let i = 0; i < format.length;) {
      if (format[i] === "[") {
        const end = format.indexOf("]", i + 1);
        if (end < 0 || format.slice(i + 1, end).includes("[")) return null;
        parts.push({literal: format.slice(i + 1, end)});
        i = end + 1;
      } else if (/[A-Za-z]/.test(format[i])) {
        const token = TOKENS.find(v => format.startsWith(v, i));
        if (!token) return null;
        parts.push({token});
        i += token.length;
      } else {
        if (format[i] === "]") return null;
        parts.push({literal: format[i++]});
      }
    }
    return parts;
  }
  function validZone(zone) {
    if (typeof zone !== "string" || !zone || zone.length > 128 || !/^[A-Za-z][A-Za-z0-9_+./-]*$/.test(zone)) return false;
    try { new Intl.DateTimeFormat("en-US", {timeZone: zone}); return true; } catch (_) { return false; }
  }
  function validTarget(value) {
    if (typeof value !== "string" || !/^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(value)) return false;
    const at = Date.parse(value + "Z");
    return Number.isFinite(at) && new Date(at).toISOString().slice(0, 16) === value;
  }
  // Each unusable value falls back on its own, keeping the rest of the settings.
  function read(raw) {
    const out = DEFAULTS(), v = raw && typeof raw === "object" ? raw : {};
    const pick = (key, ok) => { if (ok(v[key])) out[key] = v[key]; };
    pick("style", x => STYLES.includes(x)); pick("size", x => SIZES.includes(x)); pick("hour", x => x === "24" || x === "12");
    pick("date", x => DATES.includes(x)); pick("format", x => Boolean(parseFormat(x)));
    for (const key of ["seconds", "weekday", "week", "dayOfYear", "nextEvent"]) pick(key, x => typeof x === "boolean");
    if (Array.isArray(v.zones)) out.zones = [...new Set(v.zones.filter(validZone))].slice(0, MAX_ZONES);
    if (Array.isArray(v.progress)) out.progress = BARS.filter(b => v.progress.includes(b));
    pick("target", validTarget);
    pick("label", x => typeof x === "string" && x.length <= 80);
    return out;
  }
  function isoWeek(d) {
    const x = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    x.setUTCDate(x.getUTCDate() + 4 - (x.getUTCDay() || 7));
    return {year: x.getUTCFullYear(), week: Math.ceil(((x - Date.UTC(x.getUTCFullYear(), 0, 1)) / 86400000 + 1) / 7)};
  }
  const dayOfYear = d => Math.floor((Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - Date.UTC(d.getUTCFullYear(), 0, 0)) / 86400000);
  function progress(d) {
    const day = (d.getUTCHours() * 3600 + d.getUTCMinutes() * 60 + d.getUTCSeconds()) / 86400;
    const year = d.getUTCFullYear(), days = (Date.UTC(year + 1, 0, 1) - Date.UTC(year, 0, 1)) / 86400000;
    return {day, week: ((d.getUTCDay() + 6) % 7 + day) / 7, year: (dayOfYear(d) - 1 + day) / days};
  }

  function create({lang, field, nextEvent}) {
    const t = copy[lang], locale = lang === "ja" ? "ja-JP" : "en-US";
    const $ = id => document.getElementById(id);
    let settings = DEFAULTS(), last = null, hands = null;
    try { settings = read(JSON.parse(localStorage.getItem("desk-clock"))); } catch (_) {}
    const zoneFormats = new Map();
    const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
    const set = (node, text) => { if (node.textContent !== text) node.textContent = text; node.hidden = !text; };
    const intl = (d, options) => new Intl.DateTimeFormat(locale, {...options, timeZone: "UTC"}).format(d);
    const hourText = h => settings.hour === "12" ? String(h % 12 || 12) : pad(h);
    const period = h => settings.hour !== "12" ? "" : h < 12 ? (lang === "ja" ? "午前" : "AM") : (lang === "ja" ? "午後" : "PM");

    function custom(d, offset) {
      const h = d.getUTCHours(), month = d.getUTCMonth() + 1, w = isoWeek(d);
      const sign = offset < 0 ? "-" : "+", oh = pad(Math.floor(Math.abs(offset) / 60)), om = pad(Math.abs(offset) % 60);
      const values = {
        YYYY: String(d.getUTCFullYear()), YY: pad(d.getUTCFullYear() % 100), MMMM: intl(d, {month: "long"}), MMM: intl(d, {month: "short"}), MM: pad(month), M: String(month),
        DD: pad(d.getUTCDate()), D: String(d.getUTCDate()), dddd: intl(d, {weekday: "long"}), ddd: intl(d, {weekday: "short"}), dd: intl(d, {weekday: lang === "ja" ? "narrow" : "short"}).slice(0, 2), d: String(d.getUTCDay()), E: String(d.getUTCDay() || 7),
        HH: pad(h), H: String(h), hh: pad(h % 12 || 12), h: String(h % 12 || 12), mm: pad(d.getUTCMinutes()), m: String(d.getUTCMinutes()), ss: pad(d.getUTCSeconds()), s: String(d.getUTCSeconds()),
        A: h < 12 ? "AM" : "PM", a: h < 12 ? "am" : "pm", GGGG: String(w.year), WW: pad(w.week), W: String(w.week),
        Z: sign + oh + ":" + om, ZZ: sign + oh + om, z: "UTC" + sign + oh + ":" + om
      };
      return parseFormat(settings.format).map(p => p.token ? values[p.token] : p.literal).join("");
    }
    function dateText(d, offset) {
      const weekday = settings.weekday ? {weekday: "short"} : {};
      if (settings.date === "none") return "";
      if (settings.date === "custom") return custom(d, offset);
      if (settings.date === "iso") return d.toISOString().slice(0, 10) + (settings.weekday ? " " + intl(d, {weekday: "short"}) : "");
      return intl(d, {...(settings.date === "long" ? {year: "numeric"} : {}), month: "long", day: "numeric", ...weekday});
    }
    function span(ms) {
      const total = Math.floor(ms / 60000), d = Math.floor(total / 1440), h = Math.floor(total % 1440 / 60), m = total % 60;
      return d ? fmt(t.spanDays, {d, h, m}) : h ? fmt(t.spanHours, {h, m}) : fmt(t.spanMin, {m});
    }

    function dial() {
      const ns = "http://www.w3.org/2000/svg";
      const shape = (tag, attributes) => { const n = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attributes)) n.setAttribute(k, v); return n; };
      const svg = shape("svg", {viewBox: "0 0 100 100", class: "dial", "aria-hidden": "true"});
      svg.append(shape("circle", {cx: 50, cy: 50, r: 48, class: "face"}));
      for (let i = 0; i < 12; i++) svg.append(shape("line", {x1: 50, y1: 5, x2: 50, y2: i % 3 ? 9 : 13, class: "mark", transform: "rotate(" + i * 30 + " 50 50)"}));
      const hand = (cls, top) => { const n = shape("line", {x1: 50, y1: 54, x2: 50, y2: top, class: "hand " + cls}); svg.append(n); return n; };
      hands = {hour: hand("hour", 26), minute: hand("minute", 14), second: settings.seconds ? hand("second", 10) : null};
      return svg;
    }

    // Rebuild only what the settings decide; tick() then fills in the values.
    function build() {
      const zone = $("clock-zone"), face = $("clock");
      zone.dataset.style = settings.style;
      zone.style.setProperty("--clock-scale", SCALE[settings.size]);
      hands = null;
      face.removeAttribute("aria-label");
      face.replaceChildren(...(settings.style === "analog" ? [dial()] : []));
      $("clock-zones").replaceChildren(...settings.zones.map(name => {
        const row = el("li");
        row.dataset.zone = name;
        row.append(el("span", "zone-name", name.split("/").pop().replaceAll("_", " ")), el("span", "zone-day muted"), el("strong", "zone-time"));
        row.title = name;
        return row;
      }));
      $("clock-bars").replaceChildren(...settings.progress.map(name => {
        const row = el("li"), bar = el("div", "bar"), fill = el("b");
        row.dataset.bar = name;
        bar.setAttribute("role", "progressbar"); bar.setAttribute("aria-label", t.progressNames[name]);
        bar.setAttribute("aria-valuemin", "0"); bar.setAttribute("aria-valuemax", "100");
        bar.append(fill);
        row.append(el("span", "", t.progressNames[name]), bar, el("span", "bar-value"));
        return row;
      }));
      $("clock-zones").hidden = !settings.zones.length;
      $("clock-bars").hidden = !settings.progress.length;
      if (last) render(last.d, last.instant, last.offset);
    }

    function render(d, instant, offset) {
      last = {d, instant, offset};
      const h = d.getUTCHours(), m = d.getUTCMinutes(), s = d.getUTCSeconds(), face = $("clock");
      const time = hourText(h) + ":" + pad(m);
      if (hands) {
        hands.hour.setAttribute("transform", "rotate(" + ((h % 12) * 30 + m / 2) + " 50 50)");
        hands.minute.setAttribute("transform", "rotate(" + (m * 6 + s / 10) + " 50 50)");
        hands.second?.setAttribute("transform", "rotate(" + s * 6 + " 50 50)");
        face.setAttribute("aria-label", (period(h) + " " + time).trim());
      } else {
        const nodes = [time];
        if (settings.seconds) nodes.push(el("small", "sec-part", pad(s)));
        if (settings.hour === "12") nodes.push(el("small", "period", period(h)));
        face.replaceChildren(...nodes);
      }
      set($("clock-date"), dateText(d, offset));
      const week = [];
      if (settings.week) week.push(fmt(t.weekText, {n: isoWeek(d).week}));
      if (settings.dayOfYear) week.push(fmt(t.dayText, {n: dayOfYear(d)}));
      set($("clock-week"), week.length ? [d.getUTCFullYear(), ...week].join(" · ") : "");
      for (const row of $("clock-zones").children) {
        const name = row.dataset.zone;
        if (!zoneFormats.has(name)) zoneFormats.set(name, new Intl.DateTimeFormat("en-US", {timeZone: name, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"}));
        const p = Object.fromEntries(zoneFormats.get(name).formatToParts(instant).map(x => [x.type, x.value]));
        const hour = Number(p.hour) % 24;
        const days = Math.round((Date.UTC(p.year, p.month - 1, p.day) - Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())) / 86400000);
        row.querySelector(".zone-day").textContent = days ? (days > 0 ? "+" : "") + days : "";
        row.querySelector(".zone-time").textContent = (period(hour) + " " + hourText(hour) + ":" + p.minute).trim();
      }
      const done = progress(d);
      for (const row of $("clock-bars").children) {
        const percent = Math.floor(done[row.dataset.bar] * 100);
        row.querySelector("b").style.width = percent + "%";
        row.querySelector(".bar").setAttribute("aria-valuenow", String(percent));
        row.querySelector(".bar-value").textContent = percent + "%";
      }
      let target = "";
      if (settings.target) {
        const diff = Date.parse(settings.target + "Z") - d.getTime();
        // Round the remaining time up so it reaches zero only at the target.
        target = (settings.label || t.target) + ": " + (diff > 0 ? fmt(t.left, {span: span(diff + 59999)}) : fmt(t.passed, {span: span(-diff)}));
      }
      set($("clock-countdown"), target);
      let next = "";
      if (settings.nextEvent) {
        const found = nextEvent(pad(h) + ":" + pad(m));
        if (!found) next = found === null ? "" : t.noNext; // null: not loaded yet
        else {
          const [eh, em] = found.time.split(":").map(Number);
          next = fmt(t.untilNext, {name: found.title}) + ": " + fmt(t.left, {span: span(((eh - h) * 60 + em - m) * 60000)});
        }
      }
      set($("clock-next"), next);
    }

    function change(patch, focus) {
      settings = read({...settings, ...patch});
      try { localStorage.setItem("desk-clock", JSON.stringify(settings)); } catch (_) {}
      build();
      renderDialog(focus);
    }

    function renderDialog(focus) {
      const box = $("clock-content"), keep = box.scrollTop;
      const keyed = (node, key) => { node.dataset.key = key; return node; };
      const select = (key, label, options, names) => {
        const s = keyed(el("select"), key);
        for (const v of options) { const o = el("option", "", names[v]); o.value = v; s.append(o); }
        s.value = settings[key]; s.onchange = () => change({[key]: s.value}, key);
        return field(label, s);
      };
      const check = (key, label, checked, apply) => {
        const input = keyed(el("input"), key);
        input.type = "checkbox"; input.checked = checked; input.onchange = () => apply(input.checked);
        const row = el("label", "clock-check"); row.append(input, label);
        return row;
      };
      const toggle = (key, label) => check(key, label, settings[key], on => change({[key]: on}, key));
      const text = (key, label, type, apply) => {
        const input = keyed(el("input"), key);
        input.type = type; input.value = settings[key] ?? "";
        input.onchange = () => apply(input.value);
        return field(label, input);
      };
      const group = (title, ...nodes) => { const g = el("fieldset", "layout-col"); g.append(el("legend", "", title), ...nodes); return g; };
      const error = el("p", "clock-error"); error.setAttribute("role", "alert");
      const grid = (...nodes) => { const g = el("div", "detail-fields"); g.append(...nodes); return g; };

      const dateNodes = [grid(select("date", t.date, DATES, t.dates))];
      if (settings.date === "custom") {
        const input = text("format", t.format, "text", value => {
          if (parseFormat(value)) change({format: value}, "format"); else error.textContent = t.badFormat;
        });
        dateNodes.push(input, el("p", "muted", t.formatHelp));
      }
      dateNodes.push(toggle("weekday", t.weekday), toggle("week", t.week), toggle("dayOfYear", t.dayOfYear));

      const zoneRows = settings.zones.map((name, i) => {
        const row = el("div", "layout-row"), remove = keyed(el("button", "go", "×"), "zone-" + i);
        remove.type = "button"; remove.setAttribute("aria-label", fmt(t.removeZone, {zone: name}));
        remove.onclick = () => change({zones: settings.zones.filter(z => z !== name)}, "zone");
        row.append(el("label", "", name), remove);
        return row;
      });
      const zoneInput = keyed(el("input"), "zone");
      zoneInput.setAttribute("list", "clock-zone-list"); zoneInput.autocomplete = "off";
      const list = el("datalist"); list.id = "clock-zone-list";
      for (const name of Intl.supportedValuesOf?.("timeZone") || []) { const o = el("option"); o.value = name; list.append(o); }
      const add = keyed(el("button", "go", t.addZone), "zone-add"); add.type = "button";
      const addZone = () => {
        const name = zoneInput.value.trim();
        if (!validZone(name)) error.textContent = t.badZone;
        else if (settings.zones.includes(name)) error.textContent = t.dupZone;
        else if (settings.zones.length >= MAX_ZONES) error.textContent = fmt(t.manyZones, {n: MAX_ZONES});
        else change({zones: [...settings.zones, name]}, "zone");
      };
      add.onclick = addZone;
      zoneInput.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); addZone(); } };

      const bars = BARS.map(name => check("bar-" + name, t.progressNames[name], settings.progress.includes(name),
        on => change({progress: on ? [...settings.progress, name] : settings.progress.filter(x => x !== name)}, "bar-" + name)));
      const label = text("label", t.countdownLabel, "text", value => change({label: value.slice(0, 80)}, "label"));
      const target = text("target", t.countdown, "datetime-local", value => change({target: value.slice(0, 16)}, "target"));
      const reset = keyed(el("button", "go", t.reset), "reset"); reset.type = "button";
      reset.onclick = () => change(DEFAULTS(), "reset");
      const actions = el("div", "layout-actions"); actions.append(reset);

      box.replaceChildren(
        el("p", "muted", t.note), error,
        grid(select("style", t.style, STYLES, t.styles), select("size", t.size, SIZES, t.sizes), select("hour", t.hour, ["24", "12"], t.hours)),
        toggle("seconds", t.seconds),
        group(t.dateGroup, ...dateNodes),
        group(t.zones, ...zoneRows, field(t.zone, zoneInput), list, add),
        group(t.progress, ...bars),
        group(t.countdownGroup, grid(label, target), toggle("nextEvent", t.nextEvent)),
        actions);
      box.scrollTop = keep;
      if (focus) box.querySelector('[data-key="' + focus + '"]')?.focus();
    }

    $("clock-open").textContent = t.button;
    $("clock-settings-heading").textContent = t.title;
    $("clock-close").textContent = t.close;
    $("clock-open").onclick = () => { renderDialog(); $("clock-dialog").showModal(); $("clock-content").scrollTop = 0; $("clock-close").focus(); };
    $("clock-close").onclick = () => $("clock-dialog").close();
    build();
    return {render};
  }
  return {create, read, parseFormat, validZone, progress};
})();
