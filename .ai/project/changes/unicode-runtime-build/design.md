# Profile3 build design

Reuse req-browser-local-check-distribution-v1 / cap-official-website.
Do not overwrite the profile1/2 pipeline. A fresh caller-owned directory receives
snapshots of seven exact profile2 source archives, the fixed source-only curator
output, and the modified Pyodide source. Builtin codecs are disabled in Setup.local.
libffi/hiwire use supplied fixed archives instead of git fetch. xz/zstd/sqlite use
existing local-source recipes. No compiler cache is used; compiler and SDK pins
remain unchanged. Inputs and all staged regular files are hash recorded.

Stage performs no downloads or compiler execution. SDK/host are explicit setup
prerequisites and the documented make is run separately with logs. Failures leave
INCOMPLETE so a partially staged tree cannot be confused with a completed receipt;
the output directory must be new and its parent trusted. No automatic fallback.

Review viewpoints: input provenance, archive validation and bounded expansion,
TOCTOU snapshot checks, source/Setup disabled module registration, supply-chain and
MPL corresponding source, output isolation, exact compiler/runtime identity.
Testing viewpoints: modified pins, tar traversal/types/links/duplicates/resource
budget, recipe anchors, incomplete snapshot, unchanged input, builtin disable and
staged hash receipt. Coding: isolated helpers, stdlib-only, project ruff checks.
Security: no live data, network in preparation only, no deploy or publication flags.
Runtime closure, static object/WASM absence and parser parity are task 1531.
