# Optional Dependency Compatibility

The core `lifetxt` package remains dependency-free apart from the existing
Windows `tzdata` requirement. Optional dependencies are installed only when a
user selects the corresponding extra.

## Supported ranges

| Extra | Dependency | Supported range | API boundary exercised |
| --- | --- | --- | --- |
| `web` | FastAPI | `>=0.95,<1.0` | `FastAPI`, request/body/query/response objects, and `TestClient` |
| `web` | Uvicorn standard | `>=0.22,<1.0` | `uvicorn.run(app, host, port, workers=1)` |
| `tui` | Textual | `>=0.24,<1.0` | `App`, `Static`, widgets, and the application event loop |
| `tui` | Watchdog | `>=3,<7` | `FileSystemEventHandler` and `Observer` |

The lower bounds represent the earliest versions selected for the current
stable API usage. The upper bounds stop resolution at the next dependency major
line, where compatibility is not implied by the current source-level contract.
They are ranges rather than exact pins so normal patch and minor security
updates remain resolver-visible.

## Maintenance rule

Changing a lower or upper bound is a compatibility decision. The change must
state which imported API or behavior justifies it, run the Web/TUI smoke tests,
and update the range test in `tests/test_release_policy.py`. Issue #350 owns the
CI environments that exercise the minimum and upper supported ranges; this
document is its authoritative input.

No optional dependency is added to the normal runtime dependency list, and the
project does not commit a transitive lockfile for end-user installations.
