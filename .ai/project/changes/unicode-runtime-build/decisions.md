# Decisions

- 2026-11-07: Split #1436 into build #1530 and independent verification #1531;
  size S, score 6 = scope1 + dependency2 + uncertainty1 + test1 + ops1. Owner's
  continue instruction authorizes implementation, not merge/adoption/publication.
- Reuse exact delivered profile2 source, preserve original notices. Generate a
  separate profile3 candidate and receipt; do not relabel historical binaries.
- Keep the source-only 18-codec allowlist until actual runtime evidence requires
  a separately recorded minimal addition. cp437 remains a specific test question.
- ccache is optional tooling. Its SDK build failed with CMake's removed legacy
  policy compatibility. Disable the wrapper in the new recipe and compile with
  the verified pinned emcc directly; keep the failed log. No compiler substitution.
- Rollback: revert the recipe PR. No live or user data change.

- Actual initial WASM boot succeeded, but zipfile reading an ASCII-filename ZIP
  raised unknown encoding cp437. Add the exact original cp437 source as a stdlib
  packaging overlay, preserve its CPython licence and mapping-origin header.
  This preserves the reviewed source-only archive/hash and changes only the new
  candidate's stdlib. Independent legal/source/runtime closure remains pending.
