# Daily Flow Lite：日次提案の設計契約案

親 #1142、調査 #1143 の成果物です。**D1〜D3は2026-10-08に承認済み（#1143 / PR #1148）です。
#1144では共有pure coreのみを実装し、CLI・API・UIは後続Issueで扱います。**
詳細な型・疑似コード・検証仕様は [英語版](../en/daily-flow-lite-contract.md) と
同じ判断に基づきます。両版に差があれば、承認前に修正してください。

## 調査時の作業契約・判断の境界（#1143）

Requirements & Design / Investigation / S / complexity 4/10
（範囲1・依存1・不確実性1・検証1・運用0）/ Standard。
adaptive-default、Kanban、W-modelを継承します。実行担当はCodex、独立した
要件・設計レビューと判断・mergeの担当は @Eruhitsuji（レビュー未完了）です。
変更対象はEN/JA設計資料と後続Issueの具体化のみです。

追跡は proposed `req-daily-flow-planner-lite` → proposed
`cap-daily-flow-planner-lite` → #1142 → #1143 → 設計PR・検証証拠。
これらは #1144 でexperimentalな共有coreとして登録します。consumer実装は別作業です。
ロールバックは追加資料のrevertで、ユーザーデータの移行はありません。
後続Issueは判断承認・依存完了・Ready条件成立までinboxを維持します。

## ソース・テストで確認した事実

調査対象はmain `8b16fcfb`（2026-10-08）。以下は現状の事実で、後段の提案と
区別します。ソースへのリンクと詳細なreuse mapは英語版にあります。

| Capability | 確認した内容 |
| --- | --- |
| `cap-next-actionable-convergence` | nextactionの対象はT/D/R/H、状態は未完了・進行中。someday/maybe/waiting/blockedタグ、未完了・未解決依存を除外。依存判定は全入力に対して行う。 |
| `cap-next-priority-ranking` / `cap-next-why-explanation` | CLIのrankは期限超過日→priority→due日→created日→行番号。不正dueを拒否。 |
| `cap-daily-command-center` | Todayが使うnext_action_itemsはpriorityの別マッピング、dueまたはdoの文字列、行番号。CLI rankと同じ並び順ではない。 |
| `cap-freebusy-detection` | E/Rのfrom/to・at・onのみ。due/do/notifyは占有ではない。repeatはskipped_recurring。点や片側だけの期間はinstant。接する区間は結合し、真の重複だけconflict。statusによる除外はしない。 |
| `cap-importance-priority-matrix` | importanceは人間の記録、urgencyはdueから導出。priorityとは別。日付dueの期限はその日の最終マイクロ秒。matrix自体は依存解決しない。 |
| `cap-workspace-aware-timezone-context` | 共通timezone_policyは曖昧・存在しない時刻を検出できる。一方freebusyのaware値変換はホスト時刻であり、workspace時刻の正しさを保証する層ではない。 |
| `cap-web-mobile-planner` | 共有モデルを読むconsumerとして拡張する。既存Day/Week/Month・Past Reviewの意味を変えない。 |

area/saved_viewはread_scopeの既存選択器（同時指定不可）、projectは既存filterを
再利用します。Format 1.0のestは見積作業量、elapsedは累積実績です。
**est−elapsedが残作業時間であるという契約はありません。**

## 承認済み判断・別途必要なconsumerの判断

決定者は @Eruhitsuji です。D1〜D3は #1143 で承認済みです。以下の表は検討した代替案を残したものです。
CLI/APIの公開契約と最終mergeは別の判断です。

| 判断 | 推奨案 | 代替案・影響 |
| --- | --- | --- |
| D1 不確実な空き時間 | 関係し得るE/Rの占有を保証できなければ、その対象時間帯全体のタスク配置を停止。既知の予定・点・候補一覧・診断を表示。 | 警告付きで見かけの空きに配置すると、予定と衝突する提案になり得るため延期。 |
| D2 見積・休憩 | 正の単一estを全量確保し、elapsedは差し引かない。分割なし。休憩とbufferは明示した0分が初期方針、任意の非負分数を指定可能。 | 残作業見積の専用意味や個人の休憩既定値には別設計・設定承認が必要。 |
| D3 順序・時間・入力 | CLI rankを再利用し同順位はsource/IDで確定。importanceは説明情報。日付・時間帯・workspace zone・active sourceを明示。過去日とDST移行日の配置はLite対象外。 | importance優先、期限最優先、過去シミュレーション、DST対応、暗黙の勤務時間は別判断・検証が必要。 |

