# life.txt

`life.txt` is a plain-text format for managing tasks, events, deadlines, reminders, habits, status / presence records, and notes in a single human-readable file.
Please refer to [life_txt_format_spec.md](./life_txt_format_spec.md) for the detailed grammar of the `life.txt`.

## Tools

This repository includes a dependency-free Python CLI:

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty
python -m lifetxt to-jsonl life.txt -o life.jsonl
python -m lifetxt status life.txt
python -m lifetxt status life.txt --format json --pretty
python -m lifetxt from-json life.json -o life.txt
python -m lifetxt from-jsonl life.jsonl -o life.txt
```

The `status` command prints the latest `S` status / presence item for each
`person:`. If `person:` is omitted, it is treated as `self` for this summary.
The latest item is selected by the newest `from:` datetime. Use `--person NAME`
to filter one person, or `--format json` / `--format jsonl` for machine-readable
output.

Input assistance is available in both non-interactive and interactive modes:

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university --tag report
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --output new_life.txt
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --append life.txt
python -m lifetxt assist --interactive --append life.txt
```

In create mode, `assist --output FILE` appends the generated line to `FILE`.
It does not overwrite existing content.

In interactive mode, enter `?`, `?type`, `?status`, or `?detail` at a prompt
to show contextual help. At the detail prompt, use `?due` or another `?key`
form for key-specific help. When the terminal supports it, Tab completes type,
status, and detail-key candidates, and Up/Down recall previous inputs. Use
`--no-completion` to disable the line editing helpers.

Existing data can be updated by line number or by `id:`. Updates are written
in-place unless `--output` is specified.

```sh
python -m lifetxt assist --update life.txt --match-id task_001 --status done --done 2026-06-06
python -m lifetxt assist --update life.txt --line 3 --title "New Title" --add-detail tag=important
python -m lifetxt assist --update life.txt --match-id task_001 --remove-detail tag --output updated_life.txt
```

The `check` command reports syntax errors and semantic warnings such as invalid status/type values, malformed `key:value` details, note status/type mismatches, date/time format issues, unusual key style, and event ranges where `to:` is earlier than `from:`.
For `type:S` status / presence records, `from:` and `state:` are required. `[/]` is recommended when the record has no `to:`, and `[x]` is recommended when `to:` is present.

## JSON Shape

Details are always represented as arrays so repeated keys round-trip safely:

```json
{
  "status": "[ ]",
  "type": "T",
  "title": "Create_Slides",
  "details": {
    "project": ["research"],
    "tag": ["important", "thesis"]
  }
}
```

Run tests with:

```sh
python -m unittest discover
```
