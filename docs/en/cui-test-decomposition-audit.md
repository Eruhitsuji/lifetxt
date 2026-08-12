# CUI Extension Test Decomposition Audit

Issue: #373

## Responsibility inventory

`tests/test_cui_extensions.py` contains several independently named contract
clusters:

- `CompletionTests` and `CliParserConsistencyTests`: shell completion and
  argparse/completion parity;
- `GitHookTests`: hook installation and refusal behavior;
- `TimerTests`: timer parsing, elapsed state, and CLI smoke behavior;
- `StatsTests`: statistics aggregation and ASCII rendering;
- `EditorResolutionTests`, `WorkspaceEditSuspendTests`, and `FzfHelperTests`:
  editor selection, terminal suspension, preview, and mutation adapters;
- `TuiTests`, `WorkspaceStateTests`, `WorkspaceKeymapRegressionTests`,
  `WorkspaceInterruptTests`, and `WorkspaceCommandTests`: interactive TUI
  rendering, state transitions, keymaps, interruption, and commands.

The module is therefore not a single cohesive test contract. The strongest
existing fixture boundary is between the completion/parser tests and the
interactive workspace tests. The latter share state builders and terminal
fixtures and should remain together until a more specific ownership seam is
proven.

## First extraction

The first XS/S extraction is `CompletionTests` plus
`CliParserConsistencyTests` into `tests/test_completion_surfaces.py`, reusing
the existing completion-surface ownership and leaving shared parser helpers in
their current owner. A dedicated implementation issue is #395.

Required parity evidence is unittest discovery, the source/destination test
counts, completion generation for every shell, parser option parity, and the
focused completion-surface suite. No production code or test assertions should
change during the move.

## Leave-as-is boundary

Do not mechanically split the remaining TUI/workspace classes by class name.
Their shared state, terminal lifecycle, and mutation fixtures make a broad
split higher risk than the file-size benefit justifies at this stage.
