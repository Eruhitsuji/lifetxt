# Requirements Document

## Project Description (Input)
No `lifetxt --version`/`-V` flag or `version` command exists anywhere in the CLI parser, even though `lifetxt.__version__` is already defined (`lifetxt/__init__.py`). A user cannot discover which release they are running without reading source. This is part of a larger "CLI diagnostics enhancement" request; scoped here to the version-discovery piece specifically, which also becomes a building block for the separate update-check/self-update commands (they need to know the current version to compare against).

## Requirements

### Requirement 1: Users can discover the installed lifetxt version from the CLI
**Objective:** As a lifetxt user or support-bundle reader, I want a standard `--version` flag, so that I can discover the installed release without reading source or guessing.

#### Acceptance Criteria
1. When `python -m lifetxt --version` (or `-V`) is run, the CLI shall print the package name and `lifetxt.__version__` and exit 0 without requiring any other argument or life.txt file.
2. The `--version` flag shall be recognized at the top level (before any subcommand), consistent with standard argparse `--version` conventions.
3. When any subcommand is also given alongside `--version`, argparse's built-in version-action behavior (print and exit immediately) shall apply, matching standard argparse semantics -- no custom subcommand-priority logic is introduced.
