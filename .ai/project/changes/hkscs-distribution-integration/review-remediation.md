# Issue 1417 independent-review remediation (2026-10-26)

Source: main 60ba43a616a3687bb76b092d09422277605d869b.
Contract: issue 1417 comment 6413978396. Bug / High / S, score 2.
Reuse cap-official-website / req-hkscs-free-distribution-v1.

## Dispositions

- T-1: REVIEWER_HANDOFF.md defines private transfer metadata, receiver-side
  length/hash/path checks, exact source/artifact scope, profile-specific tests,
  evidence recording and separate object checkpoint scope. The independent
  report at issue 1417 comment 6413507506 already records receipt and actual
  historical profile2 execution. This is external evidence, not a new execution
  by this implementer. Latest product acceptance is separate on issue 1399.
- T-2: all four Path.read_text calls in tests/test_custom_distribution.py now
  specify UTF-8. This fixes three failing test methods under cp932 defaults,
  including the fourth read reached later in one method.
- T-3: mapping-attribution status/next_action and evidence hashes stay unchanged.
  No resolved-removed declaration, legal acceptance or flag changes. Updating
  that hash-bound record requires separately scoped independent source-specific
  acceptance; it cannot follow automatically from this encoding fix.

## Verification

Executed on Linux/Python 3.12 with Path.read_text's unspecified default forced
by unittest.mock.patch to cp932. This simulates the reported decoding condition;
it is not a native Windows execution. No Windows-wide UTF8 mode is needed.

Before the fix: tests.test_custom_distribution collected 7, errors 3, skipped 2;
the errors were UnicodeDecodeError at wasm-proof and mapping-attribution JSON.
After the fix: the same 7 collected, 5 passed, 2 legacy actual-artifact skips;
zero errors/failures. This executes the existing behavioral tests under a
non-UTF8 default rather than adding a test that mirrors the changed syntax.

Focused modules test_custom_distribution, test_hkscs_free, test_hkscs_profile2,
test_hkscs_verification_inputs, test_browser_review_remediation: 36 collected,
33 passed, 3 explicit missing actual-artifact skips. Real profile2/legacy artifact,
source/object/WASM and Chromium re-execution were not performed in this session.

Self-review checked all reads in the affected test file, mutation-test isolation,
profile1/profile2 separation, unchanged runtime/source/evidence/mapping/flags and
handoff instructions versus CLI/API contracts. Separate implementation and
integration review of this final head remain pending. Owner merge, limited
technical acceptance, legal/source retention and publication are distinct.
Rollback: revert the PR; no stored-data or runtime migration.

Reproduction command (run before and after the patch):

```sh
python - <<'PY'
from pathlib import Path
import unittest
from unittest.mock import patch
read_text = Path.read_text

def cp932_default(self, encoding=None, errors=None):
    return read_text(self, encoding='cp932' if encoding is None else encoding,
                     errors=errors)

with patch.object(Path, 'read_text', cp932_default):
    suite = unittest.defaultTestLoader.loadTestsFromName('tests.test_custom_distribution')
    result = unittest.TextTestRunner().run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```

Changed Python file: ruff check / format --check passed. Supported-runtime,
traceability and change-package-closeout focused checks: 19 collected, all passed
(the final PR's traceability chain is checked again after its URL is recorded).
