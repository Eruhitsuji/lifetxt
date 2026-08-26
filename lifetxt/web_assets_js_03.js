        "Switch Status between active records only and latest status per person.":
          "ステータス表示を「進行中のレコードのみ」と「人ごとの最新ステータス」で切り替えます。",
        "Cycle Agenda blocker filtering: all, only blocked, or hide blocked records.":
          "予定のブロックフィルタを順に切り替えます: すべて、ブロック中のみ、ブロック中を隠す。",
        "Download the current Items result as CSV, JSON, or Markdown.":
          "現在のアイテム結果を CSV、JSON、または Markdown でダウンロードします。",
        "Group the Items list without changing the source file.":
          "元ファイルを変更せずにアイテム一覧をグループ化します。",
        "Sort visible Items by line, time, title, type, status, or source.":
          "表示中のアイテムを行番号・時刻・タイトル・種類・ステータス・ソースで並べ替えます。",
        "Choose ascending or descending sort order.": "並べ替え順を昇順または降順から選びます。",
        "Limit the number of visible Items. Leave empty for all matching records.":
          "表示するアイテム数を制限します。空欄にすると条件に一致する全レコードを表示します。",
        "Search title, raw line, and detail values. Shortcut: /.":
          "タイトル・生の行・詳細値を検索します。ショートカット: /。",
        "Dashboard: overview KPI tiles, attention list, completions, and project progress.":
          "ダッシュボード: KPIタイル、要注意リスト、完了状況、プロジェクトの進捗を一覧表示します。",
        "Items: searchable record list with filters, grouping, edit modal, bulk actions, and exports.":
          "アイテム: フィルタ・グループ化・編集モーダル・一括操作・書き出しに対応した検索可能なレコード一覧です。",
        "Agenda: date-range list for due, do, at, from/to, on, and notify_at records.":
          "予定: due・do・at・from/to・on・notify_at を持つレコードの期間別一覧です。",
        "Timeline: chronological board for today, next 24 hours, or week with an updated now line.":
          "タイムライン: 今日・今後24時間・週単位で見られる、現在時刻ラインが更新される時系列ボードです。",
        "Calendar: month/week grid of dated records; click a day for Agenda or an entry for details.":
          "カレンダー: 日付付きレコードを月/週で表示するグリッドです。日付をクリックすると予定、エントリをクリックすると詳細が開きます。",
        "Focus: reduced-noise list of overdue, due-today, and in-progress work.":
          "フォーカス: 期限超過・本日期限・進行中の作業だけに絞った、雑音の少ない一覧です。",
        "Review: weekly/monthly/custom period summary with Markdown copy.":
          "レビュー: 週次/月次/任意期間のまとめをMarkdownとしてコピーできます。",
        "Messages: type M records, sender/recipient filters, and notification-oriented conversations.":
          "メッセージ: 種類 M のレコード、送信者/宛先フィルタ、通知志向の会話を扱います。",
        "Team: presence, workload, and recent messages grouped by person.":
          "チーム: 在席状況・作業量・最近のメッセージを人ごとにまとめて表示します。",
        "Status: latest or active presence records for each person.":
          "ステータス: 各メンバーの最新または進行中の在席レコードです。",
        "Notifications: due messages/reminders, acknowledge, snooze, and browser alert controls.":
          "通知: 期限が来たメッセージ/リマインダー、確認・スヌーズ・ブラウザ通知の操作です。",
        "Stats: charts, heatmaps, and type/status breakdowns.":
          "統計: グラフ、ヒートマップ、種類/ステータス別の内訳です。",
        "Graph: id, parent, ref, depends_on, blocks, and related links.":
          "グラフ: id・parent・ref・depends_on・blocks および related のリンクです。",
        "Display: read-focused wall mode that hides editing controls. Use Back or Exit Display to leave.":
          "表示: 編集操作を隠した閲覧専用の壁掛けモードです。戻る、または「表示を終了」で抜けられます。",
        "Kiosk: always-on board with clock, auto-refresh, optional kiosk_filter, and auto-scroll.":
          "キオスク: 時計・自動更新・任意の kiosk_filter・自動スクロールを備えた常時表示ボードです。",
        "Create a life.txt record. Pick a status, type, title, and detail keys; press n to open this editor from the keyboard.":
          "life.txt のレコードを作成します。ステータス・種類・タイトル・詳細キーを指定できます。キーボードから開くには n。",
        "Workflow state: [ ] open, [/] active, [x] done, [-] cancelled, [>] deferred, [?] maybe, [N] note.":
          "ワークフローの状態: [ ] 未着手, [/] 進行中, [x] 完了, [-] キャンセル, [>] 先送り, [?] 保留, [N] メモ。",
        "Record kind: T task, E event, D deadline, R reminder, H habit, N note, S presence status, M message, J journal.":
          "レコードの種類: T タスク, E イベント, D 締切, R リマインダー, H 習慣, N メモ, S 在席ステータス, M メッセージ, J 日誌。",
        "Short human-readable record text. Use quotes in raw life.txt if the title contains spaces.":
          "人が読みやすい短いレコード文です。タイトルに空白を含む場合は、生の life.txt では引用符で囲ってください。",
        "One key:value per line. Repeat the same key for multiple values. Use body: or | continuation lines for longer text.":
          "1行につき key:value を1つ。同じキーを繰り返すと複数の値を指定できます。長い文には body: または | の継続行を使います。",
      },
    };

    //: Labels that embed a date, count, or duration. A dictionary keyed by
    //: the whole string could never match these, so each language provides a
    //: pattern whose $1/$2 placeholders carry the numbers across untouched.
    const I18N_PATTERNS = {
      ja: [
        [/^Open (\d{4}-\d{2}-\d{2}) in Agenda$/, "$1 を予定で開く"],
        [/^(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})$/, "$1 〜 $2"],
        [/^View all (\d+) \((\d+) more\)$/, "すべて表示 $1 件 (他 $2 件)"],
        [/^View all (\d+) →$/, "すべて表示 $1 件 →"],
        [/^\+(\d+) more$/, "他 $1 件"],
        [/^Done \((\d+)d\)$/, "完了 ($1日)"],
        [/^Started (.+)$/, "$1 に開始"],
        [/^started (\d+) mins? ago$/, "$1 分前に開始"],
        [/^started (\d+) hrs? ago$/, "$1 時間前に開始"],
        [/^(\d+)d overdue$/, "$1 日超過"],
        [/^(\d+)d ago$/, "$1 日前"],
        [/^(\d+) days$/, "$1 日間"],
        [/^occ #(\d+)$/, "第 $1 回"],
        [/^Day (\d+) of (\d+)$/, "$2日間中 $1日目"],
      ],
    };

    //: Classes whose text is life.txt content rather than interface chrome.
    const I18N_RECORD_CLASSES = [
      "item", "item-title", "title", "meta", "source",
      "tl-entry", "tl-title", "cal-entry", "cal-entry-title",
      "focus-row", "focus-row-title", "focus-row-main", "focus-row-meta",
      "team-card", "msg-row", "diagnostic", "dash-item", "kpi-value",
      "dash-row-title", "person-status-title", "person-msg-title", "person-meta",
      "tl-card-title", "tl-card-meta", "message-thread-meta",
    ];

    //: Attribute values users read, translated with the same dictionary.
    const I18N_ATTRIBUTES = ["title", "placeholder", "aria-label"];

    let _i18nApplying = false;

    function currentLanguage() {
      const urlLang = (new URLSearchParams(location.search).get("lang") || "").toLowerCase();
      return urlLang || String(appConfig?.web?.language || "").toLowerCase();
    }