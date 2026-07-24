# Use-case installation and operations guide

This guide describes practical setups using features currently implemented in lifetxt. See [CLI](./cli.md), [Web](./web.md), [AI/MCP](./ai-integration.md), and the [format specification](./life_txt_format_spec.md) for complete references.

## Common setup

```sh
git clone https://github.com/Eruhitsuji/lifetxt.git
cd lifetxt
python -m pip install -e .
python -m lifetxt init
python -m lifetxt doctor
python -m lifetxt check life.txt
```

For the browser UI:

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

Recommended workspace:

```text
workspace/
├── life.txt
├── .lifetxt.json
├── projects/
├── .generated/
├── archive/
└── .cache/lifetxt/
```

Track hand-maintained files in Git. Keep generated and cache directories ignored when they can be recreated. Store calendar URLs, API tokens, and SMTP passwords in environment variables, never in life.txt.

## Personal task management

Use `quick` for capture, `agenda` for daily planning, `health` for overdue/blocked work, and `review` for weekly reflection.

```sh
echo "Call the clinic" | python -m lifetxt quick - --append life.txt
python -m lifetxt agenda life.txt --around now --window 1d --open
python -m lifetxt health life.txt
python -m lifetxt review life.txt --format markdown
```

Assign stable IDs before relying on update, done, and link commands:

```sh
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids life.txt --assign
```

## Students and researchers

Split long-running work by project and connect records with `parent`, `depends_on`, `blocks`, and `ref`.

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

## Small teams sharing through Git

Use `assignee`, `owner`, `team`, and stable IDs. Install the validation hook:

```sh
python -m lifetxt git-hook install
python -m lifetxt git-hook status
```

```sh
python -m lifetxt filter "projects/**/*.life.txt" --assignee alice --open
python -m lifetxt status "projects/**/*.life.txt" --active
python -m lifetxt check life.txt projects/
```

Keep branches and commits small. lifetxt is not a server-side collaborative editor, so resolve Git conflicts explicitly and rerun `check` afterward.

## Calendar synchronization

Keep imported records separate from hand-maintained records.

```sh
export LIFETXT_GOOGLE_CAL_ICS='https://example.invalid/private.ics'
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS \
  -o .generated/google_calendar.life.txt \
  --cache-dir .cache/lifetxt --tag google \
  --merge-existing --soft-delete-missing
python -m lifetxt agenda life.txt .generated/google_calendar.life.txt --around now --window 1w
```

## Local and remote Web UI

Local-only:

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

Token-protected LAN or remote access:

```sh
export LIFETXT_API_TOKEN='replace-with-a-long-random-value'
python -m lifetxt serve life.txt --host 0.0.0.0 --token-env LIFETXT_API_TOKEN
```

Use `--read-only` for public dashboards and wall displays. Put internet-facing deployments behind HTTPS, access control, backups, process supervision, and logging.

## AI clients

```sh
python -m lifetxt mcp life.txt
python -m lifetxt mcp life.txt .generated/google_calendar.life.txt --write-file life.txt
```

Start with read tools and require review before mutations. With multiple inputs, always fix the writable target with `--write-file`.

## Maintenance

Run `check`, `doctor`, and `health` regularly. Preview bulk ID assignment or transformations with `--dry-run`, do not hand-edit generated files, and keep a backup independent of the Git remote.
