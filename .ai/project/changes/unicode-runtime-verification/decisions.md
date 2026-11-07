# Decisions

- Permit empty generated cjkcodecs directories, reject payloads/links. The initial
  directory-only check failed on actual configure output; the full error is kept
  in .profile3-static.log locally. No failed run was counted as successful.
- Bind all retained build payloads to the fixed checkpoint manifest before static
  checks; source readback alone cannot vouch for a substituted static library.
- Full reconstructed-source six-family scan records 33 references and 28 retained
  CJK samples. This is not source-wide or licence removal acceptance.
- Parser parity uses only public examples and synthetic bounded inputs; no user
  life.txt or credentials. Node is not Chromium product/browser acceptance.
- No runtime/permission flags change. Rollback is revert the verification PR.
