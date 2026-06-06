# life.txt

`life.txt` is a plain-text format for managing tasks, events, deadlines, reminders, habits, and notes in a single human-readable file.
Please refer to [life_txt_format_spec.md](./life_txt_format_spec.md) for the detailed grammar of the `life.txt`.

## Tools

This repository includes a dependency-free Python CLI:

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty
python -m lifetxt to-jsonl life.txt -o life.jsonl
python -m lifetxt from-json life.json -o life.txt
python -m lifetxt from-jsonl life.jsonl -o life.txt
```

Input assistance is available in both non-interactive and interactive modes:

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university --tag report
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --output new_life.txt
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --append life.txt
python -m lifetxt assist --interactive --append life.txt
```

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