CLI名・flagとWeb URI・auth・可視性はD1〜D3の承認に含みません。
#1145/#1146で公開インターフェースの承認を別途行います。#1146は公開APIとして
Highを維持し、routeが小さいという理由でStandardへ下げません。

## 日時と入力

変更しないsnapshotを入力とします。activeな認可済みworkspace全項目、source
revision、設定・scope snapshot、対象日、時間帯、解決済みtimezone、注入した
基準時刻evaluated_at、policy versionと上限を含めます。既存のsnapshot/revision
機構を選定し、Gitがないテキストファイルでも使える形にします。

日付だけでは勤務時間を推測しません。時間帯がなければ入力エラーです。
休日・曜日を自動推測せず、週末も明示時間帯があれば同条件です。新設定キーは
導入しません。将来設定を追加するならプロジェクトの設定完了規則に従います。
区間は[start,end)、1ローカル日内。終端だけ翌日0時を許可します。

今日の開始はmax(指定開始,evaluated_at)。秒を切り捨てません。未来は時間帯全体。
過去日はpast_date_unsupported、今日の終了後はwindow_elapsedで配置なしです。
rankの期限超過判定は対象日、urgencyの基準は有効開始日時とし、出力に記録します。

日付doは対象日に取り組む意図、日時doは最早開始です。固定予定ではありません。
未来doはfuture_intentで未配置、過去doは候補可能。複数・不正do/dueは未配置。
dueはsoft deadline：期限内に終わる最初の枠を探し、なければ最早の実行可能枠に
配置してdeadline_missedを説明します。既に期限超過でも候補から外しません。
日付dueはMatrixと同じ日末、日時dueは実時刻です。

#1144のtimezone adapterは共通interpreterでderived copyを正規化し、オフセットが
一定の日だけworkspace壁時計のnaive値でagenda/freebusyを呼びます。aware値を
freebusyのホスト変換に渡しません。元の値はprovenanceに保持します。
境界・offset・on/atの対応を検証できない、fold/gapがある、対象区間に関係する
DST移行がある場合はunsupported_timezone_windowとして配置を停止します。
既存エンジンやFormatを変えず、対応拡大は別Issueとします。

## Source・候補・占有

占有と依存は**認可済みactive全体**、project/area/saved_viewは**候補だけ**を
絞ります。別projectの会議を空き扱いしません。認可された情報だけでは占有を
証明できないWeb環境は利用不可・不完全とし、隠れた予定の時刻・数・名称を
診断や空き枠で漏らしません。具体的なauth契約は #1146 で確定します。

配置対象は共有is_actionableを通るTだけです。完了・取消・保留・parking・blocked
は対象外、D/R/H/Eは作業タスクにしません。除外されたTは理由付きunplaced、
他kind等は認可範囲内の除外数で説明します。候補を置いたことだけでは依存は
完了しないため、後続タスクを同一提案でunlockしません。

単一の一意IDが必要です。IDなしTはmissing_identity、重複IDはambiguous_identity
で配置停止。依存未解決・曖昧な参照・cycleは安全側に扱います。
同じsourceを二重に読むことは防止しますが、別pathの同じ内容を同一タスクと
推測しません。週次の過去ファイルを自動scan/importしません。
archiveの完了依存を使う場合は明示的にcontext-onlyとして読み、候補・占有に
加えません。active/context双方のID衝突を確認します。固定レイアウト不要です。
読み取り中のrevision変化は1回だけ再試行後source_changedで停止します。
[テキストエディタのみの運用](text-editor-only-workflow.md)はそのまま使えます。

固定占有は既存freebusyのE/R semanticsを保守的に再利用し、取消を含むstatusで
新たに除外しません。onは終日占有、on+atも既存の両match（終日含む）を保ちます。
Rのatは点で占有なし、Eのatだけは所要時間不明です。片側期間、不正・非正の期間、
時刻欠損、曖昧な対応、repeatはD1対象です。正しい完全な対象外区間は除外可能。
repeatの起点が遠いことだけでは対象外を証明しません。初期Liteは疑わしい入力で
日全体を不確実とできます。重複予定はunionを占有、接するだけならconflictなしです。

## 配置と説明

estは既存normalize/validateとparse_elapsedで解釈し、単一の正の整数分を要求。
欠損・0・負・不正・複数は未配置。推測見積、分割、progressからの時間推定はなし。
elapsed>=estでも完了とはしません。不正elapsedは警告、時間差引きはなしです。

