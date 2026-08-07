# Design

## Summary

`scripts/check_release_policy.py` builds a JSON manifest via
`lifetxt.release_policy.release_manifest` and writes it to stdout with
`sys.stdout.write(text)`. The manifest embeds Web UI translation strings
(`lifetxt/web_assets.py`, `config/release/web-ja-translation-baseline-v1.json`),
which can legitimately contain characters outside a narrow console codec, for
example U+21B5 (↵). On a default Windows console (`cp932`), the bare write
raises `UnicodeEncodeError` and the command crashes after already having
completed the actual release-policy checks (#95).

The fix adds one helper, `_write_stdout(stream, text)`, and calls it in place
of the bare `sys.stdout.write(text)`. It attempts the normal write first; only
on `UnicodeEncodeError` does it re-encode the text using the stream's own
declared encoding with `errors="backslashreplace"` and write that instead.
UTF-8 terminals are unaffected because the first `stream.write(text)` call
already succeeds for them — the fallback path never executes there.

## Interfaces and Contracts

- **ADDED**: `scripts/check_release_policy._write_stdout(stream, text)` —
  module-private helper, not part of any public API. No new CLI flags, no
  change to `main()`'s return value or the `--output` file path (which
  already writes with `encoding="utf-8"` and is untouched).
- **MODIFIED**: `scripts/check_release_policy.main()` — replaces
  `sys.stdout.write(text)` with `_write_stdout(sys.stdout, text)`.

## Test Strategy

Real `TextIOWrapper` behavior is what actually raises `UnicodeEncodeError` in
production, so the regression test reproduces it directly rather than mocking
the exception:

- `tests/test_check_release_policy_cli.py` loads the script via
  `importlib.util.spec_from_file_location` (scripts/ is not a package) and
  exercises `_write_stdout` against a small fake stream that calls
  `text.encode(self.encoding)` before recording the write — the same failure
  mode a real `TextIOWrapper` exhibits.
- Manually verified against a real `io.TextIOWrapper(io.BytesIO(), encoding="cp932")`:
  before the fix this raises `UnicodeEncodeError` on the same input from the
  original incident (`U+21B5`); after the fix it writes
  `b'note \\u21b5 end\r\n'` without raising.

## Risks and Mitigations

- **Risk**: silently mangling output on a codec that could actually display
  the character with a different code page than Python detected.
  **Mitigation**: out of scope — Python's `sys.stdout.encoding` reflects the
  actual console code page; this change only prevents a crash when that
  codec truly cannot represent the character, matching the incident's
  documented acceptance criteria ("keeps UTF-8/Unicode output readable on
  UTF-8 terminals").
- **Risk**: masking a future, unrelated `UnicodeEncodeError` bug in manifest
  generation.
  **Mitigation**: the fallback still writes the offending text (escaped)
  rather than swallowing it, and the command's exit code is unchanged, so a
  broken manifest still fails the same way it did before for anything other
  than the encoding step itself.
