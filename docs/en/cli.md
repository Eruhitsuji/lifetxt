# life.txt CLI Guide

This document describes the command-line interface provided by:

```sh
python -m lifetxt
```

The CLI is dependency-free and reads UTF-8 `life.txt`, JSON, JSONL, or CSV files.
Most file-reading commands accept one or more paths. Use `-` or omit paths to
read from standard input.

## 1. Command Overview

```sh
python -m lifetxt tour
python -m lifetxt check [path ...]
python -m lifetxt integrity [path ...]
python -m lifetxt ids [path ...]
python -m lifetxt links [path ...]
python -m lifetxt sources [path ...]
python -m lifetxt notes [path ...]
python -m lifetxt convert --from FORMAT --to FORMAT [path ...]
python -m lifetxt to-json [path ...]
python -m lifetxt to-jsonl [path ...]
python -m lifetxt to-csv [path ...]
python -m lifetxt demo [options]
python -m lifetxt markdown [path ...]
python -m lifetxt import-ics [path ...]
python -m lifetxt import [path ...]
python -m lifetxt sync-ics --url-env ENVVAR
python -m lifetxt filter [path ...]
python -m lifetxt from-json [path ...]
python -m lifetxt from-jsonl [path ...]
python -m lifetxt from-csv [path ...]
python -m lifetxt status [path ...]
python -m lifetxt notify [path ...]
python -m lifetxt agenda [path ...]
python -m lifetxt assist [options]
python -m lifetxt tui [path ...]
python -m lifetxt fzf [path ...]
python -m lifetxt timer start path --id ID
python -m lifetxt timer pause
python -m lifetxt timer resume
python -m lifetxt timer stop
python -m lifetxt timer summary [path ...]
python -m lifetxt stats [path ...]
python -m lifetxt lifecycle-stats [path ...]
python -m lifetxt git-hook install
python -m lifetxt completion bash
python -m lifetxt serve [path ...]
python -m lifetxt web [path ...]
python -m lifetxt config init
python -m lifetxt config show
python -m lifetxt init
python -m lifetxt doctor
python -m lifetxt quick "Title"
python -m lifetxt add "Title"
python -m lifetxt done [path ...]
python -m lifetxt complete [path ...]
python -m lifetxt assign [path ...]
python -m lifetxt batch [path ...]
python -m lifetxt archive [path ...]
python -m lifetxt undo [path ...]
python -m lifetxt summary [path ...]
python -m lifetxt inbox [path ...]
python -m lifetxt cleanup [path ...]
python -m lifetxt health [path ...]
python -m lifetxt review [path ...]
python -m lifetxt who [path ...]
python -m lifetxt search PATTERN [path ...]
python -m lifetxt find TERM [path ...]
python -m lifetxt snapshot [path ...]
python -m lifetxt lint [path ...]
python -m lifetxt diff FILE_A FILE_B
python -m lifetxt plot [path ...]
python -m lifetxt export-heatmap [path ...]
python -m lifetxt migrate [path ...]
python -m lifetxt from-markdown [path ...]
python -m lifetxt deps [path ...]
python -m lifetxt tag list [path ...]
python -m lifetxt watch [path ...] -- COMMAND
python -m lifetxt encrypt [path ...]
python -m lifetxt decrypt [path ...]
python -m lifetxt share [path ...]
python -m lifetxt digest [path ...]
python -m lifetxt template list
python -m lifetxt workspace list
python -m lifetxt project list
python -m lifetxt portfolio [path ...]
python -m lifetxt today [path ...]
python -m lifetxt area list [path ...]
python -m lifetxt backlinks ID [path ...]
python -m lifetxt temporal ID [path ...]
python -m lifetxt timeline ID [path ...] [--since ISO] [--until ISO] [--event TYPE] [--limit N] [--as-of TIMESTAMP] [--json]
python -m lifetxt timeline --workspace-timeline [path ...] [--since ISO] [--until ISO] [--event TYPE] [--project NAME] [--limit N] [--json]
python -m lifetxt history-check [path ...] [--id ID] [--commit-limit N] [--json]
python -m lifetxt freebusy [path ...] --from START --to END
python -m lifetxt flow [path ...] --date YYYY-MM-DD --day-start HH:MM --day-end HH:MM [--format text|json]
python -m lifetxt item-uri format ID [--base-url URL] [--json]
python -m lifetxt item-uri parse URI [--json]
python -m lifetxt backup verify BACKUP
python -m lifetxt backup verify --latest [--destination DIR]
python -m lifetxt query "QUERY" [path ...] [--explain]
python -m lifetxt view list
python -m lifetxt group list [path ...]
python -m lifetxt message recipients [path ...]
python -m lifetxt person list [path ...]
python -m lifetxt proposal list
python -m lifetxt ticket list [path ...]
python -m lifetxt version list [path ...]
python -m lifetxt sprint list [path ...]
python -m lifetxt rrule daily
python -m lifetxt update-check
python -m lifetxt update
python -m lifetxt server-init --server-config server-init.json
python -m lifetxt server-update --server-config server-update.json
python -m lifetxt remote profile-list
python -m lifetxt vm run program.life.txt --entry s1
```

| Command | Purpose |
|---|---|
| `check` | Validate life.txt syntax and semantic warnings |
| `integrity` | Run a read-only aggregate data-integrity report |
| `ids` | Audit present, missing, and duplicate item IDs |
| `links` | Inspect ID-based references between items |
| `sources` | Report which input file owns each parsed item |
| `convert` | Explicit stateless conversion through the shared item model |
| `to-json` | Convert life.txt to a JSON array |
| `to-jsonl` | Convert life.txt to JSONL |
| `to-csv` | Convert life.txt to CSV |
| `export` | Unified `--format json\|jsonl\|csv\|markdown\|life\|sqlite\|lifetxtz` entry point |
| `demo` | Generate valid demo life.txt records for demos, tests, and screenshots |
| `markdown` | Render safe Markdown fields as HTML, text, JSON, or JSONL |
| `import-ics` | Convert iCalendar `.ics` events to life.txt event items |
| `sync-ics` | Fetch iCalendar URLs and regenerate life.txt event items |
| `filter` | Filter items and output life.txt, JSON, or JSONL |
| `from-json` | Convert JSON to life.txt |
| `from-jsonl` | Convert JSONL to life.txt |
| `from-csv` | Convert CSV to life.txt |
| `status` | Show the latest `S` status / presence record for each person |
| `state` (`s`) | Record a presence status, closing the previously open one |
| `files` | Inspect, verify, and hash `file:` and `dir:` attachments |
| `start` | Start work: task in progress, timer running, presence recorded |
| `stop` | Stop work: timer stopped with `elapsed:`, presence closed |
| `notify` | Show or watch due type `M` message notifications |
| `agenda` | Show items related to a datetime range |
| `assist` | Create or update life.txt items from prompts or flags |
| `tui` | Open an interactive terminal workspace for tasks, agenda, and status |
| `fzf` | Select filtered items with `fzf` or `peco` and run an action |
| `timer` | Track elapsed time for one task-like item |
| `stats` | Summarize task, habit, mood, and project activity |
| `git-hook` | Install or inspect Git hooks that validate life.txt files |
| `completion` | Generate shell completion scripts |
| `serve` | Run the optional FastAPI REST API and browser GUI |
| `mcp` | Run the stdio MCP server for AI clients |
| `config` | Create or inspect an external JSON config file |
| `init` | Interactive first-time setup: create life.txt and .lifetxt.json |
| `doctor` | Check Python version, files, depen