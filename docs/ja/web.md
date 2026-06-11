# life.txt Web API / GUI

Web interface は任意機能です。FastAPI と uvicorn を使いますが、core parser と
CLI は外部依存なしのままです。

## install

```sh
pip install -r requirements-web.txt
```

## 起動

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

ブラウザで開きます。

```txt
http://127.0.0.1:8000/
```

複数ファイルを同時に読めます。作成、更新、削除は既定では最初のファイルに対して
行います。変更先を明示したい場合は `--write-file` を使います。

```sh
python -m lifetxt serve life.txt .generated/google_calendar.life.txt --write-file life.txt
```

## REST API

| Method | Path | 目的 |
|---|---|---|
| `GET` | `/api/health` | 読み込み path と書き込み先を表示 |
| `GET` | `/api/items` | item 一覧。filter 指定可能 |
| `POST` | `/api/items` | 書き込み先ファイルに item を追記 |
| `PUT` | `/api/items/{line}` | 書き込み先ファイルの指定行 item を置換 |
| `DELETE` | `/api/items/{line}` | 書き込み先ファイルの指定行 item を削除 |
| `GET` | `/api/agenda` | 日時範囲に関連する agenda record を表示 |
| `GET` | `/api/status` | 最新 status / presence record を表示 |

item payload 例:

```json
{
  "status": "[ ]",
  "type": "T",
  "title": "Write Report",
  "details": {
    "due": ["2026-06-12"],
    "project": ["university"]
  }
}
```

例:

```sh
curl "http://127.0.0.1:8000/api/items?kind=T&open_only=true"
curl "http://127.0.0.1:8000/api/agenda?around=now&window=1d"
curl "http://127.0.0.1:8000/api/status?active=true"
```

## GUI

ブラウザGUIは以下に対応します。

- item 一覧と filter
- line、time、title、type、status、source による item 並び替え
- 現在時刻付近の agenda 表示
- active な status / presence 表示
- item 作成
- 編集可能な item の選択と保存
- 編集可能な item 行の削除

編集可能なのは書き込み先ファイル由来の item です。
`.generated/google_calendar.life.txt` など生成ファイル由来の item は read-only として
表示します。

layout は responsive です。広い画面では item 一覧と editor を横並びにし、狭い
ブラウザウィンドウでは縦並びに切り替えます。
