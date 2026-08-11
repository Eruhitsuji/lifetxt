# Transaction Recovery and Strict Timer Writes

この文書は compensated multi-target transaction contract の上に追加された durable recovery layer を説明します。transaction journals、explicit recovery actions、strict timer revisions、revision-metrics relocation、deterministic clocks、diagnostics、schemas、support bundles を扱います。

## Durable journal の目的

`lifetxt.multi_target` は every target を lock し、expected revisions を validate し、replacements を stage し、deterministic order で commit し、同じ process 内の後続 write が fail した場合は committed targets を compensate します。それでも process termination、power loss、OS failure は sequence を interrupt できます。

transaction journal は、その interruption を guessing なしに inspect/recover するための exact evidence を記録します。unrelated files が portable filesystem transaction を共有するという主張ではありません。

## Journal contents

default journal directory は writable life.txt の横の `.lifetxt-transactions` です。config または `LIFETXT_TRANSACTION_JOURNAL_DIR` で override できます。

各 transaction directory には `journal.json` と exact before/after binary artifacts が入ります。journal は transaction ID、operation、targets、expected/before/after revisions、artifact hashes、commit/compensation progress、timestamps、state、last error を記録します。

terminal states は `committed`、`compensated`、`abandoned` です。recovery states には `prepared`、`committing`、`compensating`、`recovery_required`、`resume_failed`、`compensation_failed` があります。

## Inspect and recover

```bash
lifetxt safety transactions list --pretty
lifetxt safety transactions inspect --journal TX_ID --pretty
lifetxt safety transactions resume --journal TX_ID --pretty
lifetxt safety transactions compensate --journal TX_ID --pretty
lifetxt safety transactions abandon --journal TX_ID --backup-dir recovery-backups --pretty
lifetxt safety transactions export --journal TX_ID --output transaction-evidence.json --pretty
```

retention cleanup は old terminal journals だけを remove できます。non-terminal journals は cleanup されません。

## Doctor and support bundles

`doctor --workspace-safety` は transaction directory を discover し、journal states を list し、recovery-required transaction を hard failure として扱います。

```bash
lifetxt doctor --workspace-safety life.txt \
  --journal-dir .cache/lifetxt/transactions \
  --support-bundle lifetxt-support.json \
  --pretty
```

support bundle は versions、hashes、diagnostics、policy output、recovery metadata を含みますが、authored life.txt content、transaction artifacts、credentials、tokens、raw absolute paths は除外します。

## Strict timer revision contract

timer operations は timer JSON state と life.txt の両方を触る場合があります。start/stop は `item_revision` と `timer_revision` の 2 revisions を使います。pause/resume/cancel は timer-state revision を使います。

```bash
lifetxt timer start life.txt --id T-1 \
  --item-revision ITEM_SHA256 \
  --timer-revision '<missing>'

lifetxt timer stop life.txt \
  --item-revision ITEM_SHA256 \
  --timer-revision TIMER_SHA256
```

Web と MCP timer tools も同じ fields を expose します。status response が revision-discovery step です。

## Recovery decision order

non-terminal journal が見つかった場合は、action を選ぶ前に inspect します。

1. `inspect` で recorded before/after revisions と target state を確認する。
2. recorded commit を完了することがまだ意図した結果である場合だけ `resume` する。
3. recorded before revisions が望ましい recovery point である場合は `compensate` する。
4. evidence を backup し、human operator が automated action を続けない判断を受け入れた後だけ `abandon` する。

## Remaining boundaries

real power-loss fault injection、すべての legacy write migration、すべての attachment handler、compound work-session capability enforcement、real terminal/browser/SMTP/platform verification は残る P0 work です。
