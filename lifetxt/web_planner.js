(() => {
  "use strict";
  const copy={en:{detType:"Type",detStatus:"Status",detWhen:"When",detTitle:"Title",detDue:"Due date",detChangeDue:"Change due date",detEdit:"Edit all fields",detDetails:"Details (key:value per line)",detSave:"Save",detReqDate:"Choose a date.",detDoneAt:"Completion date and time",detDoneNow:"Complete now",detDoneAt2:"Complete at selected time",detMarkDone:"Mark as done",detSaved:"Saved.",skip:"Skip to Planner",web:"Full Web UI",eyebrow:"Your day, in one place",title:"Day Planner",weekTitle:"Week Planner",today:"Today",choose:"Choose date",day:"Day",week:"Week",previousDay:"Previous day",nextDay:"Next day",previousWeek:"Previous week",nextWeek:"Next week",weekOf:"Week of",selected:"Selected",todayMarker:"TODAY",past:"Past",todayState:"Today",future:"Future",schedule:"Schedule",tasks:"Tasks",habits:"Habits",habitCue:"Cue",habitMinimum:"Minimum version",habitRecordMinimum:"Record minimum",habitMinimumRecorded:"Minimum version recorded",habitRest:"Rest today",habitRestRecorded:"Rest day recorded",habitUndoRest:"Undo rest",notes:"Notes",journal:"Journal",reviewActivity:"Review / Activity",moreReview:"Show more",newNote:"＋ Add a note",writeJournal:"Write today's journal",capture:"＋ Quick Capture",prompt:"What do you want to remember?",submitCapture:"Capture",labelTitle:"Title",labelBody:"Details / journal",save:"Save",close:"Close",empty:"Nothing here for this day.",emptyDate:"No dated items.",showDay:"Open day view",event:"Event",reminder:"Reminder",deadline:"Deadline",task:"Task",done:"Mark done",detail:"Details",saved:"Saved.",captured:"Captured.",readonly:"This workspace is read-only. Changes are disabled.",loading:"Loading…",error:"Could not load the Planner: ",captureError:"Capture failed: ",saveError:"Could not save: ",journalRequired:"Enter journal text before saving."},ja:{detType:"種別",detStatus:"状態",detWhen:"日時",detTitle:"タイトル",detDue:"期限",detChangeDue:"期限を変更",detEdit:"すべて編集",detDetails:"詳細(1行に key:value)",detSave:"保存",detReqDate:"日付を選んでください。",detDoneAt:"完了日時",detDoneNow:"今すぐ完了",detDoneAt2:"指定した日時で完了",detMarkDone:"完了にする",detSaved:"保存しました。",skip:"Plannerへ移動",web:"Web UI全体",eyebrow:"今日をひとつの画面に",title:"デイリープランナー",weekTitle:"週間プランナー",today:"今日",choose:"日付を選ぶ",day:"日",week:"週",previousDay:"前の日",nextDay:"次の日",previousWeek:"前の週",nextWeek:"次の週",weekOf:"週の期間",selected:"選択中",todayMarker:"今日",past:"過去",todayState:"今日",future:"未来",schedule:"予定",tasks:"タスク",habits:"習慣",habitCue:"きっかけ",habitMinimum:"最小版",habitRecordMinimum:"最小版を記録",habitMinimumRecorded:"最小版を記録済み",habitRest:"今日は休む",habitRestRecorded:"休みを記録済み",habitUndoRest:"休みを取り消す",notes:"メモ",journal:"日誌",reviewActivity:"レビュー / アクティビティ",moreReview:"さらに表示",newNote:"＋ メモを追加",writeJournal:"今日の日誌を書く",capture:"＋ クイックキャプチャ",prompt:"覚えておきたいことは何ですか？",submitCapture:"記録",labelTitle:"タイトル",labelBody:"詳細 / 日誌",save:"保存",close:"閉じる",empty:"この日の記録はありません。",emptyDate:"予定はありません。",showDay:"日表示を開く",event:"予定",reminder:"リマインダー",deadline:"期限",task:"タスク",done:"完了を記録",saved:"保存しました。",captured:"記録しました。",readonly:"このworkspaceは読み取り専用です。変更できません。",loading:"読み込み中…",error:"Plannerを読み込めませんでした：",captureError:"記録できませんでした：",saveError:"保存できませんでした：",journalRequired:"日誌の内容を入力してください。",detail:"詳細"}};
  const displayCopy = {
    en: {allDay:"All day", dueLabel:"Due: ", stateProgress:"In progress", stateDone:"Done", stateCanceled:"Canceled", stateDeferred:"Deferred", stateTentative:"Tentative", habitOpen:"Not recorded", habitDone:"✓ Done", reviewEvents:"Recorded changes: ", event_completed:"Completed", event_reopened:"Reopened", event_canceled:"Canceled", event_schedule_changed:"Rescheduled", event_created:"Created", event_status_changed:"Status changed"},
    ja: {allDay:"終日", dueLabel:"期限: ", stateProgress:"進行中", stateDone:"完了", stateCanceled:"中止", stateDeferred:"延期", stateTentative:"未確定", habitOpen:"未記録", habitDone:"✓ 完了", reviewEvents:"記録された変更: ", event_completed:"完了", event_reopened:"再開", event_canceled:"中止", event_schedule_changed:"日程変更", event_created:"作成", event_status_changed:"状態変更"}
  };
  const layoutCopy = {
    en: {layoutShare:"Put applied layout in URL", layoutLinked:"The address bar now includes this layout.", layoutScoped:"You are editing the layout for this link."},
    ja: {layoutShare:"適用済みの画面構成をURLに反映", layoutLinked:"画面構成をアドレスバーのURLに反映しました。", layoutScoped:"このリンクの画面構成を編集中です。"}
  };
  const NOTE_PAGE_SIZE=5;
  let notesPage=null, noteRows=[], notesBusy=false, loadGeneration=0;
  // "echo" repeats the visible headings: keep it for assistive technology only.
  const announce=(value,quiet)=>{const node=$('feedback');node.textContent=value;node.dataset.quiet=String(quiet)};
  const feedback={set text(value){announce(value,false)},set echo(value){announce(value,true)}};
  const $=id=>document.getElementById(id), params=new URLSearchParams(location.search);let scopeArea=params.get('area')||'',scopeView=params.get('saved_view')||'',todaySyncTimer=null;
  let requestedLang=params.get("lang"),lang=["en","ja"].includes(requestedLang)?requestedLang:((navigator.language||"en").slice(0,2)==="ja"?"ja":"en"), t=copy.en, today="", date="", view=["week","month"].includes(params.get("view"))?params.get("view"):"day", writable=false, edit=null, pending=false, sourceRevision="";

  const focusCopy = {
    en: {focusTitle:"Focus now", focusMode:"Today emphasis", focusAuto:"Auto", focusMorning:"Morning", focusDaytime:"Daytime", focusEvening:"Evening", focusStandard:"Standard", focusTimes:"Automatic time bands (workspace time)", focusMorningStart:"Morning starts", focusDaytimeStart:"Daytime starts", focusEveningStart:"Evening starts", focusSettingsHelp:"Morning < Daytime < Evening. Night continues until the next morning. Saved only in this browser.", focusInvalid:"Enter HH:MM times with Morning < Daytime < Evening.", focusMorningHelp:"Today's appointments, priority tasks and the suggested day plan.", focusDaytimeHelp:"Next appointment, remaining tasks and current or upcoming suggestions. Suggestions are not actuals.", focusEveningHelp:"Recorded completions, habits and journal. Unfinished work remains available.", focusStandardHelp:"Standard display. Auto uses workspace time; unavailable or stale time falls back here.", focusUpcoming:"Current / upcoming suggestion", focusNext:"Next appointment", focusCompleted:"Recorded completions", focusUnavailable:"Could not load completion evidence. Retry by reloading the day."},
    ja: {focusTitle:"今の注目", focusMode:"今日の強調表示", focusAuto:"自動", focusMorning:"朝", focusDaytime:"日中", focusEvening:"夜", focusStandard:"標準", focusTimes:"自動判定の時間帯（workspace時刻）", focusMorningStart:"朝の開始", focusDaytimeStart:"日中の開始", focusEveningStart:"夜の開始", focusSettingsHelp:"朝 < 日中 < 夜の順に設定します。夜は翌朝まで続きます。このブラウザーだけに保存します。", focusInvalid:"HH:MM形式で、朝 < 日中 < 夜の順に設定してください。", focusMorningHelp:"今日の予定・優先タスクと、1日の提案プランを確認します。", focusDaytimeHelp:"次の予定・残りタスクと、現在以降の提案を確認します。提案は実績ではありません。", focusEveningHelp:"記録された完了・習慣・日誌を振り返ります。未完了の作業も引き続き確認できます。", focusStandardHelp:"標準表示です。自動判定はworkspace時刻を使い、時刻が不明・古い場合はこの表示に戻ります。", focusUpcoming:"現在以降の提案", focusNext:"次の予定", focusCompleted:"記録された完了", focusUnavailable:"完了記録を読み込めませんでした。日表示を再読み込みしてください。"}
  };
  const timeReviewCopy = {
    en: {
      timeReviewTitle: "Time-based review", timeReviewHelp: "Choose any review period. Selections are temporary, reset when the day reloads, and do not change your records.",
      timeReviewMode: "Review period", timeReviewMorning: "Morning", timeReviewMidday: "Midday", timeReviewEvening: "Evening", timeReviewNight: "Night",
      timeReviewActuals: "Recorded completions (whole selected day)", timeReviewCandidates: "Important task candidates (choose up to 3)",
      timeReviewFlow: "Open Suggested Daily Flow", timeReviewCount: "Temporarily selected", timeReviewEmpty: "No matching task candidates.",
      timeReviewNoEvidence: "No completion records returned.", timeReviewLoading: "Loading day data…", timeReviewUnavailable: "Could not load day data. Reload the day to retry.",
      timeReviewEvidenceUnavailable: "Completion evidence unavailable. Reload the day to retry.",
      timeReviewComplete: "Returned review has no reported completeness limitations.", timeReviewPartial: "Partial completion evidence — other activity may be missing.",
      timeReviewPrompts: {
        morning: ["What matters most today?", "Which tasks would make today meaningful?"],
        midday: ["What have you accomplished so far?", "What needs adjusting for the afternoon?"],
        evening: ["What did you achieve today?", "Which remaining tasks deserve attention tonight?"],
        night: ["What did you learn today?", "What should you carry forward to tomorrow?"]
      }
    },
    ja: {
      timeReviewTitle: "時間帯別レビュー", timeReviewHelp: "任意の時間帯を選んで振り返ります。選択は一時的で、日表示の再読み込みで解除され、記録は変更されません。",
      timeReviewMode: "レビューする時間帯", timeReviewMorning: "朝", timeReviewMidday: "昼", timeReviewEvening: "夕", timeReviewNight: "夜",
      timeReviewActuals: "記録された完了（選択日全体）", timeReviewCandidates: "重要タスク候補（最大3件）",
      timeReviewFlow: "今日のおすすめ / Daily Flow を開く", timeReviewCount: "一時選択中", timeReviewEmpty: "該当するタスク候補はありません。",
      timeReviewNoEvidence: "取得された完了記録はありません。", timeReviewLoading: "日表示のデータを取得中…", timeReviewUnavailable: "日表示のデータを取得できませんでした。再読み込みしてください。",
      timeReviewEvidenceUnavailable: "完了実績を取得できませんでした。日表示を再読み込みしてください。",
      timeReviewComplete: "取得したレビューに完全性の制限は報告されていません。", timeReviewPartial: "完了実績は一部のみです。他の活動が欠けている可能性があります。",
      timeReviewPrompts: {
        morning: ["今日、最も大切にしたいことは何ですか？", "今日を充実させるために選ぶタスクは何ですか？"],
        midday: ["ここまでに何を達成しましたか？", "午後の計画で調整したいことは何ですか？"],
        evening: ["今日、何を達成しましたか？", "夜に優先したい残タスクは何ですか？"],
        night: ["今日、何を学びましたか？", "明日へ何を引き継ぎたいですか？"]
      }
    }
  };
  const timeReviewSelected = new Set();
  function renderTimeReviewPrompts() {
    const mode = $("time-review-mode").value;
    $("time-review-prompts").replaceChildren(...(t.timeReviewPrompts[mode] || t.timeReviewPrompts.morning).map(question => mk("li", "", question)));
  }
  function resetTimeReview() {
    const enabled = view === "day" && date && date === today && !preference().hidden_sections.includes("review");
    $("time-review-panel").hidden = !enabled;
    timeReviewSelected.clear();
    $("time-review-evidence").textContent = t.timeReviewLoading;
    $("time-review-completions").replaceChildren();
    $("time-review-count").textContent = t.timeReviewLoading;
    $("time-review-tasks").replaceChildren();
    $("time-review-flow").disabled = true;
    renderTimeReviewPrompts();
  }
  function renderTimeReview(day, tasks, review) {
    if (view !== "day" || date !== today) return;
    const evidence = $("time-review-evidence");
    evidence.textContent = !review ? t.timeReviewEvidenceUnavailable :
      [review.complete === true ? t.timeReviewComplete : t.timeReviewPartial, ...(review.limitations || [])].join(" · ");
    if (review) {
      const completed = review.completed || [];
      $("time-review-completions").replaceChildren(...(completed.length ?
        completed.map(row => mk("li", "", row.target?.title || row.title || row.event || t.flowUnknown)) :
        [mk("li", "", t.timeReviewNoEvidence)]));
    }
    const refs = [...(day.due_today || []), ...(day.next_actions || [])].filter(ref => ref.kind === "T" && !ref.blocked);
    // Require a source and line match (null source denotes the single-file API),
    // not title alone, or an explicit ID.
    // The command center already applies the selected scope.
    const candidates = (tasks.items || []).filter(item => refs.some(ref =>
      ref.title === item.title && ((ref.id && ref.id === item.id && (!ref.source || ref.source === item.source)) ||
        (ref.source === item.source && ref.line != null && ref.line === item.line))));
    const target = $("time-review-tasks"), controls = [];
    target.replaceChildren();
    function updateSelection() {
      $("time-review-count").textContent = t.timeReviewCount + ": " + timeReviewSelected.size + " / 3";
      for (const control of controls) control.disabled = !control.checked && timeReviewSelected.size >= 3;
    }
    for (const item of candidates) {
      const row = mk("div", "time-review-task"), label = mk("label"), check = mk("input");
      check.type = "checkbox";
      check.onchange = () => {
        if (check.checked && timeReviewSelected.size < 3) timeReviewSelected.add(item);
        else { timeReviewSelected.delete(item); check.checked = false; }
        updateSelection();
      };
      controls.push(check);
      label.append(check, mk("span", "", item.title));
      const detail = mk("button", "", t.detail);
      detail.type = "button";
      detail.setAttribute("aria-label", t.detail + ": " + item.title);
      detail.onclick = () => showDetail(item);
      row.append(label, detail);
      target.append(row);
    }
    if (!candidates.length) target.append(mk("p", "empty", t.timeReviewEmpty));
    updateSelection();
    $("time-review-flow").disabled = false;
  }
  function openTimeReviewFlow() {
    $("flow-disclosure").open = true;
    $("flow-heading").focus();
  }
  const defaultTimeBands = {morning:"05:00", daytime:"11:00", evening:"18:00"};
  let focusMode = "auto", workspaceClock = null, clockSyncPending = false;
  let focusAgenda = [], focusReview = null, focusDataReady = false;
  function validTimeBands(value) {
    return value && ["morning","daytime","evening"].every(k => typeof value[k] === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value[k])) && value.morning < value.daytime && value.daytime < value.evening;
  }
  function acceptWorkspaceClock(config, started) {
    workspaceClock = null;
    const raw = config.current_datetime;
    if (typeof raw !== "string" || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$/.test(raw) || raw.slice(0,10) !== config.today || performance.now()-started > 10000) return;
    const epoch = Date.parse(raw), offset = (Number(raw.slice(-5,-3))*60+Number(raw.slice(-2))) * (raw.at(-6)==="-"?-1:1);
    if (!Number.isFinite(epoch) || Math.abs(offset)>840) return;
    workspaceClock = {epoch, offset, received:performance.now()};
  }
  function workspaceInstant() {
    if (!workspaceClock) return null;
    const age = performance.now()-workspaceClock.received;
    if (age < 0 || age > 120000) return null;
    const epoch = workspaceClock.epoch+age, local = new Date(epoch+workspaceClock.offset*60000);
    if (local.toISOString().slice(0,10)!==today) return null;
    return {epoch, hhmm:local.toISOString().slice(11,16)};
  }
  function activeFocusMode() {
    if (view!=="day" || dayPosition()!=="today") return "standard";
    if (focusMode!=="auto") return focusMode;
    const instant = workspaceInstant();
    if (!instant) return "standard";
    const bands = preference().time_bands, time = instant.hhmm;
    return time < bands.morning || time >= bands.evening ? "evening" : time < bands.daytime ? "morning" : "daytime";
  }
  function focusTarget(id) {
    if (id==="flow") return $("flow-panel");
    if (id==="review") return $("review-panel");
    return $(id)?.closest("section");
  }
  function updateFocus() {
    const mode = activeFocusMode(), enabled = view==="day" && dayPosition()==="today";
    $("today-focus").hidden = !enabled;
    $("today-focus").dataset.mode = mode;
    $("focus-status").textContent = t["focus"+mode[0].toUpperCase()+mode.slice(1)] + " · " + t["focus"+mode[0].toUpperCase()+mode.slice(1)+"Help"];
    $("focus-links").replaceChildren();
    document.querySelectorAll(".focus-time-marker").forEach(n=>n.remove());
    document.querySelectorAll(".focus-emphasis,.focus-upcoming").forEach(n=>n.classList.remove("focus-emphasis","focus-upcoming"));
    if (!enabled || mode==="standard") return;
    const ids = {morning:["schedule","tasks","flow"], daytime:["schedule","tasks","flow"], evening:["review","habits","journal"]}[mode];
    for (const id of ids) {
      const node = focusTarget(id);
      if (!node || node.hidden || (!focusDataReady && id!=="flow")) continue;
      node.classList.add("focus-emphasis");
      const link = document.createElement("a");
      link.href = "#"+(id==="flow"?"flow-heading":id==="review"?"review-panel":id);
      link.textContent = id==="flow"?t.flowTitle:id==="review"?t.focusCompleted:t[id];
      link.onclick = () => { if(id==="flow") $("flow-disclosure").open=true; const target=$(link.hash.slice(1));target.tabIndex=-1;target.focus(); };
      $("focus-links").append(link);
    }
    const instant = workspaceInstant();
    if (mode==="daytime" && instant && focusDataReady && !focusTarget("schedule").hidden) {
      const matches = focusAgenda.filter(r=>r.type==="E").flatMap(r=>(r.matches||[]).map(m=>({title:r.title,start:m.start}))).filter(m=>typeof m.start==="string" && m.start.startsWith(today+"T") && m.start.slice(11,16)>=instant.hhmm).sort((a,b)=>a.start.localeCompare(b.start));
      if (matches.length) {const p=document.createElement("p");p.textContent=t.focusNext+": "+matches[0].start.slice(11,16)+" · "+matches[0].title;$("focus-links").append(p);}
    }
    if (mode==="daytime" && instant) document.querySelectorAll(".flow-candidate").forEach(n=>{if(Date.parse(n.dataset.end)>instant.epoch){n.classList.add("focus-upcoming");const label=document.createElement("small");label.className="focus-time-marker";label.textContent=t.focusUpcoming;n.append(label)}});
  }
  const flowCopy = {
    en: {
      flowTitle: "Suggested Daily Flow",
      flowUnsaved: "Read-only suggestions, not saved or executed. Fixed appointments stay fixed.",
      flowStart: "Window start",
      flowEnd: "Window end (00:00 = next midnight)",
      flowRequest: "Get suggestions",
      flowReady:
        "Enter an explicit window and request suggestions for this day. No automatic refresh.",
      flowPast:
        "Suggestions are unsupported for past dates. Use Review / Activity for historical evidence.",
      flowLoading: "Loading read-only suggestions…",
      flowError: "Could not load suggestions. Check the window, scope and connection, then retry.",
      flowAuth: "Access denied. Use an authorized Web session; suggestions need read access only.",
      flowInvalid: "Enter both times as HH:MM, with end after start (00:00 means next midnight). If valid, check workspace timezone and scope.",
      flowComplete: "Complete",
      flowPartial: "Partial — some records could not be used",
      flowBlocked: "Blocked — no safe candidate placement",
      flowUnknown: "Unknown",
      flowCertified: "Certified",
      flowInventory: "Inventory",
      flowOccupancy: "Occupancy",
      flowBounded: "Bounded",
      flowWarning: "Incomplete suggestions. Unknown occupancy must not be treated as free time.",
      flowEmpty: "No timeline entries in this window. See unplaced tasks and diagnostics below.",
      flowWhy: "Why",
      flowMinutes: "minutes",
      flowFixed: "Fixed appointment (not movable)",
      flowCandidate: "Suggested task (not saved)",
      flowBreak: "Suggested break (not saved)",
      flowBuffer: "Suggested buffer (not saved)",
      flowInstants: "Point reminders / events (do not reserve time)",
      flowUnplaced: "Unplaced tasks",
      flowDiagnostics: "Diagnostics",
      flowProvenance: "Source / revision and request context",
      flowEvaluated: "Evaluated at",
      flowWindow: "Window / effective window",
      flowNone: "None",
      flowDetail: "Open current item details",
      flowDetailError: "Current details unavailable or item changed. Request suggestions again.",
      flowSource: "Source token / line",
      flowCode: "Code / parameters",
      flowReasons: "Completeness reasons",
      flowDeadline: "Deadline status",
      flowMet: "Met",
      flowMissed: "Missed",
      flowNoDeadline: "No deadline",
    },
    ja: {
      flowTitle: "今日のおすすめ / Daily Flow",
      flowUnsaved: "読み取り専用の提案です。未保存・未実行です。固定予定は移動しません。",
      flowStart: "対象時間の開始",
      flowEnd: "対象時間の終了（00:00 は翌日午前0時）",
      flowRequest: "おすすめを取得",
      flowReady: "この日の対象時間を明示して取得してください。自動更新はしません。",
      flowPast:
        "過去の日付の提案には対応していません。実績はレビュー / アクティビティで確認してください。",
      flowLoading: "読み取り専用の提案を取得中…",
      flowError: "提案を取得できませんでした。時間・スコープ・接続を確認して再試行してください。",
      flowAuth:
        "アクセスが拒否されました。認証済みのWebセッションを使用してください。必要なのは読み取り権限のみです。",
      flowInvalid:
        "開始と終了をHH:MMで指定し、終了を開始より後にしてください（00:00 は翌日午前0時）。正しい場合はworkspaceのタイムゾーンとスコープも確認してください。",
      flowComplete: "完全",
      flowPartial: "一部のみ — 利用できない記録があります",
      flowBlocked: "取得不可 — 安全な候補配置ができません",
      flowUnknown: "不明",
      flowCertified: "確認済み",
      flowInventory: "対象データ",
      flowOccupancy: "予定の占有情報",
      flowBounded: "件数制限あり",
      flowWarning: "不完全な提案です。不明な占有情報を空き時間として扱わないでください。",
      flowEmpty:
        "この時間帯に表示できる予定・候補はありません。未配置タスクと診断を確認してください。",
      flowWhy: "理由",
      flowMinutes: "分",
      flowFixed: "固定予定（移動不可）",
      flowCandidate: "提案タスク（未保存）",
      flowBreak: "提案休憩（未保存）",
      flowBuffer: "提案余裕時間（未保存）",
      flowInstants: "時点の通知・予定（時間を占有しません）",
      flowUnplaced: "未配置タスク",
      flowDiagnostics: "診断",
      flowProvenance: "参照元・リビジョンと取得条件",
      flowEvaluated: "評価日時",
      flowWindow: "対象時間 / 有効時間",
      flowNone: "なし",
      flowDetail: "現在の記録の詳細を開く",
      flowDetailError:
        "現在の詳細を取得できないか、記録が変更されています。提案を再取得してください。",
      flowSource: "参照元トークン / 行",
      flowCode: "コード / パラメーター",
      flowReasons: "完全性の理由",
      flowDeadline: "期限の判定",
      flowMet: "期限内",
      flowMissed: "超過",
      flowNoDeadline: "期限なし",
    },
  };
  // Translate engine evidence only; eligibility, ordering and scheduling stay server-side.
  const flowReasons = {
    eligible_task: ["Eligible actionable task", "実行可能な候補タスク"],
    full_estimate: ["Uses the full authored estimate", "記録された見積もり全体を使用"],
    historical_elapsed: [
      "Historical elapsed time is not subtracted",
      "過去の実績時間は差し引きません",
    ],
    priority_context: ["Shared priority and urgency context", "共通の優先度・緊急度の情報"],
    earliest_fit: [
      "Earliest safe slot in canonical priority order",
      "共通の優先順位で最初の安全な空き枠",
    ],
    deadline_missed: ["Placement misses the deadline", "配置すると期限を超過"],
    reserved_after_task: ["Reserved after the task", "タスクの後に確保"],
    fixed_attendance: ["Authored fixed attendance", "記録された固定予定"],
    missing_estimate: ["No authored estimate", "見積もり未記入"],
    ambiguous_estimate: ["Multiple estimates", "見積もりが複数"],
    invalid_estimate: ["Estimate is invalid or nonpositive", "見積もりが不正または正の値でない"],
    insufficient_capacity: ["No slot fits the full estimate", "見積もり全体が収まる枠がありません"],
    unresolved_dependency: ["Dependency is unresolved", "依存先が未解決"],
    missing_identity: ["Missing full item ID", "記録の完全なIDがありません"],
    not_actionable: ["Task is not actionable", "実行可能なタスクではありません"],
    future_intent: ["Authored intent is after this day", "記録された実行日はこの日より後"],
    ambiguous_do: ["Multiple intent dates", "実行日の指定が複数"],
    ambiguous_due: ["Multiple deadlines", "期限の指定が複数"],
    invalid_do: ["Invalid intent date", "実行日が不正"],
    invalid_due: ["Invalid deadline", "期限が不正"],
    invalid_elapsed: ["Invalid historical elapsed time", "過去の実績時間が不正"],
    occupancy_unavailable: [
      "Active source snapshot unavailable",
      "有効な参照元のスナップショットを取得できません",
    ],
    source_changed: [
      "Sources changed during the read; retry",
      "取得中に参照元が変更されました。再取得してください",
    ],
    unsupported_timezone_window: [
      "DST or timezone window unsupported",
      "夏時間・タイムゾーンの時間帯に未対応",
    ],
    past_date_unsupported: ["Past dates unsupported", "過去の日付には未対応"],
    window_elapsed: ["Requested window has elapsed", "指定した時間帯は終了しています"],
    input_parse_error: ["Input contains parse errors", "入力に解析エラーがあります"],
    ambiguous_identity: ["Duplicate or ambiguous item IDs", "記録のIDが重複または曖昧"],
    ambiguous_source: ["Conflicting source rows", "参照元の行が競合"],
    occupancy_unknown: ["Busy time cannot be certified", "占有時間を確認できません"],
    limit_exceeded: ["Safe resource limit exceeded", "安全な処理上限を超過"],
    skipped_recurring: ["Recurring occupancy is unsupported", "繰り返し予定の占有時間には未対応"],
    missing_time_detail: ["Time detail is missing", "時刻の詳細がありません"],
    incomplete_period: ["Incomplete event period", "予定の期間情報が不完全"],
    invalid_time_value: ["Invalid time value", "時刻の値が不正"],
    invalid_span: ["Invalid event span", "予定の期間が不正"],
    plan_blocked: [
      "Safe planning is blocked; see diagnostics",
      "安全な提案を作成できません。診断を確認してください",
    ],
    conflict: ["Fixed appointments overlap", "固定予定が重複"],
    unknown_duration: ["Event duration is unknown", "予定の所要時間が不明"],
  };
  let flowGeneration = 0,
    flowController = null,
    flowDetailGeneration = 0;
  function flowText(code) {
    return flowReasons[code]?.[lang === "ja" ? 1 : 0] || t.flowUnknown + " (" + String(code) + ")";
  }
  function flowNode(tag, text, parent, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    if (parent) parent.append(node);
    return node;
  }
  function resetFlow() {
    ++flowGeneration;
    ++flowDetailGeneration;
    flowController?.abort();
    flowController = null;
    $("flow-result").replaceChildren();
    $("flow-result").setAttribute("aria-busy", "false");
    $("flow-request").disabled = dayPosition() === "past";
    $("flow-status").textContent = dayPosition() === "past" ? t.flowPast : t.flowReady;
  }
  function flowEvidence(parent, rows) {
    if (!rows?.length) return;
    const list = flowNode("ul", undefined, parent, "flow-reasons");
    for (const row of rows) {
      const li = flowNode("li", flowText(row.code), list);
      flowNode(
        "small",
        t.flowCode +
          ": " +
          row.code +
          (Object.keys(row.params || {}).length ? " · " + JSON.stringify(row.params) : ""),
        li,
      );
    }
  }
  async function flowDetails(ref) {
    const generation = ++flowDetailGeneration,
      context = flowGeneration;
    try {
      const data = await api("/api/items/id/" + encodeURIComponent(ref.id));
      if (generation !== flowDetailGeneration || context !== flowGeneration || view !== "day") return;
      const record = data.item;
      if (!record || record.id !== ref.id) throw Error("changed");
      showDetail(record);
    } catch (_) {
      if (generation === flowDetailGeneration && context === flowGeneration)
        $("flow-status").textContent = t.flowDetailError;
    }
  }
  function flowReference(parent, ref) {
    if (!ref) return;
    flowNode(
      "p",
      t.flowSource + ": " + ref.source + " / " + (ref.line ?? "—"),
      parent,
      "flow-source",
    );
    if (ref.id) {
      flowNode("small", "ID: " + ref.id, parent);
      const b = flowNode("button", t.flowDetail, parent);
      b.type = "button";
      b.addEventListener("click", () => flowDetails(ref));
    }
  }
  function flowDisclosure(parent, label) {
    const d = flowNode("details", undefined, parent, "flow-disclosure");
    flowNode("summary", label, d);
    return d;
  }
  function renderFlow(data) {
    const target = $("flow-result");
    target.replaceChildren();
    const c = data.completeness;
    const state =
      { complete: t.flowComplete, partial: t.flowPartial, blocked: t.flowBlocked }[c.state] ||
      t.flowUnknown;
    $("flow-status").textContent = state + " · " + data.date + " · " + data.timezone;
    flowNode("p", t.flowUnsaved, target, "flow-notice");
    flowNode(
      "p",
      t.flowOccupancy +
        ": " +
        (c.occupancy === "certified" ? t.flowCertified : t.flowUnknown) +
        " · " +
        t.flowInventory +
        ": " +
        (c.inventory === "complete" ? t.flowComplete : t.flowBounded),
      target,
    );
    if (c.state !== "complete") flowNode("p", t.flowWarning, target, "flow-notice");
    if (c.reasons?.length)
      flowEvidence(
        flowDisclosure(target, t.flowReasons + " (" + c.reasons.length + ")"),
        c.reasons.map((code) => ({ code })),
      );
    const kinds = {
      fixed: t.flowFixed,
      candidate: t.flowCandidate,
      policy_break: t.flowBreak,
      buffer: t.flowBuffer,
    };
    const timeline = flowNode("ol", undefined, target, "flow-timeline");
    for (const row of data.timeline) {
      const li = flowNode("li", undefined, timeline),
        article = flowNode("article", undefined, li, "flow-card flow-" + row.kind);
      article.dataset.end = row.end;
      flowNode("strong", kinds[row.kind] || t.flowUnknown, article);
      flowNode("p", row.start + " → " + row.end, article);
      const ref = row.item || row.candidate;
      if (ref) flowNode("h3", ref.title, article);
      const minutes =
        row.duration_minutes ??
        row.why?.find((r) => r.code === "reserved_after_task")?.params?.minutes ??
        (Date.parse(row.end) - Date.parse(row.start)) / 60000;
      if (Number.isFinite(minutes)) flowNode("p", minutes + " " + t.flowMinutes, article);
      if (row.deadline_status)
        flowNode(
          "p",
          t.flowDeadline +
            ": " +
            ({ met: t.flowMet, missed: t.flowMissed, none: t.flowNoDeadline }[row.deadline_status] ||
              t.flowUnknown),
          article,
        );
      flowEvidence(article, row.why);
      flowReference(flowDisclosure(article, t.flowProvenance), ref);
    }
    if (!data.timeline.length) flowNode("p", t.flowEmpty, target);
    const instants = flowDisclosure(target, t.flowInstants + " (" + data.instants.length + ")");
    for (const row of data.instants) {
      const article = flowNode("article", undefined, instants, "flow-card");
      flowNode("h3", row.item?.title, article);
      flowNode("p", row.at, article);
      flowReference(article, row.item);
    }
    const unplaced = flowDisclosure(target, t.flowUnplaced + " (" + data.unplaced.length + ")");
    for (const row of data.unplaced) {
      const article = flowNode("article", undefined, unplaced, "flow-card");
      flowNode("h3", row.item?.title, article);
      flowNode("p", flowText(row.reason), article);
      flowEvidence(article, row.why);
      for (const code of row.secondary || []) flowNode("p", flowText(code), article);
      flowReference(article, row.item);
    }
    if (!data.unplaced.length) flowNode("p", t.flowNone, unplaced);
    const diagnostics = flowDisclosure(
      target,
      t.flowDiagnostics + " (" + data.diagnostics.length + ")",
    );
    for (const row of data.diagnostics) {
      const article = flowNode("article", undefined, diagnostics, "flow-card");
      if (row.item) flowNode("h3", row.item.title, article);
      flowEvidence(article, [row]);
      flowReference(article, row.item);
    }
    if (!data.diagnostics.length) flowNode("p", t.flowNone, diagnostics);
    const provenance = flowDisclosure(target, t.flowProvenance);
    flowNode("p", t.flowEvaluated + ": " + data.evaluated_at, provenance);
    if (data.window)
      flowNode(
        "p",
        t.flowWindow +
          ": " +
          data.window.start +
          " → " +
          data.window.end +
          " / " +
          data.window.effective_start +
          " → " +
          data.window.effective_end,
        provenance,
      );
    flowNode(
      "pre",
      JSON.stringify(
        {
          schema: data.schema,
          policy_version: data.policy_version,
          scope: data.scope,
          policy: data.policy,
          source_revision: data.source_revision,
        },
        null,
        2,
      ),
      provenance,
    );
  }
  async function requestFlow(event) {
    event.preventDefault();
    resetFlow();
    if (view !== "day" || dayPosition() === "past") return;
    const start = $("flow-start").value,
      end = $("flow-end").value;
    if (
      !/^([01]\d|2[0-3]):[0-5]\d$/.test(start) ||
      !/^([01]\d|2[0-3]):[0-5]\d$/.test(end) ||
      (end !== "00:00" && end <= start)
    ) {
      $("flow-status").textContent = t.flowInvalid;
      return;
    }
    const generation = flowGeneration,
      controller = new AbortController();
    flowController = controller;
    $("flow-result").setAttribute("aria-busy", "true");
    $("flow-status").textContent = t.flowLoading;
    const query = new URLSearchParams({ date, day_start: start, day_end: end });
    if (scopeArea) query.set("area", scopeArea);
    if (scopeView) query.set("saved_view", scopeView);
    try {
      const response = await fetch("/api/daily-flow?" + query, {
        signal: controller.signal,
        cache: "no-store",
      });
      if (generation !== flowGeneration) return;
      if (!response.ok) {
        $("flow-status").textContent = [401, 403].includes(response.status)
          ? t.flowAuth
          : [400, 422].includes(response.status)
            ? t.flowInvalid
            : t.flowError;
        return;
      }
      const data = await response.json();
      if (generation !== flowGeneration) return;
      if (
        data.schema !== "daily-flow-lite-v1" ||
        data.date !== date ||
        !data.completeness ||
        !["timeline", "instants", "unplaced", "diagnostics"].every((k) => Array.isArray(data[k]))
      )
        throw Error("Invalid response");
      renderFlow(data);
      updateFocus();
    } catch (error) {
      if (generation === flowGeneration && error.name !== "AbortError") {
        $("flow-result").replaceChildren();
        $("flow-status").textContent = t.flowError;
      }
    } finally {
      if (generation === flowGeneration) {
        flowController = null;
        $("flow-result").setAttribute("aria-busy", "false");
      }
    }
  }
  function translate(){t=copy[lang];Object.assign(t,flowCopy[lang],focusCopy[lang],timeReviewCopy[lang],displayCopy[lang],layoutCopy[lang]);Object.assign(t,lang==="ja"?{emptyNotes:"通常のメモはありません。",moreNotes:"さらに表示",editNote:"編集",viewSelector:"Plannerの表示",anchorDate:"表示の基準日",month:"月",monthTitle:"月間プランナー",previousMonth:"前の月",nextMonth:"次の月",densityNone:"予定なし",densityLow:"少ない",densityMedium:"普通",densityHigh:"多い",items:"件",outsideMonth:"表示月の外",scope:"スコープ",all:"すべて",customize:"カスタマイズ",sections:"Dayセクション",density:"密度",comfortable:"標準",compact:"コンパクト",apply:"適用",reset:"workspaceの既定値に戻す",moveUp:"上へ",moveDown:"下へ",showSection:"表示"}:{emptyNotes:"No ordinary Notes.",moreNotes:"Load more",editNote:"Edit",viewSelector:"Planner view",anchorDate:"View anchor date",month:"Month",monthTitle:"Month Planner",previousMonth:"Previous month",nextMonth:"Next month",densityNone:"No dated items",densityLow:"Low density",densityMedium:"Medium density",densityHigh:"High density",items:"items",outsideMonth:"Outside selected month",scope:"Scope",all:"All",customize:"Customize",sections:"Day sections",density:"Density",comfortable:"Comfortable",compact:"Compact",apply:"Apply",reset:"Reset to workspace defaults",moveUp:"Move up",moveDown:"Move down",showSection:"Show"});document.documentElement.lang=lang;document.querySelectorAll("[data-i18n]").forEach(n=>n.textContent=t[n.dataset.i18n]||n.textContent);$('view-switch').setAttribute("aria-label",t.viewSelector);document.title=(view==="week"?t.weekTitle:view==="month"?t.monthTitle:t.title)+" · life.txt"}
  let revision = null, captureRevision = null;
  const recordRevisions = new WeakMap();
  function revisionError(conflict=false) {
    return lang === "ja"
      ? (conflict ? "データが更新されています。入力を控えてから再読み込みし、最新の内容を確認してやり直してください。" : "更新用リビジョンを取得できません。再読み込みしてやり直してください。")
      : (conflict ? "Data changed. Keep a copy of your input, reload, review the latest data and try again." : "Could not obtain a write revision. Reload and try again.");
  }
  function responseRevision(response) {
    const token = response.headers.get("X-Lifetxt-Revision");
    return response.headers.get("ETag") || (token ? '"' + token + '"' : null);
  }
  async function api(path, options={}) {
    const {expectedRevision, ...init} = options;
    const unsafe = ["POST", "PUT", "PATCH", "DELETE"].includes((init.method || "GET").toUpperCase());
    if (unsafe) {
      // An explicit snapshot must never be upgraded by discovery or background reads.
      if (expectedRevision === undefined && !revision) {
        await api('/api/revision');
      }
      const expected = expectedRevision === undefined ? revision : expectedRevision;
      if (!expected) throw Error(revisionError());
      const headers = new Headers(init.headers || {});
      headers.set("If-Match", expected);
      init.headers = headers;
    }
    const response = await fetch(path, init);
    const raw = await response.text();
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; } catch (_) {}
    if (!response.ok) {
      const error = Error(response.status === 409 ? revisionError(true) : response.status === 428 ? revisionError() : data.message || data.detail || "Request failed");
      error.status = response.status;
      throw error;
    }
    const token = responseRevision(response);
    if (token) revision = token;
    recordRevisions.set(data, token);
    // Associate each editable record with the response that supplied its contents.
    for (const item of [...(data.items || []), ...(data.item ? [data.item] : [])]) {
      recordRevisions.set(item, token);
    }
    return data;
  }
  const vals=(item,key)=>Array.isArray(item?.details?.[key])?item.details[key]:item?.details?.[key]?[item.details[key]]:[];
  const pathFor=i=>i.id?"/api/items/id/"+encodeURIComponent(i.id):i.line&&i.editable?"/api/items/"+encodeURIComponent(i.line):null;
  function card(target, title, meta, action, label, detail, guidance = [], additionalActions = []) {
    const node = document.createElement("article");
    node.className = "card";
    const content = document.createElement("div");
    content.className = "card-content";
    const strong = document.createElement("strong");
    strong.textContent = title || "";
    content.append(strong);
    for (const text of [meta, ...guidance]) {
      if (!text) continue;
      const paragraph = document.createElement("p");
      paragraph.textContent = text;
      content.append(paragraph);
    }
    node.append(content);
    const actions = document.createElement("div");
    actions.className = "card-actions";
    if (action) {
      const choices = [[label, ""], ...additionalActions];
      const buttons = choices.map(([text]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = text;
        return button;
      });
      buttons.forEach((button, index) => {
        button.addEventListener("click", async event => {
          event.stopPropagation();
          if (button.disabled) return;
          buttons.forEach(control => { control.disabled = true; });
          try { await action(choices[index][1]); }
          catch (error) { feedback.text=t.error + error.message; }
          finally { buttons.forEach(control => { control.disabled = false; }); }
        });
        actions.append(button);
      });
    }
    if (detail) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = t.detail;
      button.addEventListener("click", () => showDetail(detail));
      actions.append(button);
    }
    if (actions.childElementCount) node.append(actions);
    target.append(node);
  }
  function mk(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
  function dField(label,control){const f=mk('label','fld',label);f.append(control);return f}
  function dInput(id,type,value){const i=document.createElement('input');i.id=id;i.type=type;i.value=value;return i}
  function dFields(...c){const g=mk('div','detail-fields');g.append(...c);return g}
  function dList(rows,cls){const l=mk('dl',cls);for(const [k,v] of rows){if(!v)continue;const r=document.createElement('div');r.append(mk('dt','',k),mk('dd','',v));l.append(r)}return l}
  function detailError(m){const e=$('detail-error');e.textContent=m;e.scrollIntoView({block:'nearest'})}
  const detailsText=d=>Object.entries(d||{}).flatMap(([k,vs])=>(Array.isArray(vs)?vs:[vs]).map(v=>k+':'+v)).join('\n');
  const parseDetails=text=>{const o={};for(const line of text.split('\n')){const x=line.trim(),c=x.indexOf(':');if(!x||c<1)continue;const k=x.slice(0,c).trim();(o[k]=o[k]||[]).push(x.slice(c+1).trim())}return o};
  function runWrite(item,url,init){if(pending)return;pending=true;$('detail-dialog').close();return api(url,{expectedRevision:recordRevisions.get(item)||null,headers:{'Content-Type':'application/json'},...init}).then(()=>{feedback.text=t.detSaved;pending=false;return load()}).catch(e=>{feedback.text=t.error+e.message}).finally(()=>{pending=false})}
  const putItem=(item,body)=>runWrite(item,pathFor(item),{method:'PUT',body:JSON.stringify(body)});
  function nowStamp(){const i=workspaceInstant();if(i)return new Date(i.epoch+workspaceClock.offset*60000).toISOString().slice(0,19);const d=new Date();return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,19)}
  function completeItem(item,stamp){const via=item.id&&(item.details?.repeat||[]).length;return runWrite(item,via?pathFor(item)+'/complete':pathFor(item),via?{method:'POST',body:JSON.stringify({done_at:stamp})}:{method:'PUT',body:JSON.stringify({status:'[x]',type:item.type,title:item.title,details:{...item.details,done:[stamp]}})})}
  function showCompletion(item){if(pending)return;const form=mk('form');form.id='planner-completion';const input=dInput('detail-done-at','datetime-local',nowStamp());input.required=true;input.step='1';form.append(dField(t.detDoneAt,input));form.onsubmit=e=>{e.preventDefault();completeItem(item,input.value)};const now=mk('button','go go-primary',t.detDoneNow);now.type='button';now.onclick=()=>completeItem(item,nowStamp());const at=mk('button','go',t.detDoneAt2);at.type='submit';at.setAttribute('form',form.id);$('detail-heading').textContent=item.title;$('detail-content').replaceChildren(form);$('detail-actions').replaceChildren(now,at);$('detail-error').textContent='';$('detail-dialog').showModal();now.focus()}
  function fullEdit(item){const box=$('detail-content'),acts=$('detail-actions');box.replaceChildren();acts.replaceChildren();$('detail-error').textContent='';const ti=dInput('detail-title','text',item.title),st=document.createElement('select');for(const v of new Set(['[ ]','[/]','[x]','[-]','[>]','[?]','[N]',item.status])){const o=document.createElement('option');o.value=o.textContent=v;st.append(o)}st.value=item.status;const ty=dInput('detail-type','text',item.type),de=document.createElement('textarea');de.value=detailsText(item.details);de.rows=6;box.append(dField(t.detTitle,ti),dFields(dField(t.detStatus,st),dField(t.detType,ty)),dField(t.detDetails,de));const b=mk('button','go go-primary',t.detSave);b.type='button';b.onclick=()=>{if(!ti.value.trim()){detailError(t.detReqDate);return}putItem(item,{status:st.value,type:ty.value.trim()||item.type,title:ti.value.trim(),details:parseDetails(de.value)})};acts.append(b);ti.focus()}
  function showDetail(record,match=null){const box=$('detail-content'),acts=$('detail-actions');box.replaceChildren();acts.replaceChildren();$('detail-heading').textContent=record.title||t.detail;$('detail-error').textContent='';const when=match?.start||vals(record,'on')[0]||vals(record,'due')[0]||'';const sum=dList([[t.detType,record.type||record.kind],[t.detStatus,record.status],[t.detWhen,when]],'detail-summary');if(sum.childElementCount)box.append(sum);const rows=Object.entries(record.details||{}).map(([k,v])=>[k,Array.isArray(v)?v.join(', '):String(v)]);const props=dList(rows,'detail-properties');if(props.childElementCount)box.append(props);const can=writable&&record.editable&&pathFor(record);if(can&&record.type==='T'){if(record.status!=='[x]'){const d=mk('button','go go-primary',t.detMarkDone);d.type='button';d.onclick=()=>showCompletion(record);acts.append(d)}const old=String(vals(record,'due')[0]||''),input=dInput('detail-due','date',old.slice(0,10)),b=mk('button','go',t.detChangeDue);b.type='button';b.onclick=()=>{if(!input.value){detailError(t.detReqDate);return}putItem(record,{status:record.status,type:record.type,title:record.title,details:{...record.details,due:[input.value+(old.includes('T')?old.slice(10):'')]}})};acts.append(dFields(dField(t.detDue,input)),b)}if(can){const eb=mk('button','go',t.detEdit);eb.type='button';eb.onclick=()=>fullEdit(record);acts.append(eb)}$('detail-dialog').showModal();box.parentElement.scrollTop=0;$('detail-close').focus()}
  function list(target,items,render){target.replaceChildren();if(!items.length){const p=document.createElement("p");p.className="empty";p.textContent=t.empty;target.append(p);return}items.forEach(x=>render(x))}
  function updateUrl() {
    const url = new URL(location.href);
    const next = url.searchParams;
    if (view !== "day" || date !== today) next.set("date", date);
    else next.delete("date");
    if (view !== "day") next.set("view", view);
    else next.delete("view");
    if (scopeArea) next.set("area", scopeArea);
    else next.delete("area");
    if (scopeView) next.set("saved_view", scopeView);
    else next.delete("saved_view");
    if (lang === "ja" || requestedLang === "en") next.set("lang", lang);
    else next.delete("lang");
    history.replaceState(history.state, "", url.pathname + url.search + url.hash);
  }
  function scopeQuery(){const p=new URLSearchParams();if(scopeArea)p.set('area',scopeArea);if(scopeView)p.set('saved_view',scopeView);return p.toString()?("&"+p.toString()):''}
  async function syncToday() {
    updateFocus();
    if (clockSyncPending || document.visibilityState === "hidden") return;
    clockSyncPending = true;
    const started = performance.now();
    try {
      const config = await api('/api/config');
      if (!/^\d{4}-\d\d-\d\d$/.test(config.today)) throw Error("Invalid date");
      acceptWorkspaceClock(config, started);
      const changed = config.today !== today;
      today = config.today;
      if (changed) {updateTemporalContext();applyPlannerPreference();await load();}
    } catch (_) {workspaceClock = null;}
    finally {clockSyncPending = false; updateFocus();}
  }
  function resumeClock() { workspaceClock = null; updateFocus(); syncToday(); }

  function setView(next){view=next;translate();$('day-view').hidden=view!=="day";$('week-view').hidden=view!=="week";$('month-view').hidden=view!=="month";$('view-day').setAttribute("aria-pressed",String(view==="day"));$('view-week').setAttribute("aria-pressed",String(view==="week"));$('view-month').setAttribute("aria-pressed",String(view==="month"));$('title').textContent=view==="week"?t.weekTitle:view==="month"?t.monthTitle:t.title;updateUrl();load()}
  const dayDate=(value,delta)=>{const [y,m,d]=value.split('-').map(Number);return new Date(Date.UTC(y,m-1,d+delta)).toISOString().slice(0,10)}; function dayPosition(){return date<today?"past":date>today?"future":"today"} function temporalLabel(){return {past:t.past,today:t.todayState,future:t.future}[dayPosition()]} function updateTemporalContext(){const node=$("temporal-context");if(!node)return;const position=dayPosition();node.dataset.position=position;$("day-view").dataset.position=position;node.textContent=temporalLabel()+" · "+date;node.setAttribute("aria-label",temporalLabel()+", "+date)}
  function weekStart(value){const weekday=new Date(value+"T00:00:00Z").getUTCDay();return dayDate(value,-((weekday+6)%7))}
  function matchTime(record,match){const start=String(match.start||""),time=start.includes("T")?start.slice(11,16):"";if(!time)return "";if(time!=="00:00")return time;const values=Object.values(record.details||{}).flat().map(String);return values.some(value=>value===time||value.includes("T"+time))?time:""}
  const stateText=status=>({"[/]":t.stateProgress,"[x]":t.stateDone,"[-]":t.stateCanceled,"[>]":t.stateDeferred,"[?]":t.stateTentative}[status]||"");
  const shortDay=value=>new Intl.DateTimeFormat(lang==="ja"?"ja-JP":"en-US",{month:"short",day:"numeric",timeZone:"UTC"}).format(new Date(value+"T00:00:00Z"));
  function spanText(record,match){
    const start=String(match.start||""),end=String(match.end||""),from=start.slice(0,10),to=end.slice(0,10)||from;
    if(!/^\d{4}-\d\d-\d\d$/.test(from)||!/^\d{4}-\d\d-\d\d$/.test(to))return start;
    const wholeDay=!matchTime(record,match)&&(!end||end.slice(11,16)==="23:59");
    if(wholeDay){
      if(from!==to)return shortDay(from)+" – "+shortDay(to);
      return from===date?t.allDay:shortDay(from)+" "+t.allDay;
    }
    const left=(from===date&&to===date?"":shortDay(from)+" ")+start.slice(11,16);
    if(!end||end===start)return left;
    return left+" – "+(from===to?"":shortDay(to)+" ")+end.slice(11,16);
  }
  function scheduleMeta(record){
    const matches=Array.isArray(record.matches)?record.matches:[];
    const times=matches.length?matches.map(match=>spanText(record,match)).join(", "):String(record.when||"");
    return [t[{E:"event",R:"reminder",D:"deadline"}[record.type]],times,stateText(record.status)].filter(Boolean).join(" · ");
  }
  function taskMeta(item){
    const due=String(vals(item,"due")[0]||""),parts=/^(\d{4}-\d\d-\d\d)(?:T(\d\d:\d\d))?/.exec(due);
    const dueText=!due?"":t.dueLabel+(parts?shortDay(parts[1])+(parts[2]?" "+parts[2]:""):due);
    return [dueText,stateText(item.status)].filter(Boolean).join(" · ");
  }
  function weekLabel(start,end){const locale=lang==="ja"?"ja-JP":"en-US", a=new Date(start+"T00:00:00Z"),b=new Date(end+"T00:00:00Z");return new Intl.DateTimeFormat(locale,{month:"short",day:"numeric",timeZone:"UTC"}).format(a)+" – "+new Intl.DateTimeFormat(locale,{month:"short",day:"numeric",year:a.getUTCFullYear()!==b.getUTCFullYear()?"numeric":undefined,timeZone:"UTC"}).format(b)}
  function renderWeek(records,start){const target=$('week-days');target.replaceChildren();const buckets=Array.from({length:7},()=>[]);for(const record of records){if(!["E","R","D","T"].includes(record.type))continue;const matches=Array.isArray(record.matches)?record.matches:[];for(const match of matches){const occurrence=String(match.start||"").slice(0,10),index=Math.round((Date.parse(occurrence+"T00:00:00Z")-Date.parse(start+"T00:00:00Z"))/86400000);if(index>=0&&index<7)buckets[index].push({record,match})}}for(const bucket of buckets)bucket.sort((a,b)=>String(a.match.start||"").localeCompare(String(b.match.start||""))||String(a.record.title||"").localeCompare(String(b.record.title||""),lang));
    for(let index=0;index<7;index++){const dateValue=dayDate(start,index),day=new Date(dateValue+"T00:00:00Z"),section=document.createElement('section'),head=document.createElement('h3'),button=document.createElement('button'),items=buckets[index];section.className='week-day';if(dateValue===date)section.classList.add('is-selected');if(dateValue===today)section.classList.add('is-today');button.type='button';button.className='week-day-link';button.setAttribute('aria-label',new Intl.DateTimeFormat(lang==='ja'?'ja-JP':'en-US',{dateStyle:'full',timeZone:'UTC'}).format(day)+', '+t.showDay);button.setAttribute('aria-current',dateValue===date?'date':'false');const weekday=new Intl.DateTimeFormat(lang==='ja'?'ja-JP':'en-US',{weekday:'short',day:'numeric',month:'short',timeZone:'UTC'}).format(day);button.textContent=weekday;if(dateValue===today){const marker=document.createElement('span');marker.className='state-marker';marker.textContent=t.todayMarker;button.append(' ',marker)}if(dateValue===date){const marker=document.createElement('span');marker.className='state-marker selected-marker';marker.textContent=t.selected;button.append(' ',marker)}button.addEventListener('click',()=>{date=dateValue;setView('day')});head.append(button);section.append(head);if(!items.length){const empty=document.createElement('p');empty.className='week-empty';empty.textContent=t.emptyDate;section.append(empty)}else{for(const {record,match} of items){const row=document.createElement('article'),meta=document.createElement('p'),title=document.createElement('strong'),kind=document.createElement('span'),when=matchTime(record,match);row.className='week-record';row.tabIndex=0;row.setAttribute('role','button');row.addEventListener('click',()=>showDetail(record,match));row.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();showDetail(record,match)}});meta.className='week-record-meta';kind.className='type-marker';kind.textContent=t[{E:'event',R:'reminder',D:'deadline',T:'task'}[record.type]];meta.append(kind);if(when){const time=document.createElement('time');time.textContent=when;time.dateTime=match.start;meta.append(' ',time)}title.textContent=record.title||'';row.append(meta,title);section.append(row)}}target.append(section)}$('week-range').textContent=weekLabel(start,dayDate(start,6));}
  async function loadWeek(){const start=weekStart(date),end=dayDate(start,6);$('week-range').textContent=weekLabel(start,end);$('week-days').replaceChildren();feedback.text=t.loading;try{const agenda=await api('/api/agenda?from='+start+'&to='+end);renderWeek(agenda.records||[],start);feedback.echo=(date===today?t.today+" · ":"")+t.weekOf+" "+weekLabel(start,end)}catch(e){feedback.text=t.error+' '+e.message}}
  function monthStart(value){return value.slice(0,7)+"-01"}
  function monthShift(value,delta){const [y,m]=value.split('-').map(Number);return new Date(Date.UTC(y,m-1+delta,1)).toISOString().slice(0,10)}
  function monthLabel(value){return new Intl.DateTimeFormat(lang==="ja"?"ja-JP":"en-US",{year:"numeric",month:"long",timeZone:"UTC"}).format(new Date(value+"T00:00:00Z"))}
  function densityText(count){if(!count)return t.densityNone;return (count<=2?t.densityLow:count<=5?t.densityMedium:t.densityHigh)+" · "+count+" "+t.items}
  function renderMonth(records,start,end){const counts=new Map();for(const record of records){if(!["E","R","D","T"].includes(record.type))continue;for(const match of Array.isArray(record.matches)?record.matches:[]){const occurrence=String(match.start||"").slice(0,10);if(occurrence>=start&&occurrence<=end)counts.set(occurrence,(counts.get(occurrence)||0)+1)}}const grid=$('month-grid'),weekdays=$('month-weekdays');grid.replaceChildren();weekdays.replaceChildren();const locale=lang==="ja"?"ja-JP":"en-US";for(let i=0;i<7;i++){const label=document.createElement('span');label.textContent=new Intl.DateTimeFormat(locale,{weekday:'narrow',timeZone:'UTC'}).format(new Date(dayDate('2026-09-07',i)+'T00:00:00Z'));weekdays.append(label)}for(let value=start;value<=end;value=dayDate(value,1)){const count=counts.get(value)||0,outside=value.slice(0,7)!==date.slice(0,7),button=document.createElement('button'),number=document.createElement('span'),density=document.createElement('span'),full=new Intl.DateTimeFormat(locale,{dateStyle:'full',timeZone:'UTC'}).format(new Date(value+'T00:00:00Z'));button.type='button';button.className='month-day';if(outside)button.classList.add('is-outside');if(value===date)button.classList.add('is-selected');if(value===today)button.classList.add('is-today');button.setAttribute('aria-label',[full,densityText(count),outside?t.outsideMonth:'',value===today?t.todayMarker:'',value===date?t.selected:''].filter(Boolean).join(', '));button.setAttribute('aria-current',value===date?'date':'false');number.className='month-number';number.textContent=String(Number(value.slice(8)));density.className='month-density density-'+(count===0?'none':count<=2?'low':count<=5?'medium':'high');density.textContent=count?String(Math.min(count,9)):'·';density.setAttribute('aria-hidden','true');button.append(number,density);button.addEventListener('click',()=>{date=value;setView('day')});grid.append(button)}$('month-heading').textContent=monthLabel(monthStart(date))}
  async function loadMonth(){const first=monthStart(date),start=weekStart(first),next=monthShift(first,1),nextWeek=weekStart(next),end=dayDate(nextWeek,nextWeek===next?-1:6);$('month-heading').textContent=monthLabel(first);$('month-grid').replaceChildren();feedback.text=t.loading;try{const agenda=await api('/api/agenda?from='+start+'&to='+end);renderMonth(agenda.records||[],start,end);feedback.echo=monthLabel(first)}catch(e){feedback.text=t.error+' '+e.message}}
  function renderNotes(){
    list($('notes'),noteRows,i=>card($('notes'),i.title,vals(i,'body')[0]||'',writable&&i.editable?()=>openEditor('N',i):null,t.editNote));
    if(!noteRows.length)$('notes').firstElementChild.textContent=t.emptyNotes;
    $('notes-count').textContent=noteRows.length+' / '+(notesPage?.total||0)+' '+t.items;
    $('more-notes').hidden=!notesPage?.has_more;
    $('more-notes').disabled=notesBusy;
  }
  const eventText=event=>event?t["event_"+event]||event:"";
  function renderReview(review) {
    const panel = $("review-panel");
    panel.hidden = dayPosition()==="future" || preference().hidden_sections.includes("review");
    if (panel.hidden) return;
    $("more-review").hidden = true;
    if (!review) {
      $("review-summary").textContent = t.focusUnavailable;
      $("review-activity").replaceChildren();
      return;
    }
    if (dayPosition()==="today") {
      $("review-summary").textContent = t.focusCompleted+" · "+(review.complete?t.flowComplete:t.flowPartial);
      list($("review-activity"),review.completed||[],row=>card($("review-activity"),row.target?.title||row.title||"",t.focusCompleted,null));
      return;
    }
    $("review-summary").textContent = t.reviewEvents+(review.counts?.events||0)+" · "+(review.complete?t.flowComplete:t.flowPartial);
    const rows = [...(review.completed||[]),...(review.changed||[]),...(review.reopened_or_rescheduled||[])], expanded = panel.dataset.expanded==="true";
    list($("review-activity"),rows.slice(0,expanded?rows.length:5),row=>card($("review-activity"),row.target?.title||row.title||eventText(row.event),eventText(row.event),null));
    $("more-review").hidden = expanded||rows.length<=5;
    $("more-review").onclick = ()=>{panel.dataset.expanded="true";renderReview(review)};
  }

  async function moreNotes(){
    if(notesBusy||!notesPage?.has_more)return;
    const generation=loadGeneration,selectedDate=date,previous=notesPage;
    notesBusy=true;renderNotes();
    try{
      const page=await api('/api/notes?date='+selectedDate+'&limit='+NOTE_PAGE_SIZE+'&offset='+previous.next_offset);
      if(generation!==loadGeneration||view!=='day'||selectedDate!==date)return;
      if(page.revision!==previous.revision){await load();return}
      noteRows.push(...(page.items||[]));notesPage=page;
    }catch(e){if(generation===loadGeneration)feedback.text=t.error+e.message}
    finally{if(generation===loadGeneration){notesBusy=false;renderNotes()}}
  }
  async function load(){focusDataReady=false;focusAgenda=[];focusReview=null;renderReview(null);resetFlow();updateFocus();const generation=++loadGeneration;resetTimeReview();notesBusy=false;notesPage=null;noteRows=[];renderNotes();if(!date)return;$('date').value=date;updateTemporalContext();$('date').setAttribute("aria-label",view!=="day"?t.anchorDate:t.choose);updateUrl();$('day-view').hidden=view!=="day";$('week-view').hidden=view!=="week";$('month-view').hidden=view!=="month";$('dock').hidden=view!=="day";$('view-day').setAttribute("aria-pressed",String(view==="day"));$('view-week').setAttribute("aria-pressed",String(view==="week"));$('view-month').setAttribute("aria-pressed",String(view==="month"));$('title').textContent=view==="week"?t.weekTitle:view==="month"?t.monthTitle:t.title;$('prev').setAttribute("aria-label",view==="week"?t.previousWeek:view==="month"?t.previousMonth:t.previousDay);$('next').setAttribute("aria-label",view==="week"?t.nextWeek:view==="month"?t.nextMonth:t.nextDay);if(view==="week"){await loadWeek();return}if(view==="month"){await loadMonth();return}feedback.text=t.loading;
    try{const [day,agenda,habits,notes,journals,tasks,review]=await Promise.all([api('/api/command-center?date='+date+scopeQuery()),api('/api/agenda?from='+date+'&to='+date+scopeQuery()),api('/api/items?type=H&open_only=true'),api('/api/notes?date='+date+'&limit='+NOTE_PAGE_SIZE+scopeQuery()),api('/api/items?type=J'),api('/api/items?type=T&open_only=true'),dayPosition()!=="future"?api('/api/temporal-review?date='+date+'&limit=100'+scopeQuery()).catch(()=>null):Promise.resolve(null)]);
      if(generation!==loadGeneration)return;
      focusAgenda=agenda.records||[];focusReview=review;focusDataReady=true;
      sourceRevision=tasks.source_revision||habits.source_revision||notes.source_revision||(recordRevisions.get(tasks)||'').replace(/^"|"$/g,'');
      list($('schedule'),(agenda.records||[]).filter(x=>["E","R","D"].includes(x.type)),x=>card($('schedule'),x.title,scheduleMeta(x),null,null,x));
      const refs=[...(day.due_today||[]),...(date===today?(day.next_actions||[]):[])].filter(x=>x.kind==="T"&&!x.blocked);const rows=(tasks.items||[]).filter(i=>refs.some(r=>(r.id&&r.id===i.id)||(r.source===i.source&&r.line===i.line)||r.title===i.title));
      list($('tasks'),rows,i=>{const action=dayPosition()==="today"&&writable&&i.editable?async()=>{showCompletion(i)}:null;card($('tasks'),i.title,taskMeta(i),action,action?t.done:"",i)});
      list($('habits'), (habits.items || []).filter(i => !['[x]', '[-]'].includes(i.status)), i => {
        const selectedDate = date;
        const finished = vals(i, 'done').some(value => value.slice(0, 10) === selectedDate);
        const minimumRecorded = finished && vals(i, 'habit_minimum_done').includes(selectedDate);
        const restDates = vals(i, 'habit_rest');
        const resting = !finished && restDates.includes(selectedDate);
        const hasMinimum = vals(i, 'habit_minimum').some(value => value.trim());
        const action = dayPosition() === "today" && writable && i.editable && !finished ? async choice => {
          if (generation !== loadGeneration) return;
          const details = {...i.details};
          if (resting) {
            const remaining = restDates.filter(value => value !== selectedDate);
            if (remaining.length) details.habit_rest = remaining;
            else delete details.habit_rest;
          } else if (choice === "rest") {
            details.habit_rest = [...restDates, selectedDate];
          } else {
            details.done = [...vals(i, 'done'), selectedDate];
            const minimumDates = vals(i, 'habit_minimum_done');
            if (choice === "minimum" && !minimumDates.includes(selectedDate)) {
              details.habit_minimum_done = [...minimumDates, selectedDate];
            }
          }
          await api(pathFor(i), {
            expectedRevision: recordRevisions.get(i) || null,
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status: i.status, type: i.type, title: i.title, details}),
          });
          await load();
        } : null;
        const guidance = [
          ['habit_cue', t.habitCue],
          ['habit_minimum', t.habitMinimum],
        ].map(([key, label]) => {
          const value = vals(i, key).map(text => text.trim()).filter(Boolean).join(', ');
          return value ? label + (lang === 'ja' ? '：' : ': ') + value : '';
        });
        let status = stateText(i.status) || t.habitOpen;
        if (finished) status = minimumRecorded ? t.habitMinimumRecorded : t.habitDone;
        else if (resting) status = t.habitRestRecorded;
        const additionalActions = [];
        if (!resting) {
          if (hasMinimum) additionalActions.push([t.habitRecordMinimum, "minimum"]);
          additionalActions.push([t.habitRest, "rest"]);
        }
        card($('habits'), i.title, status, action, resting ? t.habitUndoRest : t.done,
          i, guidance, additionalActions);
      });
      notesPage=notes;noteRows=notes.items||[];renderNotes();
      $('review-panel').dataset.expanded="false";renderReview(review);
      const j=(journals.items||[]).find(i=>vals(i,'on').some(d=>String(d).slice(0,10)===date));$('journal').textContent=j?(vals(j,'body')[0]||j.title):t.empty;$('edit-journal').dataset.id=j?.id||'';$('edit-journal').disabled=!writable;
      applyPlannerPreference();
      renderTimeReview(day,tasks,review);
      feedback.echo=date===today?t.today:date;
    }catch(e){if(generation===loadGeneration){feedback.text=t.error+' '+e.message;$('time-review-evidence').textContent=t.timeReviewUnavailable;$('time-review-count').textContent=t.timeReviewUnavailable}}}
  function shift(n){date=view==="month"?monthShift(monthStart(date),n):dayDate(date,n*(view==="week"?7:1));load()}
  const sectionIds=["schedule","tasks","habits","notes","journal","review"];
  let plannerDefaults={sections:sectionIds,hidden_sections:[],density:"comfortable"},plannerPreference=null,layoutInUrl=false;
  function normalizePlannerPreference(value){const source=value||plannerDefaults,sections=Array.isArray(source.sections)?source.sections:sectionIds,ordered=[...new Set(sections.filter(id=>sectionIds.includes(id))),...sectionIds.filter(id=>!sections.includes(id))];return {sections:ordered,hidden_sections:[...new Set((Array.isArray(source.hidden_sections)?source.hidden_sections:[]).filter(id=>sectionIds.includes(id)))],density:["comfortable","compact"].includes(source.density)?source.density:"comfortable",time_bands:validTimeBands(source.time_bands)?{...source.time_bands}:{...defaultTimeBands}}}
  function localPlannerPreference() {
    try {
      return normalizePlannerPreference(JSON.parse(localStorage.getItem("lifetxt_planner_prefs_v1")));
    } catch (_) {
      return normalizePlannerPreference(plannerDefaults);
    }
  }
  function preference() {
    if (plannerPreference) return plannerPreference;
    const local = localPlannerPreference();
    const linked = layoutUrl.read(params);
    const validSections = ids => Array.isArray(ids) && ids.every(id => sectionIds.includes(id));
    layoutInUrl = validSections(linked?.sections) && validSections(linked.hidden_sections)
      && ["comfortable", "compact"].includes(linked.density);
    plannerPreference = layoutInUrl
      ? normalizePlannerPreference({...linked, time_bands: local.time_bands})
      : local;
    return plannerPreference;
  }
  function applyPlannerPreference(){const pref=preference(),day=$('day-view');day.classList.toggle('density-compact',pref.density==='compact');for(const id of sectionIds){const node=focusTarget(id);if(node)node.hidden=pref.hidden_sections.includes(id)}for(const id of pref.sections){const node=focusTarget(id);if(node)day.append(node)} if(focusDataReady)renderReview(focusReview);$("time-review-panel").hidden=view!=="day"||date!==today||pref.hidden_sections.includes("review");updateFocus(); }
  function renderPreferenceControls(){const pref=preference(),target=$('section-preferences');target.replaceChildren();for(const id of pref.sections){const row=document.createElement('div');row.className='preference-row';row.dataset.section=id;const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=!pref.hidden_sections.includes(id);check.dataset.section=id;const name=id==='review'?t.reviewActivity:t[id];label.append(check,' ',name);const up=document.createElement('button'),down=document.createElement('button');up.type=down.type='button';up.textContent=t.moveUp;down.textContent=t.moveDown;up.setAttribute('aria-label',t.moveUp+' '+name);down.setAttribute('aria-label',t.moveDown+' '+name);up.onclick=()=>{const before=row.previousElementSibling;if(before)target.insertBefore(row,before)};down.onclick=()=>{const after=row.nextElementSibling;if(after)target.insertBefore(after,row)};row.append(label,up,down);target.append(row)}$('density').value=pref.density;for(const k of ["morning","daytime","evening"])$("focus-"+k).value=pref.time_bands[k];$("focus-settings-error").textContent="";}
  function writePlannerLayoutUrl() {
    const {sections, hidden_sections, density} = preference();
    layoutUrl.write({sections, hidden_sections, density});
  }
  function saveLocalPlannerPreference(value) {
    try { localStorage.setItem("lifetxt_planner_prefs_v1", JSON.stringify(value)); } catch (_) {}
  }
  function savePlannerPreference(value) {
    const previous = preference();
    plannerPreference = normalizePlannerPreference(value);
    if (layoutInUrl) {
      writePlannerLayoutUrl();
      if (JSON.stringify(previous.time_bands) !== JSON.stringify(plannerPreference.time_bands)) {
        saveLocalPlannerPreference({...localPlannerPreference(), time_bands: plannerPreference.time_bands});
      }
    } else {
      saveLocalPlannerPreference(plannerPreference);
    }
    applyPlannerPreference();
  }
  function resetPlannerPreference() {
    if (layoutInUrl) {
      savePlannerPreference({...plannerDefaults, time_bands: preference().time_bands});
    } else {
      plannerPreference = normalizePlannerPreference(plannerDefaults);
      try { localStorage.removeItem("lifetxt_planner_prefs_v1"); } catch (_) {}
      applyPlannerPreference();
    }
    renderPreferenceControls();
  }
  function bindLayoutUrlControls() {
    $("customize").onclick = () => {
      renderPreferenceControls();
      $("layout-url-status").textContent = layoutInUrl ? t.layoutScoped : "";
      $("customize-dialog").showModal();
    };
    $("layout-url-share").onclick = () => {
      preference();
      layoutInUrl = true;
      writePlannerLayoutUrl();
      $("layout-url-status").textContent = t.layoutLinked;
    };
    $("reset-customization").onclick = resetPlannerPreference;
  }
  function openEditor(kind,item=null){if(!writable)return;edit={kind,item,revision:item?(recordRevisions.get(item)||null):revision};$('editor-heading').textContent=kind==='J'?t.journal:t.notes;$('editor-title').value=item?.title||(kind==='J'?'Journal '+date:'');$('editor-body').value=vals(item,'body')[0]||'';$('editor-feedback').textContent='';$('editor').showModal();$('editor-title').focus()}
  async function boot(){translate();$("focus-mode").onchange=()=>{focusMode=$("focus-mode").value;updateFocus();};const clockStarted=performance.now();$('more-notes').onclick=moreNotes;bindLayoutUrlControls();$('customize-form').onsubmit=e=>{e.preventDefault();const rows=[...$('section-preferences').children],hidden=rows.filter(row=>!row.querySelector('input').checked).map(row=>row.dataset.section);const bands=Object.fromEntries(["morning","daytime","evening"].map(k=>[k,$("focus-"+k).value]));if(!validTimeBands(bands)){$("focus-settings-error").textContent=t.focusInvalid;$("focus-morning").focus();return;}savePlannerPreference({time_bands:bands,sections:rows.map(row=>row.dataset.section),hidden_sections:hidden,density:$('density').value});$('customize-dialog').close()};$('prev').onclick=()=>shift(-1);$('next').onclick=()=>shift(1);$('today').onclick=()=>{date=today;load()};$('prev').setAttribute('aria-label',t.previousDay);$('next').setAttribute('aria-label',t.nextDay);$('view-day').onclick=()=>setView('day');$('view-week').onclick=()=>setView('week');$('view-month').onclick=()=>setView('month');$('date').onchange=()=>{if(/^\d{4}-\d\d-\d\d$/.test($('date').value)){date=$('date').value;load()}};
    $('open-capture').onclick=()=>{if(!writable)return;captureRevision=sourceRevision?'"'+sourceRevision+'"':revision;$('capture-feedback').textContent='';$('capture-dialog').showModal()};$('capture-form').onsubmit=async e=>{e.preventDefault();if(pending||!writable)return;pending=true;const b=$('capture-form').querySelector('[type=submit]');b.disabled=true;try{await api('/api/items/capture',{expectedRevision:captureRevision,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('capture-text').value,expected_source_revision:(captureRevision||'').replace(/^"|"$/g,'')})});$('capture-text').value='';$('capture-dialog').close();feedback.text=t.captured;await load()}catch(err){$('capture-feedback').textContent=t.captureError+err.message}finally{pending=false;b.disabled=false}};
    $('new-note').onclick=()=>openEditor('N');$('edit-journal').onclick=async()=>{const j=(await api('/api/items?type=J')).items||[];openEditor('J',j.find(i=>vals(i,'on').some(d=>String(d).slice(0,10)===date))||null)};
    $('editor-form').onsubmit=async e=>{e.preventDefault();if(!edit||pending)return;const {kind,item,revision:expectedRevision}=edit,body=$('editor-body').value.trim();if(kind==='J'&&!body){$('editor-feedback').textContent=t.journalRequired;return}const details={...(item?.details||{})};if(body)details.body=[body];else delete details.body;if(kind==='J'&&!details.on)details.on=[date];const payload={status:'[N]',type:kind,title:$('editor-title').value.trim(),details};pending=true;const button=$('editor-form').querySelector('[type=submit]');button.disabled=true;try{await api(item?pathFor(item):'/api/items',{expectedRevision,method:item?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});$('editor').close();feedback.text=t.saved;await load()}catch(err){$('editor-feedback').textContent=t.saveError+err.message}finally{pending=false;button.disabled=false}};
    $('time-review-mode').onchange=renderTimeReviewPrompts;$('time-review-flow').onclick=openTimeReviewFlow;
    document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());const [config,health,areas,views]=await Promise.all([api('/api/config'),api('/api/health'),api('/api/areas'),api('/api/saved-views')]);today=config.today;acceptWorkspaceClock(config,clockStarted);plannerDefaults=normalizePlannerPreference(config.web?.planner);const scopeSelect=$("scope");(areas.areas||[]).forEach(a=>{const o=document.createElement("option");o.value="area:"+a.name;o.textContent="Area: "+a.name;scopeSelect.append(o)});(views.views||[]).forEach(v=>{const o=document.createElement("option");o.value="saved_view:"+v.name;o.textContent="Saved View: "+v.name;scopeSelect.append(o)});scopeSelect.value=scopeArea?("area:"+scopeArea):scopeView?("saved_view:"+scopeView):"";scopeSelect.onchange=()=>{const value=scopeSelect.value;scopeArea=value.startsWith("area:")?value.slice(5):"";scopeView=value.startsWith("saved_view:")?value.slice(11):"";updateUrl();load()};writable=!health.read_only&&(health.can_write ?? Boolean(health.writable_path));['open-capture','new-note','edit-journal'].forEach(id=>$(id).disabled=!writable);if(!writable)feedback.text=t.readonly;date=/^\d{4}-\d\d-\d\d$/.test(params.get('date')||'')?params.get('date'):today;applyPlannerPreference();await load();document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible")resumeClock();else{workspaceClock=null;updateFocus();}});window.addEventListener("focus",resumeClock);todaySyncTimer=setInterval(syncToday,60000)}
  function bootError(e){feedback.text=t.error+e.message;['open-capture','new-note','edit-journal'].forEach(id=>$(id).disabled=true)}
  $('flow-form').addEventListener('submit',requestFlow);['flow-start','flow-end'].forEach(id=>$(id).addEventListener('input',resetFlow));$('flow-disclosure').addEventListener('toggle',()=>{if(!$('flow-disclosure').open)resetFlow()});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>boot().catch(bootError),{once:true});else boot().catch(bootError);
})();
