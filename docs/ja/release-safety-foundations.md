# Release safety and Format 1.0 foundations

この batch は remote writes と Format 1.0 を stable と宣言する前に、dependency-free safety services を追加します。

## Revision-required operations

`lifetxt.safe_ops` は次の operation contracts を expose します。

- `quick_capture`
- `item_update`
- `mcp_write`
- `notification_acknowledgement`
- `timer_state`
- `archive`
- `undo`

すべての operation は `expected_hash` を要求します。omitted の場合は `ExpectedRevisionRequired`、stale hash の場合は `MutationConflict` です。text transforms は in-lock current text に対して実行されます。timer state JSON も同じ rule です。

## Safety commands

```bash
lifetxt safety locks life.txt --stale-after 300 --pretty
lifetxt safety serve-target life.txt --write-file shared/life.txt --pretty
lifetxt safety timezone life.txt --timezone Asia/Tokyo --pretty
lifetxt safety write-routes --root . --strict
lifetxt safety release-gate life.txt --root . --pretty
```

locks command は lock metadata と stale evidence を report しますが、locks は delete しません。serve-target は read/write target mismatch と Windows drive-relative paths を detect します。timezone precedence は CLI override、file directive、config、host timezone の順です。write-route audit は low-level mutation boundary 以外の direct writes を report します。

## Format 1.0 draft commands

```bash
lifetxt format info life.txt --pretty
lifetxt format check life.txt --pretty
lifetxt format canon life.txt --pretty
lifetxt format canon life.txt --write --pretty
lifetxt format schemas dist/schemas --pretty
```

current directive は `#! format_version: 1` です。unversioned files は compatibility mode で readable/writable です。unsupported versions は migration 前に rewrite してはいけません。

`format canon --write` は inspected file の exact hash で repair します。intervening edit は conflict です。

## Capability document

```bash
lifetxt capabilities --authentication token --pretty
lifetxt capabilities --read-only --authentication session --pretty
```

versioned response は format/canonical/schema versions、supported operations、authentication mode、read-only state、writable targets、optional features、SHA-256 revision-precondition support を report します。future remote clients の base contract です。

### Cross-surface capability matrix

```bash
lifetxt capabilities --surface-matrix
lifetxt capabilities --surface-matrix --format json --pretty
```

additive で read-only な mode で、real な top-level CLI command ごとに Web UI・interactive curses TUI・REST API・MCP で同等の機能が利用できるかを report します。default の `lifetxt capabilities` document は一切変更しません。

各 command は surface ごとに次の5つの安定した support state のいずれかを report します:

- `full` -- command が対応する operation が全て その surface で利用可能
- `partial` -- command が複数の operation に対応し、一部だけ利用可能
- `unsupported` -- 対応する operation は存在するが、その surface では未実装
- `not_applicable` -- command が意図的に CLI-only（interface launcher、local administration、file-format import/export converter）であり、cross-surface parity は期待されない
- `unmapped` -- command がまだ authoritative な operation/surface metadata に接続されていない。これは known gap であり、その surface に機能がないという主張ではない。

matrix は `lifetxt.cli_taxonomy`（canonical CLI command catalog）と `lifetxt.surface_runtime.OPERATION_REGISTRY`（既存の CLI/Web/MCP semantic operation registry）から derive され、第二の hand-maintained feature table ではありません。`web_ui` と `api` は独立した column として report されますが、現時点では同じ registry の事実（`"web" in operation.surfaces`）から計算されています -- これは known な、documented された limitation であり、より細かい per-operation の Web UI/REST API audit が完了するまでのものです。

## Safety boundary checklist

- unsupported `#! format_version:` を宣言する file は、migration path を選ぶまで mutate しない。
- `format canon --write` は inspected revision だけで実行する。intervening edit は conflict として扱う。
- clients は individual commands から write safety を推測せず、`lifetxt capabilities` を advertised contract として扱う。
