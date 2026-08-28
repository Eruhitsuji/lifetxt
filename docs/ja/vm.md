# lifetxt VM（opt-in のチューリング完全実行モデル）

`lifetxt vm run` は、`life.txt` の既存 custom key のごく一部を 2-counter
Minsky machine として解釈する。任意精度 counter を使うこの計算モデルは
チューリング完全であり、lifetxt の主要ユースケースではなく独立した
実験的 / 趣味的拡張として位置付けられる。

> `life.txt` Format 1.0 自体はプログラミング言語ではない。`lifetxt vm`
> は、valid な `life.txt` records を使って記述される opt-in の
> チューリング完全実行モデルである。

## 安全に追加できる理由

Format 1.0 はもともと未知の custom key を許容する: parser はそれらを
`Item.details` に保持し、`check` は non-blocking な style warning
(`W106`) として報告するだけでエラーにはしない。`lifetxt vm` は新しい
文法を一切追加しない。`value:` / `op:` / `var:` / `next:` / `zero:` /
`nonzero:` という通常の custom key を、呼び出し側が明示的にプログラムを
構築・実行したときだけ命令として解釈する。

**他のどのコマンドも VM record を実行しない。** `check`、`agenda`、
`filter`、`search`、Web API、MCP、TUI はすべて同じファイルを、
未知の custom key を持つ通常の item として parse するだけである。実行可能性は
`lifetxt vm run` に限定される。

## 使い方

```console
$ lifetxt vm run program.life.txt --entry s1
HALT after 7 steps
x=0
y=3

$ lifetxt vm run program.life.txt --entry s1 --json
{
  "halted": true,
  "entry": "s1",
  "steps": 7,
  "state": {
    "x": 0,
    "y": 3
  }
}
```

| Option | 意味 |
|---|---|
| `path ...` | 1 つ以上の life.txt file、または stdin (`-`)。VM record は通常の Task/Event/Note などと自由に混在できる — `value:` または `op:` を持つ record だけが program の一部として読まれる |
| `--entry ID` | 必須。実行を開始する instruction の `id:` |
| `--max-steps N` | 無限ループ防止の step limit。既定 `100000`。`0` は無制限実行（明示的 opt-in） |
| `--json` | 最終 state を JSON で出力 |

exit code `0` は step limit 内で `HALT` したことを意味する。0 以外は
validation 失敗、`HALT` 前の step limit 到達、または `Ctrl+C` による
中断を意味する。

## 命令セット（v0）

既存の `id:` で address される 3 命令のみ:

```text
INC(var, next)
DEC_JZ(var, nonzero, zero)
HALT
```

### Counter

```life.txt
[N] N Counter_X id:x value:3
```

`value:` は実行**開始時**の値。実行中の state はメモリ上にのみ存在し、
`lifetxt vm run` は元の file に書き戻さない。必須: `id:` 1つ、`value:`
1つ（非負の十進整数、bit幅上限なし）。

### `INC`

```life.txt
[N] N Increment_Y id:s2 op:inc var:y next:s1
```

```text
state[y] = state[y] + 1
pc = s1
```

必須: `id:`、`op:inc`、`var:`、`next:`。

### `DEC_JZ`

```life.txt
[N] N Check_X id:s1 op:dec_jz var:x nonzero:s2 zero:halt
```

```text
if state[x] == 0:
    pc = halt
else:
    state[x] = state[x] - 1
    pc = s2
```

必須: `id:`、`op:dec_jz`、`var:`、`nonzero:`、`zero:`。

### `HALT`

```life.txt
[N] N Halt id:halt op:halt
```

実行を停止する。必須: `id:`、`op:halt`。

## Control flow

`next:` / `zero:` / `nonzero:` は同一 program 内の別 instruction の
`id:` を参照する。独立した address 空間は存在せず、`lifetxt links` が
既に理解している既存の `id:` 参照機構を、そのまま control-flow graph の
辺として再利用する。

## program の可視化: `lifetxt vm graph`

`lifetxt vm graph` は、検証済みの program の counter/instruction を
directed graph として出力する。node id の正規化・quote 処理は
`lifetxt links --format mermaid|dot` と同じ共有 helper をそのまま
再利用している。

