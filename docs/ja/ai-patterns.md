# 公式記述パターンカタログ

68件の架空の教育用パターンから、必要な分類だけを選んでください。Format 1.0が仕様の正本で、このカタログは仕様を追加・変更しません。コードはcanonical fixtureを日英で共用し、入力文は翻訳で意味を変えないよう原言語のまま掲載しています。

[Assistant Prompt Profile](../../prompts/lifetxt-assistant.md) / [Format 1.0](./life_txt_format_spec.md) / [Without MCP](./ai-integration.md#9-without-mcp)

## 段階的に読む

通常は依頼文とリポジトリURLをAIに渡します。AIはREADMEの入口からProfileを読み、必要なら本索引→該当分類→仕様へ進みます。全件の読込や複数URLの提示は必須ではありません。ブラウズ/取得不能なら資料未確認と明示し、CLI未実行は **not run** とします。

```text
「明日、草案を作る」をlifetxt形式に変換してください。
https://github.com/Eruhitsuji/lifetxt
```

これは取得・理解・正答・通知実行を保証しません。例の基準日時は相対日付の変換練習用であり、絶対日時を持つ提供済み履歴/状態スナップショットの現在時刻を表すものではありません。あなたの会話では実際の日時/TZを使い、例の日時を現在日として流用しないでください。

## 分類とカバレッジ

| Category | IDs | Cases | Source / reuse |
| --- | --- | ---: | --- |
| [型・用途](./ai-patterns/types.md) | PAT-TYPE-001–009 | 9 | §2–3, §9, §13–14; tasks/events/habits_reminders/diary/messages/team_status/status_presence |
| [状態・ライフサイクル](./ai-patterns/statuses.md) | PAT-STATUS-001–007 | 7 | §2, §7.5, §10, §14; tasks/events/messages/status_presence |
| [日時・タイムゾーン](./ai-patterns/time.md) | PAT-TIME-001–010 | 10 | §7.4, §8, §9.8–9.9; recurrence_time/messages + conformance |
| [繰り返し・境界](./ai-patterns/recurrence.md) | PAT-REC-001–008 | 8 | §7.6, §8.1; habits_reminders/recurrence_time + tests/test_recurrence.py |
| [ID・参照・階層](./ai-patterns/relationships.md) | PAT-REL-001–008 | 8 | §5.1, §7.1–7.2; linked/hierarchy/recurrence_time + tests/test_links.py |
| [引用・値・本文](./ai-patterns/grammar.md) | PAT-GRAM-001–008 | 8 | §1.1, §4–7, §11–12, §15–16; json_roundtrip/markdown/attachments/hierarchy |
| [実務の複合例](./ai-patterns/composite.md) | PAT-COM-001–008 | 8 | §7–14 + owning feature docs; minimal/agenda/hierarchy/team_status/messages/diary/attachments |
| [AI誤変換・意味 A](./ai-patterns/pitfalls-a.md) / [B](./ai-patterns/pitfalls-b.md) | PAT-PIT-001–010 | 10 | Profile; AI guide §9; #1164; #1164 comments 6078516662/6078553354/6079794954/6080057300; AI guide contrasts |
| **Total** | Stable IDs; one meaning decision per case | **68** | Canonical fixtures + source comparisons |

既存examples/Profile/AI guideは素材を再利用し、自然言語・文脈・判断理由・独立診断・日英対応を新たに整備しました。68件は網羅性の目安で、record数や反例file数ではありません。init presetは見出し中心の雛形で、このカタログの代替ではありません。

### 全type・status

| Type | Pattern |
| --- | --- |
| `T` | [PAT-TYPE-001](./ai-patterns/types.md#pat-type-001) |
| `E` | [PAT-TYPE-002](./ai-patterns/types.md#pat-type-002) |
| `D` | [PAT-TYPE-003](./ai-patterns/types.md#pat-type-003) |
| `R` | [PAT-TYPE-004](./ai-patterns/types.md#pat-type-004) |
| `H` | [PAT-TYPE-005](./ai-patterns/types.md#pat-type-005) |
| `N` | [PAT-TYPE-006](./ai-patterns/types.md#pat-type-006) |
| `S` | [PAT-TYPE-007](./ai-patterns/types.md#pat-type-007) |
| `M` | [PAT-TYPE-008](./ai-patterns/types.md#pat-type-008) |
| `J` | [PAT-TYPE-009](./ai-patterns/types.md#pat-type-009) |

| Status | Pattern |
| --- | --- |
| `[ ]` | [PAT-STATUS-001](./ai-patterns/statuses.md#pat-status-001) |
| `[/]` | [PAT-STATUS-002](./ai-patterns/statuses.md#pat-status-002) |
| `[x]` | [PAT-STATUS-003](./ai-patterns/statuses.md#pat-status-003) |
| `[-]` | [PAT-STATUS-004](./ai-patterns/statuses.md#pat-status-004) |
| `[>]` | [PAT-STATUS-005](./ai-patterns/statuses.md#pat-status-005) |
| `[?]` | [PAT-STATUS-006](./ai-patterns/statuses.md#pat-status-006) |
| `[N]` | [PAT-STATUS-007](./ai-patterns/statuses.md#pat-status-007) |

### 主要key群

各入口から同じ分類の関連例へ進めます。表のkey群は全体で確認し、1つの例へ全部を詰め込みません。型固有の推奨keyはFormat §9を参照してください。priority/contextなども原入力に指定があるときだけ採用し、PIT-006の非創作原則を守ります。

| Specification group | Keys / boundary | Entry |
| --- | --- | --- |
| Common / §7.1 | `id, source, uid, project, tag, note, body, url, file, dir` | [PAT-GRAM-008](./ai-patterns/grammar.md#pat-gram-008) |
| Links / §7.2 | `parent, ref, depends_on, blocks, related, duplicate_of, replaced_by, follows, realizes` | [PAT-REL-001](./ai-patterns/relationships.md#pat-rel-001) |
| People / §7.3 | `user, owner, assignee, attendee, person, sender, recipient, team, group` | [PAT-COM-005](./ai-patterns/composite.md#pat-com-005) |
| Time / §7.4 | `from, to, on, at, due, do, done, notify_at, notify_from, notify_to, ack, snooze_until` | [PAT-TIME-001](./ai-patterns/time.md#pat-time-001) |
| Effort / §7.5 | `est, elapsed, progress` | [PAT-STATUS-002](./ai-patterns/statuses.md#pat-status-002) |
| Recurrence / §7.6 | `repeat, interval, until, count; RRULE storage/expansion limits` | [PAT-REC-001](./ai-patterns/recurrence.md#pat-rec-001) |
| Messages / §7.7 | `sender, recipient, body, notify_at, notify_from, notify_to, ack, snooze_until, channel` | [PAT-COM-006](./ai-patterns/composite.md#pat-com-006) |
| Journal / §7.8 | `on, at, from, to, mood, weather, loc, body` | [PAT-COM-004](./ai-patterns/composite.md#pat-com-004) |
| Workflow / §7.9 | `reason, moved_to` | [PAT-STATUS-004](./ai-patterns/statuses.md#pat-status-004) |
| System / §7.10 | `created, updated, record` | [PAT-COM-008](./ai-patterns/composite.md#pat-com-008) |

本文/物理行継続/引用/コメント/ヘッダー/Markdown/添付はGRAM、参照欠落/循環/部分共有はREL、候補日/依頼と完了/成功条件/取得証拠/能力主張はPITで確認します。機能固有recordと監査履歴の完全な体系は[projects](./projects.md)・[tickets](./tickets.md)・所有機能の文書へ委ねます。

## 検証・レビューの境界

68件・92個の独立fixture（yearly variantと反例を含む）をCore 1.0.3/source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`で実測しました。9件の固定範囲agendaも保存・再比較します。コマンド、入力SHA-256、exit、全diagnostics、日英対応は[manifest](../../examples/ai-patterns/manifest.json)。未実装枠は0件です。

| Class | Interpretation |
| --- | --- |
| A | Syntax error; expected nonzero exit and diagnostics |
| B | Validator warning; may have exit 0 |
| C | Source meaning differs even when syntax passes |
| D | Prose falsely claims a capability or evidence; code alone may pass |

warningを消すためのdone/ID/日時の創作は禁止です。著者による意味照合は独立承認ではありません。checkは自然言語への忠実性、承認成功、通知配信、機密除外を保証しません。外部LLM試験は本カタログでは実施しておらず、モデル精度向上は未検証です。

### 現在の既知の境界

- [#1217](https://github.com/Eruhitsuji/lifetxt/issues/1217): 仕様のRRULE subset説明と現在Coreの追加対応に差があります。unsupportedの例には実測W223のBYSETPOSを使い、月次ordinal BYDAYを未対応とは紹介しません。
- [#1218](https://github.com/Eruhitsuji/lifetxt/issues/1218): on+offset付き時刻の繰り返し起点差、RRULE展開のoffset表現を別調査へ切り出しました。元の値の保存と実時刻比較の忠実性を区別します。
- 月末/閏日のclampや浮動時刻の範囲制限、custom key/record保持≠検索・展開・外部実行は分類ページの実測/注意を確認してください。

## 再検証・保守

```sh
python scripts/check_ai_patterns.py --output .cache/ai-patterns-final.json
python -m unittest tests.test_ai_patterns tests.test_ai_prompt_profile
```

[Fixture保守手順](../../examples/ai-patterns/README.md)に従い、正本と日英コピーを同時更新します。IDは再利用せず、統合・廃止や件数変更は根拠を残します。PR/独立review/最終mergeは[#1200](https://github.com/Eruhitsuji/lifetxt/issues/1200)で追跡し、全子Issueがmainへ統合されてから親を完了にします。optionalなURLのみ/Profileのみ/Profile+patternの効果観測は[#1164](https://github.com/Eruhitsuji/lifetxt/issues/1164)。[#823](https://github.com/Eruhitsuji/lifetxt/issues/823)のAPIは引き続き保留です。
