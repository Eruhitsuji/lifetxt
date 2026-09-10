# Native History と Git の consistency

`lifetxt history-check PATH [PATH ...]` は、現在の life.txt にある Native
History と、到達可能な Git revision から観測できる state transition を、
read-only かつ bounded に semantic 比較します。

```bash
lifetxt history-check life.txt
lifetxt history-check life.txt --id task-1
lifetxt history-check life.txt --commit-limit 50 --json
```

既定 commit limit は100、許容範囲は1～500です。raw line、format、comment、
commit 数は比較しません。隣接 Git state から item creation、lifecycle status、
progress、`follows` / `realizes` / `replaced_by`、`on` / `due` / `from` / `to` /
`at` の変更を projection し、その bounded transition 集合を正規化 Native
event と照合します。1つの commit で複数 event を検証できます。利用可能な
場合は exact source-content revision provenance を優先し、timestamp だけでは
identity を証明しません。

result の分類は次のとおりです。

- `verified`: 両 source が同じ semantic transition を示す
- `native_only`: window 内に対応 Git transition がない
- `git_only`: Git transition に Native event がなく、通常は coverage gap
- `conflict`: 比較可能な evidence の before/after の意味が矛盾する
- `unverifiable`: Native evidence が malformed / non-authoritative、または v1
  に決定的 Git projection がない record kind

Git は任意です。repository 外でも Native History と `timeline` は従来どおり
動作し、`history-check` は Git unavailable を示して有効な Native change を
`native_only` とします。shallow history、missing path、commit-limit truncation
は明示的 limitation で、`complete:true` にはなりません。ticket event と
time entry は Native Timeline で読めますが、決定的 Git semantic projection
を追加するまでは v1 で `unverifiable` です。

verifier は Native History や Git の repair、backfill、並べ替え、write を一切
行いません。既存の `timeline`、`thread --revision`、`thread --as-of`、
`thread --diff` の動作も変えません。JSON output は
[`native-git-history-consistency-v1.schema.json`](../../dist/schemas/native-git-history-consistency-v1.schema.json)
に従います。
