# Personal Context toolkit

Personal Context toolkit は、lifetxt の既存 **Personal AI Memory** 規約の上に構築する薄い決定的レイヤーです。新しいレコード種別、データベース、AIプロバイダ依存、第一級Query語彙は追加しません。

Personal Context の事実は、引き続き通常の Note として記録します。

```text
[ ] N "エディタではダークモードを好む" id:pref-editor person:self tag:preference source:user updated:2026-08-24T10:00:00+09:00
```

toolkit は既存の `person:`、`tag:`、`source:`、`updated:`、ID/link、Temporal Context、workspace、Unified Inbox を組み合わせます。

## Context Health

Personal Context の鮮度と内部整合性を確認します。

```bash
lifetxt context health
lifetxt context health --format json --pretty
```

ライフサイクル状態は次の3つです。

- `current` — stale でも superseded でもない
- `stale` — 既存 Temporal Context の `stale_since` 判定に該当する
- `superseded` — 別の authoritative record が `corrects:<このID>` を持つ

加えて、独立した品質上の問題として以下を報告します。

- `source:` がない
- ID参照先が存在しない、または曖昧である

既存のstaleness閾値は変更できます。

```bash
lifetxt context health --stale-after-days 30
```

Health確認はworkspaceを書き換えません。

## なぜこの情報を記憶しているのか

`context why` は、保存済みデータと決定的に導出できる情報だけを使って1件を説明します。

```bash
lifetxt context why pref-editor
lifetxt context why pref-editor --format json --pretty
```

`source:` / `updated:`、person/tag、current/stale/superseded状態、incoming/outgoing ID linkを表示します。これはLLMによる説明ではなく、モデルのchain-of-thoughtを生成・公開する機能でもありません。

## 過去を削除せずに記憶を訂正する

明示的な事実や嗜好が変わった場合は、古い履歴を書き換えずに置換候補をstageします。

```bash
lifetxt memory correct pref-editor "エディタではライトモードを好む"
```

このコマンドは Unified Inbox に pending proposal を作成します。authoritative な `life.txt` は変更しません。

提案される置換レコードも通常の Note です。該当する `person:`、`tag:`、`project:` を引き継ぎ、lifetxt が新しいIDを生成したうえで次の情報を付加します。

```text
corrects:pref-editor source:manual updated:<現在時刻>
```

通常のproposal workflowで確認・反映します。

```bash
lifetxt proposal list
lifetxt proposal show P-12345678
lifetxt proposal accept P-12345678
```

accept後は、Context Health / Context Why / Context Capsule が、新しいauthoritative recordの `corrects:pref-editor` を根拠として古い `pref-editor` を superseded と扱います。

`corrects:` はこの段階では意図的に **custom detailの規約** とします。Format 1.0 の新しい第一級keyやQuery fieldではありません。そのため通常の「未知のcustom key」に対する非blocking diagnosticが表示される場合がありますが、値はparser/serializerで保持されます。

## Portable Context Capsule

AIやscriptへ渡せるboundedなprovider-independent snapshotを生成します。

```bash
lifetxt context capsule --pretty
lifetxt context capsule --tag preference --pretty
lifetxt context capsule --tag goal --limit 20 --pretty
```

既定出力はJSONです。Capsuleには次が含まれます。

- `schema: personal-context-capsule-v1`
- 選択されたcontextに対する決定的SHA-256 `revision`
- person/tag/bounds
- 決定的順序のitem records

入力とオプションが同じならrevisionも同じです。supersededとstaleな記憶は既定で除外します。古いcontextも明示的に必要な場合だけ `--include-stale` を指定します。

Capsuleは **生成されたread-only projection** であり、新しいsource of truthではありません。ChatGPT、Claude、Gemini、ローカルLLM、IDE agent、scriptなどが利用しても、authoritative storageは引き続きlifetxt側です。

exportは明示操作ですが、外部サービスへ渡す前に選択workspaceと内容を確認してください。操作権限と情報開示ポリシーは別の問題です。

## Decision Memory

意思決定も新しいrecord kindにはせず、`tag:decision` を付けた通常のPersonal Context Noteとして扱います。

```text
[ ] N "ローカルキャッシュにはSQLiteを使う" id:decision-cache person:self tag:decision project:demo source:user updated:2026-08-24T10:00:00+09:00
```

一覧表示します。

```bash
lifetxt decisions
lifetxt decisions --project demo
lifetxt decisions --format json --pretty
```

既定ではstaleとsupersededなdecisionを除外し、Capsuleと同じPersonal Context lifecycle判定を利用します。

## Workspace・複数ファイル

read系コマンドは通常のlifetxt workspace/path解決を利用します。

```bash
lifetxt context health --workspace personal
lifetxt context capsule --workspace personal --tag preference
lifetxt decisions --workspace personal --project demo
```

明示pathも利用できます。`memory correct` は選択されたread workspaceから対象を解決し、通常のproposal/write targetに対してstageします。authoritative mutationはproposalをacceptした時だけ発生します。

## 設計上の境界

この最初のtoolkitでは、以下は追加しません。

- Personal Context専用record kind
- `subject:`、`assertion:`、`confidence:`、`valid_from:`、`valid_to:` などの新contract
- `corrects:` 用Query syntax
- embedding/vector storage/RAG corpus
- provider固有memory API
- AIからauthoritative Personal Contextへの自動書き込み

目的は、既存のユーザー所有plain-text memoryを、最小限の実装追加で「検査可能・訂正可能・持ち運び可能」にすることです。