```console
$ lifetxt vm graph program.life.txt --entry s1
graph LR
    x(["x=3"])
    y(["y=0"])
    s1["s1: dec_jz x"]:::entry
    s2["s2: inc y"]
    halt["halt: halt"]

    s1 -. var .-> x
    s1 -- nonzero --> s2
    s1 -- zero --> halt
    s2 -. var .-> y
    s2 -- next --> s1

    classDef entry stroke-width:3px

$ lifetxt vm graph program.life.txt --format dot
digraph vm {
    x [shape=ellipse, label="x=3"];
    ...
}
```

| Option | 意味 |
|---|---|
| `path ...` | 1つ以上の life.txt file、または stdin 用の `-`。入力の扱いは `vm run` と同じ。 |
| `--entry ID` | 省略可。指定した場合、該当 instruction node が強調表示され（mermaid では `:::entry`、dot では `peripheries=2`）、`vm run --entry` と同じ方法で検証される -- 存在しない id や counter を指す id はエラーで失敗する。 |
| `--format {mermaid,dot}` | 出力形式。既定は `mermaid`。 |

`--entry` から到達可能かどうかに関わらず、宣言された全ての counter と
instruction が描画される -- これは検証済み program に対する静的な export
であり、`vm run` の実行結果ではない。counter は stadium 形状の node
（mermaid では `(["..."])`、dot では `shape=ellipse`）、instruction は
矩形（`["..."]` / `shape=box`）で描画され、視覚的に区別できる。辺は 2 種類
描画される: instruction 間の実線でラベル付きの `next:`/`zero:`/`nonzero:`
control-flow 遷移と、各 instruction からそれが読み書きする counter への
破線の `var:` 辺。`vm run` 自身の検証に失敗する program は、ここでも
何も描画されずに同様に失敗する。

## 例: X の値を Y に移す

```life.txt
[N] N Counter_X id:x value:3
[N] N Counter_Y id:y value:0

[N] N Check_X id:s1 op:dec_jz var:x nonzero:s2 zero:halt
[N] N Increment_Y id:s2 op:inc var:y next:s1

[N] N Halt id:halt op:halt
```

```console
$ lifetxt vm run program.life.txt --entry s1
HALT after 7 steps
x=0
y=3
```

`s1` を通過するたび（zero branch でも nonzero branch でも）1 step として
数えるため、decrement 3 回 + increment 3 回 + 最後の zero 判定 1 回で
合計 7 step になる。

## 実行前の validation

`lifetxt vm run` は、通常の lifetxt validator の custom-key policy とは
分離した専用 validation を実行前に行う。少なくとも次を reject する:

- 存在しない、または instruction ではない（counter を指している）
  `--entry` id
- `id:` を持たない VM record、または singleton であるべき detail
  （`id:` / `value:` / `op:` / `var:` / `next:` / `zero:` / `nonzero:`）が
  複数指定されている record
- `value:` と `op:` を同時に持つ record（counter か instruction の
  どちらか一方でなければならない）
- counter と instruction を跨いだ重複 `id:`
- unknown な `op:` 値
- `var:` / `next:` を欠く `op:inc`、`var:` / `nonzero:` / `zero:` を
  欠く `op:dec_jz`
- 存在しない counter を参照する `var:`
- 存在しない id、または instruction ではなく counter を指す
  `next:` / `zero:` / `nonzero:`
- 非負の十進整数ではない `value:`

すべての失敗は `ERROR: ...` として stderr に出力され、exit code は
非ゼロ、実行は一切行われない。

## 無限実行対策

命令セットはチューリング完全なため、停止しない program を記述できる。
`--max-steps`（既定 `100000`）は実行される命令数の上限で、到達すると
`HALT` を待たずに、その時点の step 数と state を添えて明確に失敗する。
`--max-steps 0` は無制限実行への明示的 opt-in であり、`Ctrl+C` でいつでも
中断できる。

## 安全境界

VM は自身の program counter と counter state 以外に副作用を持たない。
次のことはできない:

- filesystem の読み書き
- shell command / process の実行
- network access
- Python `eval` / `exec`
- environment variable の読み取り
- MCP / Web API / 任意の plugin の呼び出し
- `life.txt` 自体の変更

## v0 の対象外

`if` / `while` / `for`、function、stack、`INC` / `DEC_JZ` 以外の
arithmetic instruction、汎用 expression 構文、I/O instruction、runtime
state の永続化、source code compiler、Web / TUI / MCP からの実行は、
すべて意図的に v0 では実装しない。将来的に、`lifetxt vm check`、
single-step trace、JSON state output、Brainfuck → lifetxt VM compiler
などが別 Issue として検討される可能性があるが、v0 の対象ではない。
