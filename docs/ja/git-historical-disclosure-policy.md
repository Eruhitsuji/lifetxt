# Historical Git evidence disclosure policy（investigation, #727）

Status: investigation のみ。本 document は endpoint や runtime code を実装
しない。将来の server / Remote Safe Mode 実装 Issue（#728）の Definition of
Ready を定義する。詳細な根拠は英語版
[git-historical-disclosure-policy.md](../en/git-historical-disclosure-policy.md)
を正とする。

## 要点（サマリー）

1. **Authorization model**: current policy と historical revision の両方が
   許可する場合のみ公開する（conjunctive）。単純な `read` role が自動的に
   historical access を意味する設計は採用しない。
2. **Allowed v1 selectors**: exact revision と bounded as-of のみ。revision
   listing/history browsing、arbitrary Git object/path 入力は許可しない。
3. **Path/workspace boundary**: server 側で既に構成済みの workspace/source
   のみを対象とし、caller が任意 path を指定することはできない。
4. **Reuse**: 既存 Remote Safe Mode の role/scope/redaction/audit/
   source-revision/bounded-result-contract をそのまま再利用し、historical
   専用の並行 policy engine は作らない。
5. **Audit**: requested selector、resolved full SHA、scope、caller identity、
   result classification/denial reason、redaction summary を記録し、秘密値や
   raw content は記録しない。
6. **Bounds**: 既存 reader の `MAX_HISTORICAL_FILE_BYTES` /
   `MAX_HISTORICAL_TOTAL_BYTES` / `MAX_HISTORY_COMMITS` /
   `GIT_TIMEOUT_SECONDS` をそのまま流用し、server 側に item-count 上限を
   追加する。
7. **Fail-closed**: current policy と historical revision の privacy
   metadata が矛盾する場合は、より制限的な側を優先する。

#728 は本 document を Definition of Ready の入力として使用するが、本
Issue 自体では実装しない。