break_minutesとbuffer_minutesは非負整数、各値は時間帯長以下。
**最後のタスクも含め、各タスク直後に休憩・bufferを確保**します。
3区間が1つの空き枠に連続して入らなければ未配置です。0分のrowは出しません。
残りの空き時間をbufferと偽りません。

CLIの_rank_keyを必要なら共有pure seamへ抽出し、既存CLI順序を変えず利用します。
行番号までのrank keyに安定したsource identityとfull IDを追加します。
Todayの異なるsortを代用しません。importance/urgencyは理由表示に留めます。

手順はsnapshot・上限検証→全体依存判定→候補filter→占有保証→理由付き分類→
rank順に1回ずつearliest fit。do以降で期限内に入る枠を優先し、なければ最早枠。
見積＋休憩＋bufferを予約し、入らないタスクはinsufficient_capacity。
最適解・backtracking・並列作業は約束しません。
同時刻のtimelineはfixed/candidate/policy_break/buffer、さらにsource/ID順。
instantは別配列、unplacedはsource/line/ID、diagnosticsはcode/source/line順です。

## 読み取りモデル案

schemaはdaily-flow-lite-v1、policy_versionはlite-greedy-v1。
JSON Schema・公開APIの実装ではなく、将来の共有モデル案です。

| フィールド | 内容 |
| --- | --- |
| evaluated_at / timezone / date | offset付き基準日時、解決済みzone、対象日 |
| source_revision | source tokenとrevisionの整列リスト、設定/scope snapshot。公開境界に絶対pathを出さない。 |
| scope / window / policy | active/context-only・候補選択と占有scope、指定/有効区間、rank/urgency基準・休憩/余白・上限・full_estimate |
| completeness | complete/partial/blocked、占有certified/unknown、inventory complete/bounded、理由code |
| timeline | fixed/candidate/policy_break/bufferの型付き時系列 |
| instants / unplaced / excluded | 点、primary/secondary未配置理由、除外数 |
| diagnostics / why | code・severity・effect・安全な参照・params、EN/JAで同じcodeを使う理由 |

timeline rowにはkind/start/end/source ref/why、candidateにはduration_minutes/
rank_key/deadline_status、policy rowには対象candidateの参照を持たせます。
unknownはnull、推測値を入れません。fixed同士の重複は表示しますが、候補は
固定予定・他候補・休憩/余白と重ならず、各Tは最大1回です。

completeは検証・占有保証済みであり、容量不足による未配置は不完全ではありません。
partialは占有保証済みでも見積不明等の一部候補問題・候補上限がある状態。
blockedは時刻・snapshot・占有・ID・resourceの問題で配置全体を止める状態です。
provenanceはbounded、認可外の情報・raw text・秘密・私的pathを出しません。
revisionはstale検出用で、提案は保存済み・採用済み・実績ではありません。
whyはcode/paramsの辞書からEN/JA表示し、色やhoverだけで説明しません。

## 将来の受け入れfixture

以下は**将来実装の検証条件**であり、現時点でschedulerテストが通ったという
意味ではありません。英語版F1〜F20と対応します。

| Fixture | 期待する扱い |
| --- | --- |
| F1 repeat E | skipped_recurring、occupancy_unknown、配置なし |
| F2 終日E | 全枠占有、容量不足 |
| F3 R at / E at | Rは点のみ、Eは時間不明で停止 |
| F4 NY 2026-03-08 02:30 / 11-01 01:30 | DST gap/foldを黙って補正せず停止 |
| F5 est欠損/0/負/不正/複数 | missing/invalid/ambiguous_estimate、未配置 |
| F6 週次context-onlyの完了依存 | 明示読取なら解消、未読なら未解決 |
| F7 10-11時と10:30-11:30 | union占有、conflictを表示 |
| F8 from/to片側・逆転 | incomplete_period/invalid_span、配置停止 |
| F9 ID重複 | ambiguous_identity、二重配置なし |
| F10 est30m elapsed40m | 30m全量予約、完了扱いなし |
| F11 明日のdo / 当日11時のdo | 未配置 / 11時以降だけ |
| F12 今日12:34:56 / 過去日 | その時刻以前に配置なし / 対象外 |
| F13 不正E時刻/時刻なし/不正T due | Eは占有不明、T dueはそのTだけ未配置 |
| F14 別projectの予定・依存 | 候補filterでも占有・依存を消さない |
| F15 タスクだけは入るが休憩込みで入らない | policyを削らず未配置 |
| F16 読取中revision変化 / 隠れた占有 | bounded retry後停止 / 情報を漏らさず利用不可 |
| F17 同rank・同lineの別source | 入力列挙順を逆転してもcanonical JSON一致 |
| F18 cap超過 | busyを切り捨てず停止、候補capは不完全表示 |
| F19 終了後/接する予定/on+at | window_elapsed / conflictなし / 終日を保持 |
| F20 UTCホスト・Tokyo workspace・+09:00 | Tokyoに正規化しホスト変換に依存しない |

