# Requirements Document

## Project Description (Input)
Two independent "doctor" implementations exist: the plain `lifetxt doctor` (`cli.py`'s `command_doctor`) and `lifetxt doctor --workspace-safety` (`doctor.py`'s `doctor_report`). They check non-overlapping optional-dependency package sets (`{textual, watchdog, matplotlib, cryptography}` vs `{fastapi, uvicorn, httpx, textual, watchdog, jsonschema}`), and neither reports the full Python version, OS/platform, lifetxt package version, or free disk space -- even though the codebase's own atomic-write/transaction-journal machinery needs real disk headroom to avoid a mid-write failure. This is part of a "system diagnostics at a glance" request, merged with a separately-proposed "output system configuration" request found to substantially overlap with this same gap.

## Requirements

### Requirement 1: The two doctor surfaces check the same optional-dependency set
**Objective:** As a user running either doctor surface, I want a consistent view of which optional packages are installed, so that I don't get a different answer depending on which flag I used.

#### Acceptance Criteria
1. `lifetxt doctor` and `lifetxt doctor --workspace-safety` shall both derive their optional-dependency report from the same single function.
2. The unified package set shall be the union of what each surface previously checked independently.

### Requirement 2: Plain doctor reports version and platform information
**Objective:** As a user or support-bundle reader, I want `lifetxt doctor` to report the lifetxt package version, full Python version, and OS/platform, so that I can discover this without a separate `--version` call plus manual OS/Python inspection.

#### Acceptance Criteria
1. `lifetxt doctor`'s output shall include a row reporting `lifetxt.__version__`, the full Python version (not just major.minor), and the OS name/release.
2. This addition shall not change the existing `python` check's major.minor-only pass/fail semantics (3.10+ required) -- it is a new, additional row.

### Requirement 3: Plain doctor reports free disk space
**Objective:** As a user, I want `lifetxt doctor` to warn me when free disk space is low, so that I can act before a config or transaction write fails partway through for lack of space.

#### Acceptance Criteria
1. `lifetxt doctor`'s output shall include a row reporting free disk space on the volume containing the resolved life.txt path's directory.
2. When free space is below 100 MiB, the row shall warn; otherwise it shall report OK with the free-space figure.
3. When the free-space check itself fails (e.g., an inaccessible path), the row shall warn with the error rather than crashing the whole doctor command.

### Requirement 4: Existing doctor behavior and JSON shape are preserved
**Objective:** As a script or test relying on `lifetxt doctor`'s existing output, I want the pre-existing checks and JSON row shape unchanged, so that this enhancement doesn't break anything depending on the current behavior.

#### Acceptance Criteria
1. The existing per-row JSON shape (`{"status": ..., "check": ..., "message": ...}`) shall be unchanged; new checks are additional rows in the same shape.
2. `--format json`/`--format text` output selection shall be unaffected.
3. Existing tests covering `lifetxt doctor`'s pass/fail/JSON behavior shall pass unmodified.
