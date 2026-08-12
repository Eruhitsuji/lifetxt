# CLI Decomposition Plan

Issue #353 records a behavior-preserving decomposition plan for the large
`lifetxt/cli.py` module. This is an investigation record; no command code is
moved by this issue.

## Responsibility inventory

| Command family | Primary responsibilities | Coupling/risk |
| --- | --- | --- |
| Parse/read and diagnostics | input paths, checks, stable diagnostic output | high: shared by most commands |
| Conversion | JSON/JSONL/CSV/Markdown import/export | medium: shared models and filters |
| Workflow/query | status, agenda, search, filter, dependencies | high: shared workspace selection |
| Mutation | assist, done, assign, batch, archive, undo | high: revision/write safety |
| Web/MCP/Remote | server startup and protocol client dispatch | high: optional imports and public schemas |
| CUI extensions | TUI, fzf/peco, timers, stats, watch | medium/high: terminal state and optional tools |
| Configuration/deployment | config, doctor, server-init/update, update-check | high: filesystem and deployment safety |
| Utility commands | completion, demo, init, digest, share, templates | low/medium: mostly bounded command-specific behavior |

## Seams and ranking

1. `completion` is the first XS/S target: its parser registration and handler
   are bounded, its output contract is already covered by completion tests, and
   it has fewer mutation/revision dependencies than the other families.
2. `demo`/`template` are secondary low-coupling candidates after completion.
3. Conversion and query families require shared helper extraction first.
4. Mutation, Web/MCP/Remote, and deployment families remain last because their
   cross-surface safety contracts are tightly coupled.

Shared input-path normalization, parser construction, output formatting, and
revision/write helpers must remain centralized until a focused extraction proves
their ownership. Duplicating them would create divergent CLI behavior.

## Compatibility protection

The first extraction must preserve `python -m lifetxt completion ...`, shell
names, generated completion text, exit codes, and parser help. The required
follow-up is #384. Its scope is only the completion command boundary; no other
family is authorized by this plan.