## 再現例

対象日2026-10-09、Asia/Tokyo、基準2026-10-08T18:00+09:00、09-12時、
休憩10分・buffer5分。active work.txtに英語版の5行fixtureを指定します。
予定は10-11時、Aはpriority:A/est45m、B・CはB/C/est30m、Unknownは見積なし。

結果はA 09:00-09:45、休憩09:45-09:55、buffer09:55-10:00、予定10-11時、
B 11:00-11:30、休憩11:30-11:40、buffer11:40-11:45。
Cは45分の枠が必要で残り15分しかなく未配置。Unknownはmissing_estimate。
占有certified、全体partial。休憩/bufferを0にするとCは11:30-12:00に入ります。
Aのdueを09:30にすればdeadline_missedを表示。固定予定・ファイルは変えません。

## 上限・計算量・性能

提案上限：context10,000項目、依存edge20,000、候補試行1,000、E/R1,000、正規化区間/空き枠2,048、
conflict pair10,000。freebusyのconflict列挙**前**にboundsを保証します。独立検証されたbounded shared sweepが
なければpotential pairをE*(E-1)/2で保守的に制限します。
占有・依存contextを先頭だけで切ることは禁止、上限超過はblockedです。
候補上限はrank上位1,000、残りはlimit_exceededと件数・bounded参照を示します。
必要な一覧を安全に保持できない場合はblocked summaryとし、黙って落としません。

N=context、D=依存edge、E=区間、C=候補、G=空き枠、K=conflict pair。
最悪時間O(N+D+E log E+C log C+C G+E²)、空間O(N+D+E+C+G+K)。
既存sweepは密な重複やactive list処理で二次になり得ます。Gには最大Cの増加を含む。

benchmark案：1,000T+100E、密な重複・短い枠・見積欠損・同順位を含め、3回warmup後
20回、parseとpure coreを分離、monotonic clockでp50/p95、tracemallocは別計測。
Python/OS/CPU/seedを記録。基準Linux hostでcore p95<=250ms、追加peak<=32MiBを
目標とし、上限データ・失敗ケースも検証します。**本調査では性能未測定です。**

既存rank＋greedyは簡潔で説明可能。期限最優先は既存priority選択を変えるため延期。
一般solverは依存・重み・探索timeout・説明の複雑性を増すためLiteでは採用しません。
性能未達ならprofile・Issue分割を先に行い、黙って上限を上げません。

## 後続作業・レビュー

| Issue | 承認後の独立した範囲とgate |
| --- | --- |
| #1144 S | 共有pure model、CLI rank seam、timezone/occupancy保証、bounded greedy。D1-D3承認、F1-F20・不変条件・benchmarkが必要。S超過なら先に分割。公開契約を追加するならHighを判断。 |
| #1145 S | CLIはrenderのみ。#1144とCLI公開契約承認、JSON一致・EN/JA・入力/読取専用検証。 |
| #1146 S/High | GET projection、既存auth/admission、privacy/bounds。#1144とAPI/auth/scope承認、High change package、隠れた占有推測・path漏洩・parity検証。 |
| #1147 S | opt-in Day panel、型別ラベル・理由・未配置・不確実性。#1146完了、320/360/390/430px・低い高さ・keyboard/screen-reader・EN/JA・loading/error/stale response・過去実績誤認防止検証。 |

非目標：doへの採用・書込、実績記録、archive自動import/rotation、repeat展開、
分割、複数日最適化、バックグラウンド更新、Remote/MCP権限、外部AI/サービス、
Format変更。エディタのみの環境で自動提案を生成できるとは主張しません。

残余リスク：D1は有用な提案を多く停止し得る、est全量は過大確保し得る、greedyは
最適ではない、legacy時間境界には回帰確認が必要、認可違反なら空き枠・依存の
推測漏洩が起き得る。自己レビューは独立承認の代用になりません。

## 調査の検証

