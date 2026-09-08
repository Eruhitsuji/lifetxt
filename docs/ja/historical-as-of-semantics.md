# Historical `as-of` semantics

Status: #699 / #702 Phase 3 の調査結果。

## 決定

現在の life.txt だけを使う一般的な `lifetxt as-of DATE` command はまだ公開
できません。現在の file は**現在**について authoritative ですが、過去の
時点にどの値や future plan が既に存在したかは証明しません。item 内の日付は
domain time であり、その時点で記録済みだったことの evidence ではありません。

historical output は、次の evidence source から復元し、その source と revision
を明示した場合だけ authoritative とします。

## Evidence inventory

| source | 証明できること | 境界 |
| --- | --- | --- |
| exact commit の Git blob/tree | その revision で track された life.txt の完全な bytes | commit time は repository evidence であり domain/event time とは限らない。uncommitted/external file は含まない |
| cutoff 以前の Git history | cutoff 以前で到達可能な最新 commit | repository/ref と author/committer timestamp policy が必要。rewrite/shallow history は不完全になり得る |
| `record:ticket_event` / `record:time_entry` | 完全かつ検証済み chain が表す field/activity | 無関係な item field や chain 開始前を復元できず、backfill を推測しない |
| `record:progress_event` | 完全かつ検証済み chain が表す progress boundary | progress のみ。baseline 不明は unavailable のまま |
| undo snapshot/current revision hash/transaction journal | 定義済み retention 内の conflict/recovery evidence | durable な historical DB や一般 as-of source ではない |
| 現在の life.txt の日付 (`on:`、`due:`、`created:` など) | 現在主張されている domain date | requested historical time にその主張が存在したことを証明しない |

## 安全に実装可能な subset

1. **Git-revision view**: caller が選択した exact commit の life.txt bytes を parse
   し、repository、ref/commit SHA、time policy、completeness caveat を付ける。
   将来機能であり、working tree へ暗黙 fallback しない。
2. **Typed event-history view**: 検証済み append-only contract が完全な chain を
   定義する field だけを復元する。progress delta と同様、baseline 不明は
   unavailable とする。
3. **Current temporal thread**: `temporal-thread-v1` は現在の authoritative
   lifecycle assertion と現在の派生 date context を表し、historical reconstruction
   ではない。

## 一般 command より前に必要な contract

将来の実装 Issue では evidence-source selection、Git repository/ref と timestamp
policy、revision ごとの multi-file membership、history completeness/retention flag、
timezone/cutoff semantics、untracked/generated/external file、output provenance、
evidence 不足時の deterministic error を定義する必要があります。Git 以外から
一般的に復元する場合は、まず append-only item-change history contract が必要です。

この contract ができるまでは一般的な `as-of` CLI/API/MCP surface を追加しません。
current item や `follows:`/`realizes:`/`replaced_by:` から historical state を推測しては
なりません。
