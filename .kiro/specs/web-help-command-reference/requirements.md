# Requirements Document

## Project Description (Input)
The TUI's `/help [query]` command shows a searchable reference of every
slash command (`lifetxt/tui_app.py`'s `help_entries()`). The Web UI's help
modal (opened via the `?` shortcut or the `?` toolbar button) shows only a
static keyboard-shortcuts table -- it has no command reference at all. The
Web UI does already have a searchable command catalog, but it is inside the
Ctrl+K command palette, which a user pressing `?` for help has no reason to
already know exists. This creates a discoverability gap: the one feature a
user reaches for by name ("help") does not show commands, and the feature
that does show commands is not reachable from "help".

## Requirements

### Requirement 1: The help modal includes a searchable command reference
**Objective:** As a Web UI user pressing `?` for help, I want to see and
search the slash-command catalog from the same place, so that I don't have
to already know Ctrl+K exists to discover what commands are available.

#### Acceptance Criteria
1. When the help modal is open, it shall show a search input and a list of
   commands below the existing keyboard-shortcuts table.
2. When the search input is empty, the list shall show every command in the
   catalog.
3. When the user types into the search input, the list shall filter to
   commands whose name, alias, or summary match the typed text, using the
   same matching behavior as the existing command palette.
4. Each listed command shall show its usage (`/name [args]`), its alias (if
   any), and its one-line summary.
5. A command that is not available in the Web UI (TUI-only) shall be
   visually marked as such rather than presented identically to an
   available command.
6. When no command matches the current search, the list shall show an
   explanatory empty state rather than an empty area.

### Requirement 2: No duplicate source of truth for the command catalog
**Objective:** As a maintainer, I want the help modal's command list to be
impossible to disagree with the command palette or `/api/commands` about
what a command means.

#### Acceptance Criteria
1. The help modal's command list shall be populated from the same
   `COMMAND_CATALOG` (loaded from `/api/commands`) the command palette
   already uses.
2. The help modal's search/filter behavior shall reuse the same matching
   function the command palette already uses, rather than a second
   implementation.