既存test_freebusy/test_nextaction/test_priority_matrix/test_read_scope/
test_timezone_policy_v2を実行し、**65テスト成功**。
さらにtest_extra_cliを実行し、rank/理由を含む**46テスト成功**。
将来schedulerのfixture実行や性能達成を示す結果ではありません。
リンク・文書検証はPRに記録します。今回はruntime変更がないため実装向けformat/
lint/type全体は対象外。設計レビューでは決定性・占有保証・privacy・互換性を確認します。


## 共有coreの実装（#1144）

`lifetxt.daily_flow.build_daily_flow`をPythonから呼び出せます。読み取り済みの
認可されたsnapshotを受け取り、ファイル・ネットワークへアクセスしません。
`occupancy_complete`はcallerが明示する必須引数です。falseなら情報を漏らさない
blocked結果となり、枠や一覧を返しません。`snapshot_consistent=False`も配置停止。
`input_diagnostics`のparser errorも占有保証・配置を止めます。ファイル読取、pathの
認可・canonical化、bounded retry、Webの可視性保証はconsumerの責任です。
coreによるファイル探索・過去週importはありません。

```python
from lifetxt.parser import parse_text
from lifetxt.daily_flow import build_daily_flow

items, diagnostics = parse_text("[ ] T Review id:review est:30m\n")
proposal = build_daily_flow(
    items, date="2026-10-09", day_start="09:00", day_end="12:00",
    timezone="Asia/Tokyo", evaluated_at="2026-10-08T18:00+09:00",
    occupancy_complete=True, input_diagnostics=diagnostics,
    policy={"break_minutes": 10, "buffer_minutes": 5},
)
# proposal["timeline"]は未保存の提案です。ファイルへ書き込みません。
```

timezoneは解決済みzoneを明示し、localは受け付けません。日付・時間帯・policyの
不正はValueError、不確実な入力はblocked結果です。`free`は配置可能な場合だけ
残りの保証済み空き枠を返し、占有不明なら見かけの空き枠を返しません。
unplacedはsource token/line/ID順。whyはcode/paramsで、consumerがEN/JAへ表示します。

`context_items`は依存・ID確認だけに参加。`source_revisions`は正規化済みsource名と
既存snapshotのSHA-256を指定でき、callerがcurrentnessを保証します。既存
mutation.read_text_snapshotのdigestを利用します。未指定ならmutation.hash_textで
parsed recordsをhashし、basisはparsed_snapshotと明示します。file byte revisionや
CAS tokenとは主張しません。指定digestはsource_snapshotです。sourceは字句的に
正規化してhash表示し、symlink/caseの同一性は上流のadmissionで解決します。
一部sourceのdigestがなければ、そのsourceはparsed_snapshotと表示します。

追加上限：detail values40,000、総text4,000,000文字、title1,024文字、
各detail value/key/source4,096文字。hard limitを減らす指定だけ許可します。
超過はblocked summaryとなり、占有を黙って切り捨てません。on×atの組合せ展開前、
conflict列挙前にも上限を確認します。元データを変更せず、提案で依存をunlockしません。

F16はcurrentness/visibility flagのcore検証で、ファイルretryやWeb認可の実装証明
ではありません。CLI/API/Plannerは #1145/#1146/#1147。公開endpoint・generated
schema・設定キー・Format keyは追加していません。

`python -m unittest tests.test_daily_flow tests.test_daily_flow_performance`で
境界・seed付き不変条件・規模テスト、
`python -m tests.test_daily_flow_performance --benchmark`で再現可能な性能測定。
parseとcoreを分離し、環境付きの証拠を残します。unit testに不安定な速度閾値は
入れません。

初期timezone adapterは、対象日に関係する完全な予定が2日を超える場合、
transition保証の探索を上限で止めて配置を停止します。UTCの安全な複数日予定でも
停止し得る保守的な制限です。無制限な日時scanや、保証していない空き枠表示を
避けます。対応拡大には別の認証済みadapterが必要です。

測定環境はPython 3.12.14/Linux x86_64、seed0、warmup3回・測定20回。
parseは別測定、tracemallocも別run。各1,000T＋100Eで、通常caseのcore p95は
96.55ms/追加peak2.93MiB、密な重複caseは212.53ms/13.48MiBでした。
基準目標250ms/32MiBを満たしていますが、他環境のSLAを保証する値ではありません。
core/規模の専用43テスト、最終focused regression179テストで契約を検証。
最終headの独立した人間のレビュー・merge判断は未完了です。
