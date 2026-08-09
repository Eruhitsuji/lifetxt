# Design Document

## Overview
Reconcile the two doctor surfaces' optional-dependency checks onto one shared function, and add version/platform/disk-space rows to the plain `lifetxt doctor` command.

## Boundary Commitments
### This Spec Owns
- `doctor.optional_dependency_report()`'s package set (widened, single source of truth).
- `cli.command_doctor`'s new system/disk rows.
### Out of Boundary
- `doctor.doctor_report()`'s own structure and hard-failure logic -- untouched beyond consuming the same (now wider) `optional_dependency_report()` it already called.
- Any new config key for the disk-space threshold -- 100 MiB is a fixed, documented heuristic for this iteration; making it configurable is a natural follow-up if requested, not assumed here.

## File Structure Plan
### Modified Files
- `lifetxt/doctor.py`: `OPTIONAL_DEPENDENCY_NAMES` constant (union of the two prior sets), `optional_dependency_report()` reads from it.
- `lifetxt/cli.py`: `command_doctor` adds system-info row, disk-space row, and replaces its hardcoded package loop with `optional_dependency_report()`.
- `tests/test_lifetxt.py`: new tests.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1, 1.2 | `doctor.OPTIONAL_DEPENDENCY_NAMES` = union of the two prior sets; both `command_doctor` and `doctor_report` call `optional_dependency_report()` |
| 2.1, 2.2 | New `"system"` check row using `platform.python_version()`/`platform.system()`/`platform.release()`/`lifetxt.__version__`, added alongside (not replacing) the existing major.minor `"python"` row |
| 3.1, 3.2, 3.3 | `shutil.disk_usage()` on the resolved life.txt path's directory, wrapped in `try/except OSError`, WARN under 100 MiB |
| 4.1, 4.2, 4.3 | All additions use `add_check(symbol, label, message)`, the same triple every existing row uses; no existing row removed or restructured |

## Testing Strategy
- Existing `LifeTxtDoctorCliTests` re-run unmodified (regression).
- New: doctor output includes version/OS/disk rows.
- New: `doctor.OPTIONAL_DEPENDENCY_NAMES` matches `optional_dependency_report()`'s keys, and every name appears as a `command_doctor` JSON row -- proves the two surfaces cannot silently diverge again.
- Live: real CLI run confirms output shape; `--workspace-safety --format json` confirms the widened set reaches that surface too.
