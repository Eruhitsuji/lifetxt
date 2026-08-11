# Use-case installation and operations guide

この guide は、現在 lifetxt に実装済みの機能だけを使った実用 setup をまとめます。完全な reference は [CLI](./cli.md)、[Web](./web.md)、[AI/MCP](./ai-integration.md)、[format specification](./life_txt_format_spec.md) を参照してください。

## Common setup

```sh
git clone https://github.com/Eruhitsuji/lifetxt.git
cd lifetxt
python -m pip install -e .
python -m lifetxt init
python -m lifetxt doctor
python -m lifetxt check life.txt
```

browser UI を使う場合:

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

推奨 workspace:

```text
workspace/
├── life.txt
├── .lifetxt.json
├── projects/
├── .generated/
├── archive/
└── .cache/lifetxt/
```

hand-maintained files は Git で追跡します。再生成できる generated/cache directories は ignore してください。calendar URL、API token、SMTP password は life.txt ではなく environment variables に置きます。

## Personal task management

capture には `quick`、daily planning には `agenda`、overdue/blocked work の確認には `health`、weekly reflection には `review` を使います。

```sh
echo "Call the clinic" | python -m lifetxt quick - --append life.txt
python -m lifetxt agenda life.txt --around now --window 1d --open
python -m lifetxt health life.txt
python -m lifetxt review life.txt --format markdown
```

`update`、`done`、link commands に依存する前に stable IDs を付けてください。

```sh
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids life.txt --assign
```

## Students and researchers

長く続く作業は project で分け、`parent`、`depends_on`、`blocks`、`ref` で records をつなぎます。

```txt
[ ] T Thesis id:proj_thesis project:thesis due:2027-02-01
  [ ] T Literature_Review id:task_lit project:thesis due:2026-08-15
  [ ] T Run_Experiment_A id:task_exp_a project:thesis depends_on:task_lit est:4h
[N] J Research_Log on:2026-07-25 project:thesis
| Reproduced the baseline.
| Next: inspect failure cases.
```

```sh
python -m lifetxt agenda life.txt projects/ --project thesis --window 2w
python -m lifetxt links life.txt projects/ --id proj_thesis
python -m lifetxt timer start projects/thesis.life.txt --id task_exp_a
python -m lifetxt timer stop
python -m lifetxt stats life.txt projects/ --project thesis
```

複数行の research log には `|` continuation を使います。繰り返し inline `body:` の後ろへ continuation を置く形は ambiguous なので避けてください。詳しくは [roundtrip and body rules](./roundtrip-and-body.md) を参照してください。

## Small teams sharing through Git

`assignee`、`owner`、`team`、stable IDs を使います。validation hook を install します。

```sh
python -m lifetxt git-hook install
python -m lifetxt git-hook status
```

```sh
python -m lifetxt filter "projects/**/*.life.txt" --assignee alice --open
python -m lifetxt status "projects/**/*.life.txt" --active
python -m lifetxt check life.txt projects/
```

branch と commit は小さく保ちます。lifetxt は server-side collaborative editor ではないため、Git conflict は明示的に解決し、その後 `check` を再実行してください。

## Calendar synchronization

imported records は hand-maintained records から分けます。

```sh
export LIFETXT_GOOGLE_CAL_ICS='https://example.invalid/private.ics'
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS \
  -o .generated/google_calendar.life.txt \
  --cache-dir .cache/lifetxt --tag google \
  --merge-existing --soft-delete-missing
python -m lifetxt agenda life.txt .generated/google_calendar.life.txt --around now --window 1w
```

private ICS URL は file に書かず、environment variable から渡してください。

## Local and remote Web UI

local-only:

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

token-protected LAN または remote access:

```sh
export LIFETXT_API_TOKEN='replace-with-a-long-random-value'
python -m lifetxt serve life.txt --host 0.0.0.0 --token-env LIFETXT_API_TOKEN
```

public dashboard や wall display では `--read-only` を使います。internet-facing deployment は HTTPS、access control、backups、process supervision、logging の背後で運用してください。

## AI clients

```sh
python -m lifetxt mcp life.txt
python -m lifetxt mcp life.txt .generated/google_calendar.life.txt --write-file life.txt
```

最初は read tools から始め、mutation 前には review を要求します。複数 input を渡す場合は、必ず `--write-file` で writable target を固定してください。

authoritative workspace が別 machine の Remote Safe Mode server にある場合、AI/MCP client から `remote_list_profiles`、`remote_test_connection`、`remote_list_resources`、`remote_get_resource` を使って read-only に参照できます。remote write は MCP tool ではなく CLI remote write flow で、proposal と confirmation を伴って行います。

## Maintenance

`check`、`doctor`、`health` を定期的に実行してください。bulk ID assignment や transformation は `--dry-run` で preview し、generated files は hand-edit せず、Git remote とは独立した backup を持ちます。
