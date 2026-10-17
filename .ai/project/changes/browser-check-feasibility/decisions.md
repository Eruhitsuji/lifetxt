# Decisions

- The 2026-10-17 user request authorizes the #1356 local investigation, not public
  JavaScript, Core contract changes, deployment or final adoption.
- Use self-hosted Pyodide314.0.7 in a module Worker; retain upstream runtime
  version/lock and exact Core bytes. No external processing API or second parser.
- Parser-only scope must be visible. Actual CLI diagnostics differ for completed
  parent/native-history inputs; do not hide those or call this full CLI checking.
- Reject unsupported format metadata at the adapter boundary, without changing
  the permissive parser or inventing a diagnostic code.
- Native corpus and Node WASM are evidenced; cloud browser cannot reach the local
  host, so browser/mobile/privacy-trace acceptance remains open in #1356/#1358.
- No public runtime redistribution until required licences/notices/SBOM and
  source obligations are verified. Final product scope/architecture needs Owner
  approval and small, ready implementation tasks after this investigation.
