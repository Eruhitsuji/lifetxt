# Historical `as-of` semantics

Status: #707 / #708 / #709 のGit-backed subsetを実装済み。

## 決定

current itemの日付からhistoryを復元しません。現在のfileは**現在**について
authoritativeですが、過去にどの値やfuture planが存在したかは証明しません。
Git-backed historical thread modeは、tracked bytesとexact revision provenanceが
evidenceを提供できる場合だけ利用できます。

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

## 実装済みGit subset

1. **Exact revision**: `lifetxt thread ID --revision REV`はcommit-ishを解決し、
   tree内に存在するrequested pathだけを読み、`temporal-thread-v1.historical`
   provenanceを返します。path欠損はincomplete、target/revision欠損はfallbackなしの
   errorです。
2. **Semantic diff**: `--diff REV_A..REV_B`は2つのnormalized historical threadを
   `temporal-diff-v1`として比較します。item/state、explicit edge、consistency、
   derived変更を分離し、serialization orderは無視します。
3. **Git as-of selection**: `--as-of OFFSET_RFC3339 [--ref REF]`は到達可能な
   commitからcutoff以前でcommitter timestamp最大のものを選びます。既定rootは
   `HEAD`、同一timestampはfull SHA最大でtie-breakし、shallow historyは
   incompleteと明示します。
4. **Typed event-history view**: 検証済み append-only contract が完全な chain を
   定義する field だけを復元する。progress delta と同様、baseline 不明は
   unavailable とする。
5. **Current temporal thread**: `temporal-thread-v1` は現在の authoritative
   lifecycle assertion と現在の派生 date context を表し、historical reconstruction
   ではない。

## 残る境界

実装contractは意図的にGit-onlyかつCLI-onlyです。current input resolutionが
requested path manifestを供給し、untracked/generated/external sourceをhistorical
resultへ推測で混ぜません。Git history rewriteを独立検証済みの真実とは扱わず、
shallow cloneはcomplete selection historyを主張しません。Git以外の復元には、
別途reviewされたappend-only history contractが必要です。TUI/API/MCPのhistorical
surfaceはfuture workです。
