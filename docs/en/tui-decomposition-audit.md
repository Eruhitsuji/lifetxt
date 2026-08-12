# TUI Decomposition Audit

Issue: #370  
Related: #312, #313  
Implementation follow-up: #390

## Responsibility Map

| Cluster | Current symbols | Dependency profile | Decision |
| --- | --- | --- | --- |
| Pure display primitives | `display_width`, `fit`, `pad`, `fit_spans`, `frame_to_text` | Standard library only | First extraction candidate #390 |
| Matching and row policy | `fuzzy_match`, `score_row`, `sort_rows`, `is_next_action` | Domain row data, no terminal I/O | Extract after layout seam |
| Workspace/session state | `WorkspaceState`, session helpers | Filesystem/configuration | Keep stateful and separate from rendering |
| Command/palette behavior | `Command`, `run_command`, completion helpers | Workspace state and mutation callbacks | Preserve command names and mutation semantics |
| Rendering | `build_frame`, `_build_*`, `draw_frame` | Layout plus curses output | Keep terminal adapter at the edge |
| Input/event loop | `handle_key`, `run_workspace`, key helpers | Curses/event loop | Last extraction due to highest coupling |

The first extraction is the pure layout/text cluster. It must preserve Unicode
and ASCII glyph selection, display-width calculations, snapshots, and the
dependency-free fallback in `lifetxt.tui`.
